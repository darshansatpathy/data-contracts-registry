.PHONY: install check test registry report audit

install:
	python -m venv .venv && .venv/bin/pip install -e ".[dev]"

check:
	ruff check . && ruff format --check . && mypy && pytest --cov=datacontracts --cov-fail-under=85

test:
	pytest

# What CI runs against the registry itself
registry:
	dcr check --fail-on high && dcr compat && dcr report --check && dcr export --check

report:
	dcr report && dcr export

audit:
	pip-audit --skip-editable
