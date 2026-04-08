# Synapse Upgrade Checklist

Use this checklist for production/self-host upgrades to avoid API/UI drift and ingestion regressions.

## 1. Pre-Upgrade Snapshot

1. Record current image/tag/commit (`api`, `worker`, `mcp`, `web`).
2. Export DB backup (or volume snapshot).
3. Capture current Gatekeeper config:
   - `GET /v1/gatekeeper/config?project_id=<project>`
4. Capture current source ownership and adoption routing:
   - `GET /v1/adoption/source-ownership?project_id=<project>`
5. Verify queue is stable:
   - `GET /v1/gatekeeper/calibration/operations/throughput?project_id=<project>`

## 2. Apply Version + Migrations

1. Pull new images / checkout release tag.
2. Run DB migrations before workers process new events.
3. Restart order:
   - API
   - Worker
   - MCP
   - Web
4. Confirm health:
   - `GET /health`
   - `GET /v1/meta/compatibility`

## 3. Routing Policy Safety Check

1. Preview adoption bootstrap profile (non-destructive):
   - `POST /v1/adoption/bootstrap-profile/apply` with `dry_run=true`
2. Check reject diagnostics for policy mismatch:
   - `GET /v1/adoption/rejections/diagnostics?project_id=<project>&days=7`
3. If required, apply bootstrap profile with explicit confirmation:
   - `POST /v1/adoption/bootstrap-profile/apply` with `dry_run=false`, `confirm_project_id=<project>`

## 4. Post-Deploy Smoke

Run:

```bash
./scripts/run_selfhost_core_acceptance.sh
```

This validates end-to-end:
- import/backfill;
- worker synthesis to draft;
- draft moderation/publish;
- MCP retrieval on published wiki knowledge.

## 5. Rollback Plan

If rollout quality regresses:

1. Pause mutating paths (optional): set source ownership mode to `advisory` or `off`.
2. Restore prior images/tags.
3. Restore DB backup (or execute scoped reset):
   - `POST /v1/adoption/project-reset` with `dry_run=false` and explicit scope.
4. Re-run post-deploy smoke to confirm recovery.
