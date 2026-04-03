# synapse-worker

Background worker for synthesis pipeline:

1. Extract claims from observations.
2. Deduplicate and cluster candidate facts.
3. Detect conflicts with published claims.
4. Generate Markdown draft pages.

## Current executable pipeline

`run_wiki_synthesis.py` processes queued rows from `claim_proposals` and writes:

- `wiki_draft_changes` (review queue with markdown patch + semantic diff)
- `wiki_conflicts` (when contradictions are detected)
- `wiki_claim_links` (traceability from claim to page/section)
- `claims` upserts (canonical claim record)
- `event_pipeline_state` (checkpoint for `memory_backfill` extraction)
- `memory_backfill_batches` progress (`processed_events`, `generated_claims`, status transitions)

Temporal behavior:
- infers claim validity windows from text (`until`, `from`, `between` patterns; explicit payload fields win),
- checks conflicts and dedup only across overlapping validity windows,
- auto-supersedes expired active statements when processing new claims for a section.
- infers missing `entity_key` and `category` for `memory_backfill` events via multilingual keyword/pattern logic, with fallback to deterministic `memory_<source_id>` keys.

Run locally:

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_wiki_synthesis.py --extract-limit 200 --limit 100 --cycles 1
```

Auto-publish policy runner (hybrid human/autonomous publication):

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_wiki_autopublish.py \
  --api-url http://localhost:8080 \
  --project-id omega_demo \
  --limit-per-project 50
```

Policy is controlled via `gatekeeper_project_configs`:
- `publish_mode_default`: `human_required|conditional|auto_publish`
- `publish_mode_by_category`: per-category overrides
- conditional thresholds: `auto_publish_min_score`, `auto_publish_min_sources`, `auto_publish_require_golden`

Production-like loop runner (used by self-hosted Docker stack):

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_worker_loop.py
```

## Knowledge Intelligence job

Daily digest + metrics generator:

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_intelligence_digest.py --project-id omega_demo --date 2026-03-31
```

Weekly digest + trend breakdown:

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_intelligence_digest.py --project-id omega_demo --kind weekly --date 2026-03-31
```

Incident escalation digest (daily pulse for unresolved over-SLA queue incidents):

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_intelligence_digest.py \
  --project-id omega_demo \
  --kind incident_escalation_daily \
  --date 2026-03-31 \
  --incident-sla-hours 24 \
  --top-n 10
```

Useful flags:
- `--all-projects` to auto-discover projects.
- `--date YYYY-MM-DD` target day (default is yesterday UTC).
- `--generated-by` actor label stored in digest metadata.

Digest delivery runner:

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_intelligence_delivery.py --project-id omega_demo --kind daily
```

Incident escalation delivery runner:

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_intelligence_delivery.py \
  --project-id omega_demo \
  --kind incident_escalation_daily
```

Delivery target config supports routing by digest kind and escalation gating:
- `digest_kinds`: optional list (`daily`, `weekly`, `incident_escalation_daily`) to scope a target to specific digests.
- `incident_escalation_require_over_sla`: defaults to `true`; when enabled, incident escalation digest is skipped for this target if there are no over-SLA open incidents.

Unified scheduler (generate + deliver):

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_intelligence_scheduler.py --all-projects
```

Weekly scheduler run:

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_intelligence_scheduler.py --all-projects --generate-kind weekly --delivery-kind weekly
```

Incident escalation scheduler run:

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_intelligence_scheduler.py \
  --all-projects \
  --generate-kind incident_escalation_daily \
  --delivery-kind incident_escalation_daily \
  --incident-sla-hours 24 \
  --top-n 10
```

Synthesis regression evaluator:

```bash
PYTHONPATH=services/worker python scripts/eval_synthesis_regression.py --dataset eval/synthesis_cases.json
```

Gatekeeper regression evaluator:

```bash
PYTHONPATH=services/worker python scripts/eval_gatekeeper_regression.py --dataset eval/gatekeeper_cases.json
```

Gatekeeper LLM threshold calibration (train/holdout search):

```bash
PYTHONPATH=services/worker python scripts/calibrate_gatekeeper_llm_thresholds.py \
  --dataset eval/gatekeeper_cases.json \
  --holdout-ratio 0.3 \
  --weights 0.2,0.3,0.35,0.4,0.5 \
  --confidences 0.6,0.65,0.7,0.75 \
  --score-thresholds 0.68,0.72,0.76 \
  --force-llm-assist
