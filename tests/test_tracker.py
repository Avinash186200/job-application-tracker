from pathlib import Path

import pytest

from jobtracker import cli, dedupe, report
from jobtracker.config import DEFAULTS, load_config, role_type
from jobtracker.pipeline import TransitionError, check_transition, got_response
from jobtracker.store import Tracker

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
SUFFIXES = DEFAULTS["company_suffixes"]


@pytest.fixture
def t(tmp_path):
    tr = Tracker(tmp_path / "t.db", load_config())
    yield tr
    tr.close()


# ------------------------------------------------------------------ config
def test_example_config_loads_and_classifies():
    cfg = load_config(EXAMPLES / "jobtracker.example.toml")
    assert cfg["follow_up_days"]["applied"] == 7 and cfg["ghost_after_days"] == 21
    assert role_type("Senior ML Engineer", cfg) == "ml-engineering"
    assert role_type("Lead Data Scientist", cfg) == "data-science"
    assert role_type("Product Manager", cfg) == "other"
    with pytest.raises(FileNotFoundError):
        load_config(EXAMPLES / "missing.toml")


# ------------------------------------------------------------------ de-duplication
@pytest.mark.parametrize("a,b", [
    (("Example Analytics Inc.", "Sr. Data Scientist"), ("example analytics", "Senior Data Scientist")),
    (("Sample Robotics Pvt Ltd", "ML Engineer"), ("Sample Robotics", "Machine Learning Engineer")),
    (("Café & Co", "Data Analyst"), ("Cafe and", "data  analyst")),
])
def test_same_role_same_key(a, b):
    assert dedupe.key(*a, SUFFIXES) == dedupe.key(*b, SUFFIXES)


def test_suffix_only_company_kept_and_different_roles_differ():
    assert dedupe.norm_company("Solutions", SUFFIXES) == "solutions"
    assert dedupe.key("Acme", "Data Scientist", SUFFIXES) != dedupe.key("Acme", "Data Engineer", SUFFIXES)


def test_norm_url_drops_tracking_and_case():
    url = "https://WWW.Jobs.Example.com/101/?utm_source=x&id=5&ref=feed"
    assert dedupe.norm_url(url) == "jobs.example.com/101?id=5"
    assert dedupe.norm_url("") == ""


def test_add_rejects_duplicates_by_key_and_url(t):
    first = t.add("Example Analytics Inc", "Data Scientist", "job-board", "2026-01-05",
                  url="https://jobs.example.com/101?utm_source=a")
    assert first.created
    again = t.add("example analytics", "data scientist", "referral", "2026-01-06")
    assert not again.created and again.id == first.id and again.reason == "same company and title"
    by_url = t.add("Example Analytics (via board)", "DS role", "job-board", "2026-01-06",
                   url="https://jobs.example.com/101?utm_source=b")
    assert not by_url.created and by_url.reason == "same URL"
    near = t.add("Example Analytic", "Data Scientist", "job-board", "2026-01-06")
    assert near.created and near.near == (first.id,)


def test_add_validates_input(t):
    with pytest.raises(ValueError):
        t.add("", "x", "job-board", "2026-01-01")
    with pytest.raises(ValueError):
        t.add("A", "B", "carrier-pigeon", "2026-01-01")
    with pytest.raises(ValueError):
        t.add("A", "B", "job-board", "01/02/2026")


# ------------------------------------------------------------------ pipeline
def test_transitions():
    check_transition("applied", "screen")
    check_transition("interview", "interview")
    check_transition("ghosted", "interview")
    for cur, new in [("applied", "accepted"), ("rejected", "screen"), ("offer", "screen"), ("applied", "hired")]:
        with pytest.raises(TransitionError):
            check_transition(cur, new)
    assert got_response(["applied", "rejected"]) and not got_response(["applied", "ghosted", "withdrawn"])


def test_status_moves_record_history_and_follow_ups(t):
    i = t.add("A Co", "Data Analyst", "job-board", "2026-01-05").id
    assert t.get(i)["follow_up_on"] == "2026-01-12"
    t.set_status(i, "screen", "2026-01-07", "call booked")
    assert t.get(i)["follow_up_on"] == "2026-01-10"
    t.set_status(i, "rejected", "2026-01-09")
    assert t.get(i)["follow_up_on"] is None
    assert [(e["on_date"], e["status"]) for e in t.history(i)] == [
        ("2026-01-05", "applied"), ("2026-01-07", "screen"), ("2026-01-09", "rejected")]
    with pytest.raises(TransitionError):
        t.set_status(i, "interview", "2026-01-10")


