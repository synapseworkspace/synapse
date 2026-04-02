# Enterprise Readiness Status

Last updated: 2026-04-03

This page is the factual status of enterprise capabilities in Synapse OSS.

## Current Status (As-Is)

| Capability | Status | Notes |
| --- | --- | --- |
| Tenant model / hard tenancy boundaries | Not implemented | Data is scoped by `project_id`; there is no first-class tenant object or DB-level tenant isolation yet. |
| SSO (OIDC/SAML) | Not implemented | No built-in IdP login flow in OSS services yet. |
| RBAC (global, resource-level) | Partial | Role checks exist for incident-secret edit paths (`X-Synapse-Roles`), not as a full cross-product policy engine. |
| Audit trail | Partial | Moderation and queue/incident paths have audit coverage, but compliance-grade export/governance package is not complete. |
| Secrets governance | Partial | Secret masking + rotation-safe behavior exists for incident adapters; full enterprise secret governance is broader than current scope. |

## What Is Already Production-Useful

- Strong core loop (`observe -> synthesize -> curate -> execute`) with moderation and MCP runtime.
- Signed provenance for OpenClaw evidence flow.
- Reliability and regression guardrails in CI (SDK matrix, retrieval/gatekeeper evaluators, web e2e).

## What Is Missing For Full Enterprise

1. First-class tenant/organization model across API/DB/UI.
2. Identity integration (OIDC first, optional SAML bridge).
3. Unified RBAC policy evaluation for all privileged operations.
4. Compliance export workflows and governance packaging.

## Full Enterprise Plan

### E1: Tenancy Foundation
- Add `tenants`, `tenant_memberships`, and tenant-scoped project mapping.
- Add tenant guard middleware and DB query guards.
- Add migration/backfill path for existing `project_id`-only deployments.

### E2: SSO Foundation
- OIDC login flow (Auth0/Okta/Azure AD compatible).
- JWT validation + claim mapping (`sub`, `email`, tenant/group claims).
- Session model for web UI and service-to-service validation strategy.

### E3: Unified RBAC
- Role catalog (`tenant_admin`, `knowledge_editor`, `approver`, `auditor`, `operator`).
- Resource-level permission checks (drafts, publish, gatekeeper controls, incident hooks, task operations).
- Deny-by-default enforcement mode and audit logging for policy decisions.

### E4: Governance Packaging
- Exportable audit bundles.
- Approval workflow templates and policy presets.
- Enterprise deployment/runbook hardening docs.

## Direct Answer

Can we build full enterprise capabilities? Yes.

Current implementation is **partial**, and full enterprise requires dedicated work across identity, tenancy, policy, and governance layers (E1-E4 above).
