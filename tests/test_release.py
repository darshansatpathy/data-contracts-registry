from __future__ import annotations

import json
from pathlib import Path

import pytest

from datacontracts.release import read_index, released, write_release

from .conftest import edit, load


def test_released_versions_are_oldest_first_and_intact(sample: Path) -> None:
    rels, problems = released(sample, "sales.customers")
    assert problems == []
    assert [r.version for r in rels] == ["1.0.0", "1.1.0"]
    assert rels[0].contract.field_named("marketing_opt_in") is None
    assert rels[1].contract.field_named("marketing_opt_in") is not None


def test_no_releases_is_not_a_problem(sample: Path) -> None:
    assert released(sample, "support.tickets") == ([], [])
    assert released(sample, "nope.nothing") == ([], [])


def test_index_missing_is_empty(tmp_path: Path) -> None:
    assert read_index(tmp_path) == {}


def test_tampering_with_a_released_file_is_detected(sample: Path) -> None:
    edit(sample, "releases/sales.customers/1.0.0.toml", "tier = 1", "tier = 2")
    rels, problems = released(sample, "sales.customers")
    assert [r.version for r in rels] == ["1.1.0"]
    assert "does not match the index" in problems[0]


def test_missing_and_broken_files_are_detected(sample: Path) -> None:
    (sample / "releases/sales.customers/1.0.0.toml").unlink()
    (sample / "releases/sales.orders/1.1.0.toml").write_text("not = [toml", encoding="utf-8")
    (sample / "releases/ml.churn_features/1.0.0.toml").write_text(
        "[sla]\nfreshness_minutes = 1\n", encoding="utf-8"
    )
    assert "file is missing" in released(sample, "sales.customers")[1][0]
    assert "invalid TOML" in released(sample, "sales.orders")[1][0]
    assert "does not parse as a contract" in released(sample, "ml.churn_features")[1][0]


def test_a_file_that_claims_another_version_is_detected(sample: Path) -> None:
    index = read_index(sample)
    src = (sample / "releases/sales.customers/1.1.0.toml").read_text(encoding="utf-8")
    (sample / "releases/sales.customers/9.9.9.toml").write_text(src, encoding="utf-8")
    index["sales.customers"]["9.9.9"] = index["sales.customers"]["1.1.0"]
    (sample / "releases/index.json").write_text(json.dumps(index), encoding="utf-8")
    assert "file says sales.customers 1.1.0" in released(sample, "sales.customers")[1][0]


def test_write_release_is_idempotent_and_refuses_to_change_history(sample: Path) -> None:
    reg = load(sample)
    c = reg.contracts["sales.orders"]
    dest = write_release(sample, c)
    assert dest == sample / "releases/sales.orders/1.2.0.toml"
    assert read_index(sample)["sales.orders"].keys() == {"1.1.0", "1.2.0"}
    write_release(sample, c)  # same content again is fine
    edit(sample, "contracts/sales.orders.toml", "tier = 1", "tier = 2")
    with pytest.raises(ValueError, match="already released with different content"):
        write_release(sample, load(sample).contracts["sales.orders"])
