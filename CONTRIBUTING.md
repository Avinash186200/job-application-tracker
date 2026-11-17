# Contributing

Thanks for taking a look. Issues and pull requests are welcome.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Before you open a pull request

```bash
ruff check .
pytest -q
```

CI runs both on Python 3.11 and 3.12, then an end-to-end CLI run on the example data.

## Guidelines

- Keep the standard-library-only runtime. Development tools can be added to the `dev` extra.
- New behaviour comes with a test. Pass dates explicitly (or use `--today`) so tests never depend on the clock.
- Changes to the report's definitions (what counts as a reply, the too-new rule) need a note in the README and the
  CHANGELOG, because they change how past numbers read.
- Never commit a real tracker database, export or personal config. They are git-ignored; keep it that way.
- Add a line to `CHANGELOG.md` under an "Unreleased" heading.
