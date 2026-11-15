from __future__ import annotations

import pytest

from datacontracts import compat
from datacontracts.compat import (
    CHANGE_KINDS,
    Change,
    bump_kind,
    parse_semver,
    required_bump,
    version_problems,
)
from datacontracts.compat import diff as _diff
from datacontracts.model import Contract

from .conftest import BASE, parse

SEEN: set[tuple[str, str]] = set()


def diff(base: Contract, head: Contract) -> list[Change]:
    """``diff`` that remembers every (kind, level) it produced."""
    out = _diff(base, head)
    SEEN.update((c.kind, c.level) for c in out)
    return out


STATUS_BLOCK = '[[field]]\nname = "status"\ntype = "string"\nnullable = false\nenum = ["placed", "paid"]\ndescription = "Where the order is in its life."\n\n'
DEPRECATION = '\n[[deprecation]]\nfield = "status"\nsunset = "2027-01-31"\n'


def kinds(base: str, head: str) -> set[tuple[str, str]]:
    return {(c.kind, c.level) for c in diff(parse(base), parse(head))}


def edit(old: str, new: str, base: str = BASE) -> tuple[str, str]:
    assert old in base, old
    return base, base.replace(old, new, 1)


# (old text, new text) applied to BASE, and the single change expected
SINGLE = [
    (STATUS_BLOCK, "", ("field-removed", "breaking")),
    ('type = "decimal"', 'type = "string"', ("type-changed", "breaking")),
    ('type = "decimal"', 'type = "double"', ("type-changed", "breaking")),
    (
        'nullable = false\ndescription = "Order total',
        'nullable = true\ndescription = "Order total',
        ("nullable-added", "breaking"),
    ),
    (
        'description = "Order total in the order currency."',
        'pii = true\ndescription = "Order total in the order currency."',
        ("pii-changed", "breaking"),
    ),
    (
        'name = "amount"\ntype = "decimal"\nnullable = false',
        'name = "amount"\ntype = "decimal"\nnullable = false\nprimary_key = true',
        ("primary-key-changed", "breaking"),
    ),
    (
        'enum = ["placed", "paid"]',
        'enum = ["placed", "paid", "shipped"]',
        ("enum-extended", "minor"),
    ),
    ('enum = ["placed", "paid"]', 'enum = ["placed"]', ("enum-narrowed", "minor")),
    ('enum = ["placed", "paid"]\n', "", ("enum-dropped", "breaking")),
    (
        'description = "Order identifier."',
        'description = "Order identifier, as the storefront prints it."',
        ("field-documented", "patch"),
    ),
    (
        'classification = "internal"',
        'classification = "confidential"',
        ("classification-raised", "breaking"),
    ),
    ("tier = 2", "tier = 3", ("tier-changed", "breaking")),
    ("tier = 2", "tier = 1", ("tier-changed", "minor")),
    ('status = "active"', 'status = "deprecated"', ("status-advanced", "minor")),
    ('owner = "sales-data"', 'owner = "finance-data"', ("owner-changed", "patch")),
    (
        'description = "Orders after cleaning, one row per order."',
        'description = "Orders after cleaning and de-duplication."',
        ("contract-documented", "patch"),
    ),
    ("retention_days = 100", "retention_days = 50", ("retention-changed", "breaking")),
    ("retention_days = 100", "retention_days = 200", ("retention-changed", "minor")),
    ("retention_days = 100\n", "", ("retention-changed", "breaking")),
    ("freshness_minutes = 60", "freshness_minutes = 120", ("sla-freshness-weakened", "breaking")),
    ("freshness_minutes = 60", "freshness_minutes = 30", ("sla-freshness-improved", "minor")),
    (
        "completeness_pct = 99.0",
        "completeness_pct = 95.0",
        ("sla-completeness-weakened", "breaking"),
    ),
    ("completeness_pct = 99.0", "completeness_pct = 99.9", ("sla-completeness-improved", "minor")),
    ("min = 0\nmax = 100", "min = -5\nmax = 100", ("quality-loosened", "breaking")),
    ("min = 0\nmax = 100", "min = 0\nmax = 500", ("quality-loosened", "breaking")),
    ("min = 0\nmax = 100", "min = 0", ("quality-loosened", "breaking")),
    ("min = 0\nmax = 100", "max = 100", ("quality-loosened", "breaking")),
    ("min = 0\nmax = 100", "min = 10\nmax = 90", ("quality-tightened", "minor")),
    ('check = "range"\nmin = 0\nmax = 100', 'check = "not_null"', ("quality-changed", "breaking")),
    ('fields = ["order_id", "amount"]', 'fields = ["order_id"]', None),
]


