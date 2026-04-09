# Synapse Getting Started (First 15 Minutes)

Last updated: 2026-04-09

This guide is optimized for first value with minimal setup decisions.
Synapse is used here as an **L2 Cognitive State Layer** with **Agentic Wiki** as the operator interface.

## 1-Command Onboarding (Orchestrated)

```bash
synapse-cli quickstart --dir . --project-id omega_demo --api-url http://localhost:8080 --doctor-strict
```

Optional full proof in one run:

```bash
synapse-cli quickstart --dir . --project-id omega_demo --api-url http://localhost:8080 --doctor-strict --verify-core-loop
```

## 3-Command SDK Onboarding (CLI-first)

For the fastest OpenClaw integration bootstrap:

```bash
synapse-cli init --dir . --project-id omega_demo --api-url http://localhost:8080
synapse-cli doctor --api-url http://localhost:8080 --project-id omega_demo --strict
synapse-cli connect openclaw --dir . --env-file .env.synapse
```

Use the generated snippet from `connect openclaw` in your runtime bootstrap module.

Optional one-command proof from CLI (when running inside repo workspace):

```bash
synapse-cli verify core-loop --project-id omega_demo --json
```

## Adoption Ops (Production-first)

Run curated sync preset with safe dry-run and immediate funnel snapshot:

```bash
synapse-cli adoption sync-preset --api-url http://localhost:8080 --project-id omega_demo --updated-by ops_admin --with-pipeline
```

Inspect why data is blocked/rejected:

```bash
synapse-cli adoption rejections --api-url http://localhost:8080 --project-id omega_demo --days 14 --sample-limit 5
```

## Choose Your Path

1. **I want proof the core loop works (recommended):** run clean self-hosted acceptance.
2. **I want a local UI to review drafts:** run self-hosted stack + web app.
3. **I only want SDK examples without infra:** run cookbook demos (offline transport).
4. **I want framework-specific onboarding:** use the 5-minute path for your runtime (OpenClaw/LangGraph/LangChain/CrewAI).
5. **I want onboarding KPI metrics:** run the Agentic onboarding benchmark kit.

## Path 1: Core Loop Proof (Recommended)

Runs full path end-to-end:
`ingest -> synthesis draft -> approval -> MCP retrieval`.

```bash
cd /Users/maksimborisov/synapse
./scripts/run_selfhost_core_acceptance.sh
```

Success criteria:
- script exits `0`;
- output contains `[selfhost-acceptance] success`.

## Path 2: Local UI + Core Services

Start API + worker + MCP + Postgres:

```bash
cd /Users/maksimborisov/synapse
cp .env.selfhost.example .env.selfhost
docker compose --env-file .env.selfhost -f infra/docker-compose.selfhost.yml up -d --build
```

Check health:

```bash
curl -fsS http://localhost:8080/health
```

Run web UI:

```bash
cd /Users/maksimborisov/synapse/apps/web
npm install
npm run dev
```

Open: `http://localhost:5173`.

## Path 3: SDK-Only Cookbook (No API/DB)

```bash
cd /Users/maksimborisov/synapse
python3 -m venv /tmp/synapse-cookbook-venv
source /tmp/synapse-cookbook-venv/bin/activate
pip install requests
```

Pick one scenario:

```bash
PYTHONPATH=/Users/maksimborisov/synapse/packages/synapse-sdk-py/src \
python3 /Users/maksimborisov/synapse/demos/cookbook/openclaw_playbook_sync.py

PYTHONPATH=/Users/maksimborisov/synapse/packages/synapse-sdk-py/src \
python3 /Users/maksimborisov/synapse/demos/cookbook/langgraph_playbook_sync.py
```

More options:
- `/Users/maksimborisov/synapse/demos/cookbook/README.md`

## Path 4: Framework Day-0 Onboarding (5 Minutes)

Choose your runtime:
- OpenClaw: `/Users/maksimborisov/synapse/docs/openclaw-quickstart-5-min.md`
- LangGraph: `/Users/maksimborisov/synapse/docs/langgraph-quickstart-5-min.md`
- LangChain: `/Users/maksimborisov/synapse/docs/langchain-quickstart-5-min.md`
- CrewAI: `/Users/maksimborisov/synapse/docs/crewai-quickstart-5-min.md`

If you want repo-local demo fixtures (runtime template + seed dataset), run:

```bash
python3 -m venv /tmp/synapse-onboarding-venv
source /tmp/synapse-onboarding-venv/bin/activate
pip install requests
PYTHONPATH=/Users/maksimborisov/synapse/packages/synapse-sdk-py/src \
python3 /Users/maksimborisov/synapse/demos/openclaw_onboarding/run_onboarding_demo.py
```

Guide:
- `/Users/maksimborisov/synapse/docs/openclaw-quickstart-5-min.md`
- `/Users/maksimborisov/synapse/docs/langgraph-quickstart-5-min.md`
- `/Users/maksimborisov/synapse/docs/langchain-quickstart-5-min.md`
- `/Users/maksimborisov/synapse/docs/crewai-quickstart-5-min.md`
- `/Users/maksimborisov/synapse/demos/openclaw_onboarding/README.md`
- `/Users/maksimborisov/synapse/docs/tutorials/04-openclaw-onboarding-kit.md`

## Path 5: Agentic Onboarding KPI Benchmark

Run deterministic KPI comparison (`baseline_static` vs Synapse modes):

```bash
cd /Users/maksimborisov/synapse
python3 scripts/benchmark_agentic_onboarding.py --scenario all --summary-only
```

Docs:
- `/Users/maksimborisov/synapse/docs/agentic-onboarding-benchmark.md`

## Next Step After First Value

1. Production/self-host setup: `/Users/maksimborisov/synapse/docs/self-hosted-deployment.md`
2. Performance tuning: `/Users/maksimborisov/synapse/docs/performance-tuning.md`
3. Contributor one-command guardrails: `/Users/maksimborisov/synapse/docs/contributor-quickstart.md`
4. OSS release process: `/Users/maksimborisov/synapse/docs/release-workflow.md`
5. Publish checklist walkthrough: `/Users/maksimborisov/synapse/docs/oss-publish-checklist.md`
6. Operator governance deep links: `/Users/maksimborisov/synapse/docs/operator-governance-deeplinks.md`
7. Operations route runbook: `/Users/maksimborisov/synapse/docs/operations-route-runbook.md`
