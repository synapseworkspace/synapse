# Synapse

Synapse is the cognitive state layer for AI agents: observe, synthesize, curate, and execute knowledge via MCP.

## Start Here

For fastest onboarding, use the guided path:
- [docs/getting-started.md](docs/getting-started.md)

One-command CLI onboarding:

```bash
synapse-cli quickstart --dir . --project-id omega_demo --api-url http://localhost:8080 --doctor-strict
```

Recommended first command (full core loop proof in one run):

```bash
./scripts/run_selfhost_core_acceptance.sh
```

New contributor validation (single command):

```bash
./scripts/run_contributor_guardrails.sh --profile quick
```

Contributor shortcut:
- [docs/contributor-quickstart.md](docs/contributor-quickstart.md)

If you are preparing a public release:
- [docs/oss-publish-checklist.md](docs/oss-publish-checklist.md)
- [docs/release-workflow.md](docs/release-workflow.md)

## Monorepo Layout

- `packages/synapse-schema` - canonical JSON Schemas for Synapse events and claims.
- `packages/synapse-sdk-ts` - TypeScript SDK.
- `packages/synapse-sdk-py` - Python SDK.
- `packages/synapse-openclaw-plugin` - OpenClaw runtime plugin package (`@synapse/openclaw-plugin`).
- `services/api` - ingestion/query API.
- `services/worker` - synthesis pipeline.
- `services/mcp` - MCP runtime server.
- `apps/web` - human-in-the-loop review UI.
- `infra/postgres` - local DB and migrations.

## Quick Local Bootstrap

```bash
cp .env.example .env
cd infra && docker compose up -d
cd ..
./scripts/apply_migrations.sh
cd services/api
python -m venv .venv && source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --port 8080
```

In another terminal:

```bash
./scripts/m1_smoke_e2e.sh
```

Run core loop acceptance (`ingest -> draft -> approve -> MCP retrieval`) against local stack:

```bash
./scripts/integration_core_loop.py
```

Run synthesis worker:

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_wiki_synthesis.py --limit 100 --cycles 1
```

Run daily intelligence digest:

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_intelligence_digest.py --all-projects
```

Run weekly intelligence digest:

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_intelligence_digest.py --all-projects --kind weekly
```

Deliver ready digests:

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_intelligence_delivery.py --kind daily --limit 100
```

Run Agent Simulator sandbox (policy replay on historical sessions):

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_agent_simulator.py \
  --project-id omega_demo \
  --policy-file ./policies.json
```

Process queued simulator runs created via API:

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_agent_simulator_queue.py --limit 10
```

Run legacy sync scheduler (periodic source refresh):

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_legacy_sync_scheduler.py \
  --all-projects \
  --api-url http://localhost:8080
```

Run MCP runtime server (knowledge tools for agents):

```bash
PYTHONPATH=services/mcp python services/mcp/scripts/run_mcp_server.py --transport stdio
```

Run self-hosted core stack (API + worker + MCP + Postgres) in Docker:

```bash
cp .env.selfhost.example .env.selfhost
docker compose --env-file .env.selfhost -f infra/docker-compose.selfhost.yml up -d --build
```

Run clean self-hosted compose acceptance (bring up stack, validate core loop, teardown):

```bash
./scripts/run_selfhost_core_acceptance.sh
```

Run self-hosted disaster-recovery acceptance (clean compose stack + seed + backup/restore drill):

```bash
./scripts/run_selfhost_dr_ci_acceptance.sh --report-file artifacts/selfhost-dr/report.json
```

Run OSS release candidate dress rehearsal (clean-room build/install/import checks):

```bash
./scripts/run_oss_rc_dress_rehearsal.sh --report-file artifacts/release/rc-dress-rehearsal.json
```

Run performance tuning advisor (worker sizing + queue profile + MCP graph knobs):

```bash
python3 scripts/run_performance_tuning_advisor.py --project-id omega_demo --write-report artifacts/perf/omega_demo.md
```

Run local Draft Inbox web UI:

```bash
cd apps/web
npm install
npm run dev
```

UI modes:
- `Core Mode` (default): Draft Inbox + moderation + Task Tracker.
- `Advanced Mode`: calibration, queue, incident, and deep governance controls.

Legacy cold-start import from existing docs:

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_legacy_import.py \
  --input-dir /path/to/legacy_docs \
  --project-id omega_demo \
  --api-url http://localhost:8080
```

Legacy cold-start import from Notion:

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_legacy_import.py \
  --notion-root-page-id <notion_page_id> \
  --notion-token "$NOTION_TOKEN" \
  --project-id omega_demo \
  --api-url http://localhost:8080
