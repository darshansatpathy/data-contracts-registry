"""Generated artefacts: JSON Schema, and DDL for a SQL warehouse."""

from __future__ import annotations

import json
from typing import Any

from datacontracts.model import Contract, Field

_JSON_TYPE: dict[str, dict[str, Any]] = {
    "string": {"type": "string"},
    "int": {"type": "integer", "minimum": -(2**31), "maximum": 2**31 - 1},
    "long": {"type": "integer"},
    "double": {"type": "number"},
    "decimal": {"type": "number"},
    "boolean": {"type": "boolean"},
    "date": {"type": "string", "format": "date"},
    "timestamp": {"type": "string", "format": "date-time"},
}
_ANSI = {
    "string": "VARCHAR",
    "int": "INTEGER",
    "long": "BIGINT",
    "double": "DOUBLE PRECISION",
    "decimal": "DECIMAL(18,4)",
    "boolean": "BOOLEAN",
    "date": "DATE",
    "timestamp": "TIMESTAMP",
}
_SPARK = {**_ANSI, "string": "STRING", "double": "DOUBLE"}


def _prop(f: Field) -> dict[str, Any]:
    prop = dict(_JSON_TYPE[f.type])
    if f.nullable:
        prop["type"] = [prop["type"], "null"]
    if f.enum:
        prop["enum"] = [*f.enum, None] if f.nullable else list(f.enum)
    prop["description"] = f.description
    if f.pii:
        prop["x-pii"] = True
    return prop


def json_schema(c: Contract) -> str:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"urn:data-contract:{c.id}:{c.version}",
        "title": c.id,
        "description": c.description,
        "type": "object",
        "additionalProperties": False,
        "required": [f.name for f in c.fields if not f.nullable],
        "properties": {f.name: _prop(f) for f in c.fields},
        "x-contract": {
            "version": c.version,
            "owner": c.owner,
            "classification": c.classification,
            "tier": c.tier,
        },
    }
    return json.dumps(schema, indent=2) + "\n"


def _q(text: str) -> str:
    return text.replace("'", "''")


def ddl(c: Contract, dialect: str = "ansi") -> str:
    """``CREATE TABLE`` for the contract.

    ``ansi`` is executed against SQLite in the tests; ``spark`` has not been run on Databricks.
    """
    if dialect not in ("ansi", "spark"):
        raise ValueError(f"unknown dialect {dialect}")
    types = _ANSI if dialect == "ansi" else _SPARK
    lines: list[str] = []
    for f in c.fields:
        col = f"  {f.name} {types[f.type]}{'' if f.nullable else ' NOT NULL'}"
        if dialect == "spark":
            col += f" COMMENT '{_q(f.description)}'"
        lines.append(col)
    if dialect == "ansi":
        keys = [f.name for f in c.fields if f.primary_key]
        if keys:
            lines.append(f"  PRIMARY KEY ({', '.join(keys)})")
        for f in c.fields:
            if f.enum:
                values = ", ".join(f"'{_q(v)}'" for v in f.enum)
                lines.append(f"  CHECK ({f.name} IS NULL OR {f.name} IN ({values}))")
    head = f"-- Generated from contracts/{c.id}.toml version {c.version}. Do not edit.\n"
    body = f"CREATE TABLE {c.id} (\n" + ",\n".join(lines) + "\n)"
    if dialect == "spark":
        body = body.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS", 1)
        body += (
            f"\nUSING DELTA\nCOMMENT '{_q(c.description)}'\nTBLPROPERTIES (\n"
            f"  'contract.version' = '{c.version}',\n  'contract.owner' = '{_q(c.owner)}',\n"
            f"  'contract.classification' = '{c.classification}',\n"
            f"  'contract.tier' = '{c.tier}'\n)"
        )
    return head + body + ";\n"
