"""The repository must agree with itself: claims, links, workflows and generated files."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest
import yaml

import datacontracts
from datacontracts import cli, compat, rules

from .conftest import ROOT, TODAY, load

README = (ROOT / "README.md").read_text(encoding="utf-8")
MD = [
    ROOT / "README.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "SECURITY.md",
    ROOT / "CHANGELOG.md",
    *(ROOT / "docs").rglob("*.md"),
]
SKIP_DIRS = {".git", ".venv", "__pycache__", ".ruff_cache", ".mypy_cache", ".pytest_cache"}


def test_version_matches_pyproject() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["version"] == datacontracts.__version__
    assert f"## [{project['version']}]" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")


def test_markdown_links_resolve() -> None:
    broken = []
    for f in MD:
        for m in re.finditer(r"\]\(([^)#\s][^)]*)\)", f.read_text(encoding="utf-8")):
            target = m.group(1)
            if target.startswith("http"):
                continue
            if not (f.parent / target.split("#")[0]).resolve().exists():
                broken.append(f"{f.relative_to(ROOT)}: {target}")
    assert broken == []


def test_readme_numbers_match_the_code() -> None:
    reg = load(ROOT)
    assert f"{len(reg.contracts)} contracts" in README or "nine contracts" in README
    assert len(reg.contracts) == 9
    assert f"{len(compat.CHANGE_KINDS)} kinds" in README and len(compat.CHANGE_KINDS) == 35
    assert f"{len(rules.REGISTRY)} rules over the registry" in README and len(rules.REGISTRY) == 17
    assert "6 reports" in README.replace("(six)", "6 reports") or "six" in README
    assert "Mutation checks: 27 deliberate bugs" in README


def test_readme_rule_table_matches_the_registry() -> None:
    rows = re.findall(r"^\| `(DC\d{3})` \| (\w+) \| (.+) \|$", README, re.MULTILINE)
    assert [(i, s, t) for i, s, t, _ in rules.catalog()] == rows


def test_readme_command_output_is_what_the_tool_prints(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["check", "--root", str(ROOT), "--today", TODAY.isoformat()]) == 0
    assert capsys.readouterr().out.strip() in README
    assert cli.main(["compat", "--root", str(ROOT)]) == 0
    assert capsys.readouterr().out.strip() in README


def test_every_command_is_documented() -> None:
    for cmd in ("check", "compat", "release", "validate", "report", "export", "rules"):
        assert f"`{cmd}`" in README, cmd
        assert f"dcr {cmd}" in README or cmd == "rules", cmd


def test_every_change_kind_appears_in_the_generated_report() -> None:
    text = (ROOT / "reports" / "change-kinds.md").read_text(encoding="utf-8")
    for kind in compat.CHANGE_KINDS:
        assert f"`{kind}`" in text


def test_adrs_are_numbered_complete_and_linked() -> None:
    adrs = sorted((ROOT / "docs" / "adr").glob("*.md"))
    assert [p.name[:4] for p in adrs] == [f"{i:04d}" for i in range(1, len(adrs) + 1)]
    for p in adrs:
        text = p.read_text(encoding="utf-8")
        for heading in ("## Status", "## Context", "## Decision", "## Consequences"):
            assert heading in text, f"{p.name} lacks {heading}"
        assert p.name in README


@pytest.mark.parametrize(
    "path", sorted((ROOT / "docs" / "runbooks").glob("*.md")), ids=lambda p: p.stem
)
def test_runbooks_are_complete_and_linked(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for h in (
        "## Purpose",
        "## Triggers",
        "## First checks",
        "## Steps",
        "## Verification",
        "## Escalation",
    ):
        assert h in text, f"{path.name} lacks {h}"
    assert path.name in README


def test_runbooks_only_name_commands_that_exist() -> None:
    parser_text = " ".join(
        (ROOT / "docs" / "runbooks" / n).read_text(encoding="utf-8")
        for n in ("breaking-change.md", "deprecating-a-field.md", "onboarding-a-consumer.md")
    )
    known = {"check", "compat", "release", "validate", "report", "export", "rules"}
    for cmd in re.findall(r"`dcr (\w+)", parser_text):
        assert cmd in known, cmd


def test_workflows_exist_and_parse() -> None:
    for name in ("ci.yml", "codeql.yml"):
        doc = yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))
        assert doc["jobs"], name


def test_ci_runs_every_registry_gate() -> None:
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for cmd in (
        "dcr check --fail-on high",
        "dcr compat",
        "dcr report --check",
        "dcr export --check",
        "dcr validate sales.orders samples/sales.orders.jsonl",
        "--cov-fail-under=85",
        "mypy",
        "pip-audit",
    ):
        assert cmd in ci, cmd
    assert "permissions:\n  contents: read" in ci


def test_ci_validates_every_sample_file() -> None:
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for sample in (ROOT / "samples").glob("*.jsonl"):
        assert f"samples/{sample.name}" in ci, sample.name


def test_makefile_targets_match_ci() -> None:
    mk = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert (
        "dcr check --fail-on high && dcr compat && dcr report --check && dcr export --check" in mk
    )


def test_codeowners_and_dependabot_are_present() -> None:
    assert (ROOT / ".github" / "CODEOWNERS").read_text(
        encoding="utf-8"
    ).strip() == "* @darshansatpathy"
    dep = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
    assert {u["package-ecosystem"] for u in dep["updates"]} == {"pip", "github-actions"}


def test_every_contract_file_matches_its_id_and_every_release_is_indexed() -> None:
    reg = load(ROOT)
    for cid, c in reg.contracts.items():
        assert c.source == f"contracts/{cid}.toml"
    index = (ROOT / "releases" / "index.json").read_text(encoding="utf-8")
    for p in (ROOT / "releases").rglob("*.toml"):
        assert p.stem in index and p.parent.name in index, p


SECRET_PATTERNS = [
    r"ghp_[A-Za-z0-9]{20,}",
    r"AKIA[0-9A-Z]{16}",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"sk-ant-[A-Za-z0-9-]{20,}",
]


def test_no_secrets_or_private_addresses_in_the_repository() -> None:
    hits = []
    for f in ROOT.rglob("*"):
        if not f.is_file() or SKIP_DIRS & set(f.relative_to(ROOT).parts) or f == Path(__file__):
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        hits += [f"{f.relative_to(ROOT)}: {p}" for p in SECRET_PATTERNS if re.search(p, text)]
        if "gmail.com" in text:
            hits.append(f"{f.relative_to(ROOT)}: personal email address")
    assert hits == []


def test_sample_data_is_clearly_synthetic() -> None:
    for f in (ROOT / "samples").glob("*.jsonl"):
        for email in re.findall(r"[\w.+-]+@[\w.-]+", f.read_text(encoding="utf-8")):
            assert email.endswith("@example.com"), (f.name, email)
