"""The status pipeline: which moves are allowed.

    applied -> screen -> interview -> offer -> accepted
       |          |          |          |
       +----------+----------+----------+--> rejected | withdrawn

``ghosted`` is set for applications with no response after ``ghost_after_days``; a late reply can still move a
ghosted application forward. Final statuses (accepted, rejected, withdrawn) do not move again; re-applying is a new
application.
"""
from __future__ import annotations

ORDER = ["applied", "screen", "interview", "offer", "accepted"]
EXITS = ["rejected", "withdrawn"]
STATUSES = ORDER + EXITS + ["ghosted"]
FINAL = {"accepted", "rejected", "withdrawn"}
ACTIVE = {"applied", "screen", "interview", "offer"}

ALLOWED: dict[str, set[str]] = {
    "applied": {"screen", "interview", "offer", "rejected", "withdrawn", "ghosted"},
    "screen": {"interview", "offer", "rejected", "withdrawn"},
    "interview": {"interview", "offer", "rejected", "withdrawn"},   # another round is still "interview"
    "offer": {"accepted", "rejected", "withdrawn"},
    "ghosted": {"screen", "interview", "offer", "rejected", "withdrawn"},
    "accepted": set(), "rejected": set(), "withdrawn": set(),
}


class TransitionError(ValueError):
    pass


def check_transition(current: str, new: str) -> None:
    if new not in STATUSES:
        raise TransitionError(f"unknown status '{new}'; use one of {', '.join(STATUSES)}")
    if new not in ALLOWED[current]:
        allowed = ", ".join(sorted(ALLOWED[current])) or "nothing (final status)"
        raise TransitionError(f"cannot move from '{current}' to '{new}'; allowed: {allowed}")


def got_response(history: list[str]) -> bool:
    """A human replied: anything past 'applied' except silence or our own withdrawal before any reply."""
    return any(s in ("screen", "interview", "offer", "accepted", "rejected") for s in history)


def reached_interview(history: list[str]) -> bool:
    return any(s in ("interview", "offer", "accepted") for s in history)
