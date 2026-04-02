# Deprecation Policy

This policy describes how Synapse evolves APIs while minimizing upgrade risk.

## Versioning Context

- Synapse follows Semantic Versioning.
- Before `1.0.0`, minor versions (`0.x`) may include breaking changes when documented.

## Deprecation Lifecycle

1. **Announce**  
   Mark API/behavior as deprecated in docs and `CHANGELOG.md`.
2. **Warn**  
   Emit runtime warnings where practical (for example Python `DeprecationWarning`).
3. **Transition Window**  
   Provide migration guidance and compatibility notes.
4. **Remove**  
   Remove deprecated behavior in a subsequent release and document clearly.

## Minimum Expectations

- Deprecation must include:
  - replacement path;
  - migration example;
  - release note entry.
- Removals should not happen silently.

## Compatibility Signals

- Public SDK exports are part of the compatibility contract.
- Contract-affecting changes should update:
  - package docs;
  - `docs/compatibility-matrix.md` (if runtime support changes);
  - release notes in `CHANGELOG.md`.

## Current Example

- `synapse_sdk.init(...)` / TS `init(...)` are deprecated in favor of:
  - Python: `Synapse(config)`
  - TypeScript: `new Synapse(config)`
