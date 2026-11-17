"""Weekly traction report: which sources and role types get replies.

Pure functions over plain dicts (as returned by ``Tracker.all_with_history``), so the numbers are easy to test.

- **response rate**: share of applications where a human replied (screen, interview, offer, accepted or rejected);
- **interview rate**: share that reached an interview;
- **median days to reply**: from applying to the first reply, over the applications that got one.

Recent applications have had less time to get a reply, so the report also shows how many in each group are still
"too new to judge" (applied fewer than ``min_age_days`` days before the report date). Those are left out of the
rates.
"""
from __future__ import annotations

import datetime as dt
import statistics
from collections import defaultdict

from .pipeline import got_response, reached_interview

REPLY = {"screen", "interview", "offer", "accepted", "rejected"}


def week_bounds(day: str) -> tuple[str, str]:
    """Monday and the following Monday (exclusive) of the week that contains ``day``."""
    d = dt.date.fromisoformat(day)
    mon = d - dt.timedelta(days=d.weekday())
    return mon.isoformat(), (mon + dt.timedelta(days=7)).isoformat()


def days_to_reply(app: dict) -> int | None:
    for e in app["events"]:
        if e["status"] in REPLY:
            return (dt.date.fromisoformat(e["on"]) - dt.date.fromisoformat(app["applied_on"])).days
    return None


def group_stats(apps: list[dict], by: str, today: str, min_age_days: int = 7) -> list[dict]:
    cutoff = (dt.date.fromisoformat(today) - dt.timedelta(days=min_age_days)).isoformat()
    groups: dict[str, list[dict]] = defaultdict(list)
    for a in apps:
        groups[a[by]].append(a)
    out = []
    for name, items in groups.items():
        judged = [a for a in items if a["applied_on"] <= cutoff or got_response([e["status"] for e in a["events"]])]
        replies = [a for a in judged if got_response([e["status"] for e in a["events"]])]
        interviews = [a for a in judged if reached_interview([e["status"] for e in a["events"]])]
        lags = [d for d in (days_to_reply(a) for a in replies) if d is not None]
        n = len(judged)
        out.append({by: name, "applications": len(items), "judged": n, "too_new": len(items) - n,
                    "replies": len(replies), "interviews": len(interviews),
                    "response_rate": round(len(replies) / n, 3) if n else None,
                    "interview_rate": round(len(interviews) / n, 3) if n else None,
                    "median_days_to_reply": statistics.median(lags) if lags else None})
    return sorted(out, key=lambda r: (-(r["response_rate"] or 0), -r["applications"], r[by]))


def weekly(apps: list[dict], week_of: str, today: str, min_age_days: int = 7) -> dict:
    """This week's activity plus all-time traction by source and by role type."""
    lo, hi = week_bounds(week_of)
    new = [a for a in apps if lo <= a["applied_on"] < hi]
    moves = [(a, e) for a in apps for e in a["events"] if lo <= e["on"] < hi and e["status"] != "applied"]
    by_status: dict[str, int] = defaultdict(int)
    for _, e in moves:
        by_status[e["status"]] += 1
    return {"week": [lo, hi], "today": today, "applied_this_week": len(new), "moves_this_week": dict(by_status),
            "by_source": group_stats(apps, "source", today, min_age_days),
            "by_role_type": group_stats(apps, "role_type", today, min_age_days)}


def _pct(x):
    return "-" if x is None else f"{x:.0%}"


def to_markdown(rep: dict) -> str:
    lo, hi = rep["week"]
    end = (dt.date.fromisoformat(hi) - dt.timedelta(days=1)).isoformat()
    lines = [f"# Traction report, week {lo} to {end}", "",
             f"Applied this week: **{rep['applied_this_week']}**. "
             "Moves this week: " + (", ".join(f"{k} {v}" for k, v in sorted(rep["moves_this_week"].items())) or "none")
             + ".", ""]
    for key, title in (("by_source", "Source"), ("by_role_type", "Role type")):
        col = key.removeprefix("by_")
        lines += [f"## By {title.lower()}", "",
                  f"| {title} | Applications | Too new | Replies | Response rate | Interview rate "
                  "| Median days to reply |",
                  "|---|---|---|---|---|---|---|"]
        for r in rep[key]:
            med = "-" if r["median_days_to_reply"] is None else f"{r['median_days_to_reply']:g}"
            lines.append(f"| {r[col]} | {r['applications']} | {r['too_new']} | {r['replies']} | "
                         f"{_pct(r['response_rate'])} | {_pct(r['interview_rate'])} | {med} |")
        lines.append("")
    lines.append("Rates leave out applications younger than the minimum age that have had no reply yet. "
                 "Small groups move a lot from one reply; read them as hints, not facts.")
    return "\n".join(lines) + "\n"