```

Build production-like holdout dataset from DB decisions + moderation labels:

```bash
python scripts/build_gatekeeper_holdout_from_db.py \
  --database-url postgresql://synapse:synapse@localhost:55432/synapse \
  --lookback-days 60 \
  --output eval/gatekeeper_cases_from_db.json
```

Calibrate on DB-derived holdout:

```bash
PYTHONPATH=services/worker python scripts/calibrate_gatekeeper_llm_thresholds.py \
  --dataset eval/gatekeeper_cases_from_db.json \
  --holdout-ratio 0.3 \
  --force-llm-assist \
  --output /tmp/gatekeeper-calibration-report.json
```

Apply recommended config via API:

```bash
python scripts/apply_gatekeeper_calibration.py \
  --report /tmp/gatekeeper-calibration-report.json \
  --project-id omega_demo \
  --api-url http://localhost:8080
```

Run full production calibration cycle per project (build -> calibrate -> apply -> snapshot):

```bash
python scripts/run_gatekeeper_calibration_cycle.py \
  --project-id omega_demo \
  --database-url postgresql://synapse:synapse@localhost:55432/synapse \
  --api-url http://localhost:8080 \
  --lookback-days 60 \
  --allow-guardrail-fail
```

Scheduled calibration sweep (nightly/weekly presets + regression alerts):

```bash
python scripts/run_gatekeeper_calibration_scheduler.py \
  --schedules-json '{
    "schedules": [
      {"project_id":"omega_demo","preset":"nightly"},
      {"project_id":"beta_demo","preset":"weekly","lookback_days":90}
    ]
  }' \
  --database-url postgresql://synapse:synapse@localhost:55432/synapse \
  --api-url http://localhost:8080 \
  --alert-webhook-url "$SYNAPSE_ALERT_SLACK_WEBHOOK" \
  --fail-on-alert
```

Run schedules persisted in API (`gatekeeper_calibration_schedules` table):

```bash
python scripts/run_gatekeeper_calibration_scheduler.py \
  --use-api-schedules \
  --api-url http://localhost:8080 \
  --database-url postgresql://synapse:synapse@localhost:55432/synapse \
  --use-db-alert-targets
```

Disable run-history persistence if needed:

```bash
python scripts/run_gatekeeper_calibration_scheduler.py \
  --use-api-schedules \
  --no-persist-run-history
```

Offline preview mode (without DB checks):

```bash
python scripts/run_gatekeeper_calibration_scheduler.py \
  --dry-run \
  --skip-due-check \
  --schedules-json '{"schedules":[{"project_id":"omega_demo","preset":"nightly"}]}'
```

Process queued calibration operations created via API (`POST /v1/gatekeeper/calibration/operations/queue`):

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_gatekeeper_calibration_operation_queue.py --limit 10
```

Scheduled incident sync worker entrypoint (reuses API preflight enforcement gate `inherit|off|block|pause`):

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_queue_incident_sync_scheduler.py \
  --all-projects \
  --api-url http://localhost:8080 \
  --requested-by incident_sync_scheduler \
  --preflight-enforcement-mode inherit \
  --batch-size 50
```

Run persisted incident-sync schedules from API (due windows + per-schedule run options):

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_queue_incident_sync_scheduler.py \
  --use-api-schedules \
  --all-projects \
  --api-url http://localhost:8080 \
  --requested-by incident_sync_scheduler \
  --schedule-limit 50
```

Dry-run preview without side effects:

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_queue_incident_sync_scheduler.py \
  --project-id omega_demo \
  --dry-run \
  --preflight-enforcement-mode block
```

Weekly drift monitor (exit code 1 on alert):

```bash
python scripts/monitor_gatekeeper_drift.py \
  --database-url postgresql://synapse:synapse@localhost:55432/synapse \
  --project-id omega_demo \
  --window-days 7
