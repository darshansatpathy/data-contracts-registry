from __future__ import annotations

import json
import sqlite3
from typing import Any

import pytest

from datacontracts import export
from datacontracts.render import all_exports
from datacontracts.validate import read_jsonl, validate_records

from .conftest import BASE, ROOT, load, parse


def schema_ok(schema: dict[str, Any], row: dict[str, Any]) -> bool:
    """A tiny checker for the subset of JSON Schema the exporter emits."""
    props = schema["properties"]
    if set(row) - set(props) or set(schema["required"]) - set(row):
        return False
    kinds = {"string": str, "integer": int, "number": (int, float), "boolean": bool}
    for name, value in row.items():
        p = props[name]
        allowed = p["type"] if isinstance(p["type"], list) else [p["type"]]
        if value is None:
            if "null" not in allowed:
                return False
            continue
        t = next(a for a in allowed if a != "null")
        if isinstance(value, bool) and t != "boolean":
            return False
        if not isinstance(value, kinds[t]):
            return False
        if "enum" in p and value not in p["enum"]:
            return False
        if "minimum" in p and not p["minimum"] <= value <= p["maximum"]:
            return False
    return True


def test_json_schema_shape() -> None:
    c = parse(BASE)
    s = json.loads(export.json_schema(c))
    assert s["$id"] == "urn:data-contract:sales.orders:1.0.0"
    assert s["additionalProperties"] is False
    assert s["required"] == ["order_id", "amount", "status"]
    assert s["properties"]["status"]["enum"] == ["placed", "paid"]
    assert s["x-contract"]["tier"] == 2


def test_nullable_and_pii_are_expressed() -> None:
    reg = load(ROOT)
    s = json.loads(export.json_schema(reg.contracts["sales.customers"]))
    assert s["properties"]["full_name"]["type"] == ["string", "null"]
    assert s["properties"]["email"]["x-pii"] is True
    assert "x-pii" not in s["properties"]["country"]
    o = json.loads(export.json_schema(reg.contracts["sales.orders"]))
    assert o["properties"]["channel"]["enum"] == ["web", "app", "store", "partner", None]


@pytest.mark.parametrize("cid", ["sales.orders", "sales.customers", "finance.invoices"])
def test_schema_agrees_with_the_validator_on_good_and_damaged_rows(cid: str) -> None:
    c = load(ROOT).contracts[cid]
    schema = json.loads(export.json_schema(c))
    good, _ = read_jsonl(ROOT / "samples" / f"{cid}.jsonl")
    for row in good:
        assert schema_ok(schema, row) and not validate_records(c, [row])
    first = good[0]
    required = next(f.name for f in c.fields if not f.nullable)
    damaged = [
        {k: v for k, v in first.items() if k != required},
        {**first, required: None},
        {**first, "surprise": 1},
        {**first, required: 12345},
    ]
    for row in damaged:
        assert not schema_ok(schema, row), row
        assert validate_records(c, [row]), row


def test_ansi_ddl_runs_and_enforces_the_contract() -> None:
    reg = load(ROOT)
    db = sqlite3.connect(":memory:")
    for dom in {c.domain for c in reg.contracts.values()}:
        db.execute(f"ATTACH DATABASE ':memory:' AS {dom}")
    for c in reg.contracts.values():
        db.execute(export.ddl(c, "ansi"))
    orders = reg.contracts["sales.orders"]
    rows, _ = read_jsonl(ROOT / "samples" / "sales.orders.jsonl")
    cols = orders.field_names
    insert = f"INSERT INTO sales.orders ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})"
    for r in rows:
        db.execute(insert, [r.get(k) for k in cols])
    assert db.execute("SELECT COUNT(*) FROM sales.orders").fetchone()[0] == len(rows)
    first = rows[0]
    for bad in (
        {**first, "customer_id": None},  # NOT NULL
        {**first, "status": "lost"},  # CHECK on the enum
        {**first, "channel": "carrier-pigeon"},  # CHECK on a nullable enum
        first,  # duplicate PRIMARY KEY
    ):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(insert, [bad.get(k) for k in cols])
    db.close()


def test_composite_keys_are_in_the_ddl() -> None:
    reg = load(ROOT)
    assert "PRIMARY KEY (revenue_date, currency)" in export.ddl(
        reg.contracts["finance.revenue_daily"]
    )
    assert "PRIMARY KEY" not in export.ddl(reg.contracts["sales.legacy_orders"]).replace(
        "PRIMARY KEY (legacy_order_no)", ""
    )


def test_spark_ddl_has_comments_and_properties_and_escapes_quotes() -> None:
    c = parse(
        BASE.replace(
            'description = "Order identifier."', 'description = "Customer\'s order identifier."'
        )
    )
    sql = export.ddl(c, "spark")
    assert sql.startswith("-- Generated from contracts/sales.orders.toml version 1.0.0")
    assert "CREATE TABLE IF NOT EXISTS sales.orders" in sql
    assert "COMMENT 'Customer''s order identifier.'" in sql
    assert "USING DELTA" in sql and "'contract.version' = '1.0.0'" in sql
    assert "'contract.classification' = 'internal'" in sql
    assert "CHECK" not in sql and "PRIMARY KEY" not in sql
    assert "STRING" in sql and "DECIMAL(18,4)" in sql


def test_unknown_dialect_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown dialect"):
        export.ddl(parse(BASE), "oracle")


def test_all_exports_cover_every_contract_in_three_forms() -> None:
    reg = load(ROOT)
    files = all_exports(reg)
    assert len(files) == 3 * len(reg.contracts)
    for cid in reg.contracts:
        assert f"schemas/{cid}.schema.json" in files
        assert f"ddl/ansi/{cid}.sql" in files and f"ddl/spark/{cid}.sql" in files


def test_exports_on_disk_are_current() -> None:
    for rel, text in all_exports(load(ROOT)).items():
        assert (ROOT / rel).read_text(encoding="utf-8") == text, rel
