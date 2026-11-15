from __future__ import annotations

from pathlib import Path

import pytest

from datacontracts import __version__, cli, rules

from .conftest import ROOT, edit


def run(capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, str, str]:
    code = cli.main(list(args))
    out = capsys.readouterr()
    return code, out.out, out.err


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as e:
        cli.main(["--version"])
    assert e.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_rules_lists_every_rule(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "rules")
    assert code == 0
    assert len(out.strip().splitlines()) == len(rules.REGISTRY) == 17
    assert "DC015  critical" in out


def test_check_passes_on_the_real_registry(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "check", "--root", str(ROOT), "--today", "2026-11-15")
    assert code == 0
    assert out.strip() == "9 contracts, 17 rules: 0 findings"


def test_check_markdown(capsys: pytest.CaptureFixture[str], sample: Path) -> None:
    edit(sample, "contracts/sales.orders.toml", 'owner = "sales-data"', 'owner = "ghost"')
    code, out, _ = run(capsys, "check", "--root", str(sample), "--format", "markdown")
    assert code == 1
    assert "## Registry check" in out and "| high | DC003 |" in out


def test_check_threshold(capsys: pytest.CaptureFixture[str], sample: Path) -> None:
    edit(
        sample,
        "contracts/sales.orders.toml",
        'description = "Calendar date of ordered_at in UTC. Added in 1.2.0 for daily reporting."',
        'description = "x"',
    )
    assert run(capsys, "check", "--root", str(sample))[0] == 0  # only a medium finding
    code, out, _ = run(capsys, "check", "--root", str(sample), "--fail-on", "medium")
    assert code == 1 and "MEDIUM   DC004" in out


def test_check_with_a_broken_registry(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    code, _, err = run(capsys, "check", "--root", str(tmp_path))
    assert code == 2 and "registry.toml: not found" in err


def test_compat_reports_pending_changes_and_passes(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "compat", "--root", str(ROOT))
    assert code == 0
    assert "sales.orders: 1.1.0 -> 1.2.0, needs a minor bump" in out
    assert "finance.invoices: 1.3.0 -> 2.0.0, needs a major bump" in out
    assert "(planned removal)" in out
    assert "sales.customers" not in out  # 1.1.0 is already released


def test_compat_fails_on_a_dishonest_bump_and_names_who_is_hit(
    capsys: pytest.CaptureFixture[str], sample: Path
) -> None:
    edit(
        sample,
        "contracts/sales.orders.toml",
        'name = "amount"\ntype = "decimal"',
        'name = "amount"\ntype = "string"',
    )
    code, out, _ = run(capsys, "compat", "--root", str(sample), "--contract", "sales.orders")
    assert code == 1
    assert "breaking type-changed `amount`" in out
    assert "high   finance.ar-aging (finance-analytics) via finance.invoices" in out
    assert "problem: sales.orders: changes need a major bump" in out


def test_compat_single_contract_and_unknown(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "compat", "--root", str(ROOT), "--contract", "ml.churn_features")
    assert code == 0 and out.strip() == "no contract differs from its last release"
    code, _, err = run(capsys, "compat", "--root", str(ROOT), "--contract", "nope.nothing")
    assert code == 2 and "no contract nope.nothing" in err


def test_compat_surfaces_a_tampered_release(
    capsys: pytest.CaptureFixture[str], sample: Path
) -> None:
    edit(sample, "releases/sales.orders/1.1.0.toml", "tier = 1", "tier = 2")
    code, _, err = run(capsys, "compat", "--root", str(sample))
    assert code == 1 and "does not match the index" in err


def test_release_publishes_pending_versions_and_then_compat_is_quiet(
    capsys: pytest.CaptureFixture[str], sample: Path
) -> None:
    code, out, _ = run(capsys, "release", "--root", str(sample), "--all")
    assert code == 0
    assert "released sales.orders 1.2.0 -> releases/sales.orders/1.2.0.toml" in out
    assert "released finance.invoices 2.0.0" in out
    code, out, _ = run(capsys, "compat", "--root", str(sample))
    assert code == 0 and "no contract differs" in out
    assert run(capsys, "check", "--root", str(sample), "--today", "2026-11-15")[0] == 0


def test_release_one_and_refusals(capsys: pytest.CaptureFixture[str], sample: Path) -> None:
    assert run(capsys, "release", "--root", str(sample), "sales.orders")[0] == 0
    assert run(capsys, "release", "--root", str(sample))[0] == 2
    code, _, err = run(capsys, "release", "--root", str(sample), "nope.nothing")
    assert code == 2 and "no contract nope.nothing" in err
    edit(sample, "contracts/sales.orders.toml", "tier = 1", "tier = 2")
    code, _, err = run(capsys, "release", "--root", str(sample), "sales.orders")
    assert code == 1 and "already released with different content" in err


def test_validate_good_and_bad(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    code, out, _ = run(
        capsys,
        "validate",
        "--root",
        str(ROOT),
        "sales.orders",
        str(ROOT / "samples/sales.orders.jsonl"),
    )
    assert code == 0 and "12 rows against sales.orders 1.2.0: 0 violations" in out
    bad = tmp_path / "bad.jsonl"
    bad.write_text(
        '{"order_id": "O-1"}\nnot json\n{"order_id": "O-2", "amount": "abc", "status": "lost", "x": 1}\n',
        encoding="utf-8",
    )
    code, out, _ = run(
        capsys, "validate", "--root", str(ROOT), "sales.orders", str(bad), "--max", "3"
    )
    assert code == 1
    assert "row 2: json: not valid JSON" in out and "... and " in out and "violations" in out


def test_validate_errors(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run(capsys, "validate", "--root", str(ROOT), "nope.nothing", "x.jsonl")
    assert code == 2 and "no contract nope.nothing" in err
    code, _, err = run(capsys, "validate", "--root", str(ROOT), "sales.orders", "missing.jsonl")
    assert code == 2 and "not found" in err


def test_report_and_export_write_then_check_then_detect_staleness(
    capsys: pytest.CaptureFixture[str], sample: Path
) -> None:
    code, out, _ = run(capsys, "report", "--root", str(sample))
    assert code == 0 and out.strip() == "wrote 6 of 6 files"
    code, out, _ = run(capsys, "export", "--root", str(sample))
    assert code == 0 and out.strip() == "wrote 27 of 27 files"
    assert (
        run(capsys, "report", "--root", str(sample), "--check")[1].strip()
        == "6 generated files are current"
    )
    assert run(capsys, "export", "--root", str(sample), "--check")[0] == 0
    run(capsys, "report", "--root", str(sample))  # second write changes nothing
    edit(sample, "contracts/sales.orders.toml", "tier = 1", "tier = 2")
    code, out, _ = run(capsys, "report", "--root", str(sample), "--check")
    assert code == 1 and "stale: reports/catalog.md" in out and "run `dcr report`" in out
    code, out, _ = run(capsys, "export", "--root", str(sample), "--check")
    assert code == 1 and "stale: ddl/spark/sales.orders.sql" in out


def test_report_and_export_with_a_broken_registry(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    assert run(capsys, "report", "--root", str(tmp_path))[0] == 2
    assert run(capsys, "export", "--root", str(tmp_path))[0] == 2
    assert run(capsys, "compat", "--root", str(tmp_path))[0] == 2
    assert run(capsys, "release", "--root", str(tmp_path), "--all")[0] == 2
    assert run(capsys, "validate", "--root", str(tmp_path), "a.b", "x")[0] == 2
