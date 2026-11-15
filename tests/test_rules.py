from __future__ import annotations

import json
import tomllib
from pathlib import Path

from datacontracts import rules
from datacontracts.model import canonical_hash
from datacontracts.release import read_index

from .conftest import ROOT, TODAY, add_release, edit, load


def run(root: Path) -> list[rules.Finding]:
    return rules.run(load(root), TODAY)


def has(root: Path, rule: str, needle: str) -> bool:
    return any(f.rule == rule and needle in f.message for f in run(root))


def test_the_real_registry_has_no_findings() -> None:
    assert rules.run(load(ROOT), TODAY) == []


def test_every_rule_has_a_failing_case_test() -> None:
    names = set(globals())
    for r in rules.REGISTRY:
        assert f"test_{r.id.lower()}" in names, f"no failing-case test for {r.id}"
    ids = [r.id for r in rules.REGISTRY]
    assert len(ids) == len(set(ids)) == 17
    assert all(r.severity in rules.SEVERITIES and r.why and r.title for r in rules.REGISTRY)


def test_findings_are_sorted_most_severe_first(sample: Path) -> None:
    edit(
        sample,
        "contracts/sales.customers.toml",
        'classification = "restricted"',
        'classification = "internal"',
    )
    edit(sample, "contracts/sales.orders.toml", 'owner = "sales-data"', 'owner = "ghost"')
    ranks = [rules.severity_rank(f.severity) for f in run(sample)]
    assert ranks == sorted(ranks, reverse=True)
    assert len(ranks) >= 2


def test_catalog_lists_every_rule() -> None:
    assert [r[0] for r in rules.catalog()] == sorted(r.id for r in rules.REGISTRY)


def test_dc001(sample: Path) -> None:
    edit(sample, "contracts/sales.orders.toml", 'domain = "sales"', 'domain = "finance"')
    assert has(sample, "DC001", "does not match domain")
    edit(sample, "contracts/sales.orders.toml", 'id = "sales.orders"', 'id = "Sales-Orders"')
    assert has(sample, "DC001", "lowercase snake case")
    (sample / "contracts/sales.orders.toml").rename(sample / "contracts/renamed.toml")
    assert has(sample, "DC001", "expected contracts/")


def test_dc002(sample: Path) -> None:
    edit(sample, "contracts/sales.orders.toml", 'version = "1.2.0"', 'version = "1.2"')
    assert has(sample, "DC002", "not MAJOR.MINOR.PATCH")


def test_dc003(sample: Path) -> None:
    edit(sample, "contracts/sales.orders.toml", 'owner = "sales-data"', 'owner = "ghost-team"')
    assert has(sample, "DC003", "ghost-team")


def test_dc004(sample: Path) -> None:
    edit(
        sample,
        "contracts/sales.orders.toml",
        'description = "Calendar date of ordered_at in UTC. Added in 1.2.0 for daily reporting."',
        'description = "x"',
    )
    assert has(sample, "DC004", "field description is shorter")
    edit(
        sample,
        "contracts/sales.orders.toml",
        'description = "One row per customer order after cleaning and de-duplication. The source of truth for revenue."',
        'description = "short"',
    )
    assert has(sample, "DC004", "contract description is shorter")


def test_dc005(sample: Path) -> None:
    edit(
        sample,
        "contracts/sales.customers.toml",
        'classification = "restricted"',
        'classification = "internal"',
    )
    assert has(sample, "DC005", "has pii fields (email, full_name)")


def test_dc006(sample: Path) -> None:
    edit(sample, "contracts/sales.customers.toml", "retention_days = 1825", "retention_days = 5000")
    assert has(sample, "DC006", "above the registry limit")
    edit(sample, "contracts/sales.customers.toml", "retention_days = 5000\n", "")
    assert has(sample, "DC006", "no retention_days")


def test_dc007(sample: Path) -> None:
    edit(
        sample,
        "contracts/sales.orders.toml",
        "[sla]\nfreshness_minutes = 60\ncompleteness_pct = 99.5\n",
        "",
    )
    assert has(sample, "DC007", "tier 1 needs both")
    edit(sample, "contracts/finance.revenue_daily.toml", "freshness_minutes = 240\n", "")
    assert has(sample, "DC007", "tier 2 needs")


