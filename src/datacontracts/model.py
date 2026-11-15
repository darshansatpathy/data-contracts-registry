"""Contract model and loader.

A registry is a directory with ``registry.toml`` (teams and policy limits) and one TOML file per
contract in ``contracts/``. Loading reports every structural problem it can find instead of
stopping at the first, and never executes anything from the files it reads.
"""

from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

TYPES = ("string", "int", "long", "double", "decimal", "boolean", "date", "timestamp")
CLASSIFICATIONS = ("public", "internal", "confidential", "restricted")
STATUSES = ("draft", "active", "deprecated", "retired")
CRITICALITIES = ("high", "medium", "low")
CHECKS = ("not_null", "unique", "range", "regex")


@dataclass(frozen=True)
class Field:
    name: str
    type: str
    nullable: bool
    description: str
    pii: bool
    primary_key: bool
    masked: bool
    derived_from: str | None
    enum: tuple[str, ...]


@dataclass(frozen=True)
class Quality:
    id: str
    field: str
    check: str
    min: float | None
    max: float | None
    pattern: str | None


@dataclass(frozen=True)
class Consumer:
    id: str
    team: str
    fields: tuple[str, ...]
    criticality: str


@dataclass(frozen=True)
class Deprecation:
    field: str
    sunset: date
    replacement: str | None


@dataclass(frozen=True)
class Sla:
    freshness_minutes: int | None
    completeness_pct: float | None


@dataclass(frozen=True)
class Contract:
    id: str
    version: str
    owner: str
    domain: str
    tier: int
    status: str
    classification: str
    description: str
    upstream: tuple[str, ...]
    retention_days: int | None
    sla: Sla
    fields: tuple[Field, ...]
    quality: tuple[Quality, ...]
    consumers: tuple[Consumer, ...]
    deprecations: tuple[Deprecation, ...]
    source: str
    raw: dict[str, Any] = field(compare=False, hash=False, repr=False)

    def field_named(self, name: str) -> Field | None:
        return next((f for f in self.fields if f.name == name), None)

    @property
    def field_names(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields)


@dataclass(frozen=True)
class Policy:
    teams: tuple[str, ...]
    max_pii_retention_days: int
    min_description_chars: int


@dataclass(frozen=True)
class Registry:
    name: str
    policy: Policy
    contracts: dict[str, Contract]
    root: Path


