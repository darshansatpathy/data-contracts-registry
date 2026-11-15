# Registering a consumer of a contract

## Purpose

A new team starts reading a contract. Registering them is what lets impact analysis warn them before a change.

## Triggers

- A team asks for access to a dataset.
- `reports/field-usage.md` shows a field with no registered reader that is in fact used.

## First checks

- Read what `dcr check` and `dcr compat` actually say before changing anything.
- Find the contract and its consumers in `reports/catalog.md`.

## Steps

1. Add a `[[consumer]]` table to the contract with an `id`, the team (it must be in `registry.toml`), a `criticality` and the exact `fields` they read.
2. List only the fields they use. Reading fewer fields means fewer breaking changes reach them.
3. Run `dcr check`: rule `DC009` rejects a missing field or an unregistered team.
4. Open the pull request against the producing team. Adding a consumer is a patch-level change.

## Verification

- `dcr check` is clean.
- `dcr compat --contract <id>` lists the consumer under `reaches:` when a field they read is changed.

## Escalation

The producing team objects to a consumer on a restricted contract: the classification and access decision belong to the data owner, not to this repository.