```

Rollback safety flow (preview impact + dual approval via API):

```bash
curl -s -X POST http://localhost:8080/v1/gatekeeper/config/rollback/preview \
  -H 'content-type: application/json' \
  -d '{"project_id":"omega_demo","snapshot_id":"<snapshot_uuid>","lookback_days":30,"limit":5000,"sample_size":25}'
```

## Agent Simulator sandbox

Replay policy changes on historical sessions before rollout:

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_agent_simulator.py \
  --project-id omega_demo \
  --policy-file ./policies.json \
  --lookback-days 14 \
  --max-sessions 200
```

Dry run (no DB writes):

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_agent_simulator.py \
  --project-id omega_demo \
  --policy-file ./policies.json \
  --dry-run
```

Process queued simulator jobs created via API (`POST /v1/simulator/runs`):

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_agent_simulator_queue.py --limit 10
```

Template + preset scheduler (recurring risk checks):

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_agent_simulator_scheduler.py \
  --schedules-file ./simulator_schedules.json
```

Dry-run preview (no DB writes):

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_agent_simulator_scheduler.py \
  --dry-run \
  --schedules-json '{"schedules":[{"project_id":"omega_demo","template_id":"gate_access_card_only","template_params":{"entity_key":"bc_omega"},"preset":"daily"}]}'
```

## Legacy Import (Cold Start)

Parse legacy docs (`.txt/.md/.csv/.json/.jsonl/.xlsx/.pdf`) and upload them as `memory_backfill` batches:

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_legacy_import.py \
  --input-dir /path/to/legacy_docs \
  --project-id omega_demo \
  --api-url http://localhost:8080 \
  --source-system legacy_import
```

All imported records are automatically enriched with deterministic wiki seed metadata:
- `metadata.synapse_seed_plan` (space/page/section hints).
- `metadata.synapse_source_provenance` (source/run traceability fingerprints).

Import from Notion page tree (recursive) via Notion API:

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_legacy_import.py \
  --notion-root-page-id 1f6bc5c4d0aa4fb8a55ff4bdf2e0e123 \
  --notion-token "$NOTION_TOKEN" \
  --project-id omega_demo \
  --api-url http://localhost:8080 \
  --source-system notion_import
```

Import from Notion database:

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_legacy_import.py \
  --notion-database-id 2f74f5a9f4a344f8b61a7f39302b5e4b \
  --notion-token "$NOTION_TOKEN" \
  --project-id omega_demo \
  --api-url http://localhost:8080
```

Dry-run parser preview without upload:

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_legacy_import.py \
  --input-dir /path/to/legacy_docs \
  --project-id omega_demo \
  --dry-run
```

Deterministic seed-planning QA (golden fixtures for grouping/section/page targeting):

```bash
PYTHONPATH=services/worker python3 scripts/eval_legacy_seed_regression.py --summary-only
```

## Legacy Sync Scheduler (Periodic Refresh)

Process configured legacy sources on schedule (enqueue due + process queue):

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_legacy_sync_scheduler.py \
  --all-projects \
  --enqueue-limit 20 \
  --process-limit 20 \
  --api-url http://localhost:8080
```

Per-source `config` supports seed-orchestration knobs:
- `seed_page_prefix`
- `seed_space_key`
- `seed_group_mode` (`entity|category|category_entity`)
- `seed_section_overrides`

Queue-only mode:

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_legacy_sync_scheduler.py \
  --all-projects \
  --skip-process
```

Process-only mode:

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_legacy_sync_scheduler.py \
  --skip-enqueue \
  --process-limit 50
```

## Gatekeeper runtime config

Worker reads per-project gatekeeper thresholds from `gatekeeper_project_configs` on each claim decision.
Update these thresholds via API (`PUT /v1/gatekeeper/config`) to tune promotion behavior without worker redeploy.

LLM-assisted Gatekeeper is optional and configured in the same endpoint:
- `llm_assist_enabled`
- `llm_provider` (`openai`)
- `llm_model`
- `llm_score_weight`
- `llm_min_confidence`
- `llm_timeout_ms`

Runtime safety:
- If LLM is disabled, unavailable, or errors, worker falls back to deterministic heuristics.
- Set `OPENAI_API_KEY` (and optional `OPENAI_BASE_URL`) in worker runtime to enable OpenAI classifier calls.
