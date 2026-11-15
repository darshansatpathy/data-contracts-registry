# Shipping a breaking change

## Purpose

A producer needs to change a contract in a way `dcr compat` calls breaking: a removed or retyped field, a weakened promise, a new null.

## Triggers

- `dcr compat --contract <id>` is run on the branch and shows the changes and the consumers they reach.
- A breaking change to a field that was never deprecated fails regardless of version (see `deprecating-a-field.md`).
- The consumers listed under `reaches:` are the people to tell, highest criticality first.

## First checks

- Read what `dcr check` and `dcr compat` actually say before changing anything.
- Find the contract and its consumers in `reports/catalog.md`.

## Steps

1. Run `dcr compat --contract <id>`. Read every `breaking` line and the `reaches` list.
2. Tell each listed consumer team, in the pull request, what changes and when. Do not rely on them reading the diff.
3. If the change can be additive instead (a new field beside the old one), do that, deprecate the old field, and ship a minor version.
4. If it must break, bump the major version, keep the previous major published as long as the consumers need it, and name the date in the description.
5. Update `[[consumer]]` entries for any team that has moved.
6. Run `dcr check`, `dcr report` and `dcr export`, then commit the contract, reports and exports together.

## Verification

- `dcr compat` exits 0 and the required bump matches the version.
- `dcr check --fail-on low` reports no findings.
- Every consumer under `reaches:` has acknowledged in the pull request.

## Escalation

A consumer cannot move in time: raise it with the producing team's owner before merging. Do not change the contract to hide the impact.
