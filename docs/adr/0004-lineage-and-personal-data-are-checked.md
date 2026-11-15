# ADR 0004: Lineage is field level, and personal data keeps its label downstream

## Status

Accepted

## Context

Most leaks of personal data are not a table that was marked wrong. They are a column derived from one that was marked right, and the label was lost on the way. Table-level lineage cannot see that.

## Decision

A field may say `derived_from = "contract.id.field"`. Rule `DC012` checks the reference resolves, that the source contract is listed upstream, and that a field derived from personal data is itself marked `pii` or explicitly `masked`. Impact analysis uses the same links to find the readers of downstream contracts.

## Consequences

- Losing a label on the way down is a build failure, not an audit finding.
- Authors have to write `derived_from`. A field they forget to link is invisible to the check.
- `masked = true` is a claim the registry cannot verify; it states that masking happens somewhere else.
