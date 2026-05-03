# Self-Hosted Deployment Guide (API + Worker + MCP + Web)

Last updated: 2026-04-09

This guide runs Synapse core services in Docker Compose with production-like defaults:
- PostgreSQL (`pgvector`)
- API (`services/api`)
- Worker loop (`services/worker`)
- MCP runtime (`services/mcp`)
- Web UI (`apps/web`, default wiki-first route)

Networking default:
- Compose binds API/MCP/Postgres ports to `127.0.0.1` by default via `SYNAPSE_BIND_HOST`.
- Keep this for local/staging unless you intentionally expose services behind a secure ingress.

## 1. Prerequisites

- Docker Engine + Docker Compose plugin
- At least 4 vCPU / 8 GB RAM for stable local or staging runs

## 2. Configure Environment

From repository root:

```bash
cp .env.selfhost.example .env.selfhost
```

Minimum required edits in `.env.selfhost`:

1. Set a strong `POSTGRES_PASSWORD`.
2. Set `SYNAPSE_UI_ORIGINS` to allowed frontend origins (do not leave `*` in production).
3. Optional: set `OPENAI_API_KEY` if you use LLM-assisted Gatekeeper mode.
4. Optional: set `SYNAPSE_OPENCLAW_PROVENANCE_SECRET` for signed OpenClaw evidence provenance.
5. Keep `SYNAPSE_BIND_HOST=127.0.0.1` unless you intentionally expose services outside localhost.
6. Daily agent reports are enabled by default in worker loop (`SYNAPSE_WORKER_ENABLE_AGENT_WORKLOGS=1`) and generated every 24h (`SYNAPSE_WORKER_AGENT_WORKLOGS_INTERVAL_SEC=86400`) with per-project local timezone schedule support.
7. Realtime worklog refresh is enabled by default (`SYNAPSE_WORKER_ENABLE_AGENT_WORKLOGS_REALTIME=1`) and reacts to recent session/task close signals.

## 3. Boot the Stack

```bash
docker compose --env-file .env.selfhost -f infra/docker-compose.selfhost.yml up -d --build
```

The stack runs migrations automatically through `migrator` before API/worker/MCP start.

## 4. Health Checks

```bash
docker compose --env-file .env.selfhost -f infra/docker-compose.selfhost.yml ps
curl -fsS http://localhost:8080/health
```

Expected:
- API responds with `{"status":"ok"}`.
- Services `api`, `worker`, `web`, `mcp`, `postgres` are `Up`.

## 5. Verify UI Routes (Wiki vs Operations)

Open the bundled web service and validate the route split:

1. Wiki-first workspace:
   - `http://localhost:4173/wiki?project=omega_demo`
2. Draft inbox (clean mode):
   - `http://localhost:4173/wiki?project=omega_demo&core_tab=drafts`
3. Operations route (migration/gatekeeper tools):
   - `http://localhost:4173/operations?project=omega_demo&core_tab=drafts`
4. BasePath-safe route (reverse-proxy friendly):
   - `http://localhost:4173/synapse/wiki?project=omega_demo`

Expected behavior:
- `Drafts` under `/wiki` stays inbox/detail focused.
- Migration and bootstrap controls appear on `/operations`.
- `/synapse/...` path works without rebuilding frontend assets.
- Reviewer/notifications controls are in `Settings` drawer (not in the core first viewport).

Reverse-proxy contract for base-path deployments:
- `/synapse/build.json` must be served as a real JSON file from the Synapse `web` origin.
- `/synapse/assets/*` must be served directly from the same Synapse `web` origin and must not be rewritten to another static site or stale bundle.
- SPA fallback (`/synapse/wiki`, `/synapse/operations`, nested review URLs) may resolve to `index.html`, but `build.json` and `/assets/*` must remain file-backed paths.
- `index.html` / SPA fallback responses should be non-cacheable, while hashed `/assets/*` responses should remain long-cache immutable.

Supported self-host workspace entry forms:
- `/synapse/wiki`
- `/synapse/wiki/<page-slug>`
- `/synapse/wiki?wiki_page=<slug>&wiki_space=<space>`
- `/synapse/?wiki_page=<slug>&wiki_space=<space>`
- `/synapse/operations`

These should all resolve against the same live web bundle and should not trigger route-context warnings when the page/query context is valid.

## 6. Core Loop Smoke Test

From repository root:

```bash
./scripts/integration_core_loop.py
```

This validates the core path end-to-end:
`ingest -> synthesis draft -> moderation approve -> MCP retrieval`.

Legacy connector queue smoke (worker scheduler + queued run processing + adoption pipeline):

```bash
./scripts/integration_legacy_sync_queue_processing.py --api-url http://localhost:8080
```

For a clean compose-profile acceptance (startup + acceptance + teardown):

