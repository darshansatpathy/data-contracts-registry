# Deprecating and removing a field

## Purpose

A field should leave a contract. Removal is allowed only after the field has been announced in a released version.

## Triggers

- A field has no registered readers (see `reports/field-usage.md`).
- A replacement field is ready.
- Rule `DC010` reports an overdue sunset.

## First checks

- Read what `dcr check` and `dcr compat` actually say before changing anything.
- Find the contract and its consumers in `reports/catalog.md`.

## Steps

1. Check `reports/field-usage.md` for who still reads the field.
2. Add `[[deprecation]]` with the field, a `sunset` date and the `replacement`. Bump the minor version.
3. `dcr release` the new version so the announcement is on record.
4. Tell the consumers listed as readers. Wait until the sunset date passes and nobody reads the field.
5. Remove the field and its deprecation, bump the major version, and release.
6. If the sunset passes and readers remain, extend the date in a minor version. Never remove the field out from under them.

## Verification

- `dcr compat` shows `field-removed ... (planned removal)` and a major bump.
- Rule `DC016` is quiet: the field was deprecated in the previous release.

## Escalation

A reader appears after the announcement: contact their team, and extend the sunset rather than removing the field.
