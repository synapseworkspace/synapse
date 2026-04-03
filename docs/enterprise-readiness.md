# Enterprise Readiness Status

Last updated: 2026-04-03

This page is the factual status of enterprise capabilities in Synapse OSS.

## Current Status (As-Is)

| Capability | Status | Notes |
| --- | --- | --- |
| Tenant model / project mapping | Implemented baseline | First-class `tenants`, `tenant_memberships`, `tenant_projects` tables + CRUD API (`/v1/tenants*`) + request-time project guard (`SYNAPSE_TENANCY_MODE=enforce`). |
| SSO (OIDC) | Implemented baseline | OIDC JWT validation via issuer discovery + JWKS (`SYNAPSE_AUTH_MODE=oidc`) with web session flow endpoints (`/v1/auth/mode`, `/v1/auth/session`). |
| RBAC (global, resource-level) | Implemented baseline | Unified policy evaluator in request middleware with deny-by-default mode (`SYNAPSE_RBAC_MODE=enforce`) and route-level role policies for core write paths. |
| Audit trail | Implemented baseline | Moderation + queue/incident audit data is exportable via governance pack (`scripts/export_enterprise_governance_pack.py`). |
| Secrets governance | Partial | Secret masking + rotation-safe behavior exists for incident adapters; full enterprise secret governance is broader than current scope. |

## What Is Already Production-Useful

- Strong core loop (`observe -> synthesize -> curate -> execute`) with moderation and MCP runtime.
- Signed provenance for OpenClaw evidence flow.
- Reliability and regression guardrails in CI (SDK matrix, retrieval/gatekeeper evaluators, web e2e, release error-budget gate).
- Enterprise authn/authz baseline in OSS: OIDC session flow + tenancy + deny-by-default RBAC modes.

## What Is Still Missing For Full Enterprise

1. SAML bridge and enterprise IdP provisioning workflows (SCIM/Just-in-Time provisioning).
2. Resource-level policy authoring UI (today policies are env/config driven).
3. Multi-region auth session replication and tenant-scoped API keys.
4. Managed compliance bundles (signed exports + retention/legal-hold workflows).

## Full Enterprise Plan

### E1: Tenancy Foundation (Done in OSS baseline)
- `tenants`, `tenant_memberships`, and tenant-scoped project mapping shipped in migration `037_enterprise_tenancy_auth_rbac.sql`.
- Tenant guard middleware shipped (`SYNAPSE_TENANCY_MODE=enforce`).

### E2: SSO Foundation (Done baseline, extend next)
- OIDC login flow for API + web session token path (`POST/GET/DELETE /v1/auth/session`).
- JWT validation + claim mapping (`sub`, `email`, tenant/roles claims) via OIDC discovery/JWKS.
- Next: SAML and SCIM provisioning.

### E3: Unified RBAC (Done baseline, deepen coverage)
- Role catalog + route-level policy enforcement with deny-by-default (`SYNAPSE_RBAC_MODE=enforce`).
- Next: per-resource policy authoring and policy-decision audit stream.

### E4: Governance Packaging (Done baseline, deepen compliance)
- Exportable governance pack shipped (`scripts/export_enterprise_governance_pack.py`, `artifacts/governance-pack/*`).
- Next: signed export bundles + retention/legal-hold policies.

## Direct Answer

Can we build full enterprise capabilities? Yes.

Current implementation now has an **enterprise-ready baseline** in OSS (OIDC + tenancy + deny-by-default RBAC + governance export).
Full enterprise depth still requires dedicated work on SAML/SCIM, fine-grained policy administration, and managed compliance workflows.
