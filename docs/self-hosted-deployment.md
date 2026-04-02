# Self-Hosted Deployment Guide (API + Worker + MCP)

Last updated: 2026-04-02

This guide runs Synapse core services in Docker Compose with production-like defaults:
- PostgreSQL (`pgvector`)
- API (`services/api`)
- Worker loop (`services/worker`)
- MCP runtime (`services/mcp`)

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
- Containers `synapse-api`, `synapse-worker`, `synapse-mcp`, `synapse-postgres` are `Up`.

## 5. Core Loop Smoke Test

From repository root:

```bash
./scripts/integration_core_loop.py
```

This validates the core path end-to-end:
`ingest -> synthesis draft -> moderation approve -> MCP retrieval`.

For a clean compose-profile acceptance (startup + acceptance + teardown):

```bash
./scripts/run_selfhost_core_acceptance.sh
```

CI opt-in path:

1. `workflow_dispatch` in `.github/workflows/ci.yml` with input `run_selfhost_acceptance=true`.
2. `workflow_dispatch` in `.github/workflows/ci.yml` with input `run_selfhost_dr_drill=true` (backup/restore drill against live compose stack).
3. Local CI toggles:
   - `SYNAPSE_RUN_SELFHOST_CORE_ACCEPTANCE=1 ./scripts/ci_checks.sh`
   - `SYNAPSE_RUN_SELFHOST_DR_ACCEPTANCE=1 ./scripts/ci_checks.sh`

## 6. Operations

Restart services:

```bash
docker compose --env-file .env.selfhost -f infra/docker-compose.selfhost.yml restart api worker mcp
```

View logs:

```bash
docker compose --env-file .env.selfhost -f infra/docker-compose.selfhost.yml logs -f api worker mcp
```

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

## 7. Backup and Restore (PostgreSQL)

Backup:

```bash
docker exec synapse-postgres pg_dump -U "${POSTGRES_USER:-synapse}" "${POSTGRES_DB:-synapse}" > synapse-backup.sql
```

Restore:

```bash
cat synapse-backup.sql | docker exec -i synapse-postgres psql -U "${POSTGRES_USER:-synapse}" "${POSTGRES_DB:-synapse}"
```

Automated backup/restore drill (dump -> restore into temporary Postgres -> row-count parity check):

```bash
./scripts/run_selfhost_backup_restore_drill.sh --env-file .env.selfhost
```

Full DR acceptance (clean compose stack + seed API data + backup/restore drill):

```bash
./scripts/run_selfhost_dr_ci_acceptance.sh --report-file artifacts/selfhost-dr/report.json
```

Detailed runbook:
- `/Users/maksimborisov/synapse/docs/backup-restore-drill.md`

## 8. Production Hardening Checklist

1. Put API and MCP behind TLS reverse proxy (Nginx/Traefik/Cloudflare Tunnel).
2. Restrict network exposure (no direct Postgres access from public internet).
3. Set strict `SYNAPSE_UI_ORIGINS` and secret-managed environment values.
4. Enable external logging/metrics pipeline (OpenTelemetry and container logs).
5. Schedule regular DB backups and restore drills.

## 9. Optional SDK Observability Stack

For a local OpenTelemetry dashboard stack (collector + Prometheus + Tempo + Grafana) and Datadog quick pack:

- `/Users/maksimborisov/synapse/docs/sdk-trace-observability.md`
- `/Users/maksimborisov/synapse/infra/observability/README.md`
