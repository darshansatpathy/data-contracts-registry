# Contract format

A registry is a directory with `registry.toml`, one TOML file per contract in `contracts/`, and a `releases/` directory that `dcr release` maintains. The loader reads every file, reports every problem in one pass, and never runs anything from them.

## registry.toml

```toml
[registry]
name = "Acme Retail data contracts (synthetic)"
teams = ["sales-data", "finance-data"]   # owners and consumer teams must be listed here
max_pii_retention_days = 1825             # personal data may not be kept longer than this
min_description_chars = 10                # shortest acceptable description
```

## A contract

The file is `contracts/<id>.toml` and the id is `<domain>.<name>` in lowercase snake case.

| Table | Key | Meaning |
|---|---|---|
| `[contract]` | `id`, `version`, `owner`, `domain`, `description` | Required. `version` is `MAJOR.MINOR.PATCH`. |
| | `tier` | 1 critical, 2 important, 3 standard. Tier 1 needs a freshness and a completeness promise. |
| | `status` | `draft`, `active`, `deprecated` or `retired`. Moves forward only. |
| | `classification` | `public`, `internal`, `confidential` or `restricted`. Personal data needs `confidential` or higher. |
| | `upstream` | Contract ids this one is built from. Lineage is checked for cycles. |
| | `retention_days` | Required when any field is personal data, and capped by the registry. |
| `[sla]` | `freshness_minutes`, `completeness_pct` | What the producer promises. Weakening either is a breaking change. |
| `[[field]]` | `name`, `type`, `nullable`, `description` | Types: `string`, `int`, `long`, `double`, `decimal`, `boolean`, `date`, `timestamp`. |
| | `pii` | The field is personal data. Changing this flag, either way, is breaking. |
| | `primary_key` | Part of the key. A live contract needs a non-nullable key. |
| | `enum` | Closed set of allowed values, on string fields only. |
| | `derived_from` | `contract.id.field` this field is computed from. Drives field-level lineage. |
| | `masked` | Personal data that has been masked on the way down, so the label need not carry over. |
| `[[quality]]` | `id`, `field`, `check` | Checks: `not_null`, `unique`, `range` (`min`, `max`), `regex` (`pattern`). |
| `[[consumer]]` | `id`, `team`, `criticality`, `fields` | Who reads this data, and which fields. `criticality` is `high`, `medium` or `low`. |
| `[[deprecation]]` | `field`, `sunset`, `replacement` | Announces that a field will be removed. |

Field order is not significant. Comments and whitespace do not count as changes: contracts are compared by the hash of their parsed content.

## What is generated

`dcr report` writes six reports to `reports/`. `dcr export` writes a JSON Schema and two kinds of DDL for every contract to `schemas/` and `ddl/`. Never edit these; CI fails if they differ from what the contracts produce.

The `ansi` DDL is executed against SQLite in the tests, with the sample rows, to check that the constraints it states agree with the validator. The `spark` DDL (Delta, with comments and table properties) has not been run on Databricks.
