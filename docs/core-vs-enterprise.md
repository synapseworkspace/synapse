# Core vs Enterprise Scope

Last updated: 2026-04-02

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
| Multi-tenant isolation (hard tenancy boundaries) | Limited | Full |
| SSO / enterprise IAM | No | Planned |
| Fine-grained RBAC administration | Partial | Full |
| Compliance-grade audit exports | Partial | Full |
| SLA-backed hosted operations | No | Planned |

## Why This Distinction Exists

- OSS core optimizes for fast adoption and developer control.
- Enterprise scope optimizes for governance, scale boundaries, and compliance operations.

If your team only needs the Agentic Wiki loop (`observe -> synthesize -> curate -> execute`), OSS core is the intended starting point.

Detailed implementation status and phased enterprise plan:
- `/Users/maksimborisov/synapse/docs/enterprise-readiness.md`
