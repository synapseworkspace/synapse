# Enterprise Governance Pack

Last updated: 2026-04-03

Synapse provides an exportable governance bundle for enterprise ops/compliance reviews.

## What It Exports

`scripts/export_enterprise_governance_pack.py` exports:

- tenancy inventory (`tenants`, `tenant_memberships`, `tenant_projects`)
- auth session posture summary (`auth_sessions` active/revoked/expired counts)
- moderation audit window (`wiki_moderation_actions`)
- queue control audit window (`gatekeeper_calibration_queue_control_events`)
- a generated runbook checklist (`RUNBOOK.md`)

## Usage

```bash
python3 scripts/export_enterprise_governance_pack.py \
  --database-url postgresql://synapse:synapse@localhost:55432/synapse \
  --output-dir artifacts/governance-pack \
  --window-days 30
```

Project-scoped review:

```bash
python3 scripts/export_enterprise_governance_pack.py \
  --database-url postgresql://synapse:synapse@localhost:55432/synapse \
  --output-dir artifacts/governance-pack-omega \
  --window-days 30 \
  --project-id omega_demo
```

## Output Files

- `enterprise_governance_pack.json`
- `summary.json`
- `tenant_memberships.csv`
- `tenant_project_bindings.csv`
- `moderation_actions_window.csv`
- `queue_control_events_window.csv`
- `RUNBOOK.md`

## Operational Notes

- Use with `SYNAPSE_RBAC_MODE=enforce` and `SYNAPSE_TENANCY_MODE=enforce` in enterprise deployments.
- If running `SYNAPSE_AUTH_MODE=oidc`, rotate and review active web sessions regularly.
- Keep exported artifacts in a restricted access bucket/path, since governance metadata may contain user identifiers.
