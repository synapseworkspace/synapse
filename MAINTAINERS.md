# Synapse Maintainers

This document defines ownership and decision scope for the OSS repository.

## Maintainer Roles

- **Core Maintainer**: can approve and merge PRs, cut releases, and update roadmap scope.
- **Package Maintainer**: owns one or more packages/services and reviews changes in that area.
- **Docs Maintainer**: owns docs quality, onboarding clarity, and release-note consistency.

## Current Ownership Map

- **Monorepo/Core governance**: Synapse Core Team
- **Python SDK (`packages/synapse-sdk-py`)**: Synapse Core Team
- **TypeScript SDK (`packages/synapse-sdk-ts`)**: Synapse Core Team
- **OpenClaw plugin (`packages/synapse-openclaw-plugin`)**: Synapse Core Team
- **API/Worker/MCP services (`services/*`)**: Synapse Core Team
- **Web console (`apps/web`)**: Synapse Core Team
- **Docs and release runbooks (`docs/*`)**: Synapse Core Team

## Review Expectations

- At least one maintainer review for non-trivial changes.
- Any schema or contract change should include:
  - compatibility note in `CHANGELOG.md`;
  - docs update in `docs/`;
  - CI/validation update when applicable.

## Release Authority

- Release tags (`vX.Y.Z`) are created by Core Maintainers only.
- Release requires green CI and updated `CHANGELOG.md`.

## Succession

- If a maintainer becomes inactive, ownership can be reassigned by Core Maintainers.
- Critical areas should always have at least one active owner.
