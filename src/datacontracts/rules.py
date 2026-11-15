"""Policy rules over the registry. Each rule has an ID, a severity, a reason and a failing-case test.

The rules check that the registry is honest about what it promises: contracts have owners and
descriptions, personal data is classified and has a retention limit, consumers read fields that
exist, lineage has no cycles, personal data does not lose its label as it flows downstream, and a
released version never changes under its consumers.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date

from datacontracts import compat, lineage
from datacontracts.model import CLASSIFICATIONS, Contract, Registry, canonical_hash
from datacontracts.release import Released, read_index, released

SEVERITIES = ("low", "medium", "high", "critical")
ID_FORMAT = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
NAME_FORMAT = re.compile(r"^[a-z][a-z0-9_]*$")


def severity_rank(s: str) -> int:
    return SEVERITIES.index(s)


@dataclass(frozen=True)
class Context:
    reg: Registry
    today: date
    releases: dict[str, tuple[list[Released], list[str]]]


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    subject: str
    message: str


@dataclass(frozen=True)
class Rule:
    id: str
    severity: str
    title: str
    why: str
    check: Callable[[Context], Iterator[tuple[str, str]]]


REGISTRY: list[Rule] = []


def rule(
    rule_id: str, severity: str, title: str, why: str
) -> Callable[[Callable[[Context], Iterator[tuple[str, str]]]], Callable[..., object]]:
    def wrap(fn: Callable[[Context], Iterator[tuple[str, str]]]) -> Callable[..., object]:
        REGISTRY.append(Rule(rule_id, severity, title, why, fn))
        return fn

    return wrap


def _pii(c: Contract) -> list[str]:
    return [f.name for f in c.fields if f.pii]


@rule(
    "DC001",
    "high",
    "Contract id is domain.name and matches its file",
    "Ids are how consumers and lineage refer to a contract; a wrong id breaks both silently.",
)
def dc001(ctx: Context) -> Iterator[tuple[str, str]]:
    for c in ctx.reg.contracts.values():
        if not ID_FORMAT.match(c.id):
            yield c.id, "id must look like `domain.name` in lowercase snake case"
        elif c.id.split(".")[0] != c.domain:
            yield c.id, f"id domain `{c.id.split('.')[0]}` does not match domain `{c.domain}`"
        if c.source != f"contracts/{c.id}.toml":
            yield c.id, f"file is {c.source}, expected contracts/{c.id}.toml"


@rule(
    "DC002",
    "high",
    "Version is MAJOR.MINOR.PATCH",
    "Compatibility checks compare versions; a free-form version cannot be compared.",
)
def dc002(ctx: Context) -> Iterator[tuple[str, str]]:
    for c in ctx.reg.contracts.values():
        if compat.parse_semver(c.version) is None:
            yield c.id, f"version `{c.version}` is not MAJOR.MINOR.PATCH"


@rule(
    "DC003",
    "high",
    "Owner is a registered team",
    "A contract nobody owns is a contract nobody fixes.",
)
def dc003(ctx: Context) -> Iterator[tuple[str, str]]:
    teams = set(ctx.reg.policy.teams)
    for c in ctx.reg.contracts.values():
        if c.owner not in teams:
            yield c.id, f"owner `{c.owner}` is not listed in registry.toml teams"


@rule(
    "DC004",
    "medium",
    "Contract and fields are described",
    "A field without a description is an argument waiting to happen between producer and consumer.",
)
def dc004(ctx: Context) -> Iterator[tuple[str, str]]:
    n = ctx.reg.policy.min_description_chars
    for c in ctx.reg.contracts.values():
        if len(c.description.strip()) < n:
            yield c.id, f"contract description is shorter than {n} characters"
        for f in c.fields:
            if len(f.description.strip()) < n:
                yield f"{c.id}.{f.name}", f"field description is shorter than {n} characters"


@rule(
    "DC005",
    "high",
    "Personal data implies confidential or restricted",
    "Classification drives access control; personal data in an internal table is a leak waiting to be found.",
)
def dc005(ctx: Context) -> Iterator[tuple[str, str]]:
    floor = CLASSIFICATIONS.index("confidential")
    for c in ctx.reg.contracts.values():
        if _pii(c) and CLASSIFICATIONS.index(c.classification) < floor:
            yield (
                c.id,
                f"has pii fields ({', '.join(_pii(c))}) but classification is {c.classification}",
            )


@rule(
    "DC006",
    "high",
    "Personal data has a retention limit",
    "Keeping personal data without a limit is a breach of storage limitation waiting for an audit.",
)
def dc006(ctx: Context) -> Iterator[tuple[str, str]]:
    cap = ctx.reg.policy.max_pii_retention_days
    for c in ctx.reg.contracts.values():
        if not _pii(c):
            continue
        if c.retention_days is None:
            yield c.id, "has pii fields but no retention_days"
        elif c.retention_days > cap:
            yield c.id, f"retention_days {c.retention_days} is above the registry limit of {cap}"


@rule(
    "DC007",
    "high",
    "Critical contracts promise freshness and completeness",
    "A tier 1 dataset with no SLA cannot be monitored, so nobody finds out when it breaks.",
)
def dc007(ctx: Context) -> Iterator[tuple[str, str]]:
    for c in ctx.reg.contracts.values():
        if c.status in ("draft", "retired"):
            continue
        if c.tier == 1 and (c.sla.freshness_minutes is None or c.sla.completeness_pct is None):
            yield c.id, "tier 1 needs both sla.freshness_minutes and sla.completeness_pct"
        elif c.tier == 2 and c.sla.freshness_minutes is None:
            yield c.id, "tier 2 needs sla.freshness_minutes"


@rule(
    "DC008",
    "high",
    "Fields are well formed and live contracts have a key",
    "Duplicate names and missing keys make joins and idempotent loads guesswork.",
)
def dc008(ctx: Context) -> Iterator[tuple[str, str]]:
    for c in ctx.reg.contracts.values():
        if not c.fields:
            yield c.id, "has no fields"
            continue
        seen: set[str] = set()
        for f in c.fields:
            if not NAME_FORMAT.match(f.name):
                yield f"{c.id}.{f.name}", "field names are lowercase snake case"
            if f.name in seen:
                yield f"{c.id}.{f.name}", "duplicate field name"
            seen.add(f.name)
            if f.enum and f.type != "string":
                yield f"{c.id}.{f.name}", "enum is only supported on string fields"
            if len(set(f.enum)) != len(f.enum):
                yield f"{c.id}.{f.name}", "enum has repeated values"
        if c.status in ("active", "deprecated"):
            keys = [f for f in c.fields if f.primary_key]
            if not keys:
                yield c.id, "live contract has no primary_key field"
            for k in keys:
                if k.nullable:
                    yield f"{c.id}.{k.name}", "primary key must not be nullable"


@rule(
    "DC009",
    "high",
    "Consumers are registered teams reading fields that exist",
    "A consumer that names a missing field is already broken or about to be.",
)
def dc009(ctx: Context) -> Iterator[tuple[str, str]]:
    teams = set(ctx.reg.policy.teams)
    for c in ctx.reg.contracts.values():
        names = set(c.field_names)
        ids: set[str] = set()
        for cons in c.consumers:
            if cons.id in ids:
                yield f"{c.id}:{cons.id}", "consumer id is registered twice"
            ids.add(cons.id)
            if cons.team not in teams:
                yield (
                    f"{c.id}:{cons.id}",
                    f"team `{cons.team}` is not listed in registry.toml teams",
                )
            for fname in cons.fields:
                if fname not in names:
                    yield f"{c.id}:{cons.id}", f"reads field `{fname}` which does not exist"
            if not cons.fields:
                yield f"{c.id}:{cons.id}", "lists no fields, so impact analysis cannot see it"


@rule(
    "DC010",
    "medium",
    "Deprecations are real and not overdue",
    "A deprecation that names no replacement, or sits past its sunset date, teaches consumers to ignore deprecations.",
)
def dc010(ctx: Context) -> Iterator[tuple[str, str]]:
    for c in ctx.reg.contracts.values():
        for d in c.deprecations:
            where = f"{c.id}.{d.field}"
            if c.field_named(d.field) is None:
                yield where, "deprecation names a field that does not exist"
                continue
            if d.replacement is not None and c.field_named(d.replacement) is None:
                yield where, f"replacement `{d.replacement}` does not exist"
            if d.sunset < ctx.today:
                yield where, f"sunset {d.sunset} has passed but the field is still in the contract"


@rule(
    "DC011",
    "high",
    "Upstream contracts exist and lineage has no cycles",
    "A cycle means nothing can be the source of truth; a missing upstream means lineage is a guess.",
)
def dc011(ctx: Context) -> Iterator[tuple[str, str]]:
    for c in ctx.reg.contracts.values():
        for up in c.upstream:
            if up == c.id:
                yield c.id, "lists itself as upstream"
            elif up not in ctx.reg.contracts:
                yield c.id, f"upstream `{up}` is not in the registry"
    for cycle in lineage.find_cycles(ctx.reg):
        yield cycle[0], "lineage cycle: " + " -> ".join(cycle)


@rule(
    "DC012",
    "high",
    "Personal data keeps its label downstream",
    "A column derived from an email address is still personal data; losing the label is how masking gets skipped.",
)
def dc012(ctx: Context) -> Iterator[tuple[str, str]]:
    for c in ctx.reg.contracts.values():
        for f in c.fields:
            if f.derived_from is None:
                continue
            ref = lineage.split_ref(f.derived_from)
            src = ctx.reg.contracts.get(ref[0]) if ref else None
            if src is None or ref is None or src.field_named(ref[1]) is None:
                yield f"{c.id}.{f.name}", f"derived_from `{f.derived_from}` does not resolve"
            elif ref[0] not in c.upstream:
                yield (
                    f"{c.id}.{f.name}",
                    f"derived from `{ref[0]}`, which is not listed as upstream",
                )
    for c, name, ref_text in lineage.pii_leaks(ctx.reg):
        yield (
            f"{c.id}.{name}",
            f"derived from personal data `{ref_text}` but is neither pii nor masked",
        )


@rule(
    "DC013",
    "high",
    "Quality rules are valid and target real fields",
    "A check that cannot run, or runs on nothing, gives false comfort.",
)
def dc013(ctx: Context) -> Iterator[tuple[str, str]]:
    for c in ctx.reg.contracts.values():
        seen: set[str] = set()
        for q in c.quality:
            where = f"{c.id}:{q.id}"
            if q.id in seen:
                yield where, "quality rule id is used twice"
            seen.add(q.id)
            if c.field_named(q.field) is None:
                yield where, f"targets field `{q.field}` which does not exist"
            if q.check == "range":
                if q.min is None and q.max is None:
                    yield where, "range needs min or max"
                elif q.min is not None and q.max is not None and q.min > q.max:
                    yield where, "range min is above max"
            if q.check == "regex":
                if q.pattern is None:
                    yield where, "regex needs a pattern"
                else:
                    try:
                        re.compile(q.pattern)
                    except re.error as exc:
                        yield where, f"pattern does not compile: {exc}"


@rule(
    "DC014",
    "high",
    "Lifecycle status agrees with lineage and consumers",
    "Live data built on a retired source, or a retired contract that is still read, is an outage with a date on it.",
)
def dc014(ctx: Context) -> Iterator[tuple[str, str]]:
    for c in ctx.reg.contracts.values():
        if c.status == "retired" and c.consumers:
            yield c.id, f"is retired but still has {len(c.consumers)} registered consumer(s)"
        for up in c.upstream:
            u = ctx.reg.contracts.get(up)
            if u is None or c.status in ("draft", "retired"):
                continue
            if u.status == "retired":
                yield c.id, f"reads retired upstream `{up}`"
            elif u.status == "deprecated" and c.status == "active":
                yield c.id, f"is active but reads deprecated upstream `{up}`"


@rule(
    "DC015",
    "critical",
    "Released versions are immutable and intact",
    "Consumers pin to a released version; if its content can change, the version number means nothing.",
)
def dc015(ctx: Context) -> Iterator[tuple[str, str]]:
    for cid, (rels, problems) in ctx.releases.items():
        for p in problems:
            yield cid, p
        for r in rels:
            head = ctx.reg.contracts.get(cid)
            if (
                head is not None
                and head.version == r.version
                and canonical_hash(head.raw) != r.hash
            ):
                yield (
                    cid,
                    f"version {r.version} is released but contracts/{cid}.toml now differs; "
                    "bump the version",
                )


@rule(
    "DC016",
    "high",
    "Version bump matches the changes",
    "Semantic versions are the signal consumers use to decide whether to look; a wrong bump hides a breaking change.",
)
def dc016(ctx: Context) -> Iterator[tuple[str, str]]:
    for cid, (rels, _) in ctx.releases.items():
        head = ctx.reg.contracts.get(cid)
        if head is None or not rels:
            continue
        prior = [r for r in rels if r.version != head.version]
        if not prior or len(prior) != len(rels):
            continue  # nothing to compare with, or this version is already released (see DC015)
        base = prior[-1].contract
        for problem in compat.version_problems(base, head, compat.diff(base, head)):
            yield cid, problem


@rule(
    "DC017",
    "low",
    "Contracts under review are labelled draft",
    "A contract that has never been released should say so; 'active' implies consumers can rely on it.",
)
def dc017(ctx: Context) -> Iterator[tuple[str, str]]:
    for c in ctx.reg.contracts.values():
        if c.status == "active" and not ctx.releases.get(c.id, ([], []))[0]:
            yield c.id, "is active but has no released version; run `dcr release`"


def run(reg: Registry, today: date) -> list[Finding]:
    releases = {cid: released(reg.root, cid) for cid in reg.contracts}
    for cid in sorted(set(read_index(reg.root)) - set(reg.contracts)):
        releases[cid] = released(reg.root, cid)
    ctx = Context(reg, today, releases)
    findings = [
        Finding(r.id, r.severity, subject, message)
        for r in REGISTRY
        for subject, message in r.check(ctx)
    ]
    findings.sort(key=lambda f: (-severity_rank(f.severity), f.rule, f.subject, f.message))
    return findings


def catalog() -> list[tuple[str, str, str, str]]:
    return sorted((r.id, r.severity, r.title, r.why) for r in REGISTRY)
