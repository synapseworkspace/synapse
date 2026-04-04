<p align="center">
  <img src="assets/synapse-logo.svg" alt="Synapse logo" width="680" />
</p>

<p align="center">
  <strong>Synapse: The Agentic Wiki and Cognitive State Layer for AI Agents.</strong><br/>
  Convert ephemeral agent experience into a shared, human-curated source of truth.
</p>

<p align="center">
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-Apache%202.0-1f6feb"></a>
  <a href="docs/compatibility-matrix.md"><img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-3776AB"></a>
  <a href="docs/compatibility-matrix.md"><img alt="Node" src="https://img.shields.io/badge/node-18%2B-339933"></a>
  <a href="services/mcp/README.md"><img alt="MCP Native" src="https://img.shields.io/badge/MCP-native-0f766e"></a>
</p>

<p align="center">
  <img src="assets/synapse-hero.svg" alt="Synapse core loop: Observe, Synthesize, Curate, Execute" width="980" />
</p>

## The Problem: "Goldfish AI" In Operations

Most production agent stacks still have three failure modes:

1. **Memory leak**: useful runtime insights disappear after a session ends.
2. **Static RAG drift**: agents rely on stale docs (PDF/Notion) while reality changes daily.
3. **Black-box learning**: business teams cannot see or safely correct what agents "learned".

## The Solution: Agentic Wiki

Synapse is middleware between your agent runtime (OpenClaw, LangGraph, CrewAI, custom stacks) and your operating knowledge.

### Core loop

1. **Observe (SDK)**: capture insights and facts from tool outputs and dialogs.
2. **Synthesize (Weaver)**: convert noisy signals into structured draft wiki updates.
3. **Curate (UI)**: humans review, edit, approve, or reject drafts.
4. **Execute (MCP)**: approved knowledge becomes live runtime context for all agents.

This is your live **single source of truth** for agent behavior.

## Synapse For OpenClaw Agents

Give OpenClaw agents a long-term collaborative brain.

### Package Registry Status

As of **April 3, 2026**:
- PyPI package `synapseworkspace-sdk`: **not published yet**.
- npm packages `@synapseworkspace/sdk`, `@synapseworkspace/schema`, `@synapseworkspace/openclaw-plugin`: **not published yet**.

Until first public package release, use repo-local install paths shown below.
Canonical package names are already fixed and are used consistently across release tooling/docs.

### Why Synapse + OpenClaw

- **Persistence**: agents remember facts across sessions.
- **Shared intelligence**: what one agent learns, all agents can use.
- **Human oversight**: operators approve/edit knowledge in a wiki workflow.

### Quick Start (OpenClaw)

Install Python SDK (current preview path):

```bash
pip install -e packages/synapse-sdk-py
```

Connect Synapse to OpenClaw:

```python
from synapse_sdk import Synapse

# Reads SYNAPSE_API_URL / SYNAPSE_PROJECT_ID / SYNAPSE_API_KEY.
# Falls back to http://localhost:8080 and current directory-derived project id.
synapse = Synapse.from_env()
synapse.attach(openclaw_runtime, integration="openclaw")
```

For existing stacks with their own memory/KB, use coexistence mode first:

```python
synapse.attach(openclaw_runtime, integration="openclaw", adoption_mode="observe_only")
```

Your runtime gets OpenClaw tools:
- `synapse_search_wiki`
- `synapse_propose_to_wiki`
- `synapse_get_open_tasks`
- `synapse_update_task_status`

Optional: pass a custom search callback if you want to override SDK default retrieval:

```python
synapse.attach(
    openclaw_runtime,
    integration="openclaw",
    openclaw_search_knowledge=lambda query, limit, filters: my_knowledge_search(query, limit, filters),
)
```

Canonical 5-minute path:
- [docs/openclaw-quickstart-5-min.md](docs/openclaw-quickstart-5-min.md)

TypeScript can use the same one-line attach flow:

```ts
import { Synapse } from "@synapseworkspace/sdk";

const synapse = Synapse.fromEnv();
synapse.attach(openclawRuntime, { integration: "openclaw" });
```

```ts
synapse.attach(openclawRuntime, { integration: "openclaw", adoptionMode: "observe_only" });
```