@pytest.mark.parametrize(("old", "new", "expected"), SINGLE)
def test_single_changes_are_classified(
    old: str, new: str, expected: tuple[str, str] | None
) -> None:
    base, head = edit(old, new)
    got = kinds(base, head)
    if expected is None:
        assert got == set()
    else:
        assert expected in got, got


def test_added_field_is_minor() -> None:
    head = BASE.replace(
        "[[quality]]",
        '[[field]]\nname = "channel"\ntype = "string"\nnullable = true\ndescription = "Sales channel."\n\n[[quality]]',
        1,
    )
    assert kinds(BASE, head) == {("field-added", "minor")}


def test_type_widening_is_minor_but_only_in_one_direction() -> None:
    narrow = BASE.replace('type = "decimal"', 'type = "int"')
    wide = BASE.replace('type = "decimal"', 'type = "long"')
    assert ("type-widened", "minor") in kinds(narrow, wide)
    assert ("type-changed", "breaking") in kinds(wide, narrow)
    assert {
        ("int", "long"),
        ("int", "double"),
        ("int", "decimal"),
        ("long", "decimal"),
    } == compat.WIDENING


def test_nullable_removed_is_minor() -> None:
    nullable = BASE.replace(
        'nullable = false\ndescription = "Order total',
        'nullable = true\ndescription = "Order total',
    )
    assert ("nullable-removed", "minor") in kinds(nullable, BASE)


def test_masking_and_enum_the_other_way() -> None:
    masked = BASE.replace(
        'description = "Order total', 'masked = true\ndescription = "Order total', 1
    )
    assert ("masking-changed", "minor") in kinds(BASE, masked)
    assert ("masking-changed", "breaking") in kinds(masked, BASE)
    closed = BASE.replace('enum = ["placed", "paid"]\n', "")
    assert ("enum-added", "minor") in kinds(closed, BASE)


def test_classification_lowered_and_status_regressed_and_upstream() -> None:
    conf = BASE.replace("internal", "confidential")
    assert ("classification-lowered", "minor") in kinds(conf, BASE)
    dep = BASE.replace('status = "active"', 'status = "deprecated"')
    assert ("status-regressed", "breaking") in kinds(dep, BASE)
    up = BASE.replace(
        "retention_days = 100", 'upstream = ["sales.raw_orders"]\nretention_days = 100'
    )
    assert ("upstream-changed", "minor") in kinds(BASE, up)


def test_sla_set_or_removed() -> None:
    no_sla = BASE.replace("[sla]\nfreshness_minutes = 60\ncompleteness_pct = 99.0\n", "")
    assert ("sla-freshness-weakened", "breaking") in kinds(BASE, no_sla)
    assert ("sla-completeness-weakened", "breaking") in kinds(BASE, no_sla)
    assert ("sla-freshness-improved", "minor") in kinds(no_sla, BASE)


def test_quality_removed_added_and_regex() -> None:
    no_q = BASE.replace(
        '[[quality]]\nid = "amount_range"\nfield = "amount"\ncheck = "range"\nmin = 0\nmax = 100\n\n',
        "",
    )
    assert ("quality-removed", "breaking") in kinds(BASE, no_q)
    assert ("quality-added", "minor") in kinds(no_q, BASE)
    rx = BASE.replace('check = "range"\nmin = 0\nmax = 100', 'check = "regex"\npattern = "a+"')
    rx2 = rx.replace("a+", "b+")
    assert ("quality-changed", "breaking") in kinds(rx, rx2)


