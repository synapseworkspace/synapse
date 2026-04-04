# Legacy Sync Orchestration

Synapse supports periodic refresh of legacy knowledge sources (local directories, Notion, and PostgreSQL SQL pulls) via source configuration + queued sync runs.

## Data model

- `legacy_import_sources`: configured sync sources and cadence.
- `legacy_import_sync_runs`: run queue and execution history.
- `legacy_import_source_fingerprints`: cross-run content fingerprint index for duplicate suppression.

## Configure a source (API)

```bash
curl -sS -X PUT http://localhost:8080/v1/legacy-import/sources \
  -H 'Content-Type: application/json' \
  -d '{
    "project_id": "omega_demo",
    "source_type": "notion_root_page",
    "source_ref": "1f6bc5c4d0aa4fb8a55ff4bdf2e0e123",
    "enabled": true,
    "sync_interval_minutes": 240,
    "updated_by": "ops_admin",
    "config": {
      "notion_token_env": "NOTION_TOKEN",
      "notion_max_pages": 300,
      "max_records": 5000,
      "chunk_size": 100,
      "seed_page_prefix": "legacy",
      "seed_space_key": "notion",
      "seed_group_mode": "category_entity",
      "seed_section_overrides": {
        "access_policy": {"section_key": "controls", "section_heading": "Access Controls"}
      }
    }
  }'
```

List sources:

```bash
curl -sS "http://localhost:8080/v1/legacy-import/sources?project_id=omega_demo"
```

List built-in Postgres profiles:

```bash
curl -sS "http://localhost:8080/v1/legacy-import/profiles?source_type=postgres_sql"
```

Configure PostgreSQL source (custom memory tables without custom importer script):

Zero-config profile mode (recommended for `ops_kb_items` / `memory_items`):

```bash
curl -sS -X PUT http://localhost:8080/v1/legacy-import/sources \
  -H 'Content-Type: application/json' \
  -d '{
    "project_id": "omega_demo",
    "source_type": "postgres_sql",
    "source_ref": "hw_memory",
    "enabled": true,
    "sync_interval_minutes": 5,
    "updated_by": "ops_admin",
    "config": {
      "sql_dsn_env": "HW_MEMORY_DSN",
      "sql_profile": "ops_kb_items",
      "max_records": 5000,
      "chunk_size": 100
    }
  }'
```

Advanced custom query mode:

```bash
curl -sS -X PUT http://localhost:8080/v1/legacy-import/sources \
  -H 'Content-Type: application/json' \
  -d '{
    "project_id": "omega_demo",
    "source_type": "postgres_sql",
    "source_ref": "hw_memory_ops",
    "enabled": true,
    "sync_interval_minutes": 30,
    "updated_by": "ops_admin",
    "config": {
      "sql_dsn_env": "HW_MEMORY_DSN",
      "sql_query": "SELECT id::text AS source_id, note AS content, entity_key, category, updated_at AS observed_at, metadata FROM ops_kb_items WHERE updated_at > %(cursor)s ORDER BY updated_at ASC LIMIT 5000",
      "sql_cursor_param": "cursor",
      "sql_cursor_column": "observed_at",
      "sql_cursor_start": "2026-01-01T00:00:00Z",
      "sql_cursor_state_key": "sql_last_cursor",
      "sql_source_id_prefix": "hw_memory",
      "max_records": 5000,
      "chunk_size": 100
    }
  }'
```

Configure low-latency PostgreSQL WAL/CDC mode (same `postgres_sql` source type, no schema-specific importer code):

```bash
curl -sS -X PUT http://localhost:8080/v1/legacy-import/sources \
  -H 'Content-Type: application/json' \
  -d '{
    "project_id": "omega_demo",
    "source_type": "postgres_sql",
    "source_ref": "hw_memory_wal",
    "enabled": true,
    "sync_interval_minutes": 1,
    "updated_by": "ops_admin",
    "config": {
      "sql_sync_mode": "wal_cdc",
      "sql_dsn_env": "HW_MEMORY_DSN",
      "wal_slot": "synapse_hw_slot",
      "wal_plugin": "test_decoding",
      "wal_create_slot_if_missing": true,
      "wal_acknowledge": true,
      "wal_max_changes": 1000,
      "wal_table_allowlist": ["public.ops_kb_items", "public.memory_items"],
      "wal_operation_allowlist": ["insert", "update"],
      "wal_content_fields": ["content", "note", "text"],
      "wal_entity_key_field": "entity_key",
      "wal_category_field": "category",
      "wal_observed_at_field": "updated_at",
      "wal_cursor_state_key": "sql_last_lsn",
      "wal_source_id_prefix": "hw_wal"
    }
  }'
```

