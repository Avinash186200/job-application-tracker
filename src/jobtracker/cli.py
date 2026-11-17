"""jobtracker: log job applications, keep them de-duplicated, move them through a pipeline, remind, report.

    jobtracker init
    jobtracker add "Example Co" "Data Scientist" --source job-board --url https://jobs.example.com/123
    jobtracker status 1 screen --note "call booked"
    jobtracker due                      # follow-ups that are due today or overdue
    jobtracker followed-up 1            # you followed up: push the next reminder out
    jobtracker ghost                    # mark old silent applications as ghosted
    jobtracker list --status interview
    jobtracker history 1
    jobtracker report --week-of 2026-01-12 --out report.md
    jobtracker import-csv applications.csv
    jobtracker export-csv tracker.csv

Global options: --db (default ./tracker.db or $JOBTRACKER_DB), --config (TOML, or $JOBTRACKER_CONFIG),
--today (YYYY-MM-DD, default the system date; fix it to make runs reproducible).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

from . import report
from .config import load_config
from .pipeline import STATUSES, TransitionError
from .store import Tracker


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="jobtracker", description="Job application tracker")
    ap.add_argument("--db", default=os.environ.get("JOBTRACKER_DB", "tracker.db"))
    ap.add_argument("--config", default=os.environ.get("JOBTRACKER_CONFIG"))
    ap.add_argument("--today", default=None, help="YYYY-MM-DD; defaults to the system date")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create the tracker database")
    a = sub.add_parser("add", help="log one application")
    a.add_argument("company")
    a.add_argument("title")
    a.add_argument("--source", required=True)
    a.add_argument("--on", help="date applied (default today)")
    a.add_argument("--location", default="")
    a.add_argument("--url", default="")
    a.add_argument("--notes", default="")

    s = sub.add_parser("status", help="move an application to a new status")
    s.add_argument("id", type=int)
    s.add_argument("new", choices=STATUSES)
    s.add_argument("--on")
    s.add_argument("--note", default="")

    sub.add_parser("due", help="follow-ups due today or overdue")
    f = sub.add_parser("followed-up", help="record a follow-up or snooze; moves the next reminder")
    f.add_argument("id", type=int)
    f.add_argument("--days", type=int)
    sub.add_parser("ghost", help="mark applications with no reply after ghost_after_days")

    ls = sub.add_parser("list", help="list applications")
    ls.add_argument("--status", choices=STATUSES)
    h = sub.add_parser("history", help="status history of one application")
    h.add_argument("id", type=int)

    r = sub.add_parser("report", help="weekly traction report")
    r.add_argument("--week-of", help="any date in the week (default today)")
    r.add_argument("--min-age-days", type=int, default=7)
    r.add_argument("--json", action="store_true")
    r.add_argument("--out")

    i = sub.add_parser("import-csv", help="add applications from a CSV")
    i.add_argument("path")
    e = sub.add_parser("export-csv", help="write every application to a CSV")
    e.add_argument("path")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = _parser().parse_args(argv)
    today = a.today or dt.date.today().isoformat()
    dt.date.fromisoformat(today)
    t = Tracker(a.db, load_config(a.config))
    try:
        return _run(a, t, today)
    except (TransitionError, ValueError, KeyError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    finally:
        t.close()


def _row(r) -> str:
    fu = f"  follow up {r['follow_up_on']}" if r["follow_up_on"] else ""
    return (f"{r['id']:>4}  {r['status']:<10} {r['applied_on']}  {r['company']} | {r['title']}  "
            f"[{r['source']}, {r['role_type']}]{fu}")


def _run(a, t: Tracker, today: str) -> int:
    if a.cmd == "init":
        print(f"tracker ready: {Path(a.db).resolve()}")
    elif a.cmd == "add":
        res = t.add(a.company, a.title, a.source, a.on or today, a.location, a.url, a.notes)
        if not res.created:
            print(f"duplicate of #{res.id} ({res.reason}); not added")
            return 1
        print(f"added #{res.id}")
        if res.near:
            print("  similar entries, check they are different roles: " + ", ".join(f"#{n}" for n in res.near))
    elif a.cmd == "status":
        t.set_status(a.id, a.new, a.on or today, a.note)
        print(f"#{a.id} -> {a.new}")
    elif a.cmd == "due":
        rows = t.due(today)
        print(f"{len(rows)} follow-up(s) due on {today}")
        for r in rows:
            print(_row(r))
    elif a.cmd == "followed-up":
        print(f"#{a.id}: next follow-up {t.followed_up(a.id, today, a.days)}")
    elif a.cmd == "ghost":
        ids = t.mark_ghosted(today)
        print(f"marked {len(ids)} as ghosted" + (": " + ", ".join(f"#{i}" for i in ids) if ids else ""))
    elif a.cmd == "list":
        for r in t.list(a.status):
            print(_row(r))
    elif a.cmd == "history":
        r = t.get(a.id)
        print(f"#{r['id']} {r['company']} | {r['title']}")
        for e in t.history(a.id):
            print(f"  {e['on_date']}  {e['status']}" + (f"  ({e['note']})" if e["note"] else ""))
    elif a.cmd == "report":
        rep = report.weekly(t.all_with_history(), a.week_of or today, today, a.min_age_days)
        text = json.dumps(rep, indent=2) if a.json else report.to_markdown(rep)
        if a.out:
            Path(a.out).write_text(text, encoding="utf-8")
            print(f"wrote {a.out}")
        else:
            print(text)
    elif a.cmd == "import-csv":
        c = t.import_csv(a.path)
        print(f"added {c['added']}, skipped {c['duplicates']} duplicate(s)")
    elif a.cmd == "export-csv":
        print(f"wrote {t.export_csv(a.path)} rows to {a.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