def test_dc008(sample: Path) -> None:
    edit(
        sample,
        "contracts/sales.orders.toml",
        'name = "order_id"\ntype = "string"\nnullable = false\nprimary_key = true',
        'name = "order_id"\ntype = "string"\nnullable = true\nprimary_key = true',
    )
    assert has(sample, "DC008", "primary key must not be nullable")
    edit(sample, "contracts/sales.orders.toml", "primary_key = true", "primary_key = false")
    assert has(sample, "DC008", "no primary_key field")
    edit(sample, "contracts/sales.orders.toml", 'name = "customer_id"', 'name = "Customer-Id"')
    assert has(sample, "DC008", "lowercase snake case")
    edit(
        sample,
        "contracts/sales.orders.toml",
        'name = "amount"\ntype = "decimal"',
        'name = "amount"\ntype = "decimal"\nenum = ["a", "a"]',
    )
    assert has(sample, "DC008", "enum is only supported on string fields")
    assert has(sample, "DC008", "enum has repeated values")
    edit(sample, "contracts/sales.orders.toml", 'name = "status"', 'name = "order_id"')
    assert has(sample, "DC008", "duplicate field name")


def test_dc008_empty_contract(sample: Path) -> None:
    (sample / "contracts/support.tickets.toml").write_text(
        '[contract]\nid = "support.tickets"\nversion = "0.1.0"\nowner = "support-data"\ndomain = "support"\ntier = 3\n'
        'status = "draft"\nclassification = "internal"\ndescription = "Tickets, no fields yet."\n',
        encoding="utf-8",
    )
    assert has(sample, "DC008", "has no fields")


def test_dc009(sample: Path) -> None:
    edit(
        sample,
        "contracts/sales.orders.toml",
        'fields = ["customer_id", "amount", "ordered_at"]',
        'fields = ["customer_id", "ghost_field"]',
    )
    assert has(sample, "DC009", "reads field `ghost_field`")
    edit(sample, "contracts/sales.orders.toml", 'team = "ml-platform"', 'team = "ghost"')
    assert has(sample, "DC009", "team `ghost`")
    edit(
        sample,
        "contracts/sales.orders.toml",
        'id = "ml.churn-feature-job"',
        'id = "finance.revenue-pipeline"',
    )
    assert has(sample, "DC009", "registered twice")
    edit(
        sample,
        "contracts/sales.orders.toml",
        'fields = ["customer_id", "ghost_field"]',
        "fields = []",
    )
    assert has(sample, "DC009", "lists no fields")


def test_dc010(sample: Path) -> None:
    edit(
        sample, "contracts/sales.raw_orders.toml", 'sunset = "2027-03-31"', 'sunset = "2026-01-01"'
    )
    assert has(sample, "DC010", "has passed but the field is still")
    edit(
        sample,
        "contracts/sales.raw_orders.toml",
        'replacement = "channel"',
        'replacement = "ghost"',
    )
    assert has(sample, "DC010", "replacement `ghost` does not exist")
    edit(
        sample,
        "contracts/sales.raw_orders.toml",
        '[[deprecation]]\nfield = "legacy_code"',
        '[[deprecation]]\nfield = "nothing"',
    )
    assert has(sample, "DC010", "names a field that does not exist")


def test_dc011(sample: Path) -> None:
    edit(
        sample,
        "contracts/sales.orders.toml",
        'upstream = ["sales.raw_orders"]',
        'upstream = ["sales.raw_orders", "ghost.table"]',
    )
    assert has(sample, "DC011", "`ghost.table` is not in the registry")
    edit(sample, "contracts/sales.orders.toml", '"ghost.table"', '"sales.orders"')
    assert has(sample, "DC011", "lists itself as upstream")
    edit(
        sample,
        "contracts/sales.raw_orders.toml",
        "retention_days = 730",
        'upstream = ["finance.invoices"]\nretention_days = 730',
    )
    assert has(sample, "DC011", "lineage cycle")


