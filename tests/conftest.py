from __future__ import annotations

import shutil
import tomllib
from datetime import date
from pathlib import Path

import pytest

from datacontracts.model import Contract, Registry, load_registry, parse_contract

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 11, 15)

BASE = """\
[contract]
id = "sales.orders"
version = "1.0.0"
owner = "sales-data"
domain = "sales"
tier = 2
status = "active"
classification = "internal"
description = "Orders after cleaning, one row per order."
retention_days = 100

[sla]
freshness_minutes = 60
completeness_pct = 99.0

[[field]]
name = "order_id"
type = "string"
nullable = false
primary_key = true
description = "Order identifier."

[[field]]
name = "amount"
type = "decimal"
nullable = false
description = "Order total in the order currency."

[[field]]
name = "status"
type = "string"
nullable = false
enum = ["placed", "paid"]
description = "Where the order is in its life."

[[quality]]
id = "amount_range"
field = "amount"
check = "range"
min = 0
max = 100

[[consumer]]
id = "finance.pipeline"
team = "finance-data"
criticality = "high"
fields = ["order_id", "amount"]
"""


def parse(text: str) -> Contract:
    c = parse_contract(tomllib.loads(text), "contracts/sales.orders.toml")
    assert c is not None
    return c


def variant(old: str, new: str, text: str = BASE) -> Contract:
    """The base contract with one piece of text replaced, parsed."""
    assert old in text, f"{old!r} not in base"
    return parse(text.replace(old, new, 1))


@pytest.fixture
def sample(tmp_path: Path) -> Path:
    """A writable copy of the real registry (contracts, releases and registry.toml)."""
    dest = tmp_path / "reg"
    dest.mkdir()
    shutil.copy(ROOT / "registry.toml", dest / "registry.toml")
    shutil.copytree(ROOT / "contracts", dest / "contracts")
    shutil.copytree(ROOT / "releases", dest / "releases")
    shutil.copytree(ROOT / "samples", dest / "samples")
    return dest


def edit(root: Path, rel: str, old: str, new: str) -> None:
    p = root / rel
    text = p.read_text(encoding="utf-8")
    assert old in text, f"{old!r} not found in {rel}"
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


def load(root: Path) -> Registry:
    reg, problems = load_registry(root)
    assert reg is not None, problems
    return reg


def add_release(root: Path, cid: str, version: str, text: str) -> None:
    """Publish ``text`` as an older release by hand, recording its hash in the index."""
    import json

    from datacontracts.model import canonical_hash

    dest = root / "releases" / cid / f"{version}.toml"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    index_path = root / "releases" / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.is_file() else {}
    index.setdefault(cid, {})[version] = canonical_hash(tomllib.loads(text))
    index_path.write_text(json.dumps(index), encoding="utf-8")
