from __future__ import annotations

from pathlib import Path

from datacontracts import compat, lineage
from datacontracts.model import Registry

from .conftest import edit, load


def test_split_ref() -> None:
    assert lineage.split_ref("sales.raw_orders.email") == ("sales.raw_orders", "email")
    assert lineage.split_ref("email") is None
    assert lineage.split_ref(".email") is None
    assert lineage.split_ref("sales.") is None


def test_downstream_map_and_closure(sample: Path) -> None:
    reg = load(sample)
    dm = lineage.downstream_map(reg)
    assert dm["sales.raw_orders"] == ["sales.orders"]
    assert dm["sales.orders"] == [
        "finance.invoices",
        "finance.revenue_daily",
        "marketing.customer_360",
        "ml.churn_features",
    ]
    closure = lineage.downstream_closure(reg, "sales.raw_orders")
    assert closure[0] == "sales.orders"
    assert set(closure) == {
        "sales.orders",
        "finance.invoices",
        "finance.revenue_daily",
        "marketing.customer_360",
        "ml.churn_features",
    }
    assert len(closure) == len(set(closure))
    assert lineage.downstream_closure(reg, "support.tickets") == []


def test_no_cycles_in_the_real_registry(sample: Path) -> None:
    assert lineage.find_cycles(load(sample)) == []


def test_each_distinct_cycle_is_found_once(sample: Path) -> None:
    # revenue_daily reads both orders and invoices, so this closes two different loops
    edit(
        sample,
        "contracts/sales.raw_orders.toml",
        "retention_days = 730",
        'upstream = ["finance.revenue_daily"]\nretention_days = 730',
    )
    cycles = lineage.find_cycles(load(sample))
    assert len(cycles) == 2
    assert all(c[0] == c[-1] for c in cycles)
    assert len({frozenset(c) for c in cycles}) == 2
    assert all(
        {"sales.raw_orders", "sales.orders", "finance.revenue_daily"} <= set(c) for c in cycles
    )


def test_a_simple_cycle_is_reported_once(sample: Path) -> None:
    edit(
        sample,
        "contracts/sales.raw_orders.toml",
        "retention_days = 730",
        'upstream = ["sales.orders"]\nretention_days = 730',
    )
    cycles = lineage.find_cycles(load(sample))
    assert len(cycles) == 1 and set(cycles[0]) == {"sales.raw_orders", "sales.orders"}


def test_unknown_upstream_is_ignored_by_the_graph(sample: Path) -> None:
    edit(
        sample,
        "contracts/sales.orders.toml",
        'upstream = ["sales.raw_orders"]',
        'upstream = ["sales.raw_orders", "ghost.table"]',
    )
    reg = load(sample)
    assert lineage.find_cycles(reg) == []
    assert "ghost.table" not in lineage.downstream_map(reg)


def test_pii_leaks(sample: Path) -> None:
    reg = load(sample)
    assert lineage.pii_leaks(reg) == []
    edit(
        sample,
        "contracts/marketing.customer_360.toml",
        "nullable = false\npii = true\nderived_from",
        "nullable = false\nderived_from",
    )
    leaks = lineage.pii_leaks(load(sample))
    assert [(c.id, name) for c, name, _ in leaks] == [("marketing.customer_360", "email")]


def test_masked_fields_are_not_leaks(sample: Path) -> None:
    edit(
        sample,
        "contracts/marketing.customer_360.toml",
        "nullable = false\npii = true\nderived_from",
        "nullable = false\nmasked = true\nderived_from",
    )
    assert lineage.pii_leaks(load(sample)) == []


def _removal(reg: Registry, cid: str, *fields: str) -> list[lineage.Impact]:
    changes = [compat.Change("field-removed", "breaking", f, "gone") for f in fields]
    return lineage.impact(reg, reg.contracts[cid], changes)


def test_impact_of_a_field_reaches_direct_readers_and_derived_downstream(sample: Path) -> None:
    reg = load(sample)
    found = _removal(reg, "sales.orders", "amount")
    direct = {i.consumer for i in found if i.via == "direct"}
    assert direct == {"finance.revenue-pipeline", "ml.churn-feature-job"}
    downstream = {(i.contract, i.consumer) for i in found if i.via != "direct"}
    assert ("finance.revenue_daily", "finance.revenue-dashboard") in downstream
    assert ("finance.invoices", "finance.ar-aging") in downstream
    assert ("marketing.customer_360", "marketing.audience-builder") in downstream
    # sorted with the most critical first
    order = {"high": 0, "medium": 1, "low": 2}
    assert [order[i.criticality] for i in found] == sorted(order[i.criticality] for i in found)


def test_a_field_nobody_reads_reaches_nobody(sample: Path) -> None:
    reg = load(sample)
    assert _removal(reg, "sales.orders", "status") == [
        i
        for i in _removal(reg, "sales.orders", "status")
        if i.consumer == "finance.revenue-pipeline"
    ]
    assert lineage.impact(reg, reg.contracts["sales.orders"], []) == []


def test_whole_contract_changes_reach_every_consumer_and_downstream_contract(sample: Path) -> None:
    reg = load(sample)
    c = compat.Change("sla-freshness-weakened", "breaking", "", "worse")
    found = lineage.impact(reg, reg.contracts["sales.orders"], [c])
    assert {i.consumer for i in found if i.via == "direct"} == {
        "finance.revenue-pipeline",
        "ml.churn-feature-job",
        "marketing.attribution-job",
    }
    assert {i.contract for i in found if i.via != "direct"} == {
        "finance.invoices",
        "finance.revenue_daily",
        "marketing.customer_360",
        "ml.churn_features",
    }
