# Security Policy

## Supported Versions

The project currently supports the latest `main` branch for security fixes.

## Reporting a Vulnerability

Please do not open public issues for sensitive security reports.

Instead:

1. Open a GitHub Security Advisory (preferred), or
2. Contact maintainers privately through the repository security contact when available.

Include:
- affected component (`services/api`, `services/mcp`, `packages/synapse-sdk-*`, `apps/web`)
- reproduction steps
- impact assessment
- proof-of-concept (if safe to share)

## Response Goals

- Acknowledge report within 72 hours.
- Provide initial triage/update within 7 days.
- Coordinate disclosure timeline with reporter when fix is ready.

## Security Scope Highlights

Focus areas in Synapse:
- API idempotency and replay semantics
- access control boundaries for project-scoped reads/writes
- secret handling for incident provider integrations
- MCP retrieval data exposure across projects
- SDK transport failure/degradation behavior

