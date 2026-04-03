# Core vs Enterprise Scope

Last updated: 2026-04-03

This page clarifies what is currently in open-source core vs what is typically packaged as enterprise/governance add-ons.

## Scope Table

| Capability | OSS Core | Enterprise Direction |
| --- | --- | --- |
| SDK observe + ingest | Yes | Yes |
| Draft synthesis pipeline | Yes | Yes |
| Wiki moderation UI (approve/edit/reject) | Yes | Yes |
| MCP retrieval runtime | Yes | Yes |
| OpenClaw integration + bootstrap memory | Yes | Yes |
| Task tracker core | Yes | Yes |
| Conflict explain + semantic diff basics | Yes | Yes |
| Multi-tenant isolation (hard tenancy boundaries) | Baseline available (`tenants`, memberships, project mapping + enforce mode) | Full |
| SSO / enterprise IAM | OIDC baseline available (JWT/JWKS + web sessions) | Full (SAML/SCIM/extensions) |
| Fine-grained RBAC administration | Deny-by-default route-level baseline | Full |
| Compliance-grade audit exports | Governance export pack baseline | Full |
| SLA-backed hosted operations | No | Planned |

## Why This Distinction Exists

- OSS core optimizes for fast adoption and developer control.
- Enterprise scope optimizes for governance, scale boundaries, and compliance operations.

If your team only needs the Agentic Wiki loop (`observe -> synthesize -> curate -> execute`), OSS core is the intended starting point.

Detailed implementation status and phased enterprise plan:
- `/Users/maksimborisov/synapse/docs/enterprise-readiness.md`
