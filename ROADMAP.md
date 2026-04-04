# Synapse Roadmap (Living)

Last updated: 2026-04-04
Owner: Core team

## Правило актуальности

Этот файл обновляется после каждого внедрения, которое меняет:
- scope фич;
- статус задач;
- архитектурные решения;
- сроки этапов.

Минимум обновления после внедрения:
1. Изменить статус задачи.
2. Добавить короткую запись в "Recent Updates".
3. При необходимости скорректировать "Next Up" и риски.

## Статусы

- `planned`: запланировано.
- `in_progress`: в работе.
- `done`: реализовано.
- `blocked`: заблокировано внешним фактором.

## Current Quarter Focus (Q2 2026)

1. Universal `synapse-sdk` contracts and adapters.
2. Ingestion API + event store.
3. Draft knowledge synthesis pipeline.
4. Gatekeeper policy layer (`operational` vs `insight` vs `golden`).
5. Human review UI for approve/edit/reject.
6. MCP runtime retrieval.
7. Bootstrap/backfill flow for existing agent memory at SDK onboarding.
8. Agentic Task Core (todo tracker + agent/runtime integration).
9. Agentic Wiki product positioning and OpenClaw-first onboarding path.
10. Core-only UX profile by default (advanced controls opt-in or env-locked).
11. Enterprise foundation kickoff: tenancy model, SSO path, and unified RBAC design.
12. Framework GTM integrations (LangGraph / LangChain / CrewAI) with contract-level CI checks.
13. Reliability + SLO guardrails (latency, quality, observability, release gating).
14. Existing-memory adoption layer (coexistence modes, migration wizard, source-ownership policy).

## Recovery Plan: Wiki-First UX + Draft Quality (April 2026)

Status: `done`

Goal:
- убрать ощущение “control center” в default self-hosted опыте;
- сделать вход в продукт через понятный wiki workflow;
- остановить захламление Drafts низко-сигнальными memory событиями.

Workstreams:
- `done` UI IA reset:
  - auth-gated entry for enforced auth projects;
  - default profile -> core wiki workspace (`Wiki/Drafts/Tasks`);
  - tabbed core navigation (`Wiki | Drafts | Tasks`) with contextual rendering;
  - advanced/ops controls hidden unless explicit advanced profile.
- `done` Draft noise suppression:
  - tighten Gatekeeper for single-source one-off memory events;
  - preserve policy-grade / repeated / multi-source signals for moderation queue.
- `done` Wiki engine UX alignment:
  - Confluence-like page-first navigation, reduced control density in first viewport.
- `done` Adoption migration mode:
  - trusted-source bootstrap approve with sampling + rollback defaults in UI flow.

## User-Friendly Wiki UX (12-Point Track)

Status: `in_progress`

Goal:
- сделать UX уровня “корпоративная wiki для обычных людей”, а не control-center;
- держать Drafts/Tasks вторичными по отношению к page-first wiki.

Checklist:
1. `done` Wiki-only landing:
   - open last visited page automatically per project (`localStorage` restore).
2. `done` Super-simple top bar:
   - compact actions (`Create`, `Share`, `Edit`, `Publish`, `Refresh Inbox`) + search.
3. `done` Clean left tree:
   - page tree with context menu (`Open`, `Move/Rename`, `Archive/Restore`);
   - drag-and-drop move with `reparent` workflow wired.
4. `in_progress` Rich page editing:
   - done: local autosave + restore for page edit drafts in core mode;
   - next: slash-first core editor, undo/redo parity, stronger version diff UX.
5. `done` Drafts as inbox:
   - Drafts live in dedicated tab; page view shows lightweight “Open drafts” context only.
6. `done` Publish modal:
   - modal with location + change summary before publish.
7. `done` Smart page creation:
   - template-first create panel (`Access Policy`, `Operations Incident`, `Customer Preference`).
8. `done` 60-second onboarding:
   - first-run guided modal with 3 steps (connect -> create -> review).
9. `in_progress` Human copy cleanup:
   - remove ops-heavy labels from core surface; keep technical language in advanced mode.
10. `done` Fast search:
    - `Cmd/Ctrl+K` jump modal, recent pages, and create-from-query path.
11. `planned` Friendly roles model:
    - Viewer / Editor / Approver / Admin language + simple permission table in UI/docs.
12. `planned` UX metrics:
    - track TTFV, time-to-first-publish, and click-depth to open/publish.

Next Up (execution order):
1. Core-mode rich editor (replace markdown textarea) with autosave indicator.
2. Friendly roles language pass + quick permissions guide in UI.
3. UX telemetry primitives for TTFV and first-publish funnel.
4. Sticky page toolbar (`History`, `Watching`, `...`) for 1:1 wiki parity.

## Confluence-Like Wiki Track (Q2-Q3 2026)

Status: `done`

Goal:
- сделать Synapse интерфейсом уровня корпоративной wiki (page-first, human editing, revision workflows, information architecture);
- оставить Drafts/Tasks как secondary operations layer.

Build-vs-buy decision:
- `not_selected` Full standalone wiki replacement (Wiki.js / BookStack / Outline) as embedded UI:
  - these projects are strong products, but not drop-in embeddable React shells for our FastAPI + MCP architecture;
  - migration and deep behavior overrides would cost more than controlled in-house shell evolution.
- `selected` Headless composition:
  - keep current React + Mantine shell;
  - keep TipTap editor/canvas as page-edit foundation;
  - incrementally add Confluence-like IA/UX on top of existing Synapse data contracts.
- `selected` OSS building blocks (to avoid custom reinventing):
  - TipTap/ProseMirror for page editor and rich blocks;
  - Mantine primitives for enterprise-grade information density and accessibility baseline;
  - Markdown + page-version model in Synapse API as system-of-record (not browser-only document state).

Execution slices:
- `done` C1 Page Editing Core:
  - direct human page edit/save with new page versions and snapshots.
- `done` C2 Full Page Index:
  - API `list pages` independent of draft queue;
  - tree built from wiki pages, not from draft-derived nodes.
  - done now: `GET /v1/wiki/pages` with page/draft counters + sort/filter + pagination metadata.
  - done now: Web `Wiki Tree` renders from wiki page index first, with draft overlay metrics.
- `done` C3 Page Operations:
  - move/rename page, archive/restore, parent-child hierarchy, breadcrumbs.
  - done now: explicit `reparent` API operation (parent-child by slug hierarchy) on top of move primitives.
  - done now: page lifecycle transition APIs (`archive`, `restore`) and wiki header controls in web UI.
- `done` C4 Collaboration:
  - comments, mentions, reviewer assignments, watch/follow pages.
  - done now: page comments + watchers + aliases API surfaces and page-context UI integration.
  - done now: page review assignments (`assign/resolve`) API + UI context workflow.
- `done` C5 Knowledge Governance:
  - page ownership, approval policies per space, status lifecycle (`draft/reviewed/published/archived`).
  - done now: space-level governance APIs (`policy`, `owners`) + page-level owners APIs.
  - done now: policy enforcement in wiki write/comment flows (`owners_only`, review-required publish gate).
  - done now: wiki notifications inbox APIs + mention/watcher/review notifications.
  - done now: reviewed status lifecycle support across DB/API/UI (`draft/reviewed/published/archived`).
- `done` C6 Quality-of-Life:
  - keyboard navigation, slash commands, richer table/callout blocks, attachment previews.
  - done now: wiki editor command palette (`Ctrl/Cmd + /`) with slash-style quick actions.
  - done now: no-code quick blocks (Info/Warning callouts, incident template, decision template).
  - done now: table authoring controls (insert/add row/add column/delete) in wiki editor.
  - done now: attachment/media preview panel on wiki pages (inline image gallery + linked file list from markdown).
  - done now: upload-to-wiki flow (`/v1/wiki/uploads`) with automatic markdown snippet insertion in page edit mode.

## Milestones

## M1: Foundation (Weeks 1-2)

Status: `done`

Scope:
- `v1` schemas (`ObservationEvent`, `Claim`, `EvidenceRef`, `DraftPage`).
- API ingestion endpoint + idempotency.
- `synapse-sdk` core skeleton (TS + Python).
- Local stack (`docker-compose`) for self-hosted mode.

Exit criteria:
- SDK event successfully lands in DB.
- Smoke e2e scenario works locally.

Progress:
- [x] Monorepo scaffold created (`packages/*`, `services/*`, `apps/*`, `infra/*`).
- [x] `v1` schema package added (`ObservationEvent`, `EvidenceRef`, `Claim`, `DraftPage`).
- [x] TS and Python SDK skeletons added.
- [x] Initial SQL migration added (`events`, `claims`, `claim_proposals`).
- [x] API wired to Postgres with idempotent writes by `event.id`.
- [x] M1 smoke script added (`scripts/m1_smoke_e2e.sh`).
- [x] End-to-end smoke demo executed locally (event dedup + DB persistence verified).
- [x] Production-like SDK transport resilience (retry/backoff/jitter/timeout/retryable status handling).
- [x] Loss-safe flush semantics in TS/Python SDK (failed batches are re-queued).
- [x] API-level persisted idempotency-key handling with TTL cleanup (`idempotency_requests`).
- [x] Framework monitor adapters implemented (`monitor()` + LangGraph/CrewAI/OpenClaw wrappers).

## M2: Synthesis Engine (Weeks 3-4)

Status: `done`

Scope:
- Claim extraction pipeline.
- Dedup + clustering.
- Conflict detection.
- Draft page generation in Markdown.
- Backfill bootstrap from historical memory (`SDK -> API batch -> worker extraction`).
- Gatekeeper triage (L1 Operational Memory, L2 Insight Candidates, L3 Golden Knowledge).

Exit criteria:
- Drafts generated from raw event stream with evidence links.

Progress:
- [x] Wiki engine storage model introduced (`wiki_*` tables, draft queue, conflicts, snapshots).
- [x] Deterministic synthesis worker implemented (`claim_proposals` -> `wiki_draft_changes`).
- [x] Page resolver pipeline implemented (entity/title/alias scoring with confidence tiers).
- [x] Section resolver + dedup + conflict heuristics implemented.
- [x] Wiki API read endpoints added (search pages, page details, drafts queue).
- [x] Historical memory ingestion API added (`POST /v1/backfill/memory`) with batch status tracking.
- [x] Worker extraction path added (`memory_backfill` events -> `claim_proposals`) with `event_pipeline_state` checkpoints.
- [x] SDK bootstrap methods added in Python/TS (`backfill_memory` / `backfillMemory`) with chunking + idempotency keys.
- [x] Introduced baseline Gatekeeper policy engine with triage tiers (`operational_memory`, `insight_candidate`, `golden_candidate`) and persisted decisions.
- [x] Added first auto-promotion criteria from L2 -> L3 (`source_diversity` + conflict-free horizon) in worker decision logic.
- [x] Added project-level Gatekeeper config surface (`/v1/gatekeeper/config`) and worker runtime adoption of per-project thresholds.
- [x] Add baseline evaluator dataset and regression harness for routing/dedup/conflict/temporal precision.
- [x] Extend evaluator coverage to Gatekeeper tier quality (precision/recall + confusion matrix by tier).
- [x] Add temporal reasoning for contradiction handling and fact expiry.
- [x] Add richer entity/category inference for raw backfill content without explicit metadata.
- [x] Upgrade Gatekeeper classifier from heuristics to LLM-assisted + source-diversity scoring.
- [x] Add deterministic Gatekeeper LLM calibration harness (train/holdout grid search + recommended config payload).

## M3: Human Curation (Weeks 5-6)

Status: `done`

Scope:
- Draft inbox.
- Approve / edit / reject workflow.
- Semantic diff between published and proposed knowledge.
- Audit log of moderation actions.
- Conflict report workflow with side-by-side evidence and one-click resolution.

Exit criteria:
- Approved drafts become published knowledge snapshot.

Progress:
- [x] Moderation API implemented (`POST /v1/wiki/drafts/{draft_id}/approve|reject`).
- [x] Approval path persists human page versions and knowledge snapshots.
- [x] Rejection path updates claim/link state and optional conflict dismissal.
- [x] Integration scenario covers moderation idempotency and state transitions end-to-end.
- [x] Added explicit `edit+approve` payload support (structured section append/replace edits during moderation approval).
- [x] Exposed moderation audit feed endpoint (`GET /v1/wiki/moderation/actions`) for UI timeline.
- [x] Added draft detail endpoint (`GET /v1/wiki/drafts/{draft_id}`) with semantic diff, markdown patch, evidence, conflicts, and per-draft moderation timeline.
- [x] Implemented first local web moderation console (`apps/web`) with Draft Inbox list, detail view, approve/edit/reject actions, and real API wiring.
- [x] Upgraded semantic diff in web UI to structured statement-level before/after visualization.
- [x] Added conflict resolver tab with one-click `Force Approve` / `Reject + Dismiss` actions for open conflicts.
- [x] Added keyboard-first moderation flow in web UI (`J/K`, `Ctrl|Cmd+Enter`, `Ctrl|Cmd+Backspace`, `Ctrl|Cmd+R`).
- [x] Added Gatekeeper rollback approval UI in Intelligence panel: rollback preview (risk + diff + changed samples), rollback request creation, multi-approver approve/reject actions, and audit trail cards.

## M4: MCP Runtime (Weeks 7-8)

Status: `done`

Scope:
- MCP tools (`search_knowledge`, `get_entity_facts`, `get_recent_changes`, `explain_conflicts`).
- SDK helper for context injection.
- Publish-to-retrieval cache invalidation.
- Semantic retrieval upgrade path (hybrid lexical + graph-aware reasoning).

Exit criteria:
- New approved knowledge visible to agents within target latency.

