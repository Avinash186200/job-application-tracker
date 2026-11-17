"""SQLite storage. One row per application, one event row per status change, CSV import and export.

Dates are ISO strings (YYYY-MM-DD) passed in by the caller, so nothing depends on the wall clock and every test can
fix "today".
"""
from __future__ import annotations

import csv
import datetime as dt
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from . import dedupe
from .config import role_type
from .pipeline import ACTIVE, check_transition

SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    role_type TEXT NOT NULL,
    location TEXT DEFAULT '',
    url TEXT DEFAULT '',
    applied_on TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'applied',
    updated_on TEXT NOT NULL,
    follow_up_on TEXT,
    notes TEXT DEFAULT '',
    dedupe_key TEXT NOT NULL UNIQUE,
    url_key TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_url_key ON applications(url_key);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id),
    on_date TEXT NOT NULL,
    status TEXT NOT NULL,
    note TEXT DEFAULT ''
);
"""

CSV_FIELDS = ["company", "title", "source", "location", "url", "applied_on", "status", "notes"]


@dataclass
class AddResult:
    id: int
    created: bool
    reason: str = ""                 # why it was not created: "same company and title" or "same URL"
    near: tuple[int, ...] = ()       # close spellings worth a look


def _add_days(day: str, n: int) -> str:
    return (dt.date.fromisoformat(day) + dt.timedelta(days=n)).isoformat()


class Tracker:
    def __init__(self, db: str | Path, cfg: dict):
        self.cfg = cfg
        self.con = sqlite3.connect(str(db))
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.executescript(SCHEMA)

    def close(self) -> None:
        self.con.close()

    # -- helpers ---------------------------------------------------------------
    def _follow_up(self, status: str, on: str) -> str | None:
        days = self.cfg["follow_up_days"].get(status)
        return _add_days(on, days) if status in ACTIVE and days else None

    def get(self, app_id: int) -> sqlite3.Row:
        row = self.con.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
        if row is None:
            raise KeyError(f"no application with id {app_id}")
        return row

    # -- add -------------------------------------------------------------------
    def add(self, company: str, title: str, source: str, applied_on: str, location: str = "", url: str = "",
            notes: str = "") -> AddResult:
        if not company.strip() or not title.strip():
            raise ValueError("company and title are required")
        if source not in self.cfg["sources"]:
            raise ValueError(f"unknown source '{source}'; configured: {', '.join(self.cfg['sources'])}")
        dt.date.fromisoformat(applied_on)
        k = dedupe.key(company, title, self.cfg["company_suffixes"])
        uk = dedupe.norm_url(url)
        row = self.con.execute("SELECT id FROM applications WHERE dedupe_key = ?", (k,)).fetchone()
        if row:
            return AddResult(row["id"], False, "same company and title")
        if uk:
            row = self.con.execute("SELECT id FROM applications WHERE url_key = ?", (uk,)).fetchone()
            if row:
                return AddResult(row["id"], False, "same URL")
        existing = [(r["id"], r["dedupe_key"]) for r in self.con.execute("SELECT id, dedupe_key FROM applications")]
        near = tuple(dedupe.near_duplicates(k, existing))
        with self.con:
            cur = self.con.execute(
                "INSERT INTO applications (company, title, source, role_type, location, url, applied_on, status,"
                " updated_on, follow_up_on, notes, dedupe_key, url_key) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (company.strip(), title.strip(), source, role_type(title, self.cfg), location, url, applied_on,
                 "applied", applied_on, self._follow_up("applied", applied_on), notes, k, uk))
            self.con.execute("INSERT INTO events (application_id, on_date, status) VALUES (?,?,?)",
                             (cur.lastrowid, applied_on, "applied"))
        return AddResult(cur.lastrowid, True, near=near)

    # -- status ----------------------------------------------------------------
    def set_status(self, app_id: int, new: str, on: str, note: str = "") -> None:
        row = self.get(app_id)
        check_transition(row["status"], new)
        if on < row["updated_on"]:
            raise ValueError(f"date {on} is before the last update {row['updated_on']}")
        with self.con:
            self.con.execute("UPDATE applications SET status = ?, updated_on = ?, follow_up_on = ? WHERE id = ?",
                             (new, on, self._follow_up(new, on), app_id))
            self.con.execute("INSERT INTO events (application_id, on_date, status, note) VALUES (?,?,?,?)",
                             (app_id, on, new, note))

    def history(self, app_id: int) -> list[sqlite3.Row]:
        return self.con.execute("SELECT on_date, status, note FROM events WHERE application_id = ? ORDER BY id",
                                (app_id,)).fetchall()

    # -- follow-ups ------------------------------------------------------------
    def due(self, today: str) -> list[sqlite3.Row]:
        return self.con.execute(
            "SELECT * FROM applications WHERE follow_up_on IS NOT NULL AND follow_up_on <= ? "
            "ORDER BY follow_up_on, id", (today,)).fetchall()

    def followed_up(self, app_id: int, on: str, days: int | None = None) -> str:
        """Record that you followed up (or snooze): the next reminder moves forward. Returns its date."""
        row = self.get(app_id)
        if row["status"] not in ACTIVE:
            raise ValueError(f"application {app_id} is '{row['status']}', nothing to follow up")
        nxt = _add_days(on, days if days is not None else self.cfg["follow_up_days"].get(row["status"], 7))
        with self.con:
            self.con.execute("UPDATE applications SET follow_up_on = ? WHERE id = ?", (nxt, app_id))
        return nxt

    def mark_ghosted(self, today: str) -> list[int]:
        """'applied' with no change for ghost_after_days -> 'ghosted'. Returns the ids moved."""
        cutoff = _add_days(today, -self.cfg["ghost_after_days"])
        ids = [r["id"] for r in self.con.execute(
            "SELECT id FROM applications WHERE status = 'applied' AND updated_on <= ?", (cutoff,))]
        for i in ids:
            self.set_status(i, "ghosted", today, f"no response in {self.cfg['ghost_after_days']} days")
        return ids

    # -- listing and CSV ---------------------------------------------------------
    def list(self, status: str | None = None) -> list[sqlite3.Row]:
        if status:
            return self.con.execute("SELECT * FROM applications WHERE status = ? ORDER BY id", (status,)).fetchall()
        return self.con.execute("SELECT * FROM applications ORDER BY id").fetchall()

    def all_with_history(self) -> list[dict]:
        apps = [dict(r) for r in self.list()]
        events: dict[int, list[dict]] = {}
        for e in self.con.execute("SELECT application_id, on_date, status FROM events ORDER BY id"):
            events.setdefault(e["application_id"], []).append({"on": e["on_date"], "status": e["status"]})
        for a in apps:
            a["events"] = events.get(a["id"], [])
        return apps

    def import_csv(self, path: str | Path) -> dict:
        """Add rows from a CSV (header: company,title,source,applied_on and optional location,url,status,notes).
        A status other than 'applied' is applied as one move on the applied_on date."""
        counts = {"added": 0, "duplicates": 0}
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                res = self.add(row["company"], row["title"], row["source"], row["applied_on"],
                               row.get("location", ""), row.get("url", ""), row.get("notes", ""))
                if not res.created:
                    counts["duplicates"] += 1
                    continue
                counts["added"] += 1
                st = (row.get("status") or "applied").strip()
                if st != "applied":
                    self.set_status(res.id, st, row.get("status_on") or row["applied_on"])
        return counts

    def export_csv(self, path: str | Path) -> int:
        rows = self.list()
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["id", *CSV_FIELDS, "role_type", "updated_on", "follow_up_on"])
            for r in rows:
                w.writerow([r["id"], *(r[c] for c in CSV_FIELDS), r["role_type"], r["updated_on"], r["follow_up_on"]])
        return len(rows)