def test_dc012(sample: Path) -> None:
    edit(
        sample,
        "contracts/marketing.customer_360.toml",
        "nullable = false\npii = true\nderived_from",
        "nullable = false\nderived_from",
    )
    assert has(sample, "DC012", "neither pii nor masked")
    edit(
        sample,
        "contracts/marketing.customer_360.toml",
        'derived_from = "sales.customers.segment"',
        'derived_from = "sales.customers.ghost"',
    )
    assert has(sample, "DC012", "does not resolve")
    edit(
        sample,
        "contracts/marketing.customer_360.toml",
        'upstream = ["sales.customers", "sales.orders"]',
        'upstream = ["sales.orders"]',
    )
    assert has(sample, "DC012", "not listed as upstream")


def test_dc013(sample: Path) -> None:
    edit(
        sample,
        "contracts/sales.orders.toml",
        'id = "customer_present"\nfield = "customer_id"',
        'id = "customer_present"\nfield = "ghost"',
    )
    assert has(sample, "DC013", "targets field `ghost`")
    edit(sample, "contracts/sales.orders.toml", "min = 0\nmax = 10000000", "min = 5\nmax = 1")
    assert has(sample, "DC013", "min is above max")
    edit(sample, "contracts/sales.orders.toml", 'id = "order_unique"', 'id = "amount_range"')
    assert has(sample, "DC013", "used twice")
    edit(
        sample,
        "contracts/sales.customers.toml",
        'pattern = "[^@\\\\s]+@[^@\\\\s]+\\\\.[^@\\\\s]+"',
        'pattern = "(["',
    )
    assert has(sample, "DC013", "does not compile")


def test_dc013_missing_params(sample: Path) -> None:
    edit(sample, "contracts/sales.orders.toml", "min = 0\nmax = 10000000\n", "")
    assert has(sample, "DC013", "range needs min or max")
    edit(
        sample,
        "contracts/sales.customers.toml",
        'pattern = "[^@\\\\s]+@[^@\\\\s]+\\\\.[^@\\\\s]+"\n',
        "",
    )
    assert has(sample, "DC013", "regex needs a pattern")


def test_dc014(sample: Path) -> None:
    (sample / "contracts/sales.legacy_orders.toml").write_text(
        (sample / "contracts/sales.legacy_orders.toml").read_text(encoding="utf-8")
        + '\n[[consumer]]\nid = "x.reader"\nteam = "sales-data"\ncriticality = "low"\nfields = ["legacy_order_no"]\n',
        encoding="utf-8",
    )
    assert has(sample, "DC014", "is retired but still has 1 registered consumer")
    edit(
        sample,
        "contracts/sales.orders.toml",
        'upstream = ["sales.raw_orders"]',
        'upstream = ["sales.legacy_orders"]',
    )
    assert has(sample, "DC014", "reads retired upstream")
    edit(sample, "contracts/sales.raw_orders.toml", 'status = "active"', 'status = "deprecated"')
    edit(
        sample,
        "contracts/sales.orders.toml",
        'upstream = ["sales.legacy_orders"]',
        'upstream = ["sales.raw_orders"]',
    )
    assert has(sample, "DC014", "active but reads deprecated upstream")


def test_dc015(sample: Path) -> None:
    edit(sample, "releases/sales.customers/1.0.0.toml", "tier = 1", "tier = 2")
    assert has(sample, "DC015", "does not match the index")
    edit(sample, "contracts/sales.customers.toml", 'name = "country"', 'name = "country_code"')
    assert has(
        sample, "DC015", "version 1.1.0 is released but contracts/sales.customers.toml now differs"
    )


def test_dc016(sample: Path) -> None:
    # a type change to a field that existed in 1.1.0 is breaking, but the version is only 1.2.0
    edit(
        sample,
        "contracts/sales.orders.toml",
        'name = "amount"\ntype = "decimal"',
        'name = "amount"\ntype = "string"',
    )
    assert has(sample, "DC016", "changes need a major bump")
    edit(sample, "contracts/sales.orders.toml", 'version = "1.2.0"', 'version = "1.1.0"')
    assert has(sample, "DC015", "now differs")


