# ADR 0001: Contracts are reviewed TOML files, not entries in a tool

## Status

Accepted

## Context

Data contracts usually live in a catalogue UI or a wiki. They change without review, cannot be diffed, and cannot be checked by a build. A producer team can change a column and nobody downstream hears about it until a dashboard breaks.

## Decision

Each contract is a TOML file in `contracts/`, reviewed in a pull request like any other code. A loader reports every structural problem in one pass. Rules (`DC001` to `DC017`) run over the whole registry, and CI fails on a high finding.

## Consequences

- A change to a promise is a pull request with a diff and an owner.
- The format is plain enough for people who do not write Python, at the cost of a stricter loader than a wiki needs.
- There is no UI. The reports are generated markdown, which is enough to read and not enough to search across hundreds of contracts.
