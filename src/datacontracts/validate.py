"""Check records against a contract. Used to test that a contract means what it says."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from datacontracts.model import Contract, Field

INT32 = (-(2**31), 2**31 - 1)
INT64 = (-(2**63), 2**63 - 1)


@dataclass(frozen=True)
class Violation:
    row: int
    field: str
    rule: str
    message: str


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[Violation]]:
    """Rows of a JSON Lines file, and a violation for every line that is not a JSON object."""
    rows: list[dict[str, Any]] = []
    bad: list[Violation] = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            bad.append(Violation(n, "", "json", f"not valid JSON: {exc.msg}"))
            continue
        if not isinstance(obj, dict):
            bad.append(Violation(n, "", "json", "line is not a JSON object"))
            continue
        rows.append(obj)
    return rows, bad


def _type_ok(f: Field, v: Any) -> str | None:
    """Returns a message if ``v`` is not a valid value of the field's type."""
    t = f.type
    if t == "string":
        return None if isinstance(v, str) else "expected a string"
    if t in ("int", "long"):
        if isinstance(v, bool) or not isinstance(v, int):
            return f"expected an integer ({t})"
        lo, hi = INT32 if t == "int" else INT64
        return None if lo <= v <= hi else f"outside the {t} range"
    if t == "double":
        return (
            None if isinstance(v, int | float) and not isinstance(v, bool) else "expected a number"
        )
    if t == "decimal":
        if isinstance(v, bool) or not isinstance(v, int | float | str):
            return "expected a decimal"
        try:
            Decimal(str(v))
        except InvalidOperation:
            return "not a decimal number"
        return None
    if t == "boolean":
        return None if isinstance(v, bool) else "expected true or false"
    if t == "date":
        try:
            if not isinstance(v, str) or len(v) != 10:
                raise ValueError
            date.fromisoformat(v)
        except ValueError:
            return "expected an ISO date (YYYY-MM-DD)"
        return None
    if t == "timestamp":
        try:
            if not isinstance(v, str):
                raise ValueError
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            return "expected an ISO 8601 timestamp"
        return None
    return f"unknown type {t}"


def _number(v: Any) -> Decimal | None:
    if isinstance(v, bool) or not isinstance(v, int | float | str):
        return None
    try:
        return Decimal(str(v))
    except InvalidOperation:
        return None


def validate_records(c: Contract, rows: Iterable[dict[str, Any]]) -> list[Violation]:
    out: list[Violation] = []
    names = set(c.field_names)
    unique_seen: dict[str, set[Any]] = {q.field: set() for q in c.quality if q.check == "unique"}
    keys = [f.name for f in c.fields if f.primary_key]
    key_seen: set[tuple[Any, ...]] = set()
    for n, row in enumerate(rows, start=1):
        for extra in sorted(set(row) - names):
            out.append(Violation(n, extra, "unknown-field", "field is not in the contract"))
        for f in c.fields:
            if f.name not in row:
                if not f.nullable:
                    out.append(Violation(n, f.name, "missing", "required field is absent"))
                continue
            v = row[f.name]
            if v is None:
                if not f.nullable:
                    out.append(Violation(n, f.name, "null", "field is not nullable"))
                continue
            msg = _type_ok(f, v)
            if msg:
                out.append(Violation(n, f.name, "type", msg))
                continue
            if f.enum and v not in f.enum:
                out.append(Violation(n, f.name, "enum", f"`{v}` is not one of {', '.join(f.enum)}"))
        for q in c.quality:
            v = row.get(q.field)
            if q.check == "not_null" and v is None:
                out.append(Violation(n, q.field, q.id, "must not be null"))
            elif q.check == "unique" and v is not None:
                if v in unique_seen[q.field]:
                    out.append(Violation(n, q.field, q.id, f"`{v}` appears more than once"))
                unique_seen[q.field].add(v)
            elif q.check == "range" and v is not None:
                num = _number(v)
                if num is None:
                    continue
                if (q.min is not None and num < Decimal(str(q.min))) or (
                    q.max is not None and num > Decimal(str(q.max))
                ):
                    out.append(Violation(n, q.field, q.id, f"{v} is outside the allowed range"))
            elif (
                q.check == "regex"
                and isinstance(v, str)
                and q.pattern
                and not re.fullmatch(q.pattern, v)
            ):
                out.append(Violation(n, q.field, q.id, f"`{v}` does not match the pattern"))
        if keys and all(row.get(k) is not None for k in keys):
            key = tuple(row[k] for k in keys)
            if key in key_seen:
                out.append(Violation(n, ",".join(keys), "primary-key", f"duplicate key {key}"))
            key_seen.add(key)
    return out
