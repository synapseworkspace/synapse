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
    "max_records": 5000,
    "chunk_size": 100
  }
}
```

Discover available profiles:

- `GET /v1/legacy-import/profiles?source_type=postgres_sql`

## Memory Tier Routing (Default Safety)

Synapse now treats runtime streams as a separate memory tier by default:

- raw event-like memory (`orders`, `status updates`, `telemetry`, `trace/log style`) is routed to `operational_memory`;
- only reusable, policy-grade facts are promoted into draft/wiki flow;
- single-source one-off observations are held back unless policy/incident signals are present.

Tune via Gatekeeper config `routing_policy` (`GET/PUT /v1/gatekeeper/config`):

- `blocked_category_keywords`
- `blocked_source_system_keywords`
- `event_stream_token_keywords`
- `event_stream_min_numeric_token_ratio`
- `event_stream_min_token_hits`
- `require_multi_source_for_wiki`
- `min_sources_for_wiki_candidate`
- `min_evidence_for_wiki_candidate`
- `allow_policy_or_incident_override`

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
