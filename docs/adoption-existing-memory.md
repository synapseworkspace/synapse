# Adopting Synapse in Existing Memory Stacks

This guide is for teams that already run production agent memory (for example `memory_items`, `ops_kb_items`, custom MCP services) and want to add Synapse without replacing what already works.

## Core Principle

Do **not** replace existing memory first.  
Run Synapse as a **knowledge synthesis and governance layer**:
- existing memory stays source for runtime/episodic state;
- Synapse ingests + synthesizes + moderates;
- approved wiki knowledge becomes policy-grade context for retrieval.

For custom Postgres memory stacks, use native `legacy-import` source type `postgres_sql` (`/v1/legacy-import/sources`) to avoid writing one-off importer scripts. Synapse supports both:
- incremental SQL polling (`sql_sync_mode=polling`, cursor state like `sql_last_cursor`);
- low-latency WAL/CDC ingestion (`sql_sync_mode=wal_cdc`, logical-slot LSN state like `sql_last_lsn`).

## Zero-Config Legacy Memory Profiles

For common schemas (`ops_kb_items`, `memory_items`) you can avoid custom importer scripts and manual SQL mapping:

1. Configure `source_type=postgres_sql`.
1. Set `config.sql_profile` (`ops_kb_items` or `memory_items`; `auto` is supported).
1. Provide DSN (`sql_dsn` or `sql_dsn_env`).

Synapse resolves table + column mapping automatically, generates safe polling SQL, and persists resolved cursor/table metadata back into source config.

```json
{
  "project_id": "omega_demo",
  "source_type": "postgres_sql",
  "source_ref": "hw_memory",
  "updated_by": "ops_admin",
  "config": {
    "sql_dsn_env": "HW_MEMORY_DSN",
    "sql_profile": "ops_kb_items",
    "curated_import": {
      "enabled": true,
      "noise_preset": "balanced",
      "drop_event_like": true
    },
    "max_records": 5000,
    "chunk_size": 100
  }
}
```

Discover available profiles:

- `GET /v1/legacy-import/profiles?source_type=postgres_sql`
- `GET /v1/legacy-import/mapper-templates?source_type=postgres_sql`
- `GET /v1/legacy-import/sync-contracts?source_type=postgres_sql`
- `GET /v1/adoption/import-connectors?source_type=postgres_sql|memory_api` (profile-aware connector catalog with `config_patch`)
- `GET /v1/adoption/noise-presets?lane=knowledge` (reusable preset catalog for snapshot/telemetry suppression)
- `GET /v1/adoption/wiki-space-templates` (role-based wiki structure presets)

SDK parity (no custom importer script):

- Python: `list_legacy_import_profiles`, `list_legacy_import_mapper_templates`, `list_legacy_import_sync_contracts`, `upsert_legacy_import_source`, `queue_legacy_import_source_sync`, `list_legacy_import_sync_runs`
- TypeScript: `listLegacyImportProfiles`, `listLegacyImportMapperTemplates`, `listLegacyImportSyncContracts`, `upsertLegacyImportSource`, `queueLegacyImportSourceSync`, `listLegacyImportSyncRuns`

### Mapper Templates + Sync Contracts (Out of the Box)

For `postgres_sql` sources, Synapse now exposes two explicit contracts:

- **Mapper templates**: ready-to-apply `config_patch` payloads for common schemas (`ops_kb_items`, `memory_items`) and sync modes (`polling`, `wal_cdc`).
- **Sync runner contracts**: required/optional config keys, state keys (`sql_last_cursor`, `sql_last_lsn`), and scheduler contract (`run_legacy_sync_scheduler.py` cadence guidance).

Example:

```bash
curl "http://localhost:8080/v1/legacy-import/mapper-templates?source_type=postgres_sql&profile=ops_kb_items"
curl "http://localhost:8080/v1/legacy-import/sync-contracts?source_type=postgres_sql"
```

This is the canonical way to build cron/CDC sync services without writing one-off importer scripts.

### Curated Import Mode (Namespace/Source Scoping)

For initial migration, you can constrain ingestion before claims are generated:

- batch-level `curated.source_systems[]`
- batch-level `curated.namespaces[]`
- `curated.noise_preset` (`off|balanced|strict|knowledge_v2|order_snapshots|telemetry|raw_event_payloads`)

`/v1/backfill/knowledge` enables curated mode by default (`knowledge_v2`) unless explicitly disabled (`curated.enabled=false`).
The API response returns filter diagnostics (`accepted_input`, `accepted`, `filtered_out`, `curated_filters.drop_reasons`) so teams can tune import scope without DB forensics.
For pre-write simulation and connector validation, add:

- `POST /v1/backfill/curated-explain` to preview `kept/dropped` + drop reasons before writing events.
- `POST /v1/adoption/import-connectors/resolve` to apply connector field overrides and receive validation hints.
- `POST /v1/adoption/first-run/bootstrap` to auto-create starter wiki pages after initial connect (`Agent Profile`, `Data Map`, `Runbook`).
- `POST /v1/adoption/wiki-space-templates/apply` to apply role-based wiki space scaffolding.
- `POST /v1/adoption/sync-presets/execute` for one-command enterprise bootstrap flow.

## Memory Tier Routing (Default Safety)

Synapse now treats runtime streams as a separate memory tier by default:

- raw event-like memory (`orders`, `status updates`, `telemetry`, `trace/log style`) is routed to `operational_memory`;
- only reusable, policy-grade facts are promoted into draft/wiki flow;
- single-source one-off observations are held back unless policy/incident signals are present.

Tune via Gatekeeper config `routing_policy` (`GET/PUT /v1/gatekeeper/config`):