Progress:
- [x] Implemented initial MCP runtime service (`services/mcp`) with tool surface: `search_knowledge`, `get_entity_facts`, `get_recent_changes`, `explain_conflicts`.
- [x] Added project-scoped retrieval cache with publish-aware invalidation based on latest `knowledge_snapshots` revision marker.
- [x] Added offline CI smoke coverage for MCP runtime cache behavior and invalidation semantics.
- [x] Added Python SDK context injection helper (`MCPContextHelper`) with OpenClaw-compatible search callback factory.
- [x] Added TypeScript SDK parity for MCP context helper + shared helper docs/examples.
- [x] Validated OpenClaw end-to-end retrieval injection with a real stdio MCP client session (`scripts/integration_openclaw_mcp_runtime.py`).
- [x] Added graph-aware retrieval hint path (`related_entity_key` + `wiki_pages.metadata.related_entities` boost) and deterministic regression evaluator (`eval/mcp_retrieval_cases.json`, `scripts/eval_mcp_retrieval_regression.py`) with CI gate.
- [x] Expanded graph-aware retrieval to explicit multi-hop relation traversal (recursive graph walk up to 3 hops) with deterministic regression coverage.
- [x] Added production-like retrieval benchmark harness (`scripts/benchmark_mcp_retrieval.py`), tuning controls for graph boosts/hops (env-configurable), and DB index migration for retrieval path (`016_mcp_retrieval_indexes.sql`).
- [x] Added weekly MCP retrieval trend monitor (`scripts/check_mcp_retrieval_trend.py`) with benchmark history, regression guardrails (latency/quality), and graph-profile recommendations only on measured quality regressions.

## M5: Knowledge Intelligence (Weeks 9-10)

Status: `done`

Scope:
- Daily/weekly intelligence digests (`new insights`, `pending approvals`, `critical conflicts`).
- Knowledge Velocity and ROI-oriented analytics widgets.
- Executive-facing "Intelligence Pulse" delivery (Slack/Email connectors).

Exit criteria:
- Ops/management receives actionable daily summary without opening wiki UI.

Progress:
- [x] Added intelligence storage model (`knowledge_daily_metrics`, `intelligence_digests`).
- [x] Implemented digest worker job (`run_intelligence_digest.py`) with project auto-discovery.
- [x] Added API retrieval endpoints for daily metrics and digest feeds.
- [x] Added scheduler + delivery adapters (Slack webhook + SMTP email) with delivery attempts audit.
- [x] Added weekly digest rollup + week-over-week trend breakdown (worker + API trends endpoint).
- [x] Added web Intelligence Pulse dashboard in `apps/web` with Knowledge Velocity, pending approvals, open conflicts KPIs, daily/weekly charts, and latest digest rendering from live `/v1/intelligence/*` APIs.
- [x] Added conflict trend drill-down stack: API (`/v1/intelligence/conflicts/drilldown`) + UI weekly conflict classes and MTTR panels.
- [x] Added digest delivery observability in `apps/web` (targets, attempt success rate, channel health, last failure details) from `/v1/intelligence/delivery/*`.

## M6: Enterprise Readiness Features (Weeks 11-12)

Status: `done`

Scope:
- Legacy Import / Cold Start (`PDF`, `Excel`, `Notion`) into structured wiki drafts.
- Agent Simulator sandbox for policy-change impact forecasting.
- Scenario replay on historical sessions before policy rollout.

Exit criteria:
- Team can bootstrap from existing docs and safely test policy edits pre-production.

Progress:
- [x] Add legacy import cold-start pipeline script (`run_legacy_import.py`) with parser coverage for text/markdown/csv/json/jsonl and optional PDF/XLSX adapters.
- [x] Extend legacy import to Notion API connector ingestion mode (cloud workspace sync).
- [x] Add Agent Simulator sandbox (policy-change impact forecasting on historical sessions).
- [x] Wire scheduled legacy sync orchestration (source configs + queued runs + worker scheduler) for periodic Notion/local refresh.
- [x] Add Agent Simulator templates + preset scheduler workflow (`run_agent_simulator_scheduler.py`) for recurring policy risk checks.

## M7: SDK Excellence (Weeks 13-14)

Status: `done`

Scope:
- Developer-first SDK surface (`Synapse(...)`, `attach(...)`, minimal boilerplate).
- End-to-end context propagation (`trace_id` / `span_id`) across nested tool chains.
- Decorator-based insight capture API for explicit tool annotation.
- Plugin architecture for Extractors / Transports / Synthesizers.
- Introspection and explainability in SDK (`debug_mode`, reason traces).
- DX ecosystem: cookbook examples + `synapse-cli` local extraction playground.
- Standards integration: OpenTelemetry bridge + MCP-native helper ergonomics.

Exit criteria:
- New developer can connect Synapse to OpenClaw and see trace-linked drafts in under 5 minutes.
- SDK emits explainable reasoning metadata for each proposed insight.
- Plugin interfaces are stable and versioned across TS/Python SDKs.

Progress:
- [x] Strong typed core contracts exist in TS/Python SDKs (`Claim`, `ObservationEvent`, `EvidenceRef`).
- [x] Transport abstraction exists (`HttpTransport` + pluggable `Transport` protocol/interface).
- [x] Monitor wrappers exist (`monitor`, LangGraph/CrewAI/OpenClaw adapters).
- [x] Add simplified facade API (`Synapse` class + `attach(...)` in TS/Python) while keeping `SynapseClient` compatibility.
- [x] Add trace propagation primitives (Python `contextvars`, TS async context) and inject `trace_id` / `span_id` into captured events.
- [x] Add `@synapse.collect_insight(...)` / TS decorator-equivalent (`collectInsight(fn, options)`) for tool-level semantic extraction hints.
- [x] Add extractor plugin interface + default implementations (`structured_result`, `keyword`) in TS/Python SDKs.
- [x] Add synthesizer plugin contract and registration lifecycle.
- [x] Add graceful degradation modes (`drop|buffer|sync_flush`) configurable per SDK runtime.
- [x] Add SDK introspection stream (`debug_mode`, decision confidence/reason hooks, structured logs).
- [x] Add OpenTelemetry exporter mapping (traces/metrics) for Datadog/Prometheus pipelines.
- [x] Add cookbook repo section (`Synapse + OpenClaw`, `Synapse + SQL`, `Synapse + Support Ops`).
- [x] Add `synapse-cli` for local extraction simulation and trace replay from terminal.

## M8: Agentic Task Core (Weeks 15-16)

Status: `done`

Scope:
- Task tracker domain in core API (`/v1/tasks*`) with timeline and linkable context.
- SDK helpers (Python/TS) for task lifecycle operations.
- OpenClaw tool surface for reading active tasks and updating status.
- MCP retrieval for task context (`get_open_tasks`, `get_task_details`).
- Local UI panel for operators (create/update/comment/link).

Exit criteria:
- Agents can consume active tasks and report progress without custom per-project code.
- Task history is auditable and linked to knowledge artifacts (`claim`/`draft`/`page`).

Progress:
- [x] Added DB schema for task core (`synapse_tasks`, `synapse_task_events`, `synapse_task_links`) via migration `036_task_core.sql`.
- [x] Implemented Task API endpoints (`GET /v1/tasks`, `GET /v1/tasks/{id}`, `POST /v1/tasks`, `POST /v1/tasks/{id}/status|comments|links`) with idempotent mutating operations.
- [x] Added Python SDK task helpers (`list_tasks`, `get_task`, `upsert_task`, `update_task_status`, `comment_task`, `link_task`) and typed task models.
- [x] Added OpenClaw connector task tools (`synapse_get_open_tasks`, `synapse_update_task_status`).
- [x] Added TypeScript SDK task helpers and transport JSON request support.
- [x] Extended MCP runtime with task tools (`get_open_tasks`, `get_task_details`) and docs.
- [x] Added web Task Tracker panel with lifecycle actions, comments timeline, and context links.
- [x] Added full web e2e coverage for task lifecycle (create -> status transitions -> comment -> context link) and aligned mock API server with production-like `/v1/tasks*` behavior.

## M9: Zero-Friction Onboarding (Weeks 17-18)

Status: `done`

Scope:
- One-command environment diagnostics for API/core loop readiness.
- Opinionated project bootstrap (`init`) with `.env` and starter config scaffolding.
- OpenClaw quick-connect command path (`connect`) for first attach.
- Canonical 3-command quickstart path for OSS users.

Exit criteria:
- New user can run diagnosis and get actionable fix hints without reading internal docs.
- First successful local attach path can be completed using CLI-driven flow.

Progress:
- [x] Added `synapse-cli doctor` with core endpoint checks (`/health`, `/v1/tasks`, `/v1/wiki/drafts`, `/v1/mcp/retrieval/explain`) and actionable remediation hints.
- [x] Added `synapse-cli init` to scaffold `.env` defaults + project id + quickstart instructions.
- [x] Added `synapse-cli connect openclaw` guided snippet generator for one-line attach.
- [x] Added “3 commands to first draft” canonical onboarding doc path in Getting Started.
- [x] Added `synapse-cli verify core-loop` one-command acceptance wrapper (script auto-discovery, dry-run preview, JSON output) plus offline CI smoke coverage.
- [x] Added `synapse-cli quickstart` orchestration command (one-command `init -> doctor -> connect`, optional `verify core-loop`) with machine-readable step reports.
- [x] Added OSS governance docs baseline (`MAINTAINERS.md`, `SUPPORT.md`, `DEPRECATION_POLICY.md`) for ownership/support/deprecation contracts.
- [x] Added SDK/API reference baseline docs (`docs/reference/*`) generated from package exports and CI freshness gate (`generate_sdk_api_reference.py --check`).
- [x] Added dedicated compatibility matrix workflow (`.github/workflows/compat-matrix.yml`) across Python (`3.10-3.13`) and Node (`18/20/22`).
- [x] Added OSS repo hardening baseline (`.github/CODEOWNERS`, `.github/dependabot.yml`, CodeQL + secret scan workflows).
- [x] Added repository hygiene gate (`scripts/check_repo_hygiene.py`) in CI to prevent tracked local artifacts.
- [x] Aligned OSS metadata to launch target repo (`synapseworkspace/synapse`) across SDK package manifests, web docs links, CODEOWNERS handle, and publish-hygiene validator defaults.

## M10: Agentic Wiki Productization (Weeks 19-22)

Status: `completed`

Scope:
- README and landing messaging aligned to "Agentic Wiki" and OpenClaw-first narrative.
- Preserve core workflow clarity: `observe -> synthesize -> curate -> execute`.
- Reduce first-run cognitive load in UI via core-only defaults/profile locks.
- Validate implementation coverage against original product thesis (not just platform mechanics).

Exit criteria:
- New visitor understands product value and target user in under 60 seconds.
- OpenClaw developer can follow dedicated quickstart path from root README.
- Core moderation workflow works without entering advanced control surfaces.

Progress:
- [x] Reworked root README around Agentic Wiki narrative + dedicated OpenClaw section and quickstart.
- [x] Added branded visual assets (`assets/synapse-logo.svg`, `assets/synapse-hero.svg`) and refined hero copy.
- [x] Introduced web `core-only` profile lock via `VITE_SYNAPSE_UI_PROFILE` (`core`, `core-only`, `wiki-core` aliases) to hide advanced mode/expert toggles for first-value deployments.
- [x] Added explicit product/value one-pager in `docs/` for investors + technical buyers (`docs/agentic-wiki-overview.md`).
- [x] Added focused OpenClaw “5-minute” copy path parity across root README, docs, and demos with canonical entrypoint (`docs/openclaw-quickstart-5-min.md`).
- [x] Added OSS "Core vs Enterprise" scope matrix in docs (`docs/core-vs-enterprise.md`) and linked it from root README.
- [x] Verified core-only UX behavior with focused e2e run under profile lock (`CI=1 VITE_SYNAPSE_UI_PROFILE=core-only npx playwright test --grep "task tracker lifecycle flow"`).

## M11: Enterprise Foundation (Weeks 23-26)

Status: `done`

Scope:
- Introduce first-class tenancy model and migration path from project-only isolation.
- Add SSO baseline (OIDC-first) for API/UI identity flows.
- Promote RBAC from incident-secret-only checks to platform-wide policy enforcement.
- Document enterprise hardening status and delivery plan for OSS adopters.

Exit criteria:
- Tenant-aware auth context exists across API/UI.
- OIDC login can authenticate and map roles/tenant claims.
- Privileged operations are consistently enforced by role policy checks.

Progress:
- [x] Added enterprise status baseline with explicit “implemented vs missing” matrix and phased delivery plan (`docs/enterprise-readiness.md`).
- [x] Add tenant entities and membership mapping in DB/API.
- [x] Implement OIDC auth mode for API + web session flow.
- [x] Add unified RBAC policy evaluator with deny-by-default mode.
- [x] Add governance export/runbook pack for enterprise operations.

## M12: Framework Integrations (Weeks 27-29)

Status: `done`

Scope:
- Make LangGraph/LangChain/CrewAI integrations first-class alongside OpenClaw.
- Provide deterministic adapter contracts with CI smoke enforcement.
- Keep one-line attach DX with integration auto-detection and explicit override.
- Publish clear framework integration matrix for users.

Exit criteria:
- Integration auto-detection is stable for LangGraph/LangChain/CrewAI-like runtimes.
- CI fails on adapter contract regressions.
- Docs include production-ready examples for each framework path.

Progress:
- [x] Added LangChain adapter support in Python/TypeScript monitor defaults and auto-detection.
- [x] Added offline Python framework contract checker (`scripts/check_framework_adapter_contracts.py`) and wired it into CI.
- [x] Extended TypeScript CI smoke to assert auto-detection for LangGraph/LangChain/CrewAI.
- [x] Added framework integration status doc (`docs/framework-integrations.md`) and linked it from README.
- [x] Added dedicated LangChain + CrewAI cookbook demos with golden output snapshots (`demos/cookbook/*`, `scripts/check_cookbook_snapshots.py`).
- [x] Added integration-version compatibility table by framework major versions (`docs/framework-integrations.md`).
- [x] Added Python native framework bindings: LangChain/LangGraph callback handler path and CrewAI event/step hook path (`synapse_sdk.integrations.native`, `scripts/check_framework_native_bindings.py`).
- [x] Added TypeScript native framework bindings parity: LangChain/LangGraph callback bind path and CrewAI native hook path (`Synapse.bindLangchain/bindLanggraph/bindCrewAi`) with CI smoke coverage.

## M13: Reliability & SLO Control (Weeks 30-33)

Status: `done`

Scope:
- Formalize runtime SLO budgets for latency and retrieval quality.
- Enforce SLO thresholds in CI/release gate path.
- Improve observability posture from "available" to "operationally actionable."
- Publish reliability runbook and escalation policy.

Exit criteria:
- Core SLO checks run in CI with deterministic fail/pass behavior.
- SLO definitions are explicit and documented for OSS operators.
- Observability and incident runbooks cover SLO breach response.

