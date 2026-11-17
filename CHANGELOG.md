# Changelog

All notable changes are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-11-17

### Added

- Command-line tracker on SQLite: `init`, `add`, `status`, `due`, `followed-up`, `ghost`, `list`, `history`,
  `report`, `import-csv`, `export-csv`.
- De-duplication by normalised company and title, and by normalised job URL; close spellings flagged for review.
- Status pipeline with allowed moves and a dated history of every move.
- Follow-up reminders per status, snoozing, and automatic ghosting of long-silent applications.
- Weekly traction report: response rate, interview rate and median days to reply by source and by role type, with
  too-new applications left out of the rates.
- TOML configuration with an example, example CSV data, tests, and CI (ruff, pytest, an end-to-end CLI run).
- `docs/daily-process.md`: a human-in-the-loop daily routine.