```bash
./scripts/run_selfhost_core_acceptance.sh
```

Recommended adoption operator pass (dry-run first):

```bash
synapse-cli adoption connect-source --api-url http://localhost:8080 --project-id omega_demo --updated-by ops_admin --connector-id postgres_sql:ops_kb_items:polling --field-overrides-json '{"sql_dsn_env":"OPS_PG_DSN"}'
synapse-cli adoption sync-preset --api-url http://localhost:8080 --project-id omega_demo --updated-by ops_admin --with-pipeline
synapse-cli adoption rejections --api-url http://localhost:8080 --project-id omega_demo --days 14 --sample-limit 5
synapse-cli adoption enterprise-readiness --api-url http://localhost:8080 --project-id omega_demo
```

CI opt-in path:

1. `workflow_dispatch` in `.github/workflows/ci.yml` with input `run_selfhost_acceptance=true`.
2. `workflow_dispatch` in `.github/workflows/ci.yml` with input `run_selfhost_dr_drill=true` (backup/restore drill against live compose stack).
3. `workflow_dispatch` in `.github/workflows/ci.yml` with input `run_selfhost_chaos_drill=true` (dependency-fault injection drill with recovery checks).
4. Local CI toggles:
   - `SYNAPSE_RUN_SELFHOST_CORE_ACCEPTANCE=1 ./scripts/ci_checks.sh`
   - `SYNAPSE_RUN_SELFHOST_DR_ACCEPTANCE=1 ./scripts/ci_checks.sh`
   - `SYNAPSE_RUN_SELFHOST_CHAOS_DRILL=1 ./scripts/ci_checks.sh`

## 7. Operations

Restart services:

```bash
docker compose --env-file .env.selfhost -f infra/docker-compose.selfhost.yml restart api worker web mcp
```

View logs:

```bash
docker compose --env-file .env.selfhost -f infra/docker-compose.selfhost.yml logs -f api worker mcp
```

Look for `agent_worklog_scheduler` events in worker logs to confirm daily-report sync runs.

Scale worker replicas (for higher ingestion throughput):

```bash
docker compose --env-file .env.selfhost -f infra/docker-compose.selfhost.yml up -d --scale worker=2
```

Run guided performance tuning (worker + queue + MCP graph):

```bash
python3 scripts/run_performance_tuning_advisor.py \
  --project-id omega_demo \
  --write-report artifacts/perf/omega_demo.md \
  > artifacts/perf/omega_demo.json
```

Runbook reference:
- `/Users/maksimborisov/synapse/docs/performance-tuning.md`

## 8. Backup and Restore (PostgreSQL)

Backup:

```bash
docker compose --env-file .env.selfhost -f infra/docker-compose.selfhost.yml exec -T postgres \
  pg_dump -U "${POSTGRES_USER:-synapse}" "${POSTGRES_DB:-synapse}" > synapse-backup.sql
```

Restore:

```bash
cat synapse-backup.sql | docker compose --env-file .env.selfhost -f infra/docker-compose.selfhost.yml exec -T postgres \
  psql -U "${POSTGRES_USER:-synapse}" "${POSTGRES_DB:-synapse}"
```

Automated backup/restore drill (dump -> restore into temporary Postgres -> row-count parity check):

```bash
./scripts/run_selfhost_backup_restore_drill.sh --env-file .env.selfhost
```

Full DR acceptance (clean compose stack + seed API data + backup/restore drill):

```bash
./scripts/run_selfhost_dr_ci_acceptance.sh --report-file artifacts/selfhost-dr/report.json
```

Automated chaos/recovery drill (baseline core loop + fault injection + post-fault core loop checks):

```bash
./scripts/run_selfhost_chaos_drill.sh --report-file artifacts/selfhost-chaos/report.json
```

Detailed runbook:
- `/Users/maksimborisov/synapse/docs/backup-restore-drill.md`

## 9. Production Hardening Checklist

1. Put API and MCP behind TLS reverse proxy (Nginx/Traefik/Cloudflare Tunnel).
2. Restrict network exposure (no direct Postgres access from public internet).
3. Set strict `SYNAPSE_UI_ORIGINS` and secret-managed environment values.
4. Enable external logging/metrics pipeline (OpenTelemetry and container logs).
5. Schedule regular DB backups and restore drills.

## 10. Optional SDK Observability Stack

For a local OpenTelemetry dashboard stack (collector + Prometheus + Tempo + Grafana) and Datadog quick pack:

- `/Users/maksimborisov/synapse/docs/sdk-trace-observability.md`
- `/Users/maksimborisov/synapse/infra/observability/README.md`

UI visual reference (from CI snapshot artifacts):
- `/Users/maksimborisov/synapse/docs/wiki-ui-visual-gallery.md`
