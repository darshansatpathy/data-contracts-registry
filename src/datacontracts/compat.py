"""Compatibility of one version of a contract against the previous one.

The rules are written from the point of view of a consumer that already reads the data:

* ``breaking``: a consumer that worked before can fail or silently get wrong answers.
* ``minor``: something new or stronger; existing consumers keep working.
* ``patch``: metadata only.

The required version bump is the highest level among the changes. Field order is not significant.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from datacontracts.model import CLASSIFICATIONS, STATUSES, Contract, Field, Quality

LEVELS = ("patch", "minor", "breaking")
_RANK = {"none": 0, "patch": 1, "minor": 2, "major": 3}
# Reading an int column as long, or as double, never loses a value that fits.
WIDENING = {("int", "long"), ("int", "double"), ("int", "decimal"), ("long", "decimal")}
_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")

# Every kind of change `diff` can report: the levels it can have, and why.
CHANGE_KINDS: dict[str, tuple[tuple[str, ...], str]] = {
    "field-removed": (
        ("breaking",),
        "Readers that select the field fail. Allowed only after a deprecation.",
    ),
    "field-added": (("minor",), "Existing readers ignore a column they do not select."),
    "type-widened": (
        ("minor",),
        "Every value that was valid is still representable (int to long, int to double, int or long to decimal).",
    ),
    "type-changed": (("breaking",), "Old values may not fit, or readers parse them differently."),
    "nullable-added": (("breaking",), "Readers that assume a value is present will meet nulls."),
    "nullable-removed": (("minor",), "A stronger guarantee: the value is always there now."),
    "pii-changed": (
        ("breaking",),
        "Access, masking and retention depend on the label, whichever way it moves.",
    ),
    "primary-key-changed": (("breaking",), "Joins and idempotent loads depend on the key."),
    "masking-changed": (
        ("breaking", "minor"),
        "Unmasking exposes personal data (breaking); masking is a stronger guarantee (minor).",
    ),
    "enum-extended": (
        ("minor",),
        "Readers must handle the new values, so the change is announced even though it adds only.",
    ),
    "enum-narrowed": (("minor",), "Fewer possible values cannot break a reader."),
    "enum-added": (("minor",), "A closed set of values is a new promise."),
    "enum-dropped": (("breaking",), "Readers may rely on the closed set."),
    "field-documented": (("patch",), "Description or derivation changed; the data did not."),
    "classification-raised": (("breaking",), "More restricted data can need new access decisions."),
    "classification-lowered": (("minor",), "Less restricted data needs no new decision."),
    "tier-changed": (
        ("breaking", "minor"),
        "A lower tier weakens operational promises (breaking); a higher one strengthens them (minor).",
    ),
    "status-advanced": (
        ("minor",),
        "Draft to active to deprecated to retired is the normal direction.",
    ),
    "status-regressed": (
        ("breaking",),
        "Consumers were told the contract was further along than it is.",
    ),
    "owner-changed": (("patch",), "Who to call changed; the data did not."),
    "contract-documented": (("patch",), "Contract description changed."),
    "retention-changed": (
        ("breaking", "minor"),
        "Shorter retention removes history readers may use (breaking); longer is a governance note (minor).",
    ),
    "upstream-changed": (("minor",), "Lineage changed; downstream owners should look."),
    "sla-freshness-weakened": (("breaking",), "Consumers plan around the promised freshness."),
    "sla-freshness-improved": (("minor",), "A stronger promise."),
    "sla-completeness-weakened": (
        ("breaking",),
        "Consumers plan around the promised completeness.",
    ),
    "sla-completeness-improved": (("minor",), "A stronger promise."),
    "quality-removed": (("breaking",), "A guarantee readers relied on is gone."),
    "quality-changed": (
        ("breaking",),
        "The rule now checks something else, or a pattern changed that cannot be compared.",
    ),
    "quality-loosened": (
        ("breaking",),
        "A range was widened, so values that used to be rejected now pass.",
    ),
    "quality-tightened": (("minor",), "A range was narrowed: a stronger guarantee."),
    "quality-added": (("minor",), "A new guarantee."),
    "field-deprecated": (("minor",), "Announces a removal so readers can move first."),
    "deprecation-withdrawn": (("patch",), "The field is no longer scheduled for removal."),
    "consumers-changed": (("patch",), "Consumers registered or left; the data did not change."),
}


@dataclass(frozen=True)
class Change:
    kind: str
    level: str
    subject: str  # a field name, or "" when the change applies to the whole contract
    detail: str
    planned: bool = False  # a removal that was announced by a deprecation in the base version


def parse_semver(version: str) -> tuple[int, int, int] | None:
    m = _SEMVER.match(version)
    return (int(m[1]), int(m[2]), int(m[3])) if m else None


def bump_kind(base: str, head: str) -> str:
    """``major``, ``minor``, ``patch``, ``none`` or ``invalid`` / ``backwards``."""
    b, h = parse_semver(base), parse_semver(head)
    if b is None or h is None:
        return "invalid"
    if h < b:
        return "backwards"
    if h == b:
        return "none"
    if h[0] != b[0]:
        return "major"
    return "minor" if h[1] != b[1] else "patch"


def required_bump(changes: list[Change]) -> str:
    if any(c.level == "breaking" for c in changes):
        return "major"
    if any(c.level == "minor" for c in changes):
        return "minor"
    return "patch" if changes else "none"


def _quality_changes(base: Contract, head: Contract) -> list[Change]:
    out: list[Change] = []
    bq: dict[str, Quality] = {q.id: q for q in base.quality}
    hq: dict[str, Quality] = {q.id: q for q in head.quality}
    for qid, q in bq.items():
        if qid not in hq:
            out.append(
                Change("quality-removed", "breaking", q.field, f"quality rule `{qid}` was removed")
            )
            continue
        n = hq[qid]
        if (q.check, q.field) != (n.check, n.field):
            out.append(
                Change(
                    "quality-changed",
                    "breaking",
                    q.field,
                    f"quality rule `{qid}` now checks something else",
                )
            )
        elif q.check == "regex" and q.pattern != n.pattern:
            out.append(
                Change("quality-changed", "breaking", q.field, f"pattern of `{qid}` changed")
            )
        elif q.check == "range":
            loosened = (n.min is None and q.min is not None) or (
                n.min is not None and q.min is not None and n.min < q.min
            )
            loosened = (
                loosened
                or (n.max is None and q.max is not None)
                or (n.max is not None and q.max is not None and n.max > q.max)
            )
            if loosened:
                out.append(
                    Change("quality-loosened", "breaking", q.field, f"range of `{qid}` was widened")
                )
            elif (q.min, q.max) != (n.min, n.max):
                out.append(
                    Change("quality-tightened", "minor", q.field, f"range of `{qid}` was narrowed")
                )
    for qid, n in hq.items():
        if qid not in bq:
            out.append(Change("quality-added", "minor", n.field, f"quality rule `{qid}` was added"))
    return out


def _field_changes(b: Field, h: Field) -> list[Change]:
    out: list[Change] = []
    n = b.name
    if b.type != h.type:
        if (b.type, h.type) in WIDENING:
            out.append(Change("type-widened", "minor", n, f"{b.type} to {h.type}"))
        else:
            out.append(Change("type-changed", "breaking", n, f"{b.type} to {h.type}"))
    if b.nullable != h.nullable:
        if h.nullable:
            out.append(Change("nullable-added", "breaking", n, "values may now be null"))
        else:
            out.append(Change("nullable-removed", "minor", n, "values are never null now"))
    if b.pii != h.pii:
        out.append(Change("pii-changed", "breaking", n, f"pii {b.pii} to {h.pii}"))
    if b.primary_key != h.primary_key:
        out.append(
            Change(
                "primary-key-changed",
                "breaking",
                n,
                f"primary_key {b.primary_key} to {h.primary_key}",
            )
        )
    if b.masked != h.masked:
        out.append(
            Change(
                "masking-changed",
                "breaking" if b.masked else "minor",
                n,
                f"masked {b.masked} to {h.masked}",
            )
        )
    if b.enum != h.enum:
        if b.enum and not h.enum:
            out.append(
                Change("enum-dropped", "breaking", n, "the closed set of values was removed")
            )
        elif not b.enum:
            out.append(Change("enum-added", "minor", n, "values are now a closed set"))
        elif set(h.enum) - set(b.enum):
            out.append(
                Change(
                    "enum-extended",
                    "minor",
                    n,
                    f"new values: {', '.join(sorted(set(h.enum) - set(b.enum)))}",
                )
            )
        else:
            out.append(
                Change(
                    "enum-narrowed",
                    "minor",
                    n,
                    f"values removed: {', '.join(sorted(set(b.enum) - set(h.enum)))}",
                )
            )
    if b.derived_from != h.derived_from or b.description != h.description:
        out.append(Change("field-documented", "patch", n, "description or derivation changed"))
    return out


def diff(base: Contract, head: Contract) -> list[Change]:
    """Every difference between two versions of the same contract, classified."""
    out: list[Change] = []
    bf = {f.name: f for f in base.fields}
    hf = {f.name: f for f in head.fields}
    announced = {d.field for d in base.deprecations}
    for name, f in bf.items():
        if name not in hf:
            out.append(
                Change(
                    "field-removed",
                    "breaking",
                    name,
                    "the field no longer exists",
                    planned=name in announced,
                )
            )
        else:
            out.extend(_field_changes(f, hf[name]))
    for name in hf:
        if name not in bf:
            out.append(Change("field-added", "minor", name, "new field"))

    if base.classification != head.classification:
        up = CLASSIFICATIONS.index(head.classification) > CLASSIFICATIONS.index(base.classification)
        out.append(
            Change(
                "classification-raised" if up else "classification-lowered",
                "breaking" if up else "minor",
                "",
                f"{base.classification} to {head.classification}",
            )
        )
    if base.tier != head.tier:
        out.append(
            Change(
                "tier-changed",
                "breaking" if head.tier > base.tier else "minor",
                "",
                f"tier {base.tier} to {head.tier}",
            )
        )
    if base.status != head.status:
        fwd = STATUSES.index(head.status) > STATUSES.index(base.status)
        out.append(
            Change(
                "status-advanced" if fwd else "status-regressed",
                "minor" if fwd else "breaking",
                "",
                f"{base.status} to {head.status}",
            )
        )
    if base.owner != head.owner:
        out.append(Change("owner-changed", "patch", "", f"{base.owner} to {head.owner}"))
    if base.description != head.description:
        out.append(Change("contract-documented", "patch", "", "description changed"))
    if base.retention_days != head.retention_days:
        shorter = base.retention_days is not None and (
            head.retention_days is None or head.retention_days < base.retention_days
        )
        out.append(
            Change(
                "retention-changed",
                "breaking" if shorter else "minor",
                "",
                f"{base.retention_days} to {head.retention_days} days",
            )
        )
    if base.upstream != head.upstream:
        out.append(Change("upstream-changed", "minor", "", "lineage changed"))

    bs, hs = base.sla, head.sla
    if bs.freshness_minutes != hs.freshness_minutes:
        worse = bs.freshness_minutes is not None and (
            hs.freshness_minutes is None or hs.freshness_minutes > bs.freshness_minutes
        )
        out.append(
            Change(
                "sla-freshness-weakened" if worse else "sla-freshness-improved",
                "breaking" if worse else "minor",
                "",
                f"{bs.freshness_minutes} to {hs.freshness_minutes} minutes",
            )
        )
    if bs.completeness_pct != hs.completeness_pct:
        worse = bs.completeness_pct is not None and (
            hs.completeness_pct is None or hs.completeness_pct < bs.completeness_pct
        )
        out.append(
            Change(
                "sla-completeness-weakened" if worse else "sla-completeness-improved",
                "breaking" if worse else "minor",
                "",
                f"{bs.completeness_pct} to {hs.completeness_pct} percent",
            )
        )

    out.extend(_quality_changes(base, head))

    bd = {d.field for d in base.deprecations}
    hd = {d.field for d in head.deprecations}
    for name in sorted(hd - bd):
        out.append(Change("field-deprecated", "minor", name, "announced for removal"))
    for name in sorted(bd - hd):
        if name in hf:
            out.append(
                Change("deprecation-withdrawn", "patch", name, "no longer scheduled for removal")
            )
    bc = {c.id for c in base.consumers}
    hc = {c.id for c in head.consumers}
    if bc != hc:
        out.append(Change("consumers-changed", "patch", "", "consumer registrations changed"))
    return out


def version_problems(base: Contract, head: Contract, changes: list[Change]) -> list[str]:
    """Problems with the version number given what changed. Empty means the bump is honest."""
    problems: list[str] = []
    actual = bump_kind(base.version, head.version)
    if actual == "invalid":
        return [f"{head.id}: version is not MAJOR.MINOR.PATCH ({base.version} to {head.version})"]
    if actual == "backwards":
        return [f"{head.id}: version goes backwards, {base.version} to {head.version}"]
    need = required_bump(changes)
    if need != "none" and actual == "none":
        problems.append(
            f"{head.id}: content changed but version is still {head.version}; needs a {need} bump"
        )
    elif _RANK[actual] < _RANK[need]:
        problems.append(
            f"{head.id}: changes need a {need} bump "
            f"but {base.version} to {head.version} is {actual}"
        )
    for c in changes:
        if c.kind == "field-removed" and not c.planned:
            problems.append(
                f"{head.id}: field `{c.subject}` was removed "
                f"without being deprecated in {base.version}"
            )
    return problems
