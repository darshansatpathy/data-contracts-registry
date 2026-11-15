from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from datacontracts.validate import read_jsonl, validate_records

from .conftest import BASE, ROOT, load, parse


def rows(*items: dict[str, Any]) -> list[dict[str, Any]]:
    return list(items)


GOOD = {"order_id": "O-1", "amount": 10.5, "status": "placed"}


def test_a_good_row_passes() -> None:
    assert validate_records(parse(BASE), rows(GOOD)) == []


@pytest.mark.parametrize(
    ("row", "rule", "field"),
    [
        ({**GOOD, "extra": 1}, "unknown-field", "extra"),
        ({"amount": 1, "status": "placed"}, "missing", "order_id"),
        ({**GOOD, "order_id": None}, "null", "order_id"),
        ({**GOOD, "order_id": 5}, "type", "order_id"),
        ({**GOOD, "amount": "abc"}, "type", "amount"),
        ({**GOOD, "amount": True}, "type", "amount"),
        ({**GOOD, "amount": [1]}, "type", "amount"),
        ({**GOOD, "status": "lost"}, "enum", "status"),
        ({**GOOD, "amount": 500}, "amount_range", "amount"),
        ({**GOOD, "amount": -1}, "amount_range", "amount"),
    ],
)
def test_each_kind_of_violation(row: dict[str, Any], rule: str, field: str) -> None:
    found = validate_records(parse(BASE), rows(row))
    assert (rule, field) in {(v.rule, v.field) for v in found}, found


def test_decimal_strings_and_numbers_are_accepted() -> None:
    assert validate_records(parse(BASE), rows({**GOOD, "amount": "10.25"})) == []
    assert validate_records(parse(BASE), rows({**GOOD, "amount": 7})) == []


@pytest.mark.parametrize(
    ("ftype", "good", "bad"),
    [
        ("string", "x", 1),
        ("int", 5, 2**31),
        ("long", 2**40, 2**64),
        ("int", 5, 1.5),
        ("int", 5, True),
        ("double", 1.5, "1.5"),
        ("double", 2, True),
        ("decimal", "1.5", "x"),
        ("boolean", True, 1),
        ("date", "2026-11-15", "15/11/2026"),
        ("date", "2026-11-15", "2026-13-45"),
        ("date", "2026-11-15", 5),
        ("timestamp", "2026-11-15T10:00:00Z", "yesterday"),
        ("timestamp", "2026-11-15T10:00:00+05:30", 5),
    ],
)
def test_types(ftype: str, good: Any, bad: Any) -> None:
    text = BASE.replace(
        'name = "amount"\ntype = "decimal"', f'name = "amount"\ntype = "{ftype}"'
    ).replace(
        '[[quality]]\nid = "amount_range"\nfield = "amount"\ncheck = "range"\nmin = 0\nmax = 100\n\n',
        "",
    )
    c = parse(text)
    assert validate_records(c, rows({**GOOD, "amount": good})) == []
    assert [v.rule for v in validate_records(c, rows({**GOOD, "amount": bad}))] == ["type"]


def test_integer_ranges_include_their_limits() -> None:
    def check(ftype: str, value: int) -> list[str]:
        text = BASE.replace(
            'name = "amount"\ntype = "decimal"', f'name = "amount"\ntype = "{ftype}"'
        ).replace(
            '[[quality]]\nid = "amount_range"\nfield = "amount"\ncheck = "range"\nmin = 0\nmax = 100\n\n',
            "",
        )
        return [v.rule for v in validate_records(parse(text), rows({**GOOD, "amount": value}))]

    assert check("int", 2**31 - 1) == [] and check("int", -(2**31)) == []
    assert check("int", 2**31) == ["type"] and check("int", -(2**31) - 1) == ["type"]
    assert check("long", 2**63 - 1) == [] and check("long", -(2**63)) == []
    assert check("long", 2**63) == ["type"] and check("long", -(2**63) - 1) == ["type"]


def test_nullable_fields_may_be_null_or_absent() -> None:
    text = BASE.replace(
        'type = "decimal"\nnullable = false', 'type = "decimal"\nnullable = true'
    ).replace(
        '[[quality]]\nid = "amount_range"\nfield = "amount"\ncheck = "range"\nmin = 0\nmax = 100\n\n',
        "",
    )
    c = parse(text)
    assert validate_records(c, rows({**GOOD, "amount": None})) == []
    assert validate_records(c, rows({"order_id": "O-1", "status": "placed"})) == []


def test_unique_regex_not_null_and_primary_key() -> None:
    extra = (
        '\n[[quality]]\nid = "u"\nfield = "status"\ncheck = "unique"\n'
        '\n[[quality]]\nid = "r"\nfield = "order_id"\ncheck = "regex"\npattern = "O-[0-9]+"\n'
        '\n[[quality]]\nid = "n"\nfield = "amount"\ncheck = "not_null"\n'
    )
    c = parse(BASE + extra)
    found = validate_records(
        c, rows(GOOD, {**GOOD, "order_id": "X"}, {**GOOD, "order_id": "O-1", "status": "paid"})
    )
    pairs = {(v.row, v.rule) for v in found}
    assert (2, "u") in pairs and (2, "r") in pairs
    assert (3, "primary-key") in pairs
    assert validate_records(c, rows({**GOOD, "amount": None}))[0].rule in ("null", "n")


def test_range_ignores_non_numbers_that_the_type_check_reports() -> None:
    found = validate_records(parse(BASE), rows({**GOOD, "amount": "abc"}))
    assert [v.rule for v in found] == ["type"]


def test_read_jsonl(tmp_path: Path) -> None:
    p = tmp_path / "x.jsonl"
    p.write_text('{"a": 1}\n\nnot json\n[1, 2]\n{"b": 2}\n', encoding="utf-8")
    rs, bad = read_jsonl(p)
    assert rs == [{"a": 1}, {"b": 2}]
    assert [(v.row, v.message) for v in bad] == [
        (3, "not valid JSON: Expecting value"),
        (4, "line is not a JSON object"),
    ]


@pytest.mark.parametrize("cid", ["sales.orders", "sales.customers", "finance.invoices"])
def test_the_shipped_samples_satisfy_their_contracts(cid: str) -> None:
    reg = load(ROOT)
    rs, bad = read_jsonl(ROOT / "samples" / f"{cid}.jsonl")
    assert bad == []
    assert len(rs) >= 5
    assert validate_records(reg.contracts[cid], rs) == []