## Queue a manual sync run

```bash
curl -sS -X POST http://localhost:8080/v1/legacy-import/sources/<source_id>/sync \
  -H 'Content-Type: application/json' \
  -d '{"project_id":"omega_demo","requested_by":"ops_ui"}'
```

## Run scheduler/processor (worker)

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_legacy_sync_scheduler.py \
  --all-projects \
  --enqueue-limit 20 \
  --process-limit 20 \
  --api-url http://localhost:8080
```

Useful modes:

- `--skip-enqueue`: process only already queued runs.
- `--skip-process`: only queue due sources.
- `--project-id <id>`: scope to a specific project.

## Inspect run history

```bash
curl -sS "http://localhost:8080/v1/legacy-import/runs?project_id=omega_demo&limit=50"
```

Run statuses:

- `queued`
- `running`
- `completed`
- `skipped` (nothing new after fingerprint dedup)
- `failed`

## Seed orchestration config (per source)

The worker applies `LegacySeedOrchestrator` before upload and writes seed metadata to each record.

- `seed_page_prefix` (`legacy` by default): top-level wiki slug segment.
- `seed_space_key` (optional): force target space segment instead of source/category inference.
- `seed_group_mode`: `entity`, `category`, or `category_entity` (default).
- `seed_section_overrides`: optional map `{category -> string|{section_key,section_heading}}`.
  - override keys are normalized through the same category normalization path as records (`ops`/`OPS`/`операции` -> `operations`, `доступ` -> `access_policy`, etc).

SQL source config extras (`source_type=postgres_sql`):

- `sql_dsn` or `sql_dsn_env`: connection DSN (prefer env var).
- `sql_sync_mode`: `polling` (default) or `wal_cdc`.
- `sql_profile`: `ops_kb_items` / `memory_items` / `auto` (recommended quick-start when no custom query is provided).
- `sql_profile_table`: optional table override for profile mode (for example `public.ops_kb_items`).
- `sql_query` or `sql_query_file`: query that returns canonical columns (`source_id`, `content`, optional `entity_key`, `category`, `observed_at`, `metadata`) or use `sql_mapping`.
- `sql_query_params`: optional static SQL parameters object.
- `sql_mapping`: optional column mapping (`source_id_field`, `content_field`, `entity_key_field`, `category_field`, `observed_at_field`, `metadata_fields`, `metadata_static`).
- `sql_cursor_param` + `sql_cursor_column` + `sql_cursor_start` + `sql_cursor_state_key`: incremental polling cursor controls (state persisted in source `config`).

WAL/CDC extras (`sql_sync_mode=wal_cdc`):

- `wal_slot`: logical replication slot name (required).
- `wal_plugin`: replication plugin (`test_decoding` by default, `wal2json` supported with parser mode).
- `wal_parser_mode`: `test_decoding` or `wal2json` (`wal_plugin` is used by default).
- `wal_create_slot_if_missing`: create slot automatically when absent (default: `false`).
- `wal_acknowledge`: use `pg_logical_slot_get_changes` (ack/advance slot) instead of peek mode.
- `wal_max_changes`: max changes pulled per run.
- `wal_table_allowlist`: optional table filter (for example `public.ops_kb_items`).
- `wal_operation_allowlist`: optional operation filter (`insert`, `update`, `delete`).
- `wal_content_fields`: ordered list of payload fields considered as content.
- `wal_entity_key_field`, `wal_category_field`, `wal_observed_at_field`, `wal_source_id_field`: optional field mapping for canonical backfill contract.
- `wal_cursor_state_key`: persisted source config key for last LSN (default `sql_last_lsn`).
- `wal_source_id_prefix`: source id prefix for generated source ids.

Low-latency note:

- `sync_interval_minutes` now supports `1` minute for near-real-time external memory sync runs.
- PostgreSQL prerequisites for logical-slot mode:
  - `wal_level=logical`;
  - replication slot capacity (`max_replication_slots`) sized for your slots;
  - configured output plugin (`test_decoding` or `wal2json`) available in your Postgres runtime.

Run `summary` includes:

- `seed_summary.seed_records`
- `seed_summary.seed_pages`
- `seed_summary.top_pages`