```

## SDK Adapters and OpenClaw

- Python SDK supports monitoring wrappers for LangGraph/CrewAI/custom runners and OpenClaw runtimes.
- SDK supports onboarding backfill of existing agent memory (`/v1/backfill/memory`) to seed wiki drafts on day 0.
- Core Agentic Todo API is available (`/v1/tasks*`) with task timeline + links to wiki artifacts.
- Synthesis engine supports temporal validity windows (`valid_from` / `valid_to`) with overlap-aware contradiction handling and retrieval.
- OpenClaw integration plan and implemented connector contract: [docs/openclaw-integration.md](docs/openclaw-integration.md)
- OpenClaw plugin package (`@synapse/openclaw-plugin`): [packages/synapse-openclaw-plugin/README.md](packages/synapse-openclaw-plugin/README.md)
- OpenClaw connectors now emit signed provenance metadata into claim evidence chain (`evidence[].provenance`, `metadata.synapse_provenance`) when provenance secret is configured.
- OpenClaw provenance verification endpoint/script: [docs/openclaw-provenance-verification.md](docs/openclaw-provenance-verification.md)
- OpenClaw x MCP end-to-end integration check script: [scripts/integration_openclaw_mcp_runtime.py](scripts/integration_openclaw_mcp_runtime.py)
- OpenClaw runtime contract matrix check script: [scripts/integration_openclaw_runtime_contract.py](scripts/integration_openclaw_runtime_contract.py)
- MCP/API retrieval parity smoke script: [scripts/check_mcp_api_retrieval_parity.py](scripts/check_mcp_api_retrieval_parity.py)
- Wiki engine and curation business logic design: [docs/wiki-engine-design.md](docs/wiki-engine-design.md)
- Core product scope and UI boundaries: [docs/core-product-scope.md](docs/core-product-scope.md)
- Legacy import cold-start pipeline: [docs/legacy-import.md](docs/legacy-import.md)
- Legacy sync orchestration (scheduled refresh): [docs/legacy-sync-orchestration.md](docs/legacy-sync-orchestration.md)
- MCP runtime tools and cache invalidation model: [docs/mcp-runtime.md](docs/mcp-runtime.md)
- Agent simulator sandbox: [docs/agent-simulator.md](docs/agent-simulator.md)
- SDK trace observability guide (OTel -> Grafana/Datadog): [docs/sdk-trace-observability.md](docs/sdk-trace-observability.md)
- Troubleshooting guide (API/worker/MCP/web/DB): [docs/troubleshooting.md](docs/troubleshooting.md)
- Production hardening checklist: [docs/production-hardening.md](docs/production-hardening.md)
- Performance tuning runbook: [docs/performance-tuning.md](docs/performance-tuning.md)
- Observability incident playbooks: [docs/observability-incident-playbooks.md](docs/observability-incident-playbooks.md)
- Local observability starter stack: [infra/observability/README.md](infra/observability/README.md)
- Local moderation web console: [apps/web/README.md](apps/web/README.md)
- End-to-end vertical scenario demo (Omega access-card policy): [demos/omega_gate/README.md](demos/omega_gate/README.md)
- OpenClaw onboarding starter kit (runtime template + seed memory + 5-minute flow): [demos/openclaw_onboarding/README.md](demos/openclaw_onboarding/README.md)
- Cookbook examples (OpenClaw, SQL, Support Ops): [demos/cookbook/README.md](demos/cookbook/README.md)
- Getting started guide (first 15 minutes): [docs/getting-started.md](docs/getting-started.md)
- Contributor one-command guardrails quickstart: [docs/contributor-quickstart.md](docs/contributor-quickstart.md)
- Python `synapse-cli` for local extraction simulation and trace replay: [docs/synapse-cli.md](docs/synapse-cli.md)
- Tutorials: [docs/tutorials/README.md](docs/tutorials/README.md)
- SDK API reference: [docs/reference/README.md](docs/reference/README.md)
- OSS readiness checklist: [docs/oss-readiness.md](docs/oss-readiness.md)
- Compatibility matrix: [docs/compatibility-matrix.md](docs/compatibility-matrix.md)
- OSS release workflow: [docs/release-workflow.md](docs/release-workflow.md)
- OSS publish checklist walkthrough: [docs/oss-publish-checklist.md](docs/oss-publish-checklist.md)
- Self-hosted deployment guide: [docs/self-hosted-deployment.md](docs/self-hosted-deployment.md)
- Backup/restore drill runbook: [docs/backup-restore-drill.md](docs/backup-restore-drill.md)
- GitHub ownership map: [.github/CODEOWNERS](.github/CODEOWNERS)
- Dependabot config: [.github/dependabot.yml](.github/dependabot.yml)
- Changelog: [CHANGELOG.md](CHANGELOG.md)
- Contributing: [CONTRIBUTING.md](CONTRIBUTING.md)
- Maintainers: [MAINTAINERS.md](MAINTAINERS.md)
- Support policy: [SUPPORT.md](SUPPORT.md)
- Deprecation policy: [DEPRECATION_POLICY.md](DEPRECATION_POLICY.md)
- Security policy: [SECURITY.md](SECURITY.md)
- Code of Conduct: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- License: [LICENSE](LICENSE) (Apache-2.0)
