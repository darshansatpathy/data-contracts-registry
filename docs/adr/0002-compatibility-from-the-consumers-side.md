# ADR 0002: Compatibility is judged from the consumer's side and enforced through semantic versions

## Status

Accepted

## Context

Producers tend to ask whether a change is safe for them. Consumers care whether their reader still works. Without a shared definition, every breaking change is an argument.

## Decision

Every kind of change is classified as breaking, minor or patch from the point of view of a reader that already works (`reports/change-kinds.md`). The required bump is the highest level. `dcr compat` and rule `DC016` fail when the version number understates the change, and removal of a field is allowed only after a released deprecation.

## Consequences

- The version number is a signal consumers can trust, because a wrong one fails the build.
- Some classifications are judgement calls (an added enum value is minor, not patch). They are written down with their reasons, so they can be argued with.
- The check sees declared contracts only. It cannot see a producer that ignores its own contract.