def canonical_hash(raw: dict[str, Any]) -> str:
    """Hash of the parsed contract, so whitespace and comment edits do not count as changes."""
    blob = json.dumps(raw, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class _Problems:
    def __init__(self) -> None:
        self.items: list[str] = []

    def add(self, where: str, message: str) -> None:
        self.items.append(f"{where}: {message}")


def _get(
    d: dict[str, Any],
    key: str,
    kind: type,
    where: str,
    p: _Problems,
    default: Any = None,
    required: bool = False,
) -> Any:
    if key not in d:
        if required:
            p.add(where, f"missing `{key}`")
        return default
    v = d[key]
    ok = isinstance(v, kind) and not (kind is int and isinstance(v, bool))
    if kind is float and isinstance(v, int) and not isinstance(v, bool):
        return float(v)
    if not ok:
        p.add(where, f"`{key}` must be {kind.__name__}, got {type(v).__name__}")
        return default
    return v


def _strings(d: dict[str, Any], key: str, where: str, p: _Problems) -> tuple[str, ...]:
    v = d.get(key, [])
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        p.add(where, f"`{key}` must be a list of strings")
        return ()
    return tuple(v)


def _tables(d: dict[str, Any], key: str, where: str, p: _Problems) -> list[dict[str, Any]]:
    v = d.get(key, [])
    if not isinstance(v, list) or not all(isinstance(x, dict) for x in v):
        p.add(where, f"`{key}` must be an array of tables")
        return []
    return v


def _choice(value: str, allowed: tuple[str, ...], what: str, where: str, p: _Problems) -> None:
    if value not in allowed:
        p.add(where, f"{what} `{value}` is not one of {', '.join(allowed)}")


def _parse_field(d: dict[str, Any], where: str, p: _Problems) -> Field:
    name = _get(d, "name", str, where, p, "", required=True)
    here = f"{where}.{name or '?'}"
    ftype = _get(d, "type", str, here, p, "string", required=True)
    _choice(ftype, TYPES, "type", here, p)
    derived = d.get("derived_from")
    if derived is not None and not isinstance(derived, str):
        p.add(here, "`derived_from` must be a string")
        derived = None
    return Field(
        name=name,
        type=ftype,
        nullable=_get(d, "nullable", bool, here, p, True),
        description=_get(d, "description", str, here, p, ""),
        pii=_get(d, "pii", bool, here, p, False),
        primary_key=_get(d, "primary_key", bool, here, p, False),
        masked=_get(d, "masked", bool, here, p, False),
        derived_from=derived,
        enum=_strings(d, "enum", here, p),
    )


def _parse_quality(d: dict[str, Any], where: str, p: _Problems) -> Quality:
    qid = _get(d, "id", str, where, p, "", required=True)
    here = f"{where}.{qid or '?'}"
    check = _get(d, "check", str, here, p, "not_null", required=True)
    _choice(check, CHECKS, "check", here, p)
    lo = d.get("min")
    hi = d.get("max")
    for label, v in (("min", lo), ("max", hi)):
        if v is not None and (not isinstance(v, int | float) or isinstance(v, bool)):
            p.add(here, f"`{label}` must be a number")
    pat = d.get("pattern")
    if pat is not None and not isinstance(pat, str):
        p.add(here, "`pattern` must be a string")
        pat = None
    return Quality(
        id=qid,
        field=_get(d, "field", str, here, p, "", required=True),
        check=check,
        min=float(lo) if isinstance(lo, int | float) and not isinstance(lo, bool) else None,
        max=float(hi) if isinstance(hi, int | float) and not isinstance(hi, bool) else None,
        pattern=pat,
    )


def _parse_consumer(d: dict[str, Any], where: str, p: _Problems) -> Consumer:
    cid = _get(d, "id", str, where, p, "", required=True)
    here = f"{where}.{cid or '?'}"
    crit = _get(d, "criticality", str, here, p, "low")
    _choice(crit, CRITICALITIES, "criticality", here, p)
    return Consumer(
        id=cid,
        team=_get(d, "team", str, here, p, "", required=True),
        fields=_strings(d, "fields", here, p),
        criticality=crit,
    )


def _parse_deprecation(d: dict[str, Any], where: str, p: _Problems) -> Deprecation | None:
    name = _get(d, "field", str, where, p, "", required=True)
    sunset = d.get("sunset")
    if isinstance(sunset, date):
        when = sunset
    elif isinstance(sunset, str):
        try:
            when = date.fromisoformat(sunset)
        except ValueError:
            p.add(f"{where}.{name}", f"`sunset` is not an ISO date: {sunset}")
            return None
    else:
        p.add(f"{where}.{name}", "missing `sunset` date")
        return None
    rep = d.get("replacement")
    return Deprecation(field=name, sunset=when, replacement=rep if isinstance(rep, str) else None)


def parse_contract(raw: dict[str, Any], source: str, p: _Problems | None = None) -> Contract | None:
    problems = p or _Problems()
    start = len(problems.items)
    head = raw.get("contract")
    if not isinstance(head, dict):
        problems.add(source, "missing [contract] table")
        return None
    where = source
    status = _get(head, "status", str, where, problems, "draft", required=True)
    _choice(status, STATUSES, "status", where, problems)
    cls = _get(head, "classification", str, where, problems, "internal")
    _choice(cls, CLASSIFICATIONS, "classification", where, problems)
    tier = _get(head, "tier", int, where, problems, 3, required=True)
    if tier not in (1, 2, 3):
        problems.add(where, f"`tier` must be 1, 2 or 3, got {tier}")
    retention = head.get("retention_days")
    if retention is not None and (not isinstance(retention, int) or isinstance(retention, bool)):
        problems.add(where, "`retention_days` must be an integer")
        retention = None
    sla_raw = raw.get("sla", {})
    if not isinstance(sla_raw, dict):
        problems.add(where, "[sla] must be a table")
        sla_raw = {}
    fresh = sla_raw.get("freshness_minutes")
    comp = sla_raw.get("completeness_pct")
    if fresh is not None and (not isinstance(fresh, int) or isinstance(fresh, bool)):
        problems.add(where, "sla.freshness_minutes must be an integer")
        fresh = None
    if comp is not None and (not isinstance(comp, int | float) or isinstance(comp, bool)):
        problems.add(where, "sla.completeness_pct must be a number")
        comp = None
    fields = tuple(
        _parse_field(d, f"{where}.field", problems) for d in _tables(raw, "field", where, problems)
    )
    quality = tuple(
        _parse_quality(d, f"{where}.quality", problems)
        for d in _tables(raw, "quality", where, problems)
    )
    consumers = tuple(
        _parse_consumer(d, f"{where}.consumer", problems)
        for d in _tables(raw, "consumer", where, problems)
    )
    deprecations = tuple(
        x
        for x in (
            _parse_deprecation(d, f"{where}.deprecation", problems)
            for d in _tables(raw, "deprecation", where, problems)
        )
        if x is not None
    )
    cid = _get(head, "id", str, where, problems, "", required=True)
    version = _get(head, "version", str, where, problems, "0.0.0", required=True)
    owner = _get(head, "owner", str, where, problems, "", required=True)
    domain = _get(head, "domain", str, where, problems, "", required=True)
    description = _get(head, "description", str, where, problems, "", required=True)
    upstream = _strings(head, "upstream", where, problems)
    if len(problems.items) > start:
        return None
    return Contract(
        id=cid,
        version=version,
        owner=owner,
        domain=domain,
        tier=tier,
        status=status,
        classification=cls,
        description=description,
        upstream=upstream,
        retention_days=retention,
        sla=Sla(
            freshness_minutes=fresh, completeness_pct=float(comp) if comp is not None else None
        ),
        fields=fields,
        quality=quality,
        consumers=consumers,
        deprecations=deprecations,
        source=source,
        raw=raw,
    )


def load_registry(root: Path) -> tuple[Registry | None, list[str]]:
    """Load ``registry.toml`` and every ``contracts/*.toml``. Returns ``(registry, problems)``."""
    p = _Problems()
    reg_file = root / "registry.toml"
    if not reg_file.is_file():
        return None, [f"{reg_file}: not found"]
    try:
        with reg_file.open("rb") as fh:
            head = tomllib.load(fh).get("registry", {})
    except tomllib.TOMLDecodeError as exc:
        return None, [f"registry.toml: invalid TOML: {exc}"]
    policy = Policy(
        teams=_strings(head, "teams", "registry.toml", p),
        max_pii_retention_days=_get(head, "max_pii_retention_days", int, "registry.toml", p, 3650),
        min_description_chars=_get(head, "min_description_chars", int, "registry.toml", p, 10),
    )
    contracts: dict[str, Contract] = {}
    cdir = root / "contracts"
    for path in sorted(cdir.glob("*.toml")) if cdir.is_dir() else []:
        rel = f"contracts/{path.name}"
        try:
            with path.open("rb") as fh:
                raw = tomllib.load(fh)
        except tomllib.TOMLDecodeError as exc:
            p.add(rel, f"invalid TOML: {exc}")
            continue
        c = parse_contract(raw, rel, p)
        if c is None:
            continue
        if c.id in contracts:
            p.add(rel, f"duplicate contract id `{c.id}` (also in {contracts[c.id].source})")
            continue
        contracts[c.id] = c
    if not contracts and not p.items:
        p.add("contracts/", "no contracts found")
    if p.items:
        return None, p.items
    return Registry(
        name=str(head.get("name", root.name)), policy=policy, contracts=contracts, root=root
    ), []
