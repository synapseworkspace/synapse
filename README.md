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

### What Synapse now compiles

Synapse is no longer just `event -> draft`.

It now pushes knowledge through:

1. `evidence / observations`
2. `knowledge candidate bundles`
3. `typed wiki outputs`

With an explicit taxonomy:
- `operational`
- `episodic`
- `semantic`
- `procedural`

And normalized wiki targets:
- `fact`
- `process_playbook`
- `data_source_doc`
- `agent_profile`
- `decision_log`
- `incident_pattern`

This is how Synapse keeps raw runtime noise out of the wiki while still promoting durable agent knowledge.

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

Operator-first adoption flow (dry-run safe by default):

```bash
synapse-cli adoption sync-preset --api-url http://localhost:8080 --project-id omega_demo --updated-by ops_admin --with-pipeline
synapse-cli adoption rejections --api-url http://localhost:8080 --project-id omega_demo --days 14
synapse-cli adoption list-drafts --api-url http://localhost:8080 --project-id omega_demo --status pending_review --limit 50
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

Enterprise shortcut (single API call):
- `POST /v1/adoption/sync-presets/execute` runs curated bootstrap profile, queues legacy-source sync, executes trusted draft bootstrap, seeds starter pages, and now previews/applies bundle-level core wiki promotion in the same flow.
- `sync-presets/execute` now defaults `starter_profile=standard`, so domain projects get the neutral core wiki pack by default; support/sales/compliance starter packs are opt-in instead of being injected automatically.
- `POST /v1/adoption/agent-wiki-bootstrap` now supports explicit `Preview -> Apply` flow, `bootstrap_publish_core=true` (publish core onboarding pages with warning blocks when coverage is partial), and returns a structured `quality_report`.
- bootstrap pack can include: `Data Sources Catalog`, `Agent Capability Profile`, `Tooling Map`, `Process Playbooks`, `Company Operating Context`, `Operational Logic Map`, plus starter pages.
- `GET /v1/adoption/wiki-quality/report` provides a hard OOTB quality gate (`core coverage`, `placeholder ratio`, `daily-summary draft ratio`) for release/onboarding checks.
- `GET /v1/adoption/wiki-richness/benchmark` scores useful wiki density instead of only slug existence.
- `GET /v1/adoption/knowledge-gaps` shows where the wiki is still missing durable answers, grounded process detail, or source-backed structure.
- `POST /v1/adoption/knowledge-gaps/tasks/sync` turns those gaps into deduplicated Synapse tasks so missing knowledge enters the execution loop.
- `GET /v1/adoption/signal-noise/audit` gives operators one compact view of rejection pressure, bundle promotion, weak page families, missing signals, and noisy source families.
- `GET /v1/adoption/evidence-ledger` exposes the normalized evidence layer directly, with source shape, volatility, PII level, transactionality, taxonomy, and bundle linkage separated from wiki intent.
- `GET /v1/adoption/evidence-ledger/stats` shows how much of the current evidence layer is durable vs ephemeral, suppressed vs promoted, and where sensitive evidence is accumulating.
- `GET /v1/adoption/stability-monitor` turns those signals into an operator-ready health state and records the safe-mode recommendation/apply loop in audit history.
- `GET /v1/adoption/synthesis-prompts` generates targeted follow-up questions for agents/operators from candidate bundles, repeated unanswered questions, and weak pages.
- `POST /v1/adoption/bundle-promotion/run` refreshes core wiki pages directly from durable evidence bundles with a safe `Preview -> Apply` flow.
- `GET /v1/adoption/business-profiles` lists ready-made business deployment profiles (`generic_service_ops`, `logistics_operator`, `support_center`, `sales_revenue_ops`, `compliance_program`, `ai_employee_org`) that bundle a synthesis pack, starter profile, default wiki space, role-template choice, and bundle-promotion defaults.
- `POST /v1/adoption/first-run/bootstrap` and `POST /v1/adoption/sync-presets/execute` now accept `business_profile_key`, so operators can select a business-shaped onboarding config instead of hand-picking `starter_profile + role_template + bundle_promotion_space_key`.
- `POST /v1/adoption/first-run/bootstrap` now also supports a safe `dry_run` preview, returning the planned starter pages and resolved defaults before anything is written, which powers profile previews in the web onboarding flow.
- Shared `Process Playbooks` and `Company Operating Context` synthesis now also flows through `synthesis_packs`, so the same business profile/policy layer that chooses starter spaces can shape recurring workflow wording and operating-principle framing without hardcoding that domain language into the compiler core.
- `support_center` and `sales_revenue_ops` now resolve to dedicated `support_ops` / `sales_ops` synthesis packs instead of falling back to `generic_ops`, so support-queue escalations and revenue/handoff workflows can get their own domain wording in task pages and shared wiki pages without changing the compiler core.
- `compliance_program` now resolves to a dedicated `compliance_ops` pack, and pack hooks also shape `Agent Capability Profile` and `Tooling Map` wording. That means capability signals, sparse-page hints, empty-tool hints, and governance guidance can stay domain-aware without baking compliance/support/sales/logistics phrasing into the compiler core.
- Runtime-surface quality fixes now also protect shared logistics synthesis from meaning bleed: task/runbook pack selection can reuse inferred domain space from synced runtime surface, logistics playbook refinement no longer lets unrelated evidence/source tokens drag other SOPs into `driver economy` wording, and source/tool mappings prefer explicit structured contracts before broad agent-level fallback.
- The runtime-surface quality pass also normalizes noisy control-plane labels before they hit shared wiki pages: `standing_order.*` process strings and raw `*_latest` source/tool tokens are summarized into cleaner process/source labels, `Tooling Map` is stricter about falling back from explicit contracts to broad per-agent hints, and `fleet sync` gets its own logistics SOP semantics instead of collapsing into generic workflow wording.
- `POST /v1/adoption/import-connectors/resolve` and `POST /v1/adoption/import-connectors/bootstrap` now return `connection_diagnostics` for `postgres_sql` sources, including resolved host preview and ambiguous-host portability warnings for split-stack self-host deployments.
- `POST /v1/adoption/import-connectors/validate` performs an optional live connectivity check for `postgres_sql` targets from inside the Synapse API runtime, so operators can verify host/network reachability before the first sync.
- `POST /v1/agents/runtime-surface/sync` lets you feed Synapse a generic control-plane surface for each agent (`runtime_overview`, `scheduled_tasks`, `standing_orders`, `capability_registry`, `action_surface`, `tool_manifest`, `source_hints`, `approvals`, `model_routing`). Synapse turns that into richer capability/tool/source contracts, per-task SOP runbooks under `agents/<id>/runbooks/*`, and stronger `source -> agent / capability / process / tool` mappings in the wiki. By default it refreshes core wiki pages immediately; on clean projects without existing domain spaces, it now infers a shared space from the synced task/capability/source contracts so runtime sync can materialize `logistics/*` (or another domain space) without requiring a follow-up bootstrap rerun.
- `GET /v1/adoption/tooling-map/diagnostics` now exposes a more general synthesis-debugging contract instead of only rendered rows: each tool row includes typed `synthesized_fields` (`value`, `origin`, `confidence`), row-level provenance (`tool_contracts`, `capability_contracts`, `source_bindings`, `fallback_fields`, `process_source_origin`), a derived relation graph (`tool -> capability/process/source/guardrail` edges), and summary quality metrics such as `field_origin_counts`, `process_equals_capability_rows`, and `overlong_source_rows`. This is intended to make runtime-surface derivation debuggable across logistics, support, sales, compliance, and future domains with the same row-level semantics.
- `GET /v1/adoption/data-sources/diagnostics` now exposes the same typed synthesis-debugging contract for source pages: each source row includes typed synthesized fields for agent/process/capability/tool/decision impact, relation edges (`source -> agent/capability/process/tool/decision`), and quality metrics (`rows_with_agents`, `rows_with_capability_or_process`, `inferred_usage_rows`, `bundle_backed_rows`, `field_origin_counts`). This keeps source debugging on the same general-purpose provenance/confidence model as `tooling-map`.
- `GET /v1/adoption/agent-capability/diagnostics` now exposes the same typed synthesis-debugging contract for agent profiles: each agent row includes runtime/profile fields plus typed synthesized capability/tool/source/action/task/decision fields, relation edges (`agent -> capability/tool/source/action/task/standing_order/decision`), and quality metrics (`rows_with_tools`, `rows_with_sources`, `rows_with_running_instances`, `rows_with_reflection`, `contract_backed_rows`, `field_origin_counts`).
- `GET /v1/adoption/process-playbooks/diagnostics` now exposes the same typed synthesis-debugging contract for playbooks: each row includes structured trigger/action/owners/tools/artifacts/decision refs plus typed synthesized fields, relation edges (`playbook -> agent/tool/artifact/decision/input`), and quality metrics (`rows_with_owners`, `rows_with_tools`, `rows_with_artifacts`, `rows_with_decisions`, `rows_with_human_loop`, `field_origin_counts`).
- `GET /v1/adoption/synthesis-graph/diagnostics` now combines those diagnostics surfaces into one graph snapshot: unified nodes/edges across tools, sources, agents, playbooks, capabilities, processes, tools, decisions, plus roll-up summaries for `tooling-map`, `data-sources`, `agent-capability`, and `process-playbooks`. This is the first general-purpose adoption graph view rather than a page-family-specific debug endpoint.

Knowledge Compiler diagnostics flow:

```bash
synapse-cli adoption sync-preset --api-url http://localhost:8080 --project-id omega_demo --updated-by ops_admin --with-pipeline
curl "http://localhost:8080/v1/adoption/wiki-richness/benchmark?project_id=omega_demo"
curl "http://localhost:8080/v1/adoption/knowledge-gaps?project_id=omega_demo"
curl -X POST "http://localhost:8080/v1/adoption/knowledge-gaps/tasks/sync" \
  -H "Content-Type: application/json" \
  -d '{"project_id":"omega_demo","created_by":"ops_admin","dry_run":true}'
curl "http://localhost:8080/v1/adoption/signal-noise/audit?project_id=omega_demo"
curl "http://localhost:8080/v1/adoption/evidence-ledger?project_id=omega_demo&limit=20"
curl "http://localhost:8080/v1/adoption/evidence-ledger/stats?project_id=omega_demo&days=30"
curl "http://localhost:8080/v1/adoption/stability-monitor?project_id=omega_demo"
curl "http://localhost:8080/v1/adoption/synthesis-prompts?project_id=omega_demo"
curl -X POST "http://localhost:8080/v1/adoption/bundle-promotion/run" \
  -H "Content-Type: application/json" \
  -d '{"project_id":"omega_demo","updated_by":"ops_admin","dry_run":true,"publish":true,"bootstrap_publish_core":true,"space_key":"operations"}'
```

This gives you a concrete loop:
- import signals
- inspect what was promoted
- inspect what is still missing
- inspect signal/noise and weak wiki families
- ask targeted follow-up questions
- publish richer pages

Opinionated first-run pack for agent-driven orgs:
- `AI Employee Org` bootstrap profile
- `Tool Catalog`
- `Scheduled Tasks`
- `Human-in-the-Loop Rules`
- `Integrations Map`
- `Escalation Rules`
- `Agent Directory Index`

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
