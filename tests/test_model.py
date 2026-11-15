from __future__ import annotations

import tomllib
from pathlib import Path

from datacontracts.model import canonical_hash, load_registry, parse_contract

from .conftest import BASE, ROOT, edit, load, parse


def test_real_registry_loads_cleanly() -> None:
    reg, problems = load_registry(ROOT)
    assert problems == []
    assert reg is not None
    assert len(reg.contracts) == 9
    c = reg.contracts["sales.orders"]
    assert c.field_named("order_id") is not None
    assert c.field_named("nope") is None
    assert c.field_names[0] == "order_id"
    assert reg.policy.max_pii_retention_days == 1825


def test_parses_every_part_of_a_contract() -> None:
    c = parse(
        BASE
        + '\n[[deprecation]]\nfield = "amount"\nsunset = "2027-01-31"\nreplacement = "order_id"\n'
    )
    assert (c.id, c.version, c.tier, c.status) == ("sales.orders", "1.0.0", 2, "active")
    assert c.sla.freshness_minutes == 60 and c.sla.completeness_pct == 99.0
    assert c.quality[0].min == 0.0 and c.quality[0].max == 100.0
    assert c.consumers[0].fields == ("order_id", "amount")
    assert c.deprecations[0].replacement == "order_id"
    assert c.field_named("status") is not None and c.field_named("status").enum == (
        "placed",
        "paid",
    )  # type: ignore[union-attr]


def test_hash_ignores_whitespace_and_comments_but_not_content() -> None:
    a = tomllib.loads(BASE)
    b = tomllib.loads("# a comment\n\n" + BASE.replace(" = ", "  =  "))
    assert canonical_hash(a) == canonical_hash(b)
    c = tomllib.loads(BASE.replace("tier = 2", "tier = 3"))
    assert canonical_hash(a) != canonical_hash(c)


def _problems(text: str) -> list[str]:
    from datacontracts.model import _Problems

    p = _Problems()
    parse_contract(tomllib.loads(text), "contracts/x.toml", p)
    return p.items


def test_each_structural_mistake_is_reported() -> None:
    cases = [
        ('type = "decimal"', 'type = "money"', "type `money` is not one of"),
        ('status = "active"', 'status = "live"', "status `live` is not one of"),
        ('classification = "internal"', 'classification = "secret"', "classification `secret`"),
        ("tier = 2", "tier = 4", "`tier` must be 1, 2 or 3"),
        ("tier = 2", 'tier = "two"', "`tier` must be int"),
        ("retention_days = 100", 'retention_days = "100"', "retention_days"),
        ("freshness_minutes = 60", 'freshness_minutes = "60"', "freshness_minutes"),
        ("completeness_pct = 99.0", 'completeness_pct = "high"', "completeness_pct"),
        ('criticality = "high"', 'criticality = "urgent"', "criticality `urgent`"),
        ('check = "range"', 'check = "median"', "check `median`"),
        ("min = 0", 'min = "zero"', "`min` must be a number"),
        ("nullable = false\nprimary_key", "nullable = 1\nprimary_key", "`nullable` must be bool"),
    ]
    for old, new, expected in cases:
        found = _problems(BASE.replace(old, new, 1))
        assert any(expected in p for p in found), (old, found)


def test_missing_required_keys_are_reported() -> None:
    for key in ("id", "version", "owner", "domain", "description", "status", "tier"):
        text = (
            "\n".join(line for line in BASE.splitlines() if not line.startswith(f"{key} = ")) + "\n"
        )
        assert any(f"missing `{key}`" in p for p in _problems(text)), key
    assert any("missing `name`" in p for p in _problems(BASE.replace('name = "order_id"\n', "", 1)))
    assert any("missing [contract]" in p for p in _problems("[sla]\nfreshness_minutes = 1\n"))


def test_malformed_sections_are_reported() -> None:
    no_sla = BASE.replace("[sla]\nfreshness_minutes = 60\ncompleteness_pct = 99.0\n", "")
    assert any("[sla] must be a table" in p for p in _problems("sla = 3\n" + no_sla))
    no_quality = BASE.replace(
        '[[quality]]\nid = "amount_range"\nfield = "amount"\ncheck = "range"\nmin = 0\nmax = 100\n\n',
        "",
    )
    assert any("must be an array of tables" in p for p in _problems("quality = 3\n" + no_quality))
    assert any(
        "list of strings" in p
        for p in _problems(BASE.replace('fields = ["order_id", "amount"]', "fields = 3"))
    )
    assert any(
        "derived_from" in p
        for p in _problems(
            BASE.replace(
                'description = "Order total', 'derived_from = 4\ndescription = "Order total', 1
            )
        )
    )
    assert any(
        "`pattern` must be a string" in p
        for p in _problems(
            BASE + '\n[[quality]]\nid = "p"\nfield = "status"\ncheck = "regex"\npattern = 5\n'
        )
    )


def test_deprecation_dates() -> None:
    assert any(
        "not an ISO date" in p
        for p in _problems(BASE + '\n[[deprecation]]\nfield = "amount"\nsunset = "soon"\n')
    )
    assert any(
        "missing `sunset`" in p for p in _problems(BASE + '\n[[deprecation]]\nfield = "amount"\n')
    )
    assert _problems(BASE + '\n[[deprecation]]\nfield = "amount"\nsunset = 2027-01-31\n') == []


def test_integers_are_not_booleans_and_floats_accept_integers() -> None:
    assert any(
        "`tier` must be int" in p for p in _problems(BASE.replace("tier = 2", "tier = true"))
    )
    c = parse(BASE.replace("completeness_pct = 99.0", "completeness_pct = 99"))
    assert c.sla.completeness_pct == 99.0


def test_registry_level_problems(tmp_path: Path) -> None:
    reg, problems = load_registry(tmp_path)
    assert reg is None and "registry.toml: not found" in problems[0]

    (tmp_path / "registry.toml").write_text("[registry\n", encoding="utf-8")
    _, problems = load_registry(tmp_path)
    assert "invalid TOML" in problems[0]

    (tmp_path / "registry.toml").write_text(
        '[registry]\nteams = ["sales-data"]\n', encoding="utf-8"
    )
    _, problems = load_registry(tmp_path)
    assert problems == ["contracts/: no contracts found"]

    (tmp_path / "contracts").mkdir()
    (tmp_path / "contracts" / "a.toml").write_text(BASE, encoding="utf-8")
    (tmp_path / "contracts" / "b.toml").write_text(BASE, encoding="utf-8")
    (tmp_path / "contracts" / "c.toml").write_text("not = [toml", encoding="utf-8")
    (tmp_path / "contracts" / "d.toml").write_text(
        BASE.replace('type = "decimal"', 'type = "money"'), encoding="utf-8"
    )
    _, problems = load_registry(tmp_path)
    text = "\n".join(problems)
    assert "duplicate contract id `sales.orders`" in text
    assert "c.toml: invalid TOML" in text
    assert "type `money`" in text


def test_a_bad_contract_in_the_real_registry_blocks_loading(sample: Path) -> None:
    edit(sample, "contracts/sales.orders.toml", "tier = 1", "tier = 9")
    reg, problems = load_registry(sample)
    assert reg is None
    assert any("tier" in p for p in problems)
    edit(sample, "contracts/sales.orders.toml", "tier = 9", "tier = 1")
    assert load(sample).contracts["sales.orders"].tier == 1