def test_dc016_removal_without_deprecation(sample: Path) -> None:
    text = (sample / "releases/finance.invoices/1.3.0.toml").read_text(encoding="utf-8")
    text = text.replace(
        '[[deprecation]]\nfield = "legacy_invoice_ref"\nsunset = "2026-09-30"\nreplacement = "invoice_id"\n',
        "",
    )
    (sample / "releases/finance.invoices/1.3.0.toml").write_text(text, encoding="utf-8")
    index = read_index(sample)
    index["finance.invoices"]["1.3.0"] = canonical_hash(tomllib.loads(text))
    (sample / "releases/index.json").write_text(json.dumps(index), encoding="utf-8")
    assert has(sample, "DC016", "removed without being deprecated in 1.3.0")


def test_dc017(sample: Path) -> None:
    index = read_index(sample)
    del index["finance.revenue_daily"]
    (sample / "releases/index.json").write_text(json.dumps(index), encoding="utf-8")
    assert has(sample, "DC017", "no released version")


def test_released_versions_of_a_deleted_contract_are_still_checked(sample: Path) -> None:
    (sample / "contracts/support.tickets.toml").unlink()
    (sample / "contracts/sales.legacy_orders.toml").unlink()
    # its releases still exist and are intact, so nothing is reported about it
    assert [f for f in run(sample) if f.subject == "sales.legacy_orders"] == []
    edit(sample, "releases/sales.legacy_orders/3.0.0.toml", "tier = 3", "tier = 1")
    assert has(sample, "DC015", "does not match the index")


def test_dc010_a_sunset_today_is_not_yet_overdue(sample: Path) -> None:
    edit(sample, "contracts/sales.raw_orders.toml", 'sunset = "2027-03-31"', f'sunset = "{TODAY}"')
    assert not has(sample, "DC010", "has passed")
    edit(sample, "contracts/sales.raw_orders.toml", f'sunset = "{TODAY}"', 'sunset = "2026-11-14"')
    assert has(sample, "DC010", "has passed")


def test_dc007_either_missing_sla_field_is_enough(sample: Path) -> None:
    edit(sample, "contracts/sales.orders.toml", "completeness_pct = 99.5\n", "")
    assert has(sample, "DC007", "tier 1 needs both")
    edit(sample, "contracts/sales.customers.toml", "freshness_minutes = 120\n", "")
    assert [f for f in run(sample) if f.rule == "DC007" and f.subject == "sales.customers"]


def test_dc014_draft_and_retired_contracts_are_exempt_from_upstream_status(sample: Path) -> None:
    # a retired contract reading a retired upstream, and a draft reading one, are both fine
    edit(
        sample,
        "contracts/sales.legacy_orders.toml",
        "tier = 3",
        'tier = 3\nupstream = ["sales.legacy_orders_old"]',
    )
    (sample / "contracts/sales.legacy_orders_old.toml").write_text(
        (sample / "contracts/sales.legacy_orders.toml")
        .read_text(encoding="utf-8")
        .replace('id = "sales.legacy_orders"', 'id = "sales.legacy_orders_old"')
        .replace('upstream = ["sales.legacy_orders_old"]\n', ""),
        encoding="utf-8",
    )
    edit(
        sample,
        "contracts/support.tickets.toml",
        "tier = 3",
        'tier = 3\nupstream = ["sales.legacy_orders"]',
    )
    assert not any(f.rule == "DC014" for f in run(sample))


def test_dc016_judges_only_versions_that_are_not_released_yet(sample: Path) -> None:
    # 1.1.0 of sales.customers is released. Even if the history before it was dishonest
    # (a field removed in a minor bump), that is DC015's concern, not a new finding.
    old = (sample / "releases/sales.customers/1.0.0.toml").read_text(encoding="utf-8")
    old += '\n[[field]]\nname = "legacy_zone"\ntype = "string"\nnullable = true\ndescription = "A field that was later dropped."\n'
    add_release(sample, "sales.customers", "1.0.0", old)
    assert not any(f.rule == "DC016" for f in run(sample))