def test_deprecation_lifecycle_and_removal_is_planned_only_after_deprecation() -> None:
    base = BASE + DEPRECATION
    assert ("field-deprecated", "minor") in kinds(BASE, base)
    assert ("deprecation-withdrawn", "patch") in kinds(base, BASE)
    planned = [
        c
        for c in diff(parse(base), parse(base.replace(STATUS_BLOCK, "").replace(DEPRECATION, "")))
        if c.kind == "field-removed"
    ]
    assert planned and planned[0].planned
    unplanned = [
        c
        for c in diff(parse(BASE), parse(BASE.replace(STATUS_BLOCK, "")))
        if c.kind == "field-removed"
    ]
    assert unplanned and not unplanned[0].planned


def test_consumer_registrations_are_a_patch() -> None:
    more = (
        BASE
        + '\n[[consumer]]\nid = "ml.job"\nteam = "ml-platform"\ncriticality = "low"\nfields = ["order_id"]\n'
    )
    assert kinds(BASE, more) == {("consumers-changed", "patch")}


def test_identical_contracts_have_no_changes() -> None:
    assert diff(parse(BASE), parse(BASE)) == []


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("1.2.3", (1, 2, 3)),
        ("0.0.0", (0, 0, 0)),
        ("1.2", None),
        ("v1.2.3", None),
        ("01.2.3", None),
        ("1.2.3-rc1", None),
    ],
)
def test_parse_semver(version: str, expected: tuple[int, int, int] | None) -> None:
    assert parse_semver(version) == expected


@pytest.mark.parametrize(
    ("base", "head", "expected"),
    [
        ("1.0.0", "2.0.0", "major"),
        ("1.0.0", "1.1.0", "minor"),
        ("1.0.0", "1.0.1", "patch"),
        ("1.0.0", "1.0.0", "none"),
        ("1.1.0", "1.0.0", "backwards"),
        ("1.0", "1.0.1", "invalid"),
        ("1.0.0", "x", "invalid"),
        ("1.2.3", "2.0.0", "major"),
        ("1.2.3", "1.3.0", "minor"),
    ],
)
def test_bump_kind(base: str, head: str, expected: str) -> None:
    assert bump_kind(base, head) == expected


def test_required_bump_takes_the_highest_level() -> None:
    mk = lambda level: Change("k", level, "", "d")  # noqa: E731
    assert required_bump([]) == "none"
    assert required_bump([mk("patch")]) == "patch"
    assert required_bump([mk("patch"), mk("minor")]) == "minor"
    assert required_bump([mk("minor"), mk("breaking"), mk("patch")]) == "major"


def _problems(old: str, new: str, version: str) -> list[str]:
    base = parse(BASE)
    head = parse(
        BASE.replace(old, new, 1).replace('version = "1.0.0"', f'version = "{version}"', 1)
    )
    return version_problems(base, head, diff(base, head))


def test_version_problems_catch_a_dishonest_bump() -> None:
    assert _problems('type = "decimal"', 'type = "string"', "1.1.0") == [
        "sales.orders: changes need a major bump but 1.0.0 to 1.1.0 is minor"
    ]
    assert _problems('type = "decimal"', 'type = "string"', "2.0.0") == []
    assert "still 1.0.0" in _problems("tier = 2", "tier = 1", "1.0.0")[0]
    assert _problems('owner = "sales-data"', 'owner = "finance-data"', "1.0.1") == []
    assert "goes backwards" in _problems("tier = 2", "tier = 1", "0.9.0")[0]


def test_removing_a_field_that_was_never_deprecated_is_always_a_problem() -> None:
    problems = _problems(STATUS_BLOCK, "", "2.0.0")
    assert problems == [
        "sales.orders: field `status` was removed without being deprecated in 1.0.0"
    ]


def test_invalid_version_is_reported() -> None:
    base = parse(BASE)
    head = parse(BASE.replace('version = "1.0.0"', 'version = "banana"'))
    assert "not MAJOR.MINOR.PATCH" in version_problems(base, head, diff(base, head))[0]


def test_zz_every_documented_kind_and_level_is_produced_and_nothing_else() -> None:
    documented = {(kind, level) for kind, (levels, _) in CHANGE_KINDS.items() for level in levels}
    assert documented == SEEN
    assert all(why.endswith(".") for _, why in CHANGE_KINDS.values())
