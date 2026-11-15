# Security policy

## Reporting a vulnerability

Please do not open a public issue for security problems. Use GitHub's
[private vulnerability reporting](https://github.com/darshansatpathy/data-contracts-registry/security/advisories/new)
for this repository. You should get an acknowledgement within three working days.

## Scope

In scope: the `dcr` tool and the integrity of releases, in particular anything that lets a released version change unnoticed, hides a breaking change, or lets a file outside the registry be read or written. Out of scope: the contents of the synthetic example contracts, and warehouses or pipelines that consume the generated DDL.

## Operating it safely

- The registry contains no secrets and no real data. Samples are synthetic.
- Contracts are trusted input from reviewed pull requests. `regex` quality checks use Python's `re`, so a pathological pattern can be slow; review patterns like code.
- `dcr` reads TOML and JSON Lines and writes only to `reports/`, `schemas/`, `ddl/` and `releases/`. It executes nothing from the files it reads.
- Do not add real customer data, personal data or internal hostnames to samples or descriptions.
