# Contributing

Thanks for taking the time to improve this project.

## Development setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make check          # ruff, mypy --strict, pytest with an 85% coverage gate
make registry       # the registry checks CI runs: rules, compatibility, generated files
```

## What a change needs

- Change `contracts/`, never `reports/`, `schemas/` or `ddl/`. Run `dcr report` and `dcr export` and commit the result; CI fails if they differ.
- Never edit a file under `releases/`. A released version is immutable (rule `DC015`); publish a new version instead.
- Run `dcr compat --contract <id>` before opening a pull request. The version bump must match the changes (rule `DC016`).
- Remove a field only after a released deprecation (see `docs/runbooks/deprecating-a-field.md`).
- A field derived from personal data is `pii` or explicitly `masked`; keep `derived_from` accurate (rule `DC012`).
- A new rule has an ID, a severity, a reason and a failing-case test; a new kind of change goes into `CHANGE_KINDS` with its reason.
- Decisions that change how compatibility or releases work get an ADR in `docs/adr/`.
- Update `CHANGELOG.md` for anything a user would notice.

## Pull requests

Keep them focused, describe the behaviour change and how you tested it, and make sure
CI is green. Security issues go through private reporting, see [SECURITY.md](SECURITY.md).
