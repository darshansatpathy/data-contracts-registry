# ADR 0005: No runtime dependencies, and schemas and DDL are generated, never written by hand

## Status

Accepted

## Context

A contract tool that needs a heavy toolchain does not get run on a laptop or in a short CI job. Hand-written schemas and DDL drift from the contract the moment someone edits one of them.

## Decision

The tool uses only the Python standard library (`tomllib`, `json`, `re`, `decimal`). JSON Schema, ANSI DDL and Spark DDL are generated from the contracts, committed, and checked for freshness in CI. The ANSI DDL is executed against SQLite in the tests with the sample data; the Spark DDL is not run anywhere in CI.

## Consequences

- Anyone can run `dcr` with a bare Python 3.11.
- Generated files appear in diffs, which is the point, and also add review noise.
- The Spark output is untested against Databricks and the README says so.