Optional advanced runtime-embedding package: `@synapseworkspace/openclaw-plugin`  
Source path: [packages/synapse-openclaw-plugin](packages/synapse-openclaw-plugin)

After first registry publication, install commands will be:
- `pip install synapseworkspace-sdk`
- `npm install @synapseworkspace/sdk`

## Product Capabilities

- **Semantic Diff**: show how understanding changed before approval.
- **Conflict Resolution**: detect and route contradictory claims.
- **Agentic Onboarding**: bootstrap from existing runtime memory on day 0.
- **No-code Knowledge Injection**: update wiki facts and change agent behavior without prompt redeploy.
- **Task-aware execution**: link operational tasks to drafts, pages, and evidence.

## 5-Minute Local Proof

Run the full core loop (`ingest -> draft -> approve -> MCP retrieval`):

```bash
./scripts/run_selfhost_core_acceptance.sh
```

Or use CLI onboarding:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e packages/synapse-sdk-py
synapse-cli quickstart --dir . --project-id omega_demo --api-url http://localhost:8080 --doctor-strict --verify-core-loop
```

Run local workspace UI:

```bash
cp .env.selfhost.example .env.selfhost
docker compose --env-file .env.selfhost -f infra/docker-compose.selfhost.yml up -d --build
cd apps/web && npm install && npm run dev
```

Open `http://localhost:5173`.

## Open-Core Stack

### Synapse Core (OSS)

- SDKs: [packages/synapse-sdk-py](packages/synapse-sdk-py), [packages/synapse-sdk-ts](packages/synapse-sdk-ts)
- Knowledge engine + API: [services/api](services/api)
- Synthesizer worker: [services/worker](services/worker)
- MCP runtime: [services/mcp](services/mcp)
- Local wiki workspace UI: [apps/web](apps/web)
- Canonical schemas: [packages/synapse-schema](packages/synapse-schema)

### Cloud / Enterprise Direction

- Multi-tenancy and RBAC
- Expert approval workflows and notifications
- Advanced analytics and ROI reporting
- Full audit trail and governance controls

## Docs

- Agentic Wiki overview: [docs/agentic-wiki-overview.md](docs/agentic-wiki-overview.md)
- Getting started: [docs/getting-started.md](docs/getting-started.md)
- OpenClaw 5-minute quickstart: [docs/openclaw-quickstart-5-min.md](docs/openclaw-quickstart-5-min.md)
- OpenClaw integration: [docs/openclaw-integration.md](docs/openclaw-integration.md)
- Existing-memory adoption playbook: [docs/adoption-existing-memory.md](docs/adoption-existing-memory.md)
- Framework integrations: [docs/framework-integrations.md](docs/framework-integrations.md)
- Wiki engine design: [docs/wiki-engine-design.md](docs/wiki-engine-design.md)
- MCP runtime: [docs/mcp-runtime.md](docs/mcp-runtime.md)
- Reliability and SLO guardrails: [docs/reliability-slo.md](docs/reliability-slo.md)
- Core vs enterprise scope: [docs/core-vs-enterprise.md](docs/core-vs-enterprise.md)
- Enterprise readiness status: [docs/enterprise-readiness.md](docs/enterprise-readiness.md)
- Enterprise governance export/runbook pack: [docs/enterprise-governance-pack.md](docs/enterprise-governance-pack.md)
- Legacy import and sync: [docs/legacy-import.md](docs/legacy-import.md), [docs/legacy-sync-orchestration.md](docs/legacy-sync-orchestration.md)
- Tutorials: [docs/tutorials/README.md](docs/tutorials/README.md)
- SDK API reference: [docs/reference/README.md](docs/reference/README.md)

## Demos

- OpenClaw onboarding kit: [demos/openclaw_onboarding/README.md](demos/openclaw_onboarding/README.md)
- End-to-end Omega scenario: [demos/omega_gate/README.md](demos/omega_gate/README.md)
- Cookbook examples: [demos/cookbook/README.md](demos/cookbook/README.md)

## OSS, Security, Release

- Contributing: [CONTRIBUTING.md](CONTRIBUTING.md)
- Security policy: [SECURITY.md](SECURITY.md)
- Release workflow: [docs/release-workflow.md](docs/release-workflow.md)
- OSS publish checklist: [docs/oss-publish-checklist.md](docs/oss-publish-checklist.md)
- License: [LICENSE](LICENSE)
