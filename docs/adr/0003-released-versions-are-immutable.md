# ADR 0003: Released versions are copies pinned by hash

## Status

Accepted

## Context

A consumer pins to a version. If the content behind that version can change, the number means nothing, and compatibility checks would compare a contract with a moving target.

## Decision

`dcr release` copies the contract to `releases/<id>/<version>.toml` and records the hash of its parsed content in `releases/index.json`. Rule `DC015` is critical: a released file that no longer matches its hash, or a contract at a released version whose content differs, fails the build. Compatibility is always measured against the latest release, and only for versions that are not released yet.

## Consequences

- Changing history needs a new version. There is no quiet fix.
- Whitespace and comment edits do not count, because the hash is over parsed content.
- Release files are the only place a past version lives, so they must be kept. They are small text files.
