# Data contracts registry

[![CI](https://github.com/darshansatpathy/data-contracts-registry/actions/workflows/ci.yml/badge.svg)](https://github.com/darshansatpathy/data-contracts-registry/actions/workflows/ci.yml)
[![CodeQL](https://github.com/darshansatpathy/data-contracts-registry/actions/workflows/codeql.yml/badge.svg)](https://github.com/darshansatpathy/data-contracts-registry/actions/workflows/codeql.yml)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)
![Typed](https://img.shields.io/badge/mypy-strict-informational)
![Dependencies](https://img.shields.io/badge/runtime%20dependencies-0-success)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**A data contract is a promise to the people who read the data. This registry keeps those promises as reviewed code, and fails the build when a change would break one.**

Each contract is a TOML file: schema, owner, classification, freshness promise, quality checks, lineage and the consumers who read it. A command-line tool, `dcr`, compares every change with the last released version, tells the author whether it is breaking and who it would reach, checks that the version number tells the truth, and refuses to let personal data lose its label as it flows downstream. JSON Schema and DDL are generated, never written by hand.

The registry in this repository is synthetic: nine contracts for an imaginary retailer, with real lineage, real consumers and one change in flight.

## What it checks

| Question | How it is answered |
|---|---|
| Will this change break a reader? | Every change is classified `breaking`, `minor` or `patch` from the reader's side (`reports/change-kinds.md`, 35 kinds). |
| Is the version number honest? | `dcr compat` and rule `DC016` fail when the bump understates the change. |
| Who is hit? | Registered consumers, and the readers of downstream contracts reached through field-level lineage. |
| Can a released version change under its readers? | No. Releases are copies pinned by hash, and rule `DC015` is critical. |
| Does personal data keep its label downstream? | Rule `DC012` follows `derived_from` links. |
| Is the data what the contract says? | `dcr validate` checks records against types, nullability, enums, ranges, patterns, uniqueness and keys. |
| Do generated artefacts match? | `dcr report --check` and `dcr export --check` fail on stale files. |

## A breaking change, caught

The author changes `amount` from `decimal` to `string` and bumps only the minor version:

```
$ dcr compat --contract sales.orders
sales.orders: 1.1.0 -> 1.2.0, needs a major bump
  breaking type-changed `amount`: decimal to string
  minor    field-added `order_date`: new field
  reaches:
    high   finance.ar-aging (finance-analytics) via finance.invoices
    high   bi.exec-scorecard (bi-platform) via finance.revenue_daily
    high   finance.revenue-dashboard (finance-analytics) via finance.revenue_daily
    high   marketing.audience-builder (marketing-analytics) via marketing.customer_360
    high   ml.churn-model-training (data-science) via ml.churn_features
    high   finance.revenue-pipeline (finance-data) direct
    medium risk.credit-exposure (risk-analytics) via finance.invoices
    medium ml.churn-feature-job (ml-platform) direct
  problem: sales.orders: changes need a major bump but 1.1.0 to 1.2.0 is minor
```

It names the change, the bump it needs, and the consumers it reaches, most critical first, including those that read through downstream contracts. The same command on the real registry, where two changes are in flight and both are correctly versioned:

```
$ dcr compat
finance.invoices: 1.3.0 -> 2.0.0, needs a major bump
  breaking field-removed `legacy_invoice_ref`: the field no longer exists (planned removal)
  patch    consumers-changed: consumer registrations changed
  reaches: no registered consumer reads the changed fields
sales.orders: 1.1.0 -> 1.2.0, needs a minor bump
  minor    field-added `order_date`: new field
```

`finance.invoices` removes `legacy_invoice_ref`, which was deprecated in the released 1.3.0 with a sunset date, so the removal is marked as planned and the major bump is correct.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

dcr check                    # 17 rules over the registry
dcr compat                   # compare with the last release
dcr validate sales.orders samples/sales.orders.jsonl
dcr release sales.orders     # publish the version, once it is final
dcr report                   # markdown reports (six)
dcr export                   # JSON Schema and DDL for every contract
make check                   # ruff, mypy --strict, pytest with an 85% coverage gate
```

```
$ dcr check
9 contracts, 17 rules: 0 findings
```

Commands: `check`, `compat`, `release`, `validate`, `report`, `export`, `rules`. `report` and `export` take `--check` to fail when files are stale.

## What is in it

| Path | What |
|---|---|
| `contracts/` | The nine contracts, one TOML file each |
| `releases/` | Released versions and `index.json` with their hashes |
| `registry.toml` | Teams and policy limits |
| `samples/` | Synthetic records that satisfy three contracts |
| `reports/` | Catalogue, lineage graph, field usage, personal data register, rules, change kinds (generated) |
| `schemas/`, `ddl/` | JSON Schema, ANSI DDL and Spark DDL (generated) |
| `docs/` | [Contract format](docs/contract-format.md), [compatibility rules](docs/compatibility-rules.md), ADRs, runbooks |

## Policy rules

| Rule | Severity | Checks |
|---|---|---|
| `DC001` | high | Contract id is domain.name and matches its file |
| `DC002` | high | Version is MAJOR.MINOR.PATCH |
| `DC003` | high | Owner is a registered team |
| `DC004` | medium | Contract and fields are described |
| `DC005` | high | Personal data implies confidential or restricted |
| `DC006` | high | Personal data has a retention limit |
| `DC007` | high | Critical contracts promise freshness and completeness |
| `DC008` | high | Fields are well formed and live contracts have a key |
| `DC009` | high | Consumers are registered teams reading fields that exist |
| `DC010` | medium | Deprecations are real and not overdue |
| `DC011` | high | Upstream contracts exist and lineage has no cycles |
| `DC012` | high | Personal data keeps its label downstream |
| `DC013` | high | Quality rules are valid and target real fields |
| `DC014` | high | Lifecycle status agrees with lineage and consumers |
| `DC015` | critical | Released versions are immutable and intact |
| `DC016` | high | Version bump matches the changes |
| `DC017` | low | Contracts under review are labelled draft |

## Design decisions

- [ADR 0001](docs/adr/0001-contracts-are-reviewed-toml.md): contracts are reviewed TOML files, not entries in a tool.
- [ADR 0002](docs/adr/0002-compatibility-from-the-consumers-side.md): compatibility is judged from the consumer's side and enforced through versions.
- [ADR 0003](docs/adr/0003-released-versions-are-immutable.md): released versions are copies pinned by hash.
- [ADR 0004](docs/adr/0004-lineage-and-personal-data-are-checked.md): lineage is field level and personal data keeps its label.
- [ADR 0005](docs/adr/0005-no-runtime-dependencies-and-generated-artefacts.md): no runtime dependencies; schemas and DDL are generated.

Runbooks: [shipping a breaking change](docs/runbooks/breaking-change.md), [deprecating a field](docs/runbooks/deprecating-a-field.md), [registering a consumer](docs/runbooks/onboarding-a-consumer.md).

## What has and has not been verified

Verified, by running it:

- The whole suite, including every one of the 17 rules failing on a purpose-built case, every kind of change in `CHANGE_KINDS` being produced and classified, and the CLI end to end.
- Mutation checks: 27 deliberate bugs in the compatibility, lineage, rule, validation, release and report code, each caught by at least one test.
- The generated ANSI DDL executes in SQLite and enforces what the contract says (not null, enum checks, primary key) on the sample rows. The JSON Schema agrees with the validator on good and damaged rows.
- The wheel installs into a clean environment and runs on a copy of the registry (CI).

Not verified, or not claimed:

- **The Spark DDL has not been run on Databricks.** It is generated and checked for shape only.
- **Nothing checks that a real producer honours its contract.** `dcr validate` works on files you hand it; this repository is not connected to a warehouse or a pipeline.
- **The registry is synthetic.** The retailer, its teams and its data are invented. The rules are real; the contracts are an example.
- **Consumers are self-registered.** Impact analysis sees only the consumers that are listed. A reader nobody registered is invisible to it.
- **`masked = true` is taken on trust.** The registry records that masking happens; it cannot verify it.
- The compatibility classifications are my judgement from a consumer's point of view. They are written down with reasons in [reports/change-kinds.md](reports/change-kinds.md) so they can be argued with.
- Written and tested by an AI assistant (Claude) working with the repository owner; the design and the numbers have not had an independent review.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). Contracts and quality patterns are trusted input from reviewed pull requests, not from outside; a `regex` check uses Python's `re`, so a pathological pattern in a contract can be slow. Report vulnerabilities privately.

## Licence

MIT. See [LICENSE](LICENSE).