- `blocked_category_keywords`
- `blocked_source_system_keywords`
- `blocked_source_type_keywords`
- `blocked_entity_keywords`
- `blocked_source_id_keywords`
- `event_stream_token_keywords`
- `durable_signal_keywords`
- `event_stream_min_numeric_token_ratio`
- `event_stream_min_token_hits`
- `event_stream_min_kv_hits`
- `min_durable_signal_hits`
- `min_durable_signal_hits_for_backfill`
- `backfill_llm_classifier_mode` (`off|assist|enforce`)
- `backfill_llm_classifier_min_confidence`
- `backfill_llm_classifier_ambiguous_only`
- `backfill_llm_classifier_model` (optional override)
- `publish_mode_by_assertion_class` (`policy|preference|incident|event|fact`)
- `retrieval_feedback_window_days`
- `retrieval_feedback_min_events`
- `retrieval_feedback_block_negative_ratio`
- `retrieval_feedback_block_balance`
- `require_multi_source_for_wiki`
- `min_sources_for_wiki_candidate`
- `min_evidence_for_wiki_candidate`
- `allow_policy_or_incident_override`
- `backfill_requires_policy_signal`

## Coexistence Modes

`Synapse.attach(..., adoption_mode=...)` (Python) / `adoptionMode` (TypeScript):

- `observe_only`:
  - capture/ingest from runtime;
  - no OpenClaw runtime tools registered;
  - safest Day-0 mode.
- `draft_only`:
  - capture + `propose_to_wiki`;
  - no retrieval tool injection yet;
  - good for moderation calibration.
- `retrieve_only`:
  - retrieval/search tools only;
  - no capture hooks/bootstrap writes;
  - use for shadow retrieval checks.
- `full_loop`:
  - full observe -> synthesize -> curate -> execute loop.

## Source Ownership Policy

Define one write-master per knowledge domain:

- `runtime_memory`: existing system is write-master; Synapse is ingest/synthesis consumer.
- `ops_kb_static`: existing system is write-master (or mirrored); Synapse references.
- `synapse_wiki`: Synapse is write-master for approved operational knowledge.

If two systems can mutate the same domain, expect source-of-truth drift.

API support:
- `GET /v1/adoption/source-ownership?project_id=...`
- `PUT /v1/adoption/source-ownership`
- `DELETE /v1/adoption/source-ownership/{domain}?project_id=...`

Runtime enforcement uses `X-Synapse-Source-System` and can run in `off|advisory|enforce` mode per domain.

## Recommended Rollout

1. `observe_only`:
   - enable attach in production;
   - collect drafts and conflict signals;
   - keep agent behavior unchanged.
2. `draft_only`:
   - enable proposal path;
   - moderate drafts and tune gatekeeper thresholds.
   - for trusted migration batches, run bootstrap dry-run + sampled bulk approve:
     - `POST /v1/wiki/drafts/bootstrap-approve/run` with `dry_run=true`;
     - inspect `sample` output and confidence/conflict filters;
     - rerun with `dry_run=false` and conservative `limit`.
3. `retrieve_only` shadow:
   - enable retrieval tools in controlled slice;
   - compare answer quality with existing retrieval path.
4. `full_loop`:
   - enable category-by-category;
   - keep default `auto_publish` for low-risk/high-confidence flows and tune policy (`human_required|conditional|auto_publish`) by risk level.

## Core UI Fast Path (Self-Hosted)

For first adoption in self-hosted mode, use the wiki-first UI without opening advanced controls:

1. Go to `Wiki Tree` and run **Connect Existing Agent Memory** wizard.
2. Open `Drafts` tab.
3. Use **Preview recommended** (auto-fills trusted sources + safe confidence/batch defaults).
4. Review sample candidates.
5. Use **Apply recommended** (same settings, conflict-safe batch).

Preset source:
- `GET /v1/wiki/drafts/bootstrap-approve/recommendation?project_id=...` provides server-side defaults based on
  source ownership, legacy connectors, queue pressure, and backfill quality counters (`dropped_event_like`, `kept_durable`, `trusted_bypass`).

Quick policy + KPI loop:
- `GET /v1/adoption/policy-calibration/quick-loop?project_id=...` for bottleneck-aware routing recommendations.
- `POST /v1/adoption/policy-calibration/quick-loop/apply` (`dry_run=true` first) for safe preset apply with rollback snapshot.
- `GET /v1/adoption/kpi?project_id=...&days=30` for onboarding KPI (`time_to_first_draft`, `time_to_first_publish`, `draft_noise_ratio`, `publish_revert_rate`).

The UI intentionally keeps migration controls collapsed by default and exposes advanced filters only on demand.

## CLI Workflow

Generate a migration plan + snippet:

```bash
synapse-cli adopt \
  --dir . \
  --memory-system ops_kb_items \
  --memory-source hybrid \
  --adoption-mode observe_only \
  --sample-file ./memory_export.jsonl
```

Run retrieval in shadow mode before `full_loop` rollout:

```bash
synapse-cli adopt \
  --dir . \
  --sample-file ./memory_export.jsonl \
  --shadow-retrieval-check \
  --shadow-query "warehouse 2 ramp status" \
  --shadow-query "bc omega gate access" \
  --json
```

Generate attach snippet directly:

```bash
synapse-cli connect openclaw --dir . --adoption-mode observe_only
```

## Operational Guardrails

- Keep `source_id` stable for idempotent backfill and dedup safety.
- Keep provenance metadata enabled (`synapse_provenance`) for auditability.
- Default is `auto_publish` with history + rollback safety; switch to `human_required` for strict review domains.
- Track moderation latency and conflict rates before enabling full-loop rollout.
- For first migration waves, prefer bootstrap-approve in capped batches (`limit`, `min_confidence`, `require_conflict_free`) and keep `dry_run` sampling in the loop.
