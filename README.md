# job-application-tracker

[![tests](https://github.com/Avinash186200/job-application-tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/Avinash186200/job-application-tracker/actions/workflows/ci.yml)

A small command-line tracker for a job search. It logs applications to SQLite, refuses duplicates, moves each
application through a status pipeline, tells you which follow-ups are due, and writes a weekly report of which
sources and role types actually get replies. Standard library only, Python 3.11+.

## What problem this solves

A spreadsheet works until it does not: the same role gets logged twice under slightly different names, nobody
remembers which applications need a nudge, and after a month it is hard to say whether job boards or referrals
are working. This tool does those three jobs and nothing else. It never applies to anything for you.

## Quick start

```bash
pip install -e ".[dev]"

jobtracker init
jobtracker add "Example Co" "Senior Data Scientist" --source job-board --url https://jobs.example.com/123
jobtracker add "example co." "Sr Data Scientist" --source referral
# duplicate of #1 (same company and title); not added

jobtracker status 1 screen --note "recruiter call booked"
jobtracker due
jobtracker report --week-of 2026-01-12
```

Try it on the example data:

```bash
jobtracker --db demo.db --config examples/jobtracker.example.toml import-csv examples/applications.example.csv
jobtracker --db demo.db --config examples/jobtracker.example.toml --today 2026-01-19 report --week-of 2026-01-12
```

## Features

| Feature | How |
|---|---|
| Log applications | `add`, or `import-csv` for a batch |
| De-duplication | Company and title are normalised (case, punctuation, accents, `Inc`/`Ltd`/`Pvt`..., `Sr`->`senior`, `ML`->`machine learning`); job URLs are normalised (host case, `www.`, tracking parameters). Either match blocks the add. Close spellings are flagged for you to check, never merged |
| Status pipeline | `applied -> screen -> interview -> offer -> accepted`, with `rejected`, `withdrawn` and `ghosted`. Illegal moves (for example `applied -> accepted`, or anything after `rejected`) are refused. Every move is stored with its date |
| Follow-up reminders | Each active status has an interval (`follow_up_days`). `due` lists what is due or overdue; `followed-up` moves the next reminder; `ghost` marks long-silent applications |
| Weekly traction report | Applications and moves this week, then response rate, interview rate and median days to reply, by source and by role type. Markdown or JSON |
| Reproducible | `--today` fixes the date, so runs and tests never depend on the clock |

## Commands

```
jobtracker [--db PATH] [--config TOML] [--today YYYY-MM-DD] COMMAND

init                                   create the database
add COMPANY TITLE --source S [--on D] [--location L] [--url U] [--notes N]
status ID NEW [--on D] [--note N]      move an application
due                                    follow-ups due today or overdue
followed-up ID [--days N]              you followed up (or snooze N days)
ghost                                  mark 'applied' with no reply after ghost_after_days
list [--status S]                      list applications
history ID                             status history
report [--week-of D] [--min-age-days N] [--json] [--out FILE]
import-csv PATH                        header: company,title,source,applied_on[,location,url,status,status_on,notes]
export-csv PATH
```

`--db` defaults to `./tracker.db` (or `$JOBTRACKER_DB`), `--config` to `$JOBTRACKER_CONFIG`. Exit codes: 0 ok,
1 duplicate not added, 2 invalid input or illegal move.

## Configuration

Copy `examples/jobtracker.example.toml` to `jobtracker.toml` (git-ignored). Every key is optional:

| Key | Meaning |
|---|---|
| `follow_up_days` | Days after the last update before a reminder, per status |
| `ghost_after_days` | Silent days before `ghost` marks an application |
| `sources` | Allowed sources; anything else is rejected so the report stays clean |
| `role_types` | Ordered keyword rules that classify job titles for the report |
| `company_suffixes` | Words dropped from company names before de-duplication |

## How the report counts

- A **reply** is any human response: screen, interview, offer, accepted or rejected. Ghosted and withdrawn are
  not replies.
- Applications younger than `--min-age-days` (default 7) with no reply yet are shown as **too new** and left out
  of the rates, so last week's batch does not drag the rate down before anyone could answer.
- Rates on small groups are noisy. The report says so.

## The daily routine

[docs/daily-process.md](docs/daily-process.md) describes a human-in-the-loop routine: replies and reminders in the
morning, searching and applying at midday, a weekly look at traction. If you automate any part of it, you approve
every submission and never let automation enter a password.

## Layout

```
src/jobtracker/
  cli.py        the command line
  store.py      SQLite storage, CSV import/export, follow-ups
  dedupe.py     company, title and URL normalisation
  pipeline.py   allowed status moves
  report.py     weekly traction report
  config.py     defaults, TOML loading, role-type rules
examples/       example config and CSV
tests/          unit and CLI tests
docs/           daily-process.md
```

## Limits

- Single user, single file. No sync, no web UI.
- Role types come from keyword rules on the title, so a vague title lands in `other`. Fix the rule, not the data.
- The report shows correlation, not cause: a source may reply more because of the roles you pick there.

## License

MIT. See [LICENSE](LICENSE). Contributing: [CONTRIBUTING.md](CONTRIBUTING.md). Changes: [CHANGELOG.md](CHANGELOG.md).
