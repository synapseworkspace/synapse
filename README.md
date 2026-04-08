<p align="center">
  <img src="assets/synapse-logo.svg" alt="Synapse logo" width="680" />
</p>

<p align="center">
  <strong>Synapse: The Agentic Wiki and Cognitive State Layer for AI Agents.</strong><br/>
  L2 memory and governance layer for AI agents, with a human-curated Wiki interface.
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

## Synapse As L2 Cognitive State Layer

- **L0**: model weights and system prompt.
- **L1**: ephemeral session context and short-term runtime memory.
- **L2 (Synapse)**: durable, governed cognitive state (facts + process rules + operational playbooks).

Agentic Wiki is the operating interface for humans.  
The product core is the **L2 state layer** used by every connected runtime through SDK + MCP.

## Synapse For OpenClaw Agents

Give OpenClaw agents a long-term collaborative brain.

### Package Install Modes

Registry install (recommended):

```bash
pip install synapseworkspace-sdk
npm install @synapseworkspace/sdk
```

Monorepo editable install (for local development in this repository):

```bash
pip install -e packages/synapse-sdk-py
```

Source install fallback (if registry propagation is still in progress):

```bash
pip install "git+https://github.com/synapseworkspace/synapse.git#subdirectory=packages/synapse-sdk-py"
```

Validate live registry availability:

```bash
python3 scripts/check_registry_package_availability.py --require-available
```

### Why Synapse + OpenClaw

- **Persistence**: agents remember facts across sessions.
- **Shared intelligence**: what one agent learns, all agents can use.
- **Human oversight**: operators approve/edit knowledge in a wiki workflow.

### Quick Start (OpenClaw)

Install Python SDK:

```bash
pip install synapseworkspace-sdk
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

Additional 5-minute paths:
- [docs/langgraph-quickstart-5-min.md](docs/langgraph-quickstart-5-min.md)
- [docs/langchain-quickstart-5-min.md](docs/langchain-quickstart-5-min.md)
- [docs/crewai-quickstart-5-min.md](docs/crewai-quickstart-5-min.md)

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

Recommended route split:
- Wiki-first workspace: `http://localhost:5173/wiki?project=omega_demo`
- Draft inbox (clean mode): `http://localhost:5173/wiki?project=omega_demo&core_tab=drafts`
- Operations tools (migration/gatekeeper): `http://localhost:5173/operations?project=omega_demo&core_tab=drafts`

Operations includes:
- Agent Worklog Policy: project-level timezone/schedule, idle-day gating, realtime trigger mode.
- AI Agent Orgchart: teams, handoffs, and direct links to agent wiki profiles.
- Migration Mode: trusted-source bootstrap preview/apply flows for existing-memory adoption.

Setup wizard v2 flow:
1. Choose connector template (`postgres_sql` or `memory_api`).
2. Validate connector config.
3. Connect source and queue first sync.
4. Preview curated import.
5. Apply first trusted batch.
6. Optional: auto-create starter wiki pages (`Agent Profile`, `Data Map`, `Runbook`) and continue in Drafts/Wiki.

## Agentic Onboarding Benchmark

Measure day-0 onboarding KPI in one command:

```bash
python3 scripts/benchmark_agentic_onboarding.py --scenario all --summary-only
```

KPI cards emitted per scenario:
- `first_useful_answer`
- `first_approved_draft`
- `first_policy_safe_publish`

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
- LangGraph 5-minute quickstart: [docs/langgraph-quickstart-5-min.md](docs/langgraph-quickstart-5-min.md)
- LangChain 5-minute quickstart: [docs/langchain-quickstart-5-min.md](docs/langchain-quickstart-5-min.md)
- CrewAI 5-minute quickstart: [docs/crewai-quickstart-5-min.md](docs/crewai-quickstart-5-min.md)
- OpenClaw integration: [docs/openclaw-integration.md](docs/openclaw-integration.md)
- Existing-memory adoption playbook: [docs/adoption-existing-memory.md](docs/adoption-existing-memory.md)
- Adoption connector cookbook: [docs/adoption-connector-cookbook.md](docs/adoption-connector-cookbook.md)
- Knowledge compiler RFC: [docs/knowledge-compiler-rfc.md](docs/knowledge-compiler-rfc.md)
- Framework integrations: [docs/framework-integrations.md](docs/framework-integrations.md)
- Cognitive State Layer (L2) positioning: [docs/cognitive-state-layer.md](docs/cognitive-state-layer.md)
- Agentic onboarding benchmark kit: [docs/agentic-onboarding-benchmark.md](docs/agentic-onboarding-benchmark.md)
- Buyer ROI + rollout one-pager: [docs/buyer-roi-rollout.md](docs/buyer-roi-rollout.md)
- Architecture diagram pack: [docs/architecture-diagram-pack.md](docs/architecture-diagram-pack.md)
- Operations route runbook: [docs/operations-route-runbook.md](docs/operations-route-runbook.md)
- Operator first-24h playbook: [docs/operator-first-24h.md](docs/operator-first-24h.md)
- Wiki engine design: [docs/wiki-engine-design.md](docs/wiki-engine-design.md)
- Wiki UX roles and metrics: [docs/wiki-ux-roles-metrics.md](docs/wiki-ux-roles-metrics.md)
- Wiki UI visual gallery (CI artifacts): [docs/wiki-ui-visual-gallery.md](docs/wiki-ui-visual-gallery.md)
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
