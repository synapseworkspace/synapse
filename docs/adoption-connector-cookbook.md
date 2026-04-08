# Adoption Connector Cookbook (Production)

This cookbook shows repeatable connector setups for existing memory stacks.

## 1) Resolve connector template with project overrides

```bash
curl -X POST "http://localhost:8080/v1/adoption/import-connectors/resolve" \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "postgres_sql",
    "connector_id": "postgres_sql:ops_kb_items:polling",
    "project_id": "omega_demo",
    "field_overrides": {
      "sql_dsn_env": "HW_MEMORY_DSN",
      "max_records": 5000,
      "chunk_size": 100,
      "curated_import.noise_preset": "balanced",
      "curated_import.drop_event_like": true
    }
  }'
```

Use `validation_hints.errors` as hard blockers and `validation_hints.warnings` as rollout checks.

## 2) Polling mode (cron)

1. Upsert source using the resolved `config_patch`.
2. Run scheduler every 5 minutes.

```bash
*/5 * * * * cd /srv/synapse && python services/worker/scripts/run_legacy_sync_scheduler.py --all-projects
```

Recommended for stable SQL schemas and low operational complexity.

## 3) WAL CDC mode (near realtime)

Use connector id `postgres_sql:<profile>:wal_cdc` and provide:

- `wal_slot`
- `wal_publication`
- optional `wal_tables`

Run scheduler every minute (or continuous worker loop if your environment supports it).

## 4) Curated import dry-run before first ingest

```bash
curl -X POST "http://localhost:8080/v1/backfill/curated-explain?sample_limit=12" \
  -H "Content-Type: application/json" \
  -d @sample_backfill_payload.json
```

Inspect:

- `summary.drop_reasons`
- `samples.dropped[]`
- `apply_payload_template`

Then submit the same curated profile to `/v1/backfill/knowledge`.

## 5) First-day quality loop

1. `GET /v1/adoption/pipeline/visibility`
2. `GET /v1/adoption/rejections/diagnostics`
3. `GET /v1/adoption/policy-calibration/quick-loop`
4. `POST /v1/adoption/policy-calibration/quick-loop/apply` (`dry_run=true` first)
5. `GET /v1/adoption/kpi`

This sequence gives deterministic onboarding quality without DB forensics.

## 6) Memory API connector (no custom importer)

Use built-in connector `memory_api:generic:polling`:

```bash
curl -X POST "http://localhost:8080/v1/adoption/import-connectors/resolve" \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "memory_api",
    "connector_id": "memory_api:generic:polling",
    "project_id": "omega_demo",
    "field_overrides": {
      "api_url": "https://memory.company/v1/items",
      "api_headers.Authorization": "env:MEMORY_API_TOKEN",
      "api_mapping.content": "text",
      "api_mapping.entity_key": "entity.id"
    }
  }'
```

Then upsert source with `source_type=memory_api` and queue sync.

## 7) First-run wiki bootstrap

After first curated batch, create starter pages in one call:

```bash
curl -X POST "http://localhost:8080/v1/adoption/first-run/bootstrap" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "omega_demo",
    "created_by": "ops_manager",
    "profile": "support_ops",
    "publish": true
  }'
```

Default pages: `Agent Profile`, `Data Map`, `Operational Runbook` (+ support escalation page for `support_ops`).

## 8) One-command enterprise sync preset

```bash
curl -X POST "http://localhost:8080/v1/adoption/sync-presets/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "omega_demo",
    "updated_by": "ops_manager",
    "reviewed_by": "ops_manager",
    "dry_run": false,
    "confirm_project_id": "omega_demo",
    "preset_key": "enterprise_curated_safe",
    "apply_bootstrap_profile": true,
    "queue_enabled_sources": true,
    "run_bootstrap_approve": true,
    "include_starter_pages": true,
    "starter_profile": "support_ops"
  }'
```

This is the fastest path for enterprise onboarding: profile apply + source queue + curated bootstrap approve + starter wiki pages.
