# Synapse Compatibility Matrix

Last updated: 2026-04-03

This matrix captures runtime support and current CI coverage for OSS packages.

## SDK Runtimes

| Component | Version policy | CI-verified now |
| --- | --- | --- |
| `synapseworkspace-sdk` (Python) | Python `>=3.10` | Python `3.12` |
| `@synapseworkspace/sdk` (TypeScript) | Node.js `>=18` | Node.js `22` |
| `@synapseworkspace/schema` | Node.js `>=18` (for package tooling) | Node.js `22` |
| `@synapseworkspace/openclaw-plugin` | Node.js `>=18` | Node.js `22` |

## Core Services (Self-Hosted)

| Service | Runtime | Baseline |
| --- | --- | --- |
| API (`services/api`) | Python | `3.12` |
| Worker (`services/worker`) | Python | `3.12` |
| MCP runtime (`services/mcp`) | Python | `3.12` |
| Web UI (`apps/web`) | Node.js + browser | Node `22`, Playwright Chromium |
| Database | PostgreSQL | `15+` |

## Agent Framework Integrations

| Integration path | Status | Verification source |
| --- | --- | --- |
| Generic monitor wrapper (`monitor`) | Supported | SDK offline smoke in `scripts/ci_checks.sh` |
| OpenClaw plugin package (`@synapseworkspace/openclaw-plugin`) | Supported | Runtime fixture tests + CI package test |
| OpenClaw connector | Supported | `scripts/integration_openclaw_mcp_runtime.py`, `scripts/integration_openclaw_runtime_contract.py` |
| MCP context injection helpers | Supported | SDK offline smoke + MCP integration script |
| LangGraph / LangChain / CrewAI wrappers | Supported (adapter level) | SDK compile + monitor smoke + cookbook snapshot contracts |

## Notes

- CI currently guarantees compatibility for the versions in the `CI-verified now` column.
- Dedicated compatibility matrix workflow runs additional SDK matrix checks across Python (`3.10/3.11/3.12/3.13`) and Node (`18/20/22`): `.github/workflows/compat-matrix.yml`.
- Framework adapter version targets are documented in `docs/framework-integrations.md` (`Version Compatibility` section).
- Additional versions in policy are expected to work and should be validated by downstream users before production rollout.
- Any support baseline change must update this document, package metadata, and `CHANGELOG.md` together.
- OpenClaw integration now includes evidence-level signed provenance metadata (`synapse.openclaw.provenance.v1`) with contract coverage.
- Audit-time provenance verification tooling is available via API + CLI (`/v1/openclaw/provenance/verify`, `scripts/verify_openclaw_provenance.py`).