Progress:
- [x] Added baseline reliability/SLO runbook (`docs/reliability-slo.md`) with explicit budgets.
- [x] Added `scripts/check_core_slo_guardrails.py` (benchmark-based latency/quality gate).
- [x] Wired SLO guardrail smoke checks into `scripts/ci_checks.sh`.
- [x] Added ingest latency + moderation latency SLO checks from API snapshots (`/v1/events/throughput`, `scripts/check_operational_slo_guardrails.py`).
- [x] Add rolling error-budget policy and release-blocking gate.
- [x] Add degraded-dependency/load-profile reliability drills.

## M14: Existing-Memory Adoption (Weeks 34-36)

Status: `done`

Scope:
- Add first-class coexistence modes for integrating Synapse into mature stacks without replacing existing memory stores.
- Provide an adoption wizard with dry-run analysis for legacy memory exports.
- Establish explicit source-ownership policy to prevent dual source-of-truth drift.
- Ship rollout playbook from `observe_only` to controlled `full_loop`.

Exit criteria:
- Team can start integration in `observe_only` with no behavior regression.
- Adoption plan can be generated automatically from sample memory export.
- SDK attach contracts document and enforce coexistence modes.

Progress:
- [x] Added SDK attach coexistence mode controls (`full_loop|observe_only|draft_only|retrieve_only`) in Python and TypeScript.
- [x] Added OpenClaw tool/hook gating by mode (capture hooks and search/propose/task tools can be policy-driven per attach).
- [x] Added CLI adoption wizard (`synapse-cli adopt`) with sample memory analysis, rollout plan, and ready-to-paste integration snippet.
- [x] Extended CLI connect flow with explicit adoption mode (`--adoption-mode`) and snippet emission.
- [x] Added CI smoke coverage for adoption wizard flow in `scripts/ci_checks.sh`.
- [x] Add API-level source ownership registry and enforcement (`write-master` by domain/category).
- [x] Add shadow retrieval evaluation command (`synapse-cli adopt --shadow-retrieval-check`) with quality diff report.
- [x] Publish dedicated migration playbook doc (`docs/adoption-existing-memory.md`) with anti-corruption layer patterns.

## Next Up (Execution Queue)

1. Expand release gate from fixture-backed checks to auto-appended live reliability history snapshots per environment.
2. Add incident runbooks linked to SLO violation codes for faster operator triage.

## Risks to Watch

1. Low precision claim extraction in noisy logs.
2. Temporal parsing ambiguity for informal date phrases (locale and shorthand variants).
3. Integration overhead across agent frameworks.
4. Scope drift between OSS core and enterprise addons.
5. Wiki bloat without strict Gatekeeper thresholds and archival policy.
6. Local dev DB instability if Docker VM storage is saturated during heavy migration replay.
7. SDK API sprawl can reduce adoption if facade and plugin boundaries are not tightly controlled.
8. Product-message drift: technical docs can overshadow Agentic Wiki value narrative and reduce conversion.

## Recent Updates