def test_status_date_cannot_go_back(t):
    i = t.add("A Co", "Analyst", "job-board", "2026-01-05").id
    with pytest.raises(ValueError):
        t.set_status(i, "screen", "2026-01-04")


# ------------------------------------------------------------------ follow-ups
def test_due_followed_up_and_ghosting(t):
    a = t.add("A Co", "Analyst", "job-board", "2026-01-01").id
    b = t.add("B Co", "Analyst", "job-board", "2026-01-06").id
    assert [r["id"] for r in t.due("2026-01-08")] == [a]
    assert t.followed_up(a, "2026-01-08") == "2026-01-15"
    assert t.due("2026-01-08") == []
    assert t.followed_up(b, "2026-01-08", days=1) == "2026-01-09"
    assert t.mark_ghosted("2026-01-22") == [a]
    assert t.get(a)["status"] == "ghosted" and t.get(a)["follow_up_on"] is None
    with pytest.raises(ValueError):
        t.followed_up(a, "2026-01-22")


# ------------------------------------------------------------------ CSV
def test_import_and_export_round_trip(t, tmp_path):
    counts = t.import_csv(EXAMPLES / "applications.example.csv")
    assert counts == {"added": 7, "duplicates": 1}
    assert t.get(2)["status"] == "interview" and t.get(2)["role_type"] == "ml-engineering"
    n = t.export_csv(tmp_path / "out.csv")
    lines = (tmp_path / "out.csv").read_text(encoding="utf-8").splitlines()
    assert n == 7 and len(lines) == 8 and lines[0].startswith("id,company,title")


# ------------------------------------------------------------------ report
def _apps(t):
    t.import_csv(EXAMPLES / "applications.example.csv")
    return t.all_with_history()


def test_week_bounds():
    assert report.week_bounds("2026-01-14") == ("2026-01-12", "2026-01-19")
    assert report.week_bounds("2026-01-12") == ("2026-01-12", "2026-01-19")


def test_group_stats_by_source(t):
    rows = {r["source"]: r for r in report.group_stats(_apps(t), "source", "2026-01-19")}
    jb = rows["job-board"]
    # job-board: Data Scientist (screen), Data Analyst (silent), Backend Developer (7 days old, silent)
    assert (jb["applications"], jb["judged"], jb["too_new"], jb["replies"]) == (3, 3, 0, 1)
    assert jb["response_rate"] == pytest.approx(1 / 3, abs=1e-3) and jb["median_days_to_reply"] == 3
    ref = rows["referral"]
    # referral: interview after 4 days, and one applied on 2026-01-13 that is too new to judge
    assert (ref["applications"], ref["judged"], ref["too_new"], ref["interviews"]) == (2, 1, 1, 1)
    assert ref["response_rate"] == 1.0 and ref["interview_rate"] == 1.0


def test_weekly_report_and_markdown(t):
    rep = report.weekly(_apps(t), "2026-01-14", "2026-01-19")
    assert rep["week"] == ["2026-01-12", "2026-01-19"]
    assert rep["applied_this_week"] == 2
    assert rep["moves_this_week"] == {"rejected": 1, "screen": 1}
    md = report.to_markdown(rep)
    assert md.startswith("# Traction report, week 2026-01-12 to 2026-01-18")
    assert "| referral | 2 | 1 | 1 | 100% | 100% | 4 |" in md
    assert "## By role type" in md


# ------------------------------------------------------------------ CLI
def test_cli_end_to_end(tmp_path, capsys):
    base = ["--db", str(tmp_path / "c.db"), "--config", str(EXAMPLES / "jobtracker.example.toml"),
            "--today", "2026-01-19"]
    assert cli.main(base + ["init"]) == 0
    assert cli.main(base + ["import-csv", str(EXAMPLES / "applications.example.csv")]) == 0
    assert cli.main(base + ["add", "Example Analytics", "Data Scientist", "--source", "job-board"]) == 1
    assert cli.main(base + ["status", "3", "screen"]) == 0
    assert cli.main(base + ["status", "3", "accepted"]) == 2
    assert cli.main(base + ["due"]) == 0
    out = capsys.readouterr().out
    assert "duplicate of #1" in out and "follow-up(s) due on 2026-01-19" in out
    assert cli.main(base + ["report", "--week-of", "2026-01-12", "--out", str(tmp_path / "r.md")]) == 0
    assert (tmp_path / "r.md").read_text(encoding="utf-8").startswith("# Traction report")
