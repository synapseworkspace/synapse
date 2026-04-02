# Synapse Troubleshooting Guide

Last updated: 2026-04-02

This guide covers common failures for self-hosted core stack (`api`, `worker`, `mcp`, `web`, `postgres`).

## 1) API Does Not Start

Symptoms:
- `uvicorn` exits on startup.
- `500` responses from `/healthz` or schema errors.

Checks:
1. Verify environment:
   - `API_HOST`, `API_PORT`, `DATABASE_URL`
2. Run migrations:
   - `./scripts/apply_migrations.sh`
3. Confirm DB connectivity from API container/venv:
   - `python -c "import psycopg; print('ok')"`
4. Confirm import path:
   - `PYTHONPATH=services/api python -c "from app.main import app; print('ok')"`

Recovery:
1. Re-apply migrations (safe/idempotent scripts only).
2. Restart API process after DB is healthy.
3. If startup fails after route/model changes, check recent response-model typing on affected endpoint.

## 2) Worker Not Producing Drafts

Symptoms:
- New events exist, but Draft Inbox remains empty.
- `claim_proposals` grows without `wiki_draft_changes`.

Checks:
1. Worker process is running:
   - `PYTHONPATH=services/worker python services/worker/scripts/run_wiki_synthesis.py --limit 10 --cycles 1`
2. Gatekeeper config is not over-restrictive for project.
3. `events` and `claim_proposals` rows are being inserted for target `project_id`.

Recovery:
1. Run single-cycle synthesis manually and inspect logs.
2. Lower temporary gatekeeper thresholds to unblock triage.
3. Validate proposal evidence quality (source diversity, temporal validity, conflict state).

## 3) MCP Runtime Returns Empty Results

Symptoms:
- `search_knowledge` / `get_entity_facts` returns empty list unexpectedly.
- Agents do not receive approved knowledge context.

Checks:
1. MCP server process:
   - `PYTHONPATH=services/mcp python services/mcp/scripts/run_mcp_server.py --transport stdio`
2. Knowledge exists and is approved (`knowledge_snapshots`/wiki pages).
3. Project scoping:
   - caller `project_id` matches moderation target project.
4. Retrieval filters:
   - `entity_key`, `category`, `page_type`, graph hop settings.

Recovery:
1. Retry with minimal filter set (`query + project_id` only).
2. Confirm cache invalidation path after new approvals.
3. Run retrieval regression check:
   - `PYTHONPATH=services/mcp python scripts/eval_mcp_retrieval_regression.py --dataset eval/mcp_retrieval_cases.json`

## 4) CORS / Web UI Cannot Reach API

Symptoms:
- Draft Inbox stuck loading.
- Browser console reports CORS/network failures.

Checks:
1. API base URL in web env (`VITE_API_BASE_URL`).
2. API CORS settings include current web origin.
3. Browser/network can resolve target host and port.

Recovery:
1. Set explicit local origin allowlist for web dev URL.
2. Restart API/web after env updates.
3. Validate with direct curl to API endpoint from same machine.

## 5) Migration Failures

Symptoms:
- `duplicate column`, `relation already exists`, lock timeout, or partial apply.

Checks:
1. Migration order and latest applied version.
2. Long-running transactions on the same tables.
3. Disk pressure / Docker VM saturation.

Recovery:
1. Stop write-heavy workloads temporarily.
2. Re-run migration script after lock clears.
3. For partial apply, inspect migration SQL and reconcile state before rerun.

## 6) Observability Signals Missing

Symptoms:
- Grafana dashboard empty.
- No `synapse_*` metrics in Prometheus/Datadog.

Checks:
1. OTel endpoint (`OTEL_EXPORTER_OTLP_ENDPOINT`) is reachable.
2. SDK telemetry sink is configured in runtime.
3. Collector + Prometheus containers healthy.
4. Datadog API/app keys and monitor payload import status.

Recovery:
1. Emit synthetic SDK telemetry:
   - `PYTHONPATH=packages/synapse-sdk-py/src python scripts/run_sdk_otel_smoke.py`
2. Validate local stack config:
   - `docker compose -f infra/observability/docker-compose.sdk-observability.yml config`
3. Validate Prometheus rules:
   - `promtool check rules infra/observability/prometheus-rules-sdk-alerts.yaml`

## 7) Fast Diagnostic Checklist

1. `./scripts/ci_checks.sh` (or `SYNAPSE_SKIP_WEB_E2E=1 ./scripts/ci_checks.sh` for quick local loop).
2. Confirm DB, API, worker, MCP processes are all up.
3. Run one deterministic end-to-end scenario:
   - `./scripts/integration_core_loop.py`
4. Validate OpenClaw integration path:
   - `PYTHONPATH=packages/synapse-sdk-py/src python scripts/integration_openclaw_mcp_runtime.py --check`
