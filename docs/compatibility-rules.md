# Compatibility rules

A contract is a promise to people who read the data. A change is judged by what it does to a reader that already works.

| Level | Meaning | Version bump |
|---|---|---|
| `breaking` | A reader that worked can fail, or quietly get wrong answers. | major |
| `minor` | Something new or stronger. Existing readers keep working. | minor |
| `patch` | Metadata only. | patch |

The required bump is the highest level among the changes. `dcr compat` compares each contract with its latest release, prints every change with its level, and fails if the version does not match. The full list of change kinds, with the reason for each, is generated into [reports/change-kinds.md](../reports/change-kinds.md).

## Four judgement calls worth knowing

**Adding an enum value is minor, not patch.** It cannot break a reader that ignores unknown values, but one that maps every value to something will meet a case it never planned for. It is announced.

**Weakening a promise is breaking, strengthening it is minor.** That holds for freshness, completeness, quality ranges, retention and tier. Consumers size their own systems against what was promised.

**Changing the personal-data flag is breaking in both directions.** Removing the flag can send data to places it was never allowed, and adding one changes who may read it.

**Removing a field is breaking, and is allowed only after a deprecation.** A field has to be announced with `[[deprecation]]` in a *released* version first. Removing a field that was never deprecated is a finding even with a major bump.

## What the check does not know

It compares declared contracts. It cannot see a producer that stops honouring its own contract, a consumer that is not registered, or a change in what a value *means* while its type stays the same. Registered consumers and `dcr validate` against real samples narrow that gap; they do not close it.
