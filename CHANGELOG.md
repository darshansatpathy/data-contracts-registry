# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-11-13

### Added
- Contract format: schema, owner, classification, SLA, quality checks, lineage, consumers and deprecations, in TOML.
- Compatibility engine with 35 kinds of change classified as breaking, minor or patch, and semantic-version enforcement.
- Immutable releases pinned by content hash, and consumer impact analysis through field-level lineage.
- Seventeen policy rules (DC001 to DC017), including personal-data propagation and release integrity.
- Record validation, JSON Schema export, and ANSI and Spark DDL export.
- Nine synthetic contracts, three sample data files and six generated reports.
- Five ADRs and three runbooks.

[0.1.0]: https://github.com/darshansatpathy/data-contracts-registry/releases/tag/v0.1.0