- 2026-04-04: Added universal Gatekeeper routing-policy layer for wiki quality control: new DB migration (`049_gatekeeper_routing_policy.sql`), API support in `GET/PUT /v1/gatekeeper/config` (`routing_policy`), and worker-side enforcement that demotes raw event-stream style memory (orders/status/telemetry/log-like payloads) to `operational_memory` unless policy/incident override signals are present; also added minimum independent evidence/source guardrails before wiki routing.
- 2026-04-04: Upgraded existing-memory connector UX from dense inline form to guided setup wizard: Wiki Tree now shows a compact status card with “Open setup wizard”, and the wizard runs a clear 3-step flow (profile -> connector config -> review/launch) before queuing first sync.
- 2026-04-04: Added user-friendly existing-memory onboarding in web core wiki workspace: new “Connect Existing Agent Memory” quickstart card (profile + DSN env + source ref + cadence), wired to native legacy-import APIs (`/v1/legacy-import/profiles`, `/v1/legacy-import/sources`, `/sync`) with one-click connect-and-first-sync flow, plus mock API parity for e2e/dev.
- 2026-04-04: Closed existing-memory adoption gap for custom stacks without custom import scripts: added built-in Postgres legacy memory profiles (`ops_kb_items`, `memory_items`, `auto`) with API discovery endpoint (`GET /v1/legacy-import/profiles`), profile-aware source upsert normalization in API, and worker-side profile auto-resolution that discovers table/columns, generates safe incremental polling SQL, and persists resolved profile/table/cursor metadata into source config.
- 2026-04-04: Switched knowledge publication defaults to autonomous-first mode: Gatekeeper fallback/default `publish_mode_default` is now `auto_publish` (API + worker), added explicit wiki page rollback endpoint (`PUT /v1/wiki/pages/{slug}/rollback`) backed by page-version history, and shipped admin-facing publish-mode control in web Governance panel so operators can downgrade to `human_required` per project when needed.
- 2026-04-03: Closed execution queue item “automated pre-prod chaos runs”: added `scripts/run_selfhost_chaos_drill.sh` (clean self-hosted stack boot, baseline core-loop acceptance, dependency fault injection, post-fault recovery + core-loop verification, JSON report), wired optional CI workflow dispatch job (`run_selfhost_chaos_drill=true`) with artifact upload, and integrated local opt-in + script-smoke coverage into `scripts/ci_checks.sh` plus reliability/self-hosted runbook updates.
- 2026-04-03: Closed execution queue item “low-latency external-memory ingestion”: extended `postgres_sql` legacy source with `sql_sync_mode=wal_cdc` (logical-slot CDC via `pg_logical_slot_get_changes|peek_changes`, `test_decoding` + `wal2json` parser support, table/operation filters, LSN state persistence, and canonical record mapping), kept polling mode as default/backward-compatible path, lowered orchestration cadence floor to 1 minute (migration `048_legacy_sync_low_latency_interval.sql` + API validation update), and added deterministic WAL connector smoke check (`scripts/check_legacy_sync_wal_connector.py`) to CI.
- 2026-04-03: Completed Recovery Plan closure for wiki-first rollout: tightened Gatekeeper runtime-noise demotion (single-source one-off runtime memory events now route to `operational_memory` unless high-priority/policy signals), simplified Draft Inbox core UX with explicit `Migration Mode` gating for bootstrap tools, and hardened trusted-source adoption API (`/v1/wiki/drafts/bootstrap-approve/run`) with apply-time trusted-source requirement + soft batch cap + safety metadata.
- 2026-04-03: Closed SAML/SCIM bridge execution queue item: added enterprise bridge migration `047_saml_scim_bridge.sql` (`enterprise_idp_connections`, `scim_api_tokens`, `scim_directory_users`), shipped tenant-scoped IdP bridge APIs (`GET/PUT /v1/enterprise/idp/connections`, `GET /v1/enterprise/idp/saml/metadata`), delivered SCIM token admin APIs (`GET/PUT/DELETE /v1/enterprise/scim/tokens`), and added SCIM provisioning surface (`/scim/v2/ServiceProviderConfig`, `/scim/v2/Users*`) wired to tenant memberships with scope-gated token auth.
- 2026-04-03: Shipped enterprise RBAC policy-decision audit baseline: added migration `046_access_policy_decisions.sql`, middleware logging for guarded request decisions (`allow|deny` with roles/project scope/path/action metadata), and compliance read API `GET /v1/enterprise/rbac/decisions` protected by operator roles in RBAC enforce mode.
- 2026-04-03: Closed the remaining C2 execution queue item: `GET /v1/wiki/pages` now supports explicit index filters (`status`, `updated_by`, `with_open_drafts`) and web Wiki Tree now exposes those filters in UI; added deep-linkable wiki selection/filter state via URL params (`project`, `wiki_space`, `wiki_page`, `wiki_status`, `wiki_updated_by`, `wiki_with_open_drafts`, `wiki_q`) for shareable page context links.
- 2026-04-03: Marked Confluence-like execution slices C1-C6 as complete (`done`) after finishing page editing/index/operations/collaboration/governance and QoL closure (including uploads, media previews, and command-palette editing).
- 2026-04-03: Completed reviewed-status lifecycle rollout: added migration `045_wiki_reviewed_status.sql` and extended wiki page status handling in API/UI to support `reviewed` between `draft` and `published`.
- 2026-04-03: Completed C6 upload workflow closure: added wiki upload storage + delivery APIs (`POST /v1/wiki/uploads`, `GET /v1/wiki/uploads`, `GET /v1/wiki/uploads/{upload_id}/content`) backed by migration `044_wiki_uploads.sql`, wired page edit UI upload action with auto-insert markdown snippet, and added page-context attachment list with direct open links.
- 2026-04-03: Extended C6 with wiki media ergonomics: `WikiPageCanvas` now extracts markdown media/attachments and renders production-style preview surfaces (image gallery + linked file list), plus quick insert commands for image/file markdown templates.
- 2026-04-03: Started C6 wiki editor quality pass: upgraded `WikiPageCanvas` with command palette (`Ctrl/Cmd + /`), quick block insertions (Info/Warning callouts, incident + decision templates), and table authoring commands (insert/add row/add column/delete), with new table typography styling for page-edit readability.
- 2026-04-03: Advanced C5 governance delivery: added migration `043_wiki_policy_notifications.sql`; shipped space policy + ownership APIs (`/v1/wiki/spaces/{space_key}/policy`, `/v1/wiki/spaces/{space_key}/owners`), page ownership APIs (`/v1/wiki/pages/{slug}/owners`), and notification inbox APIs (`/v1/wiki/notifications*`); enforced wiki space policy in write/comment flows (`owners_only` + review-required publish gate), added mention/watcher/review assignment notification fan-out, and integrated web governance controls + notifications inbox into core wiki workspace.
- 2026-04-03: Extended C4 collaboration with reviewer workflow: added migration `042_wiki_review_assignments.sql`, API endpoints for page review assignments (`list/upsert/resolve`), and web Page Context card to assign and resolve reviewers directly from wiki page operations.
- 2026-04-03: Started C4 collaboration layer for wiki pages: added migration `041_wiki_collaboration.sql`, new APIs for page aliases/comments/watchers (`/aliases`, `/comments`, `/watchers`), alias-aware page resolution for `GET /v1/wiki/pages/{slug}` and history (canonical slug fallback via alias), and integrated collaboration cards into `Page Context` UI.
- 2026-04-03: Extended C3 with lifecycle + hierarchy operations: added `PUT /v1/wiki/pages/{slug}/reparent`, `PUT /v1/wiki/pages/{slug}/archive`, and `PUT /v1/wiki/pages/{slug}/restore`; web wiki page header now exposes `Archive`/`Restore` actions and uses explicit reparent flow from `Move/Rename`.
- 2026-04-03: Started C3 page operations execution: added API endpoint `PUT /v1/wiki/pages/{slug}/move` with optional subtree move (`include_descendants`), slug/title rename support, backward-compat alias insertion, source-ownership + idempotency safeguards, and knowledge snapshot invalidation; web `Wiki Page` now includes breadcrumb navigation and inline `Move/Rename` flow (parent path + slug leaf + subtree toggle) with immediate tree refresh.
- 2026-04-03: Started Confluence-like C2 execution: added API endpoint `GET /v1/wiki/pages` (independent page index with page/draft counters, sort/filter, and paging metadata) and switched web Wiki Tree rendering to page-index-first mode, so pages appear even without active drafts; page edits/creates now trigger tree refresh immediately.
- 2026-04-03: Further de-emphasized non-wiki surfaces in core header navigation: replaced direct `Draft Inbox`/`Tasks` top actions with a single `Operations` entrypoint and nested operational actions (`Open Draft Inbox`, `Open Tasks`) so wiki remains the dominant product affordance.
- 2026-04-03: Added wiki-first empty-state experience: `Wiki Home` now renders spaces directory and recent-pages quick-jump when no page is selected, avoiding dead-end empty preview states and reinforcing page-centric navigation.
- 2026-04-03: Reduced Draft Inbox operational noise in core mode: default Draft view now exposes queue-first cards only, while filters/bootstrap/queue controls are moved behind `Open operations`; expert mode still shows full controls by default.
- 2026-04-03: Added wiki page-level decision surface for core mode: `Wiki Page` now includes a page header card with page status/type/version, latest update metadata, revision delta summary, and quick actions (`Refresh Page`, `Open Page Drafts`) while `Page Context` now exposes compact change deltas from recent revisions.
- 2026-04-03: Finalized wiki-centric visual hierarchy in core landing: updated primary banner/product copy to `Company Wiki, Written by Agents`, removed equal visual emphasis for Drafts/Tasks in the hero, and positioned operations controls as secondary actions to align with corporate-wiki-first product intent.
- 2026-04-03: Reframed core navigation to wiki-first command pattern: replaced equal-priority `Wiki/Drafts/Tasks` tabs with a corporate-wiki command bar (`Open Wiki` primary + secondary operations actions), added page quick-jump, and introduced a dedicated `Page Context` rail (sections, recent revisions, page-scoped open drafts) to make wiki browsing the dominant workflow.
- 2026-04-03: Simplified core connection setup: `API URL` field is now advanced-only, while core mode uses `VITE_SYNAPSE_API_URL`/default endpoint to reduce first-run configuration burden; Playwright config now injects API URL via env for deterministic core e2e.
- 2026-04-03: Reduced `Drafts` first-view density in core mode: bootstrap migration controls are now collapsed behind `Open tools`, and triage/intent analytics cards are shown only in expert mode, keeping default operator flow focused on queue + moderation actions.
- 2026-04-03: Started Confluence-like wiki page-first alignment in core mode: added dedicated `Wiki Page` preview panel with read-only wiki canvas (article view) next to `Wiki Tree`, so operators can browse published content without entering moderation screens.
- 2026-04-03: Hardened migration bootstrap safety defaults in `Drafts`: batch approve now requires a matching dry-run preview (same project/source/confidence/conflict/limit settings), reducing accidental mass-approval risk during first-time backfill adoption.
- 2026-04-03: Started adoption migration UX in web `Drafts`: added `Bootstrap Migration` card with trusted-source filters, confidence/limit controls, dry-run candidate preview, and batch-approve execution against `POST /v1/wiki/drafts/bootstrap-approve/run` for first-run backfill onboarding.
- 2026-04-03: Completed core wiki IA split in default profile: added explicit `Wiki | Drafts | Tasks` navigation tabs, switched core rendering to contextual surfaces (task tracker isolated from wiki/draft moderation panels), auto-routed triage/quick-moderation actions to `Drafts`, and updated core e2e coverage for the new workflow.
- 2026-04-03: Started Wiki-first recovery implementation: web console now enforces a cleaner default IA (advanced control-center mode hidden unless explicit advanced UI profile), added auth-gated entry screen for enforced auth projects, and simplified core banner from walkthrough-heavy blocks to a compact `Wiki/Drafts/Tasks` operator surface.
- 2026-04-03: Started Draft noise suppression rollout: Gatekeeper now demotes single-source one-off observations without policy signal to `operational_memory`, reducing low-signal draft creation from raw memory/backfill streams.
- 2026-04-03: Added native existing-memory SQL adoption path to reduce custom importer burden: introduced `postgres_sql` legacy source type across API + DB migration (`040_legacy_sync_postgres_sql_source.sql`), implemented generic SQL importer (`SQLImporter`) with canonical-column/mapping support, deterministic `source_id` generation, metadata enrichment, and incremental cursor handoff; wired scheduled sync engine cursor state persistence (`sql_last_cursor`) and one-shot SQL mode in `run_legacy_import.py`, plus docs and CI smoke coverage updates.
- 2026-04-03: Hardened self-hosted production defaults and adoption diagnostics: switched selfhost MCP transport default to `streamable-http`, removed fixed `container_name` from selfhost compose, added loopback-safe port binds (`SYNAPSE_BIND_HOST`), added MCP healthcheck + restart-loop detection in selfhost acceptance scripts, added selfhost static consistency CI gate (`scripts/check_selfhost_stack_defaults.py`), improved wiki search explainability metadata + new `GET /v1/wiki/stats`, and shipped trusted-source bootstrap migration endpoint `POST /v1/wiki/drafts/bootstrap-approve/run` (`dry_run` + confidence/conflict/source filters).
- 2026-04-03: Completed M14 existing-memory adoption closure: added API source-ownership registry endpoints (`GET/PUT/DELETE /v1/adoption/source-ownership`) + runtime write-master enforcement by domain with advisory/enforce modes and `X-Synapse-Source-System` support, shipped `synapse-cli adopt --shadow-retrieval-check` (baseline-vs-Synapse diff report), and extended CI smoke coverage for shadow adoption checks.
- 2026-04-03: Started M14 existing-memory adoption track: added Python/TypeScript SDK coexistence modes (`full_loop|observe_only|draft_only|retrieve_only`) with OpenClaw hook/tool gating, shipped CLI migration wizard `synapse-cli adopt` (+ sample memory risk analysis + rollout plan), extended `synapse-cli connect openclaw` with `--adoption-mode`, and added CI smoke coverage for adoption flow.
- 2026-04-03: Added hybrid publish-control business logic: Gatekeeper config now supports `publish_mode_default` + per-category overrides + conditional auto-publish thresholds (`auto_publish_min_score`, `auto_publish_min_sources`, `auto_publish_require_golden`, `auto_publish_allow_conflicts`); API endpoint `POST /v1/wiki/auto-publish/run` executes policy-driven approvals; worker loop now includes scheduled auto-publish job (`run_wiki_autopublish.py`).
- 2026-04-03: Completed enterprise foundation closure (M11): shipped migration `037_enterprise_tenancy_auth_rbac.sql` with first-class `tenants`/`tenant_memberships`/`tenant_projects`/`auth_sessions`, added API auth session flow (`/v1/auth/mode`, `/v1/auth/session`), wired request middleware for OIDC + tenancy enforcement + unified RBAC deny-by-default modes, added web console auth-session controls/token propagation, and published governance export/runbook tooling (`scripts/export_enterprise_governance_pack.py`, `docs/enterprise-governance-pack.md`).
- 2026-04-03: Completed reliability release-policy closure (M13): added rolling error-budget release gate (`scripts/check_release_error_budget.py`, `eval/reliability_error_budget_sample.jsonl`) and deterministic reliability drill suite (`scripts/run_reliability_drills.py`) with CI enforcement in `scripts/ci_checks.sh`.
- 2026-04-03: Closed framework milestone status sync (M12): all listed LangChain/LangGraph/CrewAI native adapter and contract tasks are complete and milestone status moved to `done`.
- 2026-04-03: Added TypeScript native framework binding parity: shipped SDK helpers (`langchainCallbackHandler`, `buildLangchainConfig`, `bindLangchain`, `bindLanggraph`, `bindCrewAi`), extended TS smoke contracts in `scripts/ci_checks.sh`, and updated framework/docs references.
- 2026-04-03: Added native framework SDK path for Python: shipped LangChain/LangGraph callback binding helpers (`langchain_callback_handler`, `bind_langchain`, `bind_langgraph`) and CrewAI native hook helper (`bind_crewai`) with new CI contract gate (`scripts/check_framework_native_bindings.py`), plus docs/reference updates.
- 2026-04-03: Completed framework + operational SLO depth pass: added dedicated LangChain/CrewAI cookbook demos with golden snapshots (`demos/cookbook/langchain_playbook_sync.py`, `demos/cookbook/crewai_playbook_sync.py`, `scripts/check_cookbook_snapshots.py`), published framework major-version compatibility matrix (`docs/framework-integrations.md`), added API ingest throughput endpoint (`GET /v1/events/throughput`), shipped operational SLO tooling (`scripts/capture_operational_slo_snapshots.py`, `scripts/check_operational_slo_guardrails.py`, `eval/operational_slo_snapshot_sample.json`), and wired all new checks into `scripts/ci_checks.sh`.
- 2026-04-03: Started framework + reliability execution track: added LangChain integration auto-detection/wrappers (Python+TypeScript), added offline framework contract checker (`scripts/check_framework_adapter_contracts.py`) and CI enforcement, added baseline SLO guardrail checker (`scripts/check_core_slo_guardrails.py`) with CI smoke, and published docs (`docs/framework-integrations.md`, `docs/reliability-slo.md`).
- 2026-04-03: Added explicit enterprise capability status page (`docs/enterprise-readiness.md`) with factual coverage matrix (tenancy/SSO/RBAC/audit/secrets) and phased E1-E4 implementation plan.
- 2026-04-03: Resolved package registry ambiguity for OSS publishing by moving npm package scope to `@synapseworkspace/*` and Python package name to `synapseworkspace-sdk`, updated release/docs/hygiene validators, and validated full `./scripts/ci_checks.sh`.
- 2026-04-03: Closed all open Dependabot PR backlog after consolidated security updates (open security alerts: 0, open PRs: 0).
- 2026-04-03: Cut release candidate artifacts for OSS launch: added `v0.1.0` release notes draft (`docs/releases/v0.1.0.md`), pushed annotated tag `v0.1.0`, and created GitHub draft release (`v0.1.0`) for `synapseworkspace/synapse`.
- 2026-04-03: Reduced open Dependabot security exposure from 8 to 4 alerts by applying non-breaking npm lockfile updates (upgraded vulnerable transitive `lodash` across root/apps lockfiles); remaining alerts require major upgrades (`vite`/`esbuild`, `diff`).
- 2026-04-03: Closed remaining roadmap queue: shipped TypeScript OpenClaw `Synapse.attach(..., integration="openclaw")` runtime parity (auto hook wiring, runtime tools, SDK auto-search fallback, provenance on `propose_to_wiki`), added canonical OpenClaw docs lint gate (`scripts/check_openclaw_docs_canonical.py`) wired into CI, introduced cookbook golden snapshot regression guard (`scripts/check_cookbook_snapshots.py` + `demos/cookbook/snapshots/*`) with CI coverage, and delivered core wiki UI theming polish pass (Confluence-like panel density/navigation cues) plus hero Execute card overflow fix in `assets/synapse-hero.svg`.
- 2026-04-03: Completed cookbook parity pass for Agentic Wiki narrative: added runnable LangGraph scenario (`demos/cookbook/langgraph_playbook_sync.py`) with observe/synthesize/execute loop, updated cookbook guide and Getting Started scenario list, and validated the new script in a clean venv (`python3 -m venv /tmp/synapse-cookbook-check && ... && python demos/cookbook/langgraph_playbook_sync.py`).
- 2026-04-02: Completed zero-config SDK attach pass: added `Synapse.from_env()` (Python) and `Synapse.fromEnv()`/`fromEnv()` (TypeScript), enabled OpenClaw auto-bootstrap default (`hybrid`) on attach, added SDK-level default retrieval-backed OpenClaw search fallback (Python connector + TS plugin fallback), introduced onboarding friction metrics APIs (`get_onboarding_metrics` / `getOnboardingMetrics`), refreshed README/OpenClaw quickstart docs, and validated end-to-end via `SYNAPSE_SKIP_WEB_E2E=1 ./scripts/ci_checks.sh`.
- 2026-04-02: Collapsed OpenClaw onboarding doc drift into a single canonical path (`docs/openclaw-quickstart-5-min.md`): converted tutorial `02-openclaw-quickstart` into alias/redirect, updated tutorials index, integration deep-dive, OSS readiness references, and cookbook onboarding pointers.
- 2026-04-02: Shifted product messaging to Agentic Wiki + OpenClaw-first narrative in root README, added dedicated OpenClaw quickstart/value block, updated hero brand assets, and introduced web core-only profile lock (`VITE_SYNAPSE_UI_PROFILE`) to keep first-run UX focused on core moderation loop.
- 2026-04-02: Completed M10 docs and UX validation pass: added `docs/agentic-wiki-overview.md`, `docs/openclaw-quickstart-5-min.md`, and `docs/core-vs-enterprise.md`; linked canonical docs from README/getting-started/demos/tutorials; and validated `core-only` UI profile behavior with Playwright under `VITE_SYNAPSE_UI_PROFILE=core-only`.
- 2026-04-02: Completed repo-target alignment pass for public launch: switched OSS metadata and links from template org to `synapseworkspace/synapse` (PyPI/npm package URLs, web docs link base, observability runbook URLs, CODEOWNERS owner), added publish-hygiene override env vars (`SYNAPSE_EXPECTED_REPO`, `SYNAPSE_EXPECTED_ISSUES`), and documented exact GitHub repository creation fields + post-create settings in OSS publish checklist.
- 2026-04-02: Completed final pre-publish hardening pass: added GitHub ownership/dependency/security automation baseline (`CODEOWNERS`, `dependabot`, `codeql`, `secret-scan`) and introduced repository hygiene CI guard (`check_repo_hygiene.py`) to block tracked local artifacts (`.venv`, `node_modules`, `.env*`), with docs/release checklist updates.
- 2026-04-02: Completed OSS publication hardening pass: added governance docs (`MAINTAINERS.md`, `SUPPORT.md`, `DEPRECATION_POLICY.md`), shipped generated SDK API reference baseline (`docs/reference/*`) with CI freshness check (`scripts/generate_sdk_api_reference.py --check`), and introduced dedicated runtime compatibility matrix workflow (`.github/workflows/compat-matrix.yml`) for Python SDK (`3.10-3.13`) and Node SDK/plugin (`18/20/22`) smoke coverage.
- 2026-04-02: Extended post-M9 onboarding DX with `synapse-cli quickstart`: one-command orchestration for `init -> doctor -> connect` plus optional `verify core-loop`, JSON step-level result contract for automation, docs updates, and offline CI smoke coverage.
- 2026-04-02: Started the next post-M9 improvement cycle and delivered `synapse-cli verify core-loop`: CLI wrapper for end-to-end acceptance (`ingest -> draft -> approve -> MCP retrieval`) with script auto-detection, dry-run mode, JSON report contract, docs updates, and offline CI smoke via a deterministic stub runner.
- 2026-04-02: Completed post-cleanup guardrails hardening: CI now explicitly asserts rejection of deprecated MCP context-policy aliases (`strict`/`default`) in both TypeScript and Python smoke flows, preventing accidental compatibility fallback reintroduction.
- 2026-04-02: Completed legacy cleanup pass for OSS/core clarity: archived outdated planning artifact (`WORKPLAN.md` -> `docs/archive/WORKPLAN-v0.1.md`), deprecated SDK `init(...)` compatibility path in favor of explicit `Synapse(...)`, removed MCP profile alias shortcuts (`strict`/`default`) to keep policy config explicit, and dropped obsolete pre-migration fallback branch from integration acceptance flow.
- 2026-04-02: Completed MCP retrieval calibration ops pass: `check_mcp_retrieval_trend.py` now emits automated `recommended_context_policy_profile` hints (`advisory|enforced|strict_enforced` + thresholds + SDK defaults), performance tuning advisor/report now includes context-policy recommendation + apply command, docs now include profile-to-threshold cookbook, and CI smoke asserts the new trend contract.
- 2026-04-02: Completed legacy import QA expansion pass: extended seed regression dataset to 5 golden cases with Notion-heavy seeding and mixed-language section override edge cases; upgraded `LegacySeedOrchestrator` with normalized override keys and multilingual category aliases (`OPS`/`операции`/`доступ` etc), and synced legacy-import/sync docs.
- 2026-04-02: Completed OpenClaw bootstrap preset parity pass for TypeScript SDK/plugin onboarding: added TS public helpers (`buildOpenClawBootstrapOptions`, `collectOpenClawBootstrapRecords`, `listOpenClawBootstrapPresets`), wired `openclawBootstrapPreset` into `Synapse.attach(...)`, updated OpenClaw docs/README examples, and added TS preset smoke coverage to contributor CI.
- 2026-04-02: Completed M9 zero-friction onboarding track: added `synapse-cli connect openclaw` (env-aware snippet generator for attach + MCP callback defaults), expanded CI smoke coverage for CLI (`doctor`, `init`, `connect`), and published canonical 3-command onboarding path in Getting Started (`init -> doctor -> connect`).
- 2026-04-02: Extended M9 onboarding flow with `synapse-cli init`: creates project-local `.env` scaffold (`SYNAPSE_API_URL`, `SYNAPSE_PROJECT_ID`, MCP/OpenClaw defaults), supports dry-run/force/json modes, emits copy-paste quickstart commands, and is now covered by offline CI smoke.
- 2026-04-02: Started zero-friction onboarding track (M9) and shipped first deliverable `synapse-cli doctor`: local API/core-loop diagnostics with strict mode, project-scoped checks (`tasks`, `wiki drafts`, `mcp retrieval explain`), actionable fix hints, JSON output for automation, and offline CI smoke coverage via embedded mock server.
- 2026-04-02: Completed MCP/OpenClaw context-policy rollout pass: added policy profile presets (`off`, `advisory`, `enforced`, `strict_enforced`) in Python/TypeScript MCP helpers, enabled profile-based defaults for direct retrieval and OpenClaw search callbacks, exported profile discovery helpers (`list_context_policy_profiles` / `listContextPolicyProfiles`), updated MCP/OpenClaw onboarding docs/tutorials, and extended CI smoke coverage to assert strict-profile threshold propagation in MCP tool calls.
- 2026-04-02: Completed legacy import QA pass: added deterministic seed-planning regression evaluator (`scripts/eval_legacy_seed_regression.py`) with golden fixtures (`eval/legacy_seed_cases.json`) covering grouping modes (`entity|category|category_entity`), section override resolution, and stable wiki page targeting under input-order changes; wired evaluator into contributor CI smoke and documented operator usage in legacy-import/worker docs.
- 2026-04-02: Completed OpenClaw bootstrap preset pass in Python SDK: wired one-line attach presets (`openclaw_bootstrap_preset=runtime_memory|event_log|hybrid`) into `Synapse.attach(...)` with tunable limits/source metadata, exported preset helpers in public SDK API (`OPENCLAW_BOOTSTRAP_PRESETS`, `build_openclaw_bootstrap_options`, `list_openclaw_bootstrap_presets`), updated OpenClaw onboarding docs/tutorial snippets, and extended offline contributor smoke checks to assert preset-enabled attach bootstrap behavior.
- 2026-04-02: Completed graph retrieval confidence pass: added shared retrieval confidence + context-policy contract (`retrieval_confidence`, `confidence_breakdown`, per-result `context_policy` eligibility), shipped runtime/API policy controls (`context_policy_mode`, `min_retrieval_confidence`, `min_total_score`, `min_lexical_score`, `min_token_overlap_ratio`) with enforced filtering support and exposed policy headers (`X-Synapse-Retrieval-Context-*`), extended SDK MCP helpers (Python/TypeScript) for context-policy propagation and fallback filtering, and upgraded web diagnostics UI/e2e to configure and inspect context-injection policy outcomes.
- 2026-04-02: Completed legacy import orchestrator pass: shipped deterministic `LegacySeedOrchestrator` enrichment for cold-start records (`synapse_seed_plan` + `synapse_source_provenance` metadata), wired orchestration into both one-shot importer (`run_legacy_import.py`) and scheduled refresh worker (`legacy_sync.py`), added per-source seed config knobs (`seed_page_prefix`, `seed_space_key`, `seed_group_mode`, `seed_section_overrides`) with run summaries (`seed_pages`, `top_pages`), and extended offline CI smoke checks/docs for seed-planning/provenance guarantees.
- 2026-04-02: Completed cold-start memory bootstrap attach pass for universal SDKs: added typed attach-time bootstrap contracts in Python (`BootstrapMemoryOptions`, `bootstrap_memory=` on `Synapse.attach`) and TypeScript (`bootstrapMemory` on `attach(...)`) with provider-or-record modes, deduped/normalized record coercion (`string|dict|typed record`), source/session-aware backfill handoff into `/v1/backfill/memory`, and structured attach lifecycle debug events (`attach_bootstrap_*`); updated Python/TypeScript SDK docs with one-line attach bootstrap examples and extended CI offline smoke (`scripts/ci_checks.sh`) to assert attach-triggered bootstrap ingestion.
- 2026-04-02: Completed core wiki intent-and-explainability UX pass in web console: added session-scoped `Intent Signals` analytics (triage opens, unique triage drafts, quick moderation counters by source lane, actions/hour, last action trace), upgraded triage lane with human-readable queue-priority reason badges plus explicit priority score chips, and added inline docs affordance via hover previews for core walkthrough links before leaving to external docs; Playwright core-flow e2e now asserts signals visibility, triage interaction tracing, and docs-preview behavior.
- 2026-04-02: Completed core walkthrough telemetry pass in `Core Mode`: added session-scoped onboarding telemetry block with first-completion latency timers for walkthrough milestones (`workspace ready`, `inbox loaded`, `first draft opened`) and explicit counters for onboarding actions (`Use demo values`, `Load Draft Queue`, `Select draft`), plus e2e coverage for telemetry panel visibility.
- 2026-04-02: Completed OSS release automation polish for CI/stdout stability: added `--summary-only` compact output mode to synthesis/gatekeeper/MCP retrieval regression evaluators (`scripts/eval_synthesis_regression.py`, `scripts/eval_gatekeeper_regression.py`, `scripts/eval_mcp_retrieval_regression.py`) and switched `scripts/ci_checks.sh` to use compact mode, reducing release-profile guardrails log volume while preserving pass/fail signals and metric thresholds.
- 2026-04-02: Completed core wiki moderation guardrails UX pass: added 6-second double-confirmation safety flow for high-impact moderation actions (force-approve and reject-dismiss variants across conflict quick actions, approve/reject forms, and bulk moderation paths), with inline button-label confirmation states (`Confirm ...`) and warning notifications before execution.
- 2026-04-02: Completed core moderation accessibility pass in web console: added explicit `aria-label` coverage for icon-only critical actions (`Refresh drafts`, `Quick approve/reject draft`) and introduced high-contrast global `focus-visible` ring styling for keyboard navigation (`.mantine-focus-auto:focus-visible`), with updated core e2e assertions validating accessible action naming.
- 2026-04-02: Completed core wiki first-run operator walkthrough in `Core Mode`: added guided 3-step onboarding panel (`connect workspace -> load inbox -> select draft`) with contextual one-click actions (`Use demo values`, `Load Draft Queue`, `Select draft`) and direct docs links (`Getting Started`, `Core Scope`, `Web Console Guide`), updated web styling/readability for the walkthrough block, and aligned Playwright core-flow assertions.
- 2026-04-02: Completed OSS publish readiness sweep validation pass: confirmed full contributor guardrails release profile (`./scripts/run_contributor_guardrails.sh --profile release`) succeeds end-to-end including RC dress rehearsal clean-room package checks and docs presence audit, with report artifact generated at `artifacts/release/rc-dress-rehearsal.json`.
- 2026-04-02: Completed MCP/API retrieval diagnostics UX follow-up: `GET /v1/mcp/retrieval/explain` now returns effective retrieval graph tuning snapshot (`graph_config.max_graph_hops`, `boost_hop1|2|3|other`) and mirrors the same values in response headers (`X-Synapse-Retrieval-Graph-*`), API CORS now exposes these headers for browser clients, advanced web diagnostics panel now renders runtime graph config chips before ranking results, e2e mock API parity was updated to match the new contract, and Playwright coverage now asserts diagnostics config visibility (`retrieval diagnostics shows runtime graph config`).
- 2026-04-02: Completed core wiki moderation UX simplification pass for non-technical operators: added `Enable Expert Controls` toggle inside `Core Mode`, defaulted queue behavior to open-drafts lane in simplified mode, hidden advanced queue presets/bulk moderation/tree builder/page-history/patch/timeline controls unless expert controls are enabled, gated throughput loading for simplified mode, and updated task lifecycle web e2e to assert the new default-first core moderation experience.
- 2026-04-02: Completed MCP/API retrieval parity hardening pass: extracted shared retrieval contract module (`services/shared/retrieval.py`) for graph config/env parsing, SQL plan builder, and explainability fields; switched MCP store and API explain endpoint to shared plan/helper flow; aligned service Docker images to include shared module (`PYTHONPATH=/app/services:*`), added deterministic parity smoke gate (`scripts/check_mcp_api_retrieval_parity.py`) in CI, and validated retrieval regression dataset remains green.
- 2026-04-02: Completed OSS contributor DX guardrails pass: added one-command newcomer validation wrapper (`scripts/run_contributor_guardrails.sh`) with `quick|full|release` profiles, connected doc shortcuts (`README.md`, `CONTRIBUTING.md`, `docs/contributor-quickstart.md`, release checklists), and wired guardrails script syntax/help checks into CI.
- 2026-04-02: Completed core wiki moderation analytics pass: added API endpoint `GET /v1/wiki/moderation/throughput` (24h moderation throughput, approval/rejection mix, decision latency percentiles, backlog/open-conflict counters, reviewer activity and health alerts), integrated compact core-mode dashboard card in Draft Inbox (`Moderation throughput (24h)`), updated web mock/e2e coverage, and synced API/UI docs.
- 2026-04-02: Completed MCP explainability pass: added per-result retrieval reason traces and score decomposition (`score_breakdown`) in MCP `search_knowledge`, shipped API operator diagnostics endpoint `GET /v1/mcp/retrieval/explain` (MCP-compatible ranking/explain payload), integrated advanced-mode web diagnostics panel ("MCP Retrieval Diagnostics") with live query + graph-hint explain flow, updated mock API parity and MCP/API/UI docs.
- 2026-04-02: Completed OSS onboarding polish pass: added first-run guide (`docs/getting-started.md`) with explicit adoption paths (core loop proof, local UI, SDK-only cookbook, OpenClaw onboarding), added release walkthrough checklist (`docs/oss-publish-checklist.md`), tightened README "Start Here" entrypoint and docs links, curated cookbook onboarding guidance (`demos/cookbook/README.md`), and synced tutorial/release/oss-readiness references.
- 2026-04-02: Completed core wiki UI polish pass in core mode: added inbox triage lane with top-priority open drafts, implemented one-click quick moderation actions directly from triage/inbox cards, added SLA-aware wait badges and status-accented draft cards for faster scanning, introduced quick approve/reject controls in Draft Detail header, and upgraded wiki canvas readability with article-style typography + read-time/word-count metadata.
- 2026-04-02: Completed self-hosted DR CI opt-in pass: added full acceptance runner (`scripts/run_selfhost_dr_ci_acceptance.sh`) that boots a clean compose stack, seeds API data, executes backup/restore drill, and emits JSON report; wired GitHub Actions `workflow_dispatch` input `run_selfhost_dr_drill=true` with report artifact upload; added local opt-in CI toggle (`SYNAPSE_RUN_SELFHOST_DR_ACCEPTANCE=1`) and updated deployment/DR docs.
- 2026-04-02: Completed OpenClaw provenance verification pass: shipped audit verification endpoint (`POST /v1/openclaw/provenance/verify`), added offline verifier CLI (`scripts/verify_openclaw_provenance.py`) and deterministic smoke harness (`scripts/smoke_openclaw_provenance_verification.py`) validating signed, digest-only, and tamper-detection paths in CI.
- 2026-04-02: Completed OSS release candidate dress rehearsal pass: hardened clean-room script (`scripts/run_oss_rc_dress_rehearsal.sh`) to pack explicit npm package paths (workspace-safe), fixed final report generation path, validated full end-to-end rehearsal locally, and synced release runbook references.
- 2026-04-02: Completed self-hosted backup/restore drill automation pass: added safe restore validation script (`scripts/run_selfhost_backup_restore_drill.sh`) that performs `pg_dump -> restore into temporary pgvector Postgres -> source/restored core-table parity check` with JSON status output, documented usage/options in deployment docs and dedicated runbook (`docs/backup-restore-drill.md`), and wired script smoke into CI checks.
- 2026-04-02: Completed OpenClaw event provenance enrichment pass: extended Python `OpenClawConnector` and `@synapse/openclaw-plugin` to generate signed provenance metadata for `propose_to_wiki` claims (HMAC-SHA256 when secret configured, digest-only fallback), injected provenance into both `evidence[].provenance` and `claim.metadata.synapse_provenance`, expanded `EvidenceRef` contracts/schema to include provenance payload, hardened runtime contract checks with signature assertions (`scripts/integration_openclaw_runtime_contract.py`), and updated OpenClaw integration docs/READMEs.
- 2026-04-02: Completed performance tuning runbook pass: added production tuning advisor (`scripts/run_performance_tuning_advisor.py`) that computes live queue/load metrics from Postgres, selects queue profile presets (`conserve|balanced|burst`), recommends worker sizing and queue control thresholds, and integrates MCP trend signals for graph knob recommendations; added markdown/json report output + apply commands, wired script checks into CI, and documented full tuning workflow (`docs/performance-tuning.md`) with links from README/self-hosted/OSS readiness docs.
- 2026-04-02: Completed core runtime acceptance on clean self-hosted compose profile: extended acceptance harness with external-worker polling and container-based MCP probe modes (`scripts/integration_core_loop.py`), added clean compose orchestration script (`scripts/run_selfhost_core_acceptance.sh`) validating `docker compose up -> core loop -> teardown`, wired optional execution into CI checks (`SYNAPSE_RUN_SELFHOST_CORE_ACCEPTANCE=1`) and GitHub Actions workflow dispatch opt-in job (`.github/workflows/ci.yml`, `run_selfhost_acceptance=true`), and documented the flow in self-hosted runbook.
- 2026-04-02: Completed OpenClaw runtime integration fixture pass: added runtime contract matrix check (`scripts/integration_openclaw_runtime_contract.py`) validating connector compatibility across multiple runtime API profiles (`on`/`register_hook`, positional/keyword `register_tool`), wired it into CI smoke path (`scripts/ci_checks.sh`), and updated integration docs/README references.
- 2026-04-02: Completed OSS troubleshooting/hardening docs pass: added production troubleshooting runbook (`docs/troubleshooting.md`), production hardening checklist (`docs/production-hardening.md`), observability incident response playbooks (`docs/observability-incident-playbooks.md`), and linked them from root README + OSS readiness checklist.
- 2026-04-02: Completed Core OSS publish polish pass: added automated publish-hygiene validator (`scripts/check_publish_hygiene.py`) to enforce npm/python package metadata and release-doc consistency, wired check into CI + release workflow (`scripts/ci_checks.sh`, `.github/workflows/release-packages.yml`), aligned schema package metadata baseline (`packages/synapse-schema/package.json` with `engines` + keywords), and updated OSS docs/runbook references (`docs/release-workflow.md`, `docs/oss-readiness.md`).
- 2026-04-02: Completed SDK observability alert pack baseline: added Prometheus alert/recording rules (`infra/observability/prometheus-rules-sdk-alerts.yaml`) for transport failure ratio, queue growth, and proposal drop detection; mounted rules into local observability compose stack; added Datadog monitor quick pack (`infra/observability/datadog/synapse-sdk-alert-monitors.json`); and updated observability runbooks/docs with import instructions and alert semantics.
- 2026-04-02: Completed OpenClaw plugin packaging pass: shipped new npm package `@synapse/openclaw-plugin` (`packages/synapse-openclaw-plugin`) with production-ready hook/tool bridge (`attach`, `registerTools`, `search_wiki`, `propose_to_wiki`, task tools), added runtime fixture tests (`tests/runtime-fixture.test.mjs`), and wired package into CI/release version checks + release workflow artifact packing (`scripts/ci_checks.sh`, `scripts/check_release_versions.py`, `.github/workflows/release-packages.yml`).
- 2026-04-02: Completed core-first wiki IA v6 in web console: added review queue presets (`Open queue`, `SLA breaches`, `Conflicts`, `High confidence`, `Full timeline`), moderation SLA threshold controls, queue health KPI widgets (`open`, `breaches`, `conflicts`, `high-confidence`, `oldest/median wait`), and aligned e2e coverage for preset switching and new controls.
- 2026-04-02: Completed SDK trace observability starter dashboards: added local observability stack (`infra/observability/docker-compose.sdk-observability.yml`) with OTel Collector + Prometheus + Tempo + Grafana provisioning, shipped prebuilt Grafana dashboard (`infra/observability/grafana/dashboards/synapse-sdk-trace-overview.json`), added Datadog dashboard quick pack (`infra/observability/datadog/synapse-sdk-trace-quickpack.json`), and added runnable SDK telemetry smoke generator (`scripts/run_sdk_otel_smoke.py`) with docs (`docs/sdk-trace-observability.md`).
- 2026-04-02: Completed OpenClaw-first onboarding kit: added production-like runtime template (`demos/openclaw_onboarding/runtime_template.py`), local seed dataset (`demos/openclaw_onboarding/dataset/openclaw_seed_memory.jsonl`), runnable 5-minute onboarding scenario (`demos/openclaw_onboarding/run_onboarding_demo.py`), and connected docs path (`docs/tutorials/04-openclaw-onboarding-kit.md`, OpenClaw integration references, root README links).
- 2026-04-02: Completed core-first wiki IA v5 in production paths: added guided wiki page creation flow in web console (autofill from draft, slug normalization, duplicate search, live page create), added page history API (`GET /v1/wiki/pages/{slug}/history`) and manual page create API (`POST /v1/wiki/pages`), integrated version-to-version markdown compare tab in Draft Detail, and aligned web mock/e2e coverage for new core controls.
- 2026-04-02: Completed self-hosted deployment baseline for OSS: added production-like Docker build assets (`services/api|worker|mcp/Dockerfile`), shipped all-in-one compose stack (`infra/docker-compose.selfhost.yml`) with migration gate + healthchecks + worker loop defaults, added `.env.selfhost.example`, and documented full deployment/ops/backup runbook in `docs/self-hosted-deployment.md`.
- 2026-04-02: Completed OSS distribution pass: added release-grade package metadata for `synapse-sdk` / `@synapse/sdk` / `@synapse/schema`, introduced cross-package version alignment guard (`scripts/check_release_versions.py`) with CI gate wiring, shipped signed/provenance release workflow (`.github/workflows/release-packages.yml`) for PyPI + npm, and published OSS docs for compatibility matrix and release runbook.
- 2026-04-02: Completed core-first wiki IA v4 in web console: added saved workspace views (persist/apply/delete), pinned pages quick-jump, and bulk moderation controls (`select all visible`, batch approve/reject, force-approve conflicts) with keyboard shortcuts (`Ctrl|Cmd+Shift+Enter`, `Ctrl|Cmd+Shift+Backspace`) plus e2e coverage updates.
- 2026-04-02: Completed core-first wiki IA v3 in web console: added Section TOC navigation in Draft Detail with section preview and quick form mapping, page-template presets for moderation edits, and fast cross-page moderation jumps (UI controls + keyboard shortcuts `Shift+J/K/C`) to speed reviewer flow across pages/conflicts.
- 2026-04-02: Completed core-first wiki IA v2 in web console: introduced `Space -> Page` navigation model (derived from wiki slug taxonomy), collapsible space groups, open-only page filter, recent-pages strip, and draft inbox text filtering while preserving core moderation flow and keyboard navigation.
- 2026-04-02: Hardened core runtime path discovered during acceptance rollout: fixed FastAPI startup schema generation issue on throughput CSV export route (`response_model=None`) and fixed MCP `get_entity_facts` SQL parameter typing (`%s::text`) to avoid `IndeterminateDatatype` failures.
- 2026-04-02: Completed core runtime acceptance suite with a dedicated reproducible scenario script (`scripts/integration_core_loop.py`) validating the primary loop end-to-end (`ingest -> synthesis draft -> moderation approve -> MCP retrieval`) against real API/worker/MCP runtime components; wired opt-in execution into CI via `SYNAPSE_RUN_CORE_ACCEPTANCE=1`.
- 2026-04-02: Completed OSS publishing hygiene baseline in-repo: added `LICENSE` (Apache-2.0), documented versioning/release policy in `CONTRIBUTING.md`, updated changelog/docs references, and marked publishing-hygiene checklist items done in `docs/oss-readiness.md`.
- 2026-04-02: Added first Confluence-like core wiki IA pass in web console: left `Wiki Tree` page navigation, page-scoped draft filtering, selected-page breadcrumbs in Draft Detail, and page-section preview loading for selected nodes; updated core e2e assertions accordingly.
- 2026-04-02: Switched web UX to core-first default (`Core Mode`) and gated heavy control-plane surfaces behind explicit `Advanced Mode`; added focused-mode messaging in UI and updated browser e2e to validate both modes.
- 2026-04-02: Added OSS readiness artifacts and onboarding docs: `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`, GitHub issue/PR templates, tutorials (`docs/tutorials/*`), and readiness checklist (`docs/oss-readiness.md`) to make open-source publication path explicit.
- 2026-04-02: Closed M8 Agentic Task Core to `done`: completed production-like `/v1/tasks*` mock API parity in web e2e server (filters, detail, upsert, status/comment/link mutation with timeline events) and added Playwright lifecycle scenario for Task Tracker panel (`create -> progress/block/done -> comment -> link`) with full suite passing.
- 2026-04-02: Started and completed first Agentic Task Core vertical slice: added migration `036_task_core.sql` (`synapse_tasks`, `synapse_task_events`, `synapse_task_links`), shipped Task API endpoints (`/v1/tasks*`) with idempotent writes and audit timeline events, added Python/TypeScript SDK task lifecycle helpers, extended OpenClaw connector with task tools (`synapse_get_open_tasks`, `synapse_update_task_status`), added MCP task retrieval tools (`get_open_tasks`, `get_task_details`), and integrated Task Tracker panel in local web UI.
- 2026-04-01: Completed server-side fleet schedule controls for Queue Command Center: upgraded `GET /v1/gatekeeper/calibration/operations/incidents/sync/schedules` with `status`/`project_contains`/`name_contains` filters, `sort_by`/`sort_dir`, `offset`/`cursor`, and `paging` metadata (`next_cursor`, `has_more`, `total`), aligned web fleet UI to server-driven filtering/sorting/pagination with persisted view state and refresh controls, and updated mock/e2e/docs for the new contract.
- 2026-04-01: Completed incident-sync schedule run timeline delivery: added API endpoint `GET /v1/gatekeeper/calibration/operations/incidents/sync/schedules/{schedule_id}/timeline` (status trend, recent run feed, failure-class aggregation sourced from queue control audit events), enriched schedule run events with structured `failure_classes`, and shipped Queue Command Center timeline UI (trend chart, failure-class breakdown, audit-linked run cards) with updated mock/e2e coverage.
- 2026-04-01: Completed scalable fleet schedule UX in Queue Command Center: added incident-sync fleet table with project/name/status/enabled filters, due-only toggle, compact row mode, client-side pagination controls, and range/page counters to keep the schedule panel usable across 200+ schedules.
- 2026-04-01: Completed incident-sync run drill-down in Queue Command Center: run endpoint payloads now include `audit_event_id` + `sync_trace`, UI now provides per-run trace inspection (`Sync trace payload`), direct jump to linked queue audit event, and one-click schedule retry shortcuts from run-result cards; mock API and e2e coverage updated accordingly.
- 2026-04-01: Completed persisted incident-sync schedule backend: added migration `035_gatekeeper_calibration_queue_incident_sync_schedules.sql` (schedule model with cadence + run options + preflight overrides + last-run state), new API endpoints (`GET/PUT/DELETE /v1/gatekeeper/calibration/operations/incidents/sync/schedules`, `POST .../sync/schedules/run`) with due-window execution and `next_run_at` advancement, schedule run audit actions (`incident_sync_schedule_updated`, `incident_sync_schedule_run`, `incident_sync_schedule_failed`, `incident_sync_schedule_deleted`), and worker scheduler support via `run_queue_incident_sync_scheduler.py --use-api-schedules`.
- 2026-04-01: Completed Queue Command Center incident-sync schedule UX: added full web management for persisted incident-sync schedules (`create/update/delete`, preset/custom cadence, preflight options, next-run override, due/force run controls), integrated run-result summaries + per-schedule status badges, and shipped scheduler observability widgets (due backlog counters, last-run outcome distribution, hourly failure heatmap) with mock API + Playwright coverage for `/v1/gatekeeper/calibration/operations/incidents/sync/schedules*`.
- 2026-04-01: Completed scheduled incident-sync worker entrypoint for unattended runs: added `services/worker/scripts/run_queue_incident_sync_scheduler.py` with project discovery (`--all-projects`), batch sync execution, multi-cycle scheduler mode, optional fail-on-failures guard, and native reuse of live preflight enforcement gate via `POST /v1/gatekeeper/calibration/operations/incidents/sync` (`preflight_enforcement_mode=inherit|off|block|pause`); wired CI help-smoke and worker README runbook examples.
- 2026-04-01: Completed command-center enforcement visibility in compare views: Queue Command Center cards now show live incident preflight posture (`mode`, `critical threshold`, `pause window`) with cross-project enforcement distribution badges, Cross-Project Observability compare cards now surface linked queue preflight mode when available, and throughput compare CSV/webhook exports now include enforcement posture columns (`incident_preflight_enforcement_mode`, `incident_preflight_pause_hours`, `incident_preflight_critical_fail_threshold`) with updated mock/e2e coverage.
- 2026-04-01: Completed sync-window preflight enforcement for live incident sync: added migration `034_gatekeeper_calibration_queue_incident_sync_enforcement.sql` (queue control fields for mode/pause-hours/critical-threshold), wired API enforcement endpoint (`PUT /v1/gatekeeper/calibration/operations/incidents/sync/enforcement`), upgraded sync engine (`POST /v1/gatekeeper/calibration/operations/incidents/sync`) with `inherit|off|block|pause` gating and per-project preflight gate evaluation, automatic queue pause mode, enforcement audit actions (`incident_sync_blocked_preflight`, `incident_sync_paused_preflight`), UI controls in Queue Command Center preflight panel, and mock/e2e coverage for block->off sync flow.
- 2026-04-01: Completed configurable escalation delivery playbooks for intelligence routing: normalized `config.incident_escalation_playbook` in API target upsert (owner-tier channel mapping, fallback recipients, severity fan-out, quiet-hours windows), upgraded worker delivery engine with route planning (`owner_tier`, `owner_tier_fallback`, `severity_fanout`), severity derivation and quiet-hours suppression logic, per-attempt routing metadata trace (`response_payload.routing`), and integration scenario assertions for playbook config + routed incident attempts.
- 2026-04-01: Completed queue incident preflight presets: added migration `033_gatekeeper_calibration_queue_incident_preflight_presets.sql`, new API endpoints (`GET/PUT /v1/gatekeeper/calibration/operations/incidents/preflight/presets`, `POST /v1/gatekeeper/calibration/operations/incidents/preflight/run`), batch preflight evaluator with severity-based alerts and project rollups, Queue Command Center UI for preset edit/run/results, and mock/e2e coverage for save + run flows.
- 2026-04-01: Completed cross-project incident SLO board: added API endpoint (`GET /v1/gatekeeper/calibration/operations/incidents/slo_board`) with MTTA-proxy/MTTR rollups, open-incident SLA breach detection, ownership rotation-lag posture, and secret-age hygiene scoring; integrated a new Queue Command Center SLO panel in web UI (trend charts + posture cards + risk leaderboard); and expanded mock/e2e coverage for refresh and rendering flow.
- 2026-04-01: Completed incident escalation digest delivery workflow: added migration `032_intelligence_incident_escalation_digest.sql` (new digest kind `incident_escalation_daily`), implemented worker generation path for over-SLA unresolved queue incidents (`run_intelligence_digest.py --kind incident_escalation_daily` with SLA/top-N controls), extended delivery engine with target-level digest routing filters (`config.digest_kinds`) and escalation gating (`incident_escalation_require_over_sla`), expanded scheduler/delivery scripts and integration scenario coverage, and added API digest/attempt filters for the new kind.
- 2026-04-01: Completed incident policy simulation mode: added API endpoint (`POST /v1/gatekeeper/calibration/operations/incidents/policies/simulate`) with dry-run routing trace (`matched_policy`, `effective_hook`, `route_trace`, `decision`) and secret-aware masking semantics, integrated simulation controls/result card in Queue Command Center UI, and expanded mock/e2e coverage.
- 2026-04-01: Completed provider secret management for incident adapters: added migration `031_gatekeeper_calibration_queue_incident_secrets_rbac.sql` (secret vault + secret event audit + per-hook/policy `secret_edit_roles`), masked secret reads (`********`) for PagerDuty/Jira adapter keys, rotation-safe preserve/rotate/clear logic with versioned secret events, optional RBAC enforcement via `X-Synapse-Roles` + `SYNAPSE_INCIDENT_SECRET_RBAC_MODE`, and UI/mock/e2e updates (including masked field assertion).
- 2026-04-01: Completed incident escalation digest feature: added API endpoint (`GET /v1/intelligence/queue/incident_escalation_digest`) with unresolved incident prioritization, SLA-age buckets, routing readiness rates, and ownership gap triage; integrated Incident Escalation Digest panel in Queue Command Center UI with refresh controls; and expanded mock/e2e coverage.
- 2026-04-01: Completed alert-to-incident policy templates: added migration `030_gatekeeper_calibration_queue_incident_policies.sql`, new policy APIs (`GET/PUT /v1/gatekeeper/calibration/operations/incidents/policies`), policy-aware sync routing (per-alert provider override, endpoint override, severity mapping, and open-on-health override), and integrated policy controls in web Queue Command Center with mock/e2e coverage.
- 2026-04-01: Completed queue incident provider adapters: added migration `029_gatekeeper_calibration_queue_incident_provider_adapters.sql` (`provider_config` + provider constraint expansion), upgraded incident hook API/worker dispatch to support `webhook`, `pagerduty`, and `jira` presets (including auth and provider-specific open/resolve payloads), integrated provider-aware controls in web Queue Command Center, and extended mock/e2e coverage for preset save flow.
- 2026-04-01: Completed governance drift dashboard: added API endpoint (`GET /v1/gatekeeper/calibration/operations/governance/drift`) with ownership coverage rates, unresolved pause age-bucket distribution, and per-project drift risk scoring; integrated Governance Drift panel in web Queue Command Center and extended mock/e2e coverage.
- 2026-04-01: Completed owner-level queue performance rollups: added owner analytics API (`GET /v1/gatekeeper/calibration/operations/throughput/owners`) with per-owner/on-call queue health, open incidents, governance pending/SLA breach counters, and MTTR/pending-age latency stats; integrated Owner Queue Performance Rollups panel in web Queue Command Center and extended mock/e2e coverage.
- 2026-04-01: Completed queue incident auto-ticket hooks: added migration `028_gatekeeper_calibration_queue_incident_hooks.sql` (hook config + incident lifecycle tables), incident hook APIs (`GET/PUT /v1/gatekeeper/calibration/operations/incidents/hooks`, `GET /v1/gatekeeper/calibration/operations/incidents`, `POST .../incidents/sync`) with auto open/resolve webhook flow and cooldown guardrails, incident enrichment in queue command-center/digest payloads + CSV export columns, and web UI incident hook controls/sync panel with mock/e2e coverage.
- 2026-04-01: Completed queue-governance policy assertion baseline: added `scripts/check_queue_governance_policy.py` (SLO/owner/alert-route guard checks) and wired it into `scripts/ci_checks.sh` as an automated CI policy gate step.
- 2026-04-01: Completed queue audit escalation actions: added annotation model + migration (`027_gatekeeper_calibration_queue_audit_annotations.sql`), audit action APIs (`POST .../throughput/audit/{event_id}/acknowledge|resolve`), latest annotation enrichment in audit feed, and UI acknowledge/resolve controls with e2e coverage.
- 2026-04-01: Completed per-project queue ownership routing: added ownership model + migration (`026_gatekeeper_calibration_queue_ownership.sql`), ownership APIs (`GET/PUT /v1/gatekeeper/calibration/operations/ownership`), ownership enrichment in command-center/digest payloads, and UI routing editor with e2e coverage.
- 2026-04-01: Completed daily queue governance digest feature: added API endpoint (`GET /v1/intelligence/queue/governance_digest`) that summarizes top congestion and unreviewed pause windows from throughput + audit streams, integrated digest card in Queue Command Center UI, and expanded mock/e2e coverage.
- 2026-04-01: Completed autoscaling "apply recommendation" workflow: added API endpoint (`POST /v1/gatekeeper/calibration/operations/throughput/recommendations/apply`) to apply recommended lag/depth controls with audit entry, wired `Apply controls` action in autoscaling UI cards, and expanded mock/e2e coverage including `apply_recommendation` audit events.
- 2026-04-01: Completed command-center export mode: added queue governance export APIs (`GET /v1/gatekeeper/calibration/operations/throughput/compare/export`, `POST /v1/gatekeeper/calibration/operations/throughput/compare/export/webhook`), wired CSV/webhook controls in web Queue Command Center, and extended mock/e2e coverage including `export_snapshot` audit events.
- 2026-04-01: Completed queue autoscaling recommendations feature: added rolling-history autoscaling API (`GET /v1/gatekeeper/calibration/operations/throughput/recommendations`) with per-project worker concurrency and lag/depth tuning guidance, integrated Queue autoscaling recommendations panel in web UI, and extended mock/e2e coverage.
- 2026-04-01: Completed queue governance audit trail feed in Intelligence panel: added persisted queue control event stream (`gatekeeper_calibration_queue_control_events`) and UI audit timeline showing actor/action/reason/pause window for control, pause/resume, and bulk operations.
- 2026-04-01: Completed queue command-center extension for throughput controls: added compare/bulk APIs (`GET /v1/gatekeeper/calibration/operations/throughput/compare`, `POST .../bulk_pause`, `POST .../bulk_resume`), integrated cross-project Queue Command Center UI with CSV project targeting + bulk pause/resume windows, and expanded Playwright mock/e2e coverage.
- 2026-04-01: Completed live SSE queue timeline mode in web UI: added `Live SSE stream` subscription toggle bound to `/v1/gatekeeper/calibration/operations/runs/{run_id}/stream`, real-time progress/status ingestion with terminal-state auto-sync, and automatic fallback to polling on stream timeout/error.
- 2026-04-01: Completed calibration queue throughput controls: added migration `024_gatekeeper_calibration_queue_controls.sql`, new throughput/control APIs (`/v1/gatekeeper/calibration/operations/throughput*`) with worker-lag and queue-depth health, queue pause/resume windows, worker-side pause-aware claim filtering, web UI control panel, and Playwright coverage for pause/resume flow.
- 2026-04-01: Completed rollback attribution request-level drill-down: added API endpoint (`GET /v1/gatekeeper/config/rollback/attribution/drilldown`) with cohort/actor causal trace expansion to impacted rollback requests, linked cohort cards to traces in web rollback panel, and extended mock/e2e coverage.
- 2026-04-01: Completed compare-mode drill-down from Cross-Project Observability leaderboard to schedule-level timelines: added API endpoint (`GET /v1/gatekeeper/calibration/observability/compare/drilldown`) with rank/neighbor context + schedule observability payload, wired click-through navigation and drill-down panel in `apps/web` schedule dashboard, and extended Playwright mock/e2e coverage for the new navigation path.
- 2026-03-31: Created living roadmap with milestone structure and update protocol.
- 2026-03-31: Started M1 implementation: scaffolded monorepo, added `synapse-schema` v1 JSON schemas, created TS/Python SDK skeletons, added API/service placeholders, and local Postgres migration/bootstrap.
- 2026-03-31: Advanced M1 implementation: connected API to Postgres (`ON CONFLICT DO NOTHING` for event idempotency), added `claim_proposals` persistence, created TS/Python quickstarts, and added `scripts/m1_smoke_e2e.sh`.
- 2026-03-31: Ran full local smoke validation. Fixed host Postgres port collision by moving container to `localhost:55432`; verified event insert/dedup and claim proposal persistence in DB.
- 2026-03-31: Implemented production-like SDK transport reliability in TS/Python: retry with exponential backoff + jitter, timeout handling, retryable HTTP status policy, idempotency-key propagation, and loss-safe flush with queue restore on failure.
- 2026-03-31: Implemented API-level persisted idempotency store (`idempotency_requests`) with payload hash verification, replay responses, conflict detection, in-progress handling, automatic periodic TTL cleanup, and manual cleanup script.
- 2026-03-31: Implemented SDK monitor adapters and OpenClaw layering primitives: Python `monitor_langgraph` / `monitor_crewai` / generic monitor + `OpenClawConnector` (hook capture + memory tools), and TS generic `monitor(...)` wrapper.
- 2026-03-31: Built and executed first vertical scenario demo (`demos/omega_gate`): OpenClaw-style events + memory tool calls flowing through Synapse SDK/API with DB verification for persisted events and queued claim proposal.
- 2026-03-31: Implemented baseline wiki engine architecture in code: new DB schema (`003_wiki_engine.sql`), deterministic worker synthesis pipeline (`services/worker/app/wiki_engine.py`), migration runner script, and wiki query endpoints in API (`/v1/wiki/pages/search`, `/v1/wiki/pages/{slug}`, `/v1/wiki/drafts`).
- 2026-03-31: Hardened synthesis runtime after first e2e: fixed `wiki_claim_links` decision constraint (`004_wiki_claim_links_constraint.sql`), added per-claim transactional isolation in worker (`savepoint` style via nested transactions), and validated end-to-end proposal->draft flow on `omega_demo`.
- 2026-03-31: Added onboarding backfill flow for existing agent memory: new API batch ingestion (`/v1/backfill/memory` + batch status endpoint), DB support (`memory_backfill_batches`, `event_pipeline_state`), worker extraction pipeline (`memory_backfill` events -> `claim_proposals`), and Python/TS SDK bootstrap methods with chunking and idempotency keys.
- 2026-03-31: Validated live bootstrap e2e on `bootstrap_demo`: SDK backfill chunk upload -> batch `ready` -> worker extraction/synthesis -> batch `completed` with generated wiki drafts; fixed Postgres locking limitation in extraction query by replacing `LEFT JOIN ... FOR UPDATE` with `NOT EXISTS`.
- 2026-03-31: Hardened backfill idempotency semantics by switching deterministic `memory_backfill` event IDs to `batch_id + source_id` (independent from chunk boundaries), preventing duplicates when chunk size changes across retries.
- 2026-03-31: Incorporated strategic product tracks into roadmap: Gatekeeper triage model, Intelligence Pulse digests + analytics, Legacy Import cold-start path, Graph-aware semantic retrieval, and Agent Simulator sandbox.
- 2026-03-31: Implemented first Gatekeeper baseline in worker + DB (`gatekeeper_decisions`): operational noise is filtered from wiki drafts, while higher-signal policy facts are marked as golden candidates and continue to moderation queue.
- 2026-03-31: Extended Gatekeeper with auto-promotion heuristics in code (`source_diversity` + open-conflict horizon + score floor) and backward-compatible claim fingerprint fallback for environments where migration `007` is not yet applied.
- 2026-03-31: Stabilized local development environment after Docker VM storage saturation (cleaned unused Docker artifacts, restored Postgres health, and re-applied migrations up to `007`).
- 2026-03-31: Implemented first human moderation runtime in API: draft approve/reject endpoints now persist page version updates, statement activation, snapshot creation, and claim/link state transitions; validated on live drafts (`bootstrap_demo`, `gatekeeper_demo`).
- 2026-03-31: Upgraded Intelligence UI rollback flow to production-safe approval workflow: added rollback preview/risk board, rollback request queue with 4-eyes approvals, reject path with reasons, and per-request audit timeline cards.
- 2026-03-31: Added Gatekeeper alert routing management in web UI: operators can create/update/delete targets, toggle enable/disable state, and configure per-target severity/code filters without leaving Intelligence panel.
- 2026-03-31: Added calibration schedule management in web UI: CRUD for schedules, preset profile preview (nightly/weekly), parameter-grid validation hints, and last-run status surfacing.
- 2026-03-31: Added browser-level Playwright e2e coverage for Intelligence dashboard critical flows (run-history rendering, calibration schedule CRUD, alert routing management, rollback request/reject workflow) with stateful mock API and CI integration.
- 2026-03-31: Completed rollback governance metrics slice end-to-end: new API analytics endpoint (`GET /v1/gatekeeper/config/rollback/metrics`) with approval/resolution lead-time stats, rejection cause aggregation, risk-level/risk-driver breakdown, and transition impact rollups; integrated a dedicated governance panel in web rollback workflow and extended Playwright mock/e2e coverage.
- 2026-03-31: Completed calibration operations controls slice: added API operation endpoints (`GET /v1/gatekeeper/calibration/operations/preview`, `POST /v1/gatekeeper/calibration/operations/run`) that execute the real scheduler script with due-state preview and manual-trigger support; added Intelligence UI controls for preview/dry-run/run-now with command preview and per-schedule execution status; extended Playwright mock/e2e coverage and kept full CI green.
- 2026-03-31: Completed schedule observability drill-down: added API endpoint (`GET /v1/gatekeeper/calibration/schedules/observability`) with per-schedule SLO health scoring, 14-day trend buckets, and top failure-class aggregation; integrated dedicated web panel with health badges, success/alert/failure rates, and trend snapshots.
- 2026-03-31: Completed rollback governance drill-down actions: extended rollback metrics API with SLA-aware pending breach detection (`sla_hours`, `pending_sla_breaches`) and upgraded web panel with 7/30/90/custom date presets, pending-SLA breach board, per-request SLA badges, and CSV export.
- 2026-03-31: Completed calibration operation safety rails: added migration `022_gatekeeper_calibration_operation_safety.sql`, project-scoped advisory run lock, operation token idempotency registry/replay, and required confirmation checkpoint (`RUN <project_id>`) for live manual runs.
- 2026-03-31: Completed multi-project observability compare mode: added API endpoint (`GET /v1/gatekeeper/calibration/observability/compare`) with project leaderboard (`health`, success/alert/failure rates, drift index, top failure classes) and integrated Cross-Project Observability board in web schedule panel with CSV project filter and live refresh.
- 2026-03-31: Completed rollback governance attribution layer: added API endpoint (`GET /v1/gatekeeper/config/rollback/attribution`) with cohort/actor grouping, approval lead-time stats, outcome rates, and resolved decision timeline; integrated Rollback Attribution panel in web governance view with cohort/actor toggle and refresh flow.
- 2026-03-31: Completed async calibration operation queue delivery: added migration `023_gatekeeper_calibration_operation_queue.sql`, API async queue endpoints (`/v1/gatekeeper/calibration/operations/queue`, `/runs*`, cancel/retry, events + SSE stream), worker queue engine (`services/worker/app/calibration_queue.py` + `run_gatekeeper_calibration_operation_queue.py`) with heartbeat/cancel-aware subprocess control, and upgraded Intelligence web panel with live queue timeline/cancel/retry controls and updated e2e coverage.
- 2026-03-31: Added M5 skeleton in production path: migration `008_knowledge_intelligence.sql`, worker digest job (`run_intelligence_digest.py`), and API endpoints for daily metrics + digest feed (`/v1/intelligence/*`).
- 2026-03-31: Expanded integration scenario (`scripts/integration_moderation_backfill.py`) to validate backfill lifecycle, moderation idempotency, and intelligence digest generation/read APIs end-to-end.
- 2026-03-31: Implemented M3 moderation upgrade: structured `edit+approve` payload (section-level append/replace), persisted moderation audit trail (`moderation_actions`), and moderation feed endpoint for UI timelines.
- 2026-03-31: Implemented Gatekeeper config surface end-to-end (`gatekeeper_project_configs` + `GET/PUT /v1/gatekeeper/config`) and wired worker decision logic to project-level thresholds without code redeploy.
- 2026-03-31: Implemented intelligence delivery fan-out: delivery targets API, delivery attempts log, worker delivery runner (`run_intelligence_delivery.py`), and combined scheduler (`run_intelligence_scheduler.py`) with Slack webhook + SMTP adapters.
- 2026-03-31: Extended integration e2e to validate digest delivery via local webhook receiver and delivery attempts API.
- 2026-03-31: Implemented weekly intelligence mode: worker weekly rollup/trend generation (`run_intelligence_digest.py --kind weekly`), weekly trend API (`/v1/intelligence/trends/weekly`), and e2e validation of weekly payload (`current_rollup`, `trend_breakdown`).
- 2026-03-31: Implemented temporal reasoning in synthesis pipeline: deterministic time-window extraction (`from/until/between`), overlap-aware dedup/conflict detection, auto-supersede of expired statements, API validity-aware statement retrieval/insertion, migration `011_temporal_reasoning_indexes.sql`, and integration e2e scenario for non-overlapping contradiction avoidance.
- 2026-03-31: Added explicit SDK Excellence track (M7) to roadmap: simplified facade, trace propagation, decorator-based insight capture, plugin architecture, introspection mode, OpenTelemetry bridge, cookbook, and `synapse-cli`.
- 2026-03-31: Implemented first M7 slice: new high-level SDK facade (`Synapse` + `attach(...)`) in Python/TypeScript with backward-compatible `init()/SynapseClient`, plus trace propagation (`trace_id`, `span_id`, `parent_span_id`) through monitored call chains and persisted event payload metadata (`_synapse.*`) in API ingestion path.
- 2026-03-31: Implemented second M7 slice: decorator-style insight capture (`collect_insight` in Python and `collectInsight` wrapper in TypeScript), extractor plugin registry (`register/unregister/list`), built-in extractors (`structured_result`, `keyword`), and CI smoke assertions for extractor-driven claim proposals and trace presence.
- 2026-03-31: Implemented third M7 slice: SDK introspection/debug mode in Python/TypeScript (`set_debug_mode` / `setDebugMode`, in-memory structured debug records, optional sink callback) with machine-readable reason logs for extraction/proposal decisions (`low_confidence`, `duplicate`, `proposed`) and CI smoke assertions on debug event stream.
- 2026-03-31: Added deterministic synthesis evaluator dataset (`eval/synthesis_cases.json`) and regression runner (`scripts/eval_synthesis_regression.py`) covering routing, dedup, conflict, section routing, and temporal parsing; integrated evaluator into CI (`scripts/ci_checks.sh`).
- 2026-03-31: Added deterministic Gatekeeper evaluator dataset (`eval/gatekeeper_cases.json`) and runner (`scripts/eval_gatekeeper_regression.py`) with tier confusion matrix plus precision/recall thresholds; integrated into CI and worker docs.
- 2026-03-31: Implemented LLM-assisted Gatekeeper path with safe fallback (OpenAI provider, per-project runtime config, confidence/weight blending), added migration `012_gatekeeper_llm_assist.sql`, and expanded deterministic evaluator with LLM override cases.
- 2026-03-31: Implemented richer backfill entity/category inference (multilingual pattern+keyword extraction with deterministic fallback), and extended synthesis evaluator coverage with `backfill_inference` cases.
- 2026-03-31: Implemented cross-SDK synthesizer plugin contract (`v1`) with registration lifecycle and runtime synthesis stage (Python/TypeScript), plus CI smoke and SDK docs updates.
- 2026-03-31: Implemented cross-SDK graceful degradation runtime modes (`buffer`, `drop`, `sync_flush`) with pending claim/backfill drains in flush lifecycle, non-throwing failure handling, and SDK docs updates.
- 2026-03-31: Implemented cross-SDK OpenTelemetry bridge mapping (trace/metric hooks) with optional dependencies, runtime telemetry sink wiring, and CI smoke coverage for span/metric emission semantics.
- 2026-03-31: Added cookbook section and runnable Python scenarios (`Synapse + OpenClaw`, `Synapse + SQL`, `Synapse + Support Ops`), wired into root/SDK docs, and extended CI compile checks for full `demos/` tree.
- 2026-03-31: Started M4 runtime delivery: implemented `services/mcp` production retrieval service with four MCP tools, project-level cache invalidation keyed by `knowledge_snapshots`, local run docs, and CI smoke coverage for cache invalidation behavior.
- 2026-03-31: Added Python SDK MCP context-injection helper (`MCPContextHelper`) with normalized tool payload handling, context markdown builder, OpenClaw search callback factory, and CI smoke coverage.
- 2026-03-31: Added TypeScript MCP context-injection helper parity (`MCPContextHelper`) and exported it through SDK index with usage docs.
- 2026-03-31: Added real OpenClaw x MCP e2e integration flow (`scripts/integration_openclaw_mcp_runtime.py`) using stdio `ClientSession` against a live FastMCP server process; integrated this check into CI.
- 2026-03-31: Added graph-aware MCP retrieval hint (`related_entity_key`) with metadata-based relevance boost and new regression evaluator dataset/script integrated into CI.
- 2026-03-31: Implemented `synapse-cli` (Python SDK) with `extract` and `replay` commands for local extraction simulation and trace timeline replay, added docs, package entrypoint, and CI smoke coverage.
- 2026-03-31: Started M6 Legacy Import: added `services/worker/app/legacy_import.py` parser engine, `run_legacy_import.py` upload/dry-run runner, docs, and offline parser smoke coverage in CI.
- 2026-03-31: Extended M6 Legacy Import with Notion connector mode: added Notion API client (pagination + retry/backoff), root-page and database ingestion paths, recursive page-tree content extraction into typed backfill records, CLI source-mode switching, and docs updates.
- 2026-03-31: Implemented M6 Agent Simulator sandbox: added policy replay engine over historical sessions (`services/worker/app/simulator.py`), runnable worker job (`run_agent_simulator.py`), persistent run/finding storage (`013_agent_simulator.sql`), API read endpoints (`/v1/simulator/runs*`), docs, and CI offline smoke coverage.
- 2026-03-31: Extended simulator with async API queue flow: added `POST /v1/simulator/runs` enqueue endpoint, queue processor worker (`run_agent_simulator_queue.py`), DB status upgrade migration (`014_agent_simulator_queue_status.sql`), and docs updates for API->worker orchestration.
- 2026-03-31: Added Gatekeeper LLM threshold calibration workflow (`scripts/calibrate_gatekeeper_llm_thresholds.py`) with deterministic train/holdout split, grid search over `llm_score_weight`/`llm_min_confidence`/`min_score_for_golden`, guardrail checks, and recommended payload for `/v1/gatekeeper/config`; integrated smoke coverage into CI.
- 2026-03-31: Implemented scheduled legacy sync orchestration for periodic cold-start refresh: new source/run/fingerprint tables (`015_legacy_sync_orchestration.sql`), worker engine (`legacy_sync.py`) + scheduler script (`run_legacy_sync_scheduler.py`), API source/run management endpoints (`/v1/legacy-import/*`), and docs updates.
- 2026-03-31: Completed M4 graph retrieval upgrade: `search_knowledge` now performs explicit multi-hop (up to 3 hops) traversal over entity relations from `wiki_pages.metadata.related_entities` with hop-based relevance boosts; extended deterministic MCP retrieval regression dataset with a 2-hop scenario and kept CI gate green.
- 2026-03-31: Added recurring Agent Simulator workflow for policy risk checks: template library (`gate_access_card_only`, `warehouse_quarantine`, `prepaid_only_dispatch`), preset-based scheduler engine (`hourly`/`every_6_hours`/`daily`/`weekly`), worker scheduler script (`run_agent_simulator_scheduler.py`), and offline CI smoke for template/schedule resolution.
- 2026-03-31: Added MCP retrieval performance track completion artifacts: benchmark runner with seeded production-like dataset (`scripts/benchmark_mcp_retrieval.py`), runtime-tunable graph boost/hops (`SYNAPSE_MCP_GRAPH_*`), retrieval path indexes (`016_mcp_retrieval_indexes.sql`), and validated benchmark snapshot (`mcp_bench`: avg p95 ≈ 46.7ms, graph top1 quality=1.0 for one-hop/two-hop checks).
- 2026-03-31: Completed roadmap hardening queue for retrieval/gatekeeper operations: added DB-backed Gatekeeper holdout builder (`scripts/build_gatekeeper_holdout_from_db.py`), safe config apply utility (`scripts/apply_gatekeeper_calibration.py`), weekly Gatekeeper drift monitor (`scripts/monitor_gatekeeper_drift.py`), and weekly MCP benchmark trend monitor (`scripts/check_mcp_retrieval_trend.py`) with CI smoke coverage.
- 2026-03-31: Delivered first M3 UI/runtime slice: added `GET /v1/wiki/drafts/{draft_id}` for full draft inspection, launched `apps/web` Draft Inbox console with approve/edit/reject actions wired to live API, enabled configurable API CORS (`SYNAPSE_UI_ORIGINS`), and extended integration e2e to validate draft-detail payload.
- 2026-03-31: Upgraded `apps/web` to production-like open-source UI stack (React + Mantine + Tabler Icons) with responsive two-pane moderation workspace, live API integration for draft moderation, and CI web build verification.
- 2026-03-31: Added advanced moderation UX layer in `apps/web`: statement-level semantic diff visualization (`before/after`), conflict resolver tab with one-click force-approve/reject-dismiss actions, and keyboard-first workflow (`J/K`, `Ctrl|Cmd+Enter`, `Ctrl|Cmd+Backspace`, `Ctrl|Cmd+R`).
- 2026-03-31: Connected UI conflict resolver to MCP-compatible explain flow via new API endpoint (`GET /v1/wiki/drafts/{draft_id}/conflicts/explain`) with root-cause and recommendation enrichment; wired frontend conflict tab to consume enriched payload and updated integration e2e checks.
- 2026-03-31: Completed M5 analytics widgets in `apps/web` using open-source Mantine Charts: live Knowledge Velocity/pending approvals/open conflicts KPI cards, daily and weekly trend charts, and latest daily digest panel wired to `/v1/intelligence/metrics/daily`, `/v1/intelligence/trends/weekly`, and `/v1/intelligence/digests/latest`.
- 2026-03-31: Completed M5 conflict drill-down delivery: added `/v1/intelligence/conflicts/drilldown` (weekly conflict-type aggregates + MTTR + top classes) and integrated it into `apps/web` Intelligence Pulse as weekly class cards and MTTR summary.
- 2026-03-31: Completed first production-like Gatekeeper calibration cycle run (`build_holdout -> calibrate -> apply -> snapshot`) via new orchestrator `scripts/run_gatekeeper_calibration_cycle.py`; artifacts stored under `artifacts/gatekeeper_calibration/<cycle_id>` (latest validation run: `20260331T172444Z`) and snapshot persisted for `integration_12723dbc`.
- 2026-03-31: Added Gatekeeper config snapshot persistence layer (migration `017_gatekeeper_config_snapshots.sql` + API `GET/POST /v1/gatekeeper/config/snapshots`) and extended integration e2e to validate snapshot create/list behavior.
- 2026-03-31: Added Intelligence delivery observability panel in `apps/web` (targets, channel-level delivery success, attempts KPI, and last failure context) wired to `/v1/intelligence/delivery/targets` and `/v1/intelligence/delivery/attempts`.
- 2026-03-31: Completed web bundle optimization: moved Intelligence dashboard into lazy-loaded chunk (`IntelligencePanel`) and configured Vite manual chunks (`intelligence_charts`, `mantine_vendor`, `react_vendor`), reducing initial moderation-console JS to ~29.6kB (gzip ~9.3kB) and removing oversized-chunk warning in build.
- 2026-03-31: Completed calibration snapshot history view in `apps/web` Intelligence panel: added live `/v1/gatekeeper/config/snapshots` integration with latest approved config highlights, guardrail status counters, snapshot timeline, and artifact reference rendering.
- 2026-03-31: Completed scheduled Gatekeeper calibration sweep wrapper (`scripts/run_gatekeeper_calibration_scheduler.py`) with nightly/weekly presets, due checks by latest calibration snapshots, regression detection, and Slack/SMTP alert delivery with persisted scheduler artifacts.
- 2026-03-31: Added calibration guardrail trend analytics API (`GET /v1/gatekeeper/calibration/trends`) and integrated it into `apps/web` Intelligence panel with accuracy/macro-F1/golden-precision trend charts plus approval gate KPIs.
- 2026-03-31: Implemented Gatekeeper config rollback flow (`POST /v1/gatekeeper/config/rollback`) with `source=rollback` snapshot trail and one-click rollback action in web calibration snapshot history.
- 2026-03-31: Completed persisted calibration scheduler config layer: migration `018_gatekeeper_calibration_schedules.sql`, API CRUD (`GET/PUT/DELETE /v1/gatekeeper/calibration/schedules`), scheduler API-source mode (`--use-api-schedules`), and integration scenario coverage for schedule upsert/list/delete.
- 2026-03-31: Completed DB-managed Gatekeeper alert routing: migration `019_gatekeeper_alert_delivery.sql`, alert targets/attempts API (`/v1/gatekeeper/alerts/*`), scheduler project-level routing via `--use-db-alert-targets`, and integration scenario coverage for target CRUD + attempt logging.
- 2026-03-31: Completed rollback safety policy: dry-run impact preview endpoint (`POST /v1/gatekeeper/config/rollback/preview`) with tier-shift estimation from recent `gatekeeper_decisions`, plus dual-approval workflow (`/v1/gatekeeper/config/rollback/requests*`) backed by migration `020_gatekeeper_rollback_requests.sql`; integration scenario now validates preview + two-step approval-to-apply flow.
