# Synapse Roadmap (Living)

Last updated: 2026-05-03
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
15. Process Playbook Intelligence (if/then runbooks, instruction capture, operator-outcome loops).
16. Agent Directory & Operations Intelligence (AI orgchart, agent folders, daily worklogs, provenance).
17. Public Launch & Positioning (package publication, onboarding KPI, Cognitive State Layer messaging).
18. Field adoption hardening (knowledge ingest lane, bootstrap profile, rejection diagnostics, project reset, self-host defaults).
19. Knowledge Compiler v2 (evidence bundles, durable knowledge synthesis, reflection/debrief, page-type compilers).

## Knowledge Compiler v2 (May 2026)

Status: `done`

Goal:
- перестать думать в модели `одно событие -> один draft`;
- сделать Synapse компилятором корпоративного знания, а не приемником agent memory/event stream;
- гарантировать, что в wiki попадают facts, processes, data docs, agent capabilities, decisions, а не raw operational flow.

Principles:
- `evidence first`: все сырые наблюдения живут сначала в evidence layer, а не в wiki.
- `bundle before publish`: знания синтезируются из bundle/cluster наблюдений, а не из одиночных событий.
- `page-type aware`: у каждого типа wiki-страницы свой extraction/synthesis contract.
- `durable + reusable + actionable`: в wiki попадает только то, что переживет сессию и поможет другому агенту/оператору.
- `reflection over raw logs`: Synapse должен уметь не только читать логи, но и собирать post-task reflection/debrief сигналы от агентов.

Phase 1 (Architecture Reset)
1. `done` Evidence layer as first-class model:
   - выделить явный слой `evidence` / `episodes` / `observations` отдельно от `claims` и `drafts`;
   - хранить source shape, freshness, volatility, PII risk, transactionality, and confidence separately from wiki intent.
2. `done` Knowledge candidate bundles:
   - добавить сущность bundle (`entity/process/topic/source-group`) с агрегатами `repeated_count`, `independent_sources`, `first_seen`, `last_seen`, `volatility`, `suggested_page_type`;
   - перевести promotion logic from event-level to bundle-level.
3. `done` Universal knowledge taxonomy v2:
   - закрепить canonical classes: `operational`, `episodic`, `semantic`, `procedural`;
   - внутри wiki compiler normalized targets: `fact`, `process_playbook`, `data_source_doc`, `agent_profile`, `decision_log`, `incident_pattern`.
4. `done` Negative routing by default:
   - explicit hard-block families before draft stage: snapshots, telemetry, payload blobs, PII-heavy records, transient state deltas, heartbeats.

Phase 2 (Signal Extraction)
5. `done` Durable knowledge scoring v2:
   - заменить текущий преимущественно event-centric scoring на composite score from durability, reusability, actionability, and scope.
6. `done` Process extraction compiler:
   - отдельный compiler for `trigger -> condition -> action -> escalation -> verification`, not generic fact extraction.
7. `done` Data-source documentation compiler:
   - строить knowledge pages из connector metadata + observed runtime usage patterns (`who reads this`, `which fields matter`, `what breaks if stale`).
8. `done` Agent capability synthesis v2:
   - собирать capability profile из static config/prompt/tools/policies + runtime evidence + worklogs, а не только из runtime traces.
9. `done` Decision-log compiler:
   - выделять decisions отдельно от discussion; обязательные source/date/outcome fields; compress many small updates into chronological decisions.
10. `done` Rich agent passport bootstrap:
   - capability/profile page must assemble from `agent config`, `system prompt`, `tool registry`, `allowed actions`, `approval/guardrail rules`, `data-source bindings`, `scheduled tasks`, `model routing/failover`, and runtime evidence;
   - eliminate default `runtime discovery pending`/`n/a` outcome for first-run core pages when static discovery is available.
11. `done` Source -> agent -> capability -> process graph:
   - build first-class linkage showing which sources feed which agent capabilities and which capabilities feed which process decisions/actions;
   - use this graph as both wiki content and synthesis input.

Phase 3 (Reflection & Learning Loops)
12. `done` Post-task reflection/debrief contract:
   - SDK/API contract for agent self-report after task/session: `what changed`, `what rule was learned`, `temporary vs durable`, `who else should know`, `confidence`, `evidence`.
13. `done` Query-gap driven knowledge creation:
   - использовать retrieval misses, repeated escalations, frequent re-queries, and repeated operator overrides как сигнал на создание/обновление wiki knowledge.
14. `done` Human-guided synthesis prompts:
   - режим targeted follow-up questions от Synapse к агенту/оператору only when evidence bundle is promising but incomplete.

Phase 4 (Wiki Output Quality)
15. `done` Page-type compilers + hard schemas:
   - у каждой core page family свой required structure and validation contract; raw payload text should fail schema by design.
16. `done` Enrichment pass before publish:
   - короткие/шаблонные/placeholder-heavy pages не публикуются сразу, а идут в enrichment pass with missing-fields diagnostics.
17. `done` Knowledge freshness semantics:
   - page-level volatility/staleness rules by page type (`policy`, `process`, `data source`, `agent profile`) instead of one global stale heuristic.
18. `done` Signal-to-noise audit dashboard:
   - surface `% evidence rejected`, `% bundles promoted`, `% published by page type`, placeholder ratio, and top noisy source families.
19. `done` Importance-aware publishing:
   - bias publish priority toward onboarding-critical page families (`agent capabilities`, `process playbooks`, `data sources`, `company operating context`) ahead of secondary technical pages;
   - allow core pages to publish with explicit block-level warnings (`inferred`, `low_confidence`, `needs_runtime_confirmation`) instead of staying hidden or overly shallow.
20. `done` Richness regression benchmark:
   - evaluate not just page existence but content density, placeholder ratio, tool-name coverage, source-binding coverage, process-step completeness, and source-to-process linkage;
   - maintain a golden bootstrap dataset and release benchmark for “useful wiki richness”.

Phase 5 (First-Run Product UX)
21. `done` Smart default space selection:
   - if useful content lands outside `general`, auto-select the richest published space or show a prominent “more content exists here” CTA.
22. `done` Self-healing persisted workspace state:
   - if saved browser state points to empty scope while another space has published content, reset or offer one-click recovery instead of showing an apparently empty wiki.
23. `done` Wiki quality report v2:
   - post-bootstrap report must explain not only coverage but also `why useful pages stayed in reviewed/draft`, `which signals were missing`, and `which page families remain weak`.
24. `done` Opinionated AI-employee-org bootstrap:
   - first-run pack for agent-driven orgs: `Agent Profile`, `Tool Catalog`, `Data Sources`, `Process Playbooks`, `Escalation Rules`, `Scheduled Tasks`, `HITL Rules`, `Integrations Map`.

Definition of done for this track:
- fresh integrations no longer produce order/payload-like wiki pages by default;
- first useful wiki output comes from compiled bundles, not direct event promotion;
- process pages read like instructions, data pages read like source contracts, agent pages read like real capability profiles;
- teams can explain why a page exists in terms of bundled evidence, not isolated raw logs;
- clean self-host bootstrap lands the user in the space with the richest useful content by default;
- release quality is measured by richness/completeness, not only by slug creation or page count.

## Real-World Adoption Backlog (April 2026)

Status: `done`

Context from live integrations:
- backfill accepted at API layer, but most records dropped into `claims.rejected` by default routing policy (especially `source_type=event|external_event`);
- teams must write custom importers and manually tune policy for first useful wiki output;
- self-host can boot backend while UI remains on stale profile/route path;
- no safe project-scope reset API for clean reruns.

### P0 (Adoption Critical)

1. `done` Split ingestion lanes (`knowledge` vs `event`):
   - add dedicated corporate-memory ingest path (`knowledge_ingest`) that does not inherit event-stream deny defaults;
   - preserve strict event filtering on runtime/event lane.
2. `done` Bootstrap profile for first wiki import:
   - one-click API/UI preset with soft thresholds, safe noise filters, and sample-based auto-approve defaults.
3. `done` Rejection diagnostics endpoint:
   - project-level aggregated visibility: top reject reasons, blocked patterns, representative examples, and suggested policy knobs.
4. `done` Admin project reset API:
   - scoped reset (`wiki/events/claims/drafts`) with dry-run preview and audit trail; no Docker volume wipe required.
5. `done` Self-host one-command “core wiki” default:
   - backend + worker + web with default `core` profile and `/wiki` route;
   - eliminate advanced/localStorage trap on first run.

P0 exit criteria:
- a clean integration can run `import -> draft -> approve -> publish -> retrieval` without custom scripts;
- first-pass import from `memory_items`/`ops_kb_items` yields useful drafts/pages by default (without manual policy surgery);
- troubleshooting requires API diagnostics, not database forensics.

### P1 (Next Iteration)

1. `done` Built-in import connectors:
   - native adapters for `memory_items` and `ops_kb_items` with declarative mapping config.
2. `done` Pipeline visibility UI:
   - end-to-end counters `accepted -> events -> claims -> drafts -> pages` with bottleneck highlighting.
3. `done` Noise-filter presets:
   - reusable presets for order snapshots, telemetry streams, and raw event payloads before claim generation.
4. `done` Curated import mode:
   - ingest constrained by explicit `namespaces`/`source_systems`.
5. `done` Predictable page listing/search:
   - explicit “show all pages” behavior and removal of `q=*` ambiguity.

### P2 (Release Process Hardening)

1. `done` API/Web compatibility contract:
   - declare minimum compatible web build per backend version and enforce in CI/release notes.
2. `done` Upgrade checklist docs:
   - migrations, worker restart, routing-policy migration steps, and rollback notes.
3. `done` Post-deploy smoke test:
   - standard smoke flow: import 10 records -> produce 1 draft -> publish 1 page -> verify `/wiki` retrieval.

Execution order for this track:
1. P0.1 ingestion lane split.
2. P0.2 bootstrap profile.
3. P0.3 rejection diagnostics.
4. P0.4 project reset API.
5. P0.5 self-host default experience.
6. P1 visibility + connectors.
7. P2 release guardrails.

## OOTB Quality Stage II (April 2026, post field feedback)

Status: `done`

Goal:
- после clean deploy + one-step bootstrap давать полезную, не зашумленную wiki без ручного SQL/policy-tuning;
- не допускать draft-flood и деградации queue при источниках с высокой событийностью.

### P0 (this sprint)

1. `done` Draft-flood guardrails:
   - routing knobs: `emit_reinforcement_drafts`, `draft_flood_max_open_per_page`, `draft_flood_max_open_per_entity`, queue pressure thresholds;
   - worker-level suppression новых draft inserts при превышении page/entity/global limits;
   - pipeline diagnostics + critical warnings для auto-safe-mode.
2. `done` High-signal default routing hardening:
   - расширен deny-list шумных source patterns (`wand_employee*`, `wand_transport_vehicle*`, `*_sheet_*`, telemetry/event snapshots);
   - legacy sync uploads принудительно в `knowledge` lane для curated memory bootstrap.
3. `done` Curated bootstrap page quality uplift:
   - Data Sources Catalog / Agent Capability / Operational Logic bootstrap pages стали содержательнее (governance + actionable fallback content).
4. `done` High-signal extraction lane for `events -> claims`:
   - добавлены `high_signal_route_keywords` + `high_signal_min_keyword_hits`, чтобы policy/process/runbook сигналы проходили даже при event-like форме.
5. `done` Pre-claim extraction reason taxonomy:
   - worker пишет агрегированные `drop_reason_counts` / `keep_reason_counts` в backfill batches;
   - `/v1/adoption/pipeline/visibility` показывает причины, почему события были отброшены до claim stage.
6. `done` Claims-floor safety diagnostics:
   - guardrail `events >= N && claims == 0 && age >= T` с критическим warning и actionable next step;
   - новые routing-policy knobs для floor-порогов (`claims_floor_*`).
7. `done` Bootstrap core publish + quality report:
   - `agent-wiki-bootstrap` now returns explicit `Preview -> Apply` guidance and structured `quality_report` (core coverage, placeholder ratio, non-publish reasons);
   - introduced `bootstrap_publish_core=true` override so onboarding-critical pages are published with warning annotations even under partial evidence.
8. `done` OOTB wiki quality gate + release regression hook:
   - added `GET /v1/adoption/wiki-quality/report` with hard checks for required core pages, `placeholder_ratio_core <= 0.10`, and `daily_summary_open_draft_ratio <= 0.20`;
   - wired self-host acceptance regression (`scripts/integration_legacy_sync_queue_processing.py`) to fail when wiki quality gate regresses after clean bootstrap.

### P1 (next)

1. `done` Agent capability enrichment from runtime signals/tools/handoffs:
   - capability bootstrap now includes per-agent `typical actions`, `escalation rules`, `constraints`, and `scenario examples` instead of template-only rows.
2. `done` Source pages enrichment with real key fields/schema/freshness/usage sampling.
3. `done` OOTB moderation policy pack:
   - auto-publish only high-signal classes;
   - noisy classes always `pending_review`.
4. `done` Runtime registry fallback from event payloads:
   - capability/source-usage discovery now infers `agent_id` from runtime event payload/metadata fields when explicit `/v1/agents/register` integration is absent.
5. `done` Signal/noise stability monitor:
   - queue growth alerts + “safe mode recommended/applied” audit trail.

## v0.1.3 Release Plan (Q2 2026)

Status: `done`

Goal:
- сделать внедрение Synapse по-настоящему “подключил и работает” для существующих agent-memory стеков;
- уменьшить ручной тюнинг gatekeeper и политику импорта на первом дне;
- довести wiki-first UX до уровня production onboarding для новых команд.

Checklist:
1. `done` Adoption setup wizard v2:
   - единый onboarding flow в UI (`connect source -> preview curated import -> first publish`) без перехода в ops-тулзы;
   - шаблоны подключений для `ops_kb_items` / `memory_items` прямо из мастера.
2. `done` Curated import dry-run explain:
   - endpoint с предпросмотром фильтрации до записи событий (`kept/dropped` + reason breakdown sample);
   - one-click “apply this profile” из dry-run результата.
3. `done` Policy calibration quick loop:
   - в UI быстрые рекомендации по routing-policy на основе reject diagnostics + pipeline bottleneck;
   - safe preset apply с rollback snapshot.
4. `done` Self-host UX consistency gate:
   - авто-проверка, что `/wiki` route и core profile активны после апгрейда/рестарта;
   - предупреждение в UI при несовместимой web/api версии.
5. `done` Adoption KPI dashboard:
   - KPI: `time_to_first_draft`, `time_to_first_publish`, `draft_noise_ratio`, `publish_revert_rate`;
   - baseline alerts для деградации качества импорта.
6. `done` Connector pack hardening:
   - расширение built-in connectors для типовых custom SQL mapping сценариев (explicit field overrides + validation hints);
   - cookbook с production примерами cron/CDC sync.
7. `done` OSS launch polish pack:
   - обновление README/Quickstart под новый setup wizard + curated import defaults;
   - релизный “operator playbook” для первых 24 часов после внедрения.

## v0.1.4 Adoption UX Hardening (Q2 2026)

Status: `done`

Goal:
- убрать последние “ручные костыли” при первом внедрении;
- сделать first-run experience предсказуемым для self-host и enterprise команд.

Checklist:
1. `done` Built-in Memory API connector:
   - добавить `memory_api` source type в legacy sync + adoption connector catalog;
   - убрать необходимость писать кастомный importer для типового REST memory API.
2. `done` First-run bootstrap pages:
   - one-click API/UI шаг, создающий стартовые wiki-страницы (`Agent Profile`, `Data Map`, `Runbook`) c idempotent поведением.
3. `done` Self-host basePath resilience:
   - поддержка `/synapse/` маршрута без ручной пересборки web ассетов.
4. `done` UI profile single-mode guard:
   - упростить профильный режим до единого core-first поведения без stale localStorage trap.
5. `done` Source-quality defaults v2:
   - усилить default-фильтры для отделения operational summary/telemetry от durable knowledge.
6. `done` One-command enterprise sync preset:
   - curated import + synthesis + safe bootstrap approve как единый workflow API.
7. `done` Onboarding funnel visibility:
   - прозрачная воронка `accepted -> events -> claims -> drafts -> pages` + reject diagnostics в API/UI.
8. `done` Role-based wiki-space templates:
   - шаблоны структур страниц под роли (Support, Logistics, SalesOps, Compliance) при подключении.

## Agent Worklog Intelligence TODO (April 2026)

Status: `done`

1. `done` Semantic daily summaries:
   - structure reports as `Done / Impact / Blockers / Escalations` with authored-page highlights and activity score.
2. `done` Timezone-aware project scheduling:
   - per-project timezone + local run window from routing policy (`agent_worklog_timezone`, schedule hour/minute).
3. `done` Orgchart API + Operations UI:
   - expose graph-ready API (`nodes/edges/teams`) and render operations orgchart (teams + handoffs + profile deep-links).
4. `done` Anti-noise worklog gating:
   - skip idle days by default using `min_activity_score` + meaningful-signal checks.
5. `done` Hybrid trigger model:
   - keep daily batch plus realtime refresh on `session_close` / `task_close` signals.

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

## Knowledge Compiler Hardening (April 2026)

Status: `done`

Goal:
- stop raw operational/event streams from becoming wiki pages;
- keep the universal SDK flow simple (`attach -> ingest -> useful wiki drafts`) for existing-memory adoption.

Checklist:
1. `done` Utility Gate v1 in worker:
   - durable knowledge-signal scoring;
   - source-id deny filters;
   - key/value payload-density event-shape detection.
2. `done` Backfill pre-enqueue suppression:
   - event-like low-signal records dropped before claim proposal queue;
   - trusted knowledge hints (`record_kind`, `knowledge_signal`) bypass suppression.
3. `done` API parity for new routing knobs:
   - `GET/PUT /v1/gatekeeper/config` normalizes new `routing_policy` fields.
4. `done` Regression tests for routing quality:
   - unit tests for snapshot-noise demotion + policy-fact retention.
5. `done` Assertion class contracts:
   - typed class labels (`policy`, `process`, `preference`, `incident`, `event`) to improve explainability.
6. `done` Retrieval-feedback loop:
   - incorporate real runtime usefulness into draft priority and policy suggestions.

## User-Friendly Wiki UX (12-Point Track)

Status: `done`

Goal:
- сделать UX уровня “корпоративная wiki для обычных людей”, а не control-center;
- держать Drafts/Tasks вторичными по отношению к page-first wiki.

Checklist:
1. `done` Wiki-only landing:
   - open last visited page automatically per project (`localStorage` restore).
2. `done` Super-simple top bar:
   - compact actions (`Create`, `Share`, `Edit`, `Publish`, `Sync`) + search.
3. `done` Clean left tree:
   - page tree with context menu (`Open`, `Move/Rename`, `Archive/Restore`);
   - drag-and-drop move with `reparent` workflow wired.
4. `done` Rich page editing:
   - done: local autosave + restore for page edit drafts in core mode;
   - done: slash-first core editor, undo/redo parity, stronger version diff UX.
5. `done` Drafts as inbox:
   - Drafts live in dedicated tab; page view shows lightweight “Open drafts” context only.
6. `done` Publish modal:
   - modal with location + change summary before publish.
7. `done` Smart page creation:
   - template-first create panel (`Access Policy`, `Operations Incident`, `Customer Preference`).
8. `done` 60-second onboarding:
   - first-run guided modal with 3 steps (connect -> create -> review).
9. `done` Human copy cleanup:
   - remove ops-heavy labels from core surface; keep technical language in advanced mode.
10. `done` Fast search:
    - `Cmd/Ctrl+K` jump modal, recent pages, and create-from-query path.
11. `done` Friendly roles model:
   - Viewer / Editor / Approver / Admin language + simple permission table in UI/docs.
12. `done` UX metrics:
   - track TTFV, time-to-first-publish, and click-depth to open/publish.

## Process Playbook Intelligence (Support Ops Focus)

Status: `done`

Goal:
- сделать Wiki не только хранилищем фактов, но и живым справочником процессов;
- позволить агентам автоматически документировать “как работает операция” в формате шагов и условий.

Checklist:
1. `done` Operator decision capture (online):
   - ingest live operator decisions from chats/tickets/macros;
   - normalize as `trigger -> action -> outcome` records.
2. `done` Template-first process pages:
   - add canonical page templates (`Issue Playbook`, `Escalation Rule`, `Customer Exception`, `Known Incident`);
   - auto-route extracted records into those templates.
3. `done` Gatekeeper process-quality routing:
   - block event-stream noise from process wiki pages;
   - promote only repeated/validated workflow signals.
4. `done` Risk-tiered publish + rollback:
   - low-risk process updates can auto-publish;
   - policy/financial/legal changes stay `human_required`;
   - full rollback path remains mandatory.
5. `done` Intent-aware context injection:
   - retrieval injects process steps by task intent, not by keyword-only matching;
   - enforce top-k verified runbook snippets in runtime context.
6. `done` Auto onboarding packs:
   - generate “day-0” role packs (critical playbooks, escalations, forbidden actions, fresh changes).
7. `done` Ticket/outcome linkage:
   - attach process statements to ticket ids and resolution outcomes;
   - prioritize process knowledge that demonstrably resolved incidents.
8. `done` Process instruction provenance:
   - link each process step to source evidence (operator session, ticket, policy page);
   - expose “why this step exists” in wiki UI and MCP retrieval explain.
9. `done` Process simulation safety check:
   - run “what changes if we update this process step” simulation before broad publish.

## Agent Directory & Operations Intelligence

Status: `done`

Goal:
- сделать в Wiki прозрачную структуру “кто из AI-агентов что делает”;
- добавить self-maintained профили агентов, ежедневные отчеты и связь с реальными артефактами знаний.

Phase 1 (MVP):
1. `done` AI Orgchart index:
   - page `Agents/Index` with team/role hierarchy and status badges.
2. `done` Agent self-profile on attach:
   - SDK `attach()` can publish/update agent profile (`responsibilities`, `tools`, `data_sources`, `limits`).
3. `done` Standard agent folder scaffold:
   - `Overview`, `Runbooks`, `Daily Reports`, `Created Pages`, `Incidents`, `Changelog`.
4. `done` Auto-generated “Created by agent” page index:
   - list pages/statements authored by each agent with timestamps and links.

Phase 2 (Scale):
5. `done` Daily worklog synthesis:
   - per-agent daily report with completed actions, blockers, escalations, and impact.
6. `done` Capability matrix:
   - “which agent handles what” with confidence and last-success evidence.
7. `done` Handoff map:
   - explicit inter-agent handoff graph (`input contract`, `output contract`, `SLA`).

Phase 3 (Governance):
8. `done` Agent scorecards:
   - quality/reliability metrics (resolution rate, rollback rate, escalation rate, SLA adherence).
9. `done` Agent-level provenance and rollback:
   - show evidence trail for agent-authored updates and support one-click rollback.
10. `done` Risk-tiered policy enforcement:
    - per-agent publish guardrails (`auto_publish` vs `human_required`) by domain risk.

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

## M15: Public Launch & Positioning (Weeks 37-40)

Status: `done`

Scope:
- remove “not published yet” friction by shipping registry-verified package installs;
- make Agentic Onboarding the primary GTM story with measurable time-to-value;
- keep OpenClaw strength while making LangGraph/LangChain/CrewAI entry equally first-class;
- reframe messaging from “wiki UI” to “Cognitive State Layer (L2 for AI agents)” without losing wiki UX clarity.

Exit criteria:
- clean-machine install works with registry packages (`pip install synapseworkspace-sdk`, `npm install @synapseworkspace/sdk`);
- onboarding benchmark is documented and reproducible (`time-to-first-useful-draft`, `time-to-first-publish`);
- top-level docs/README consistently present Synapse as L2 cognitive layer with Agentic Wiki as operational interface.

Checklist:
1. `done` Kill “Not Published Yet” docs state:
   - complete trusted publishing for PyPI/npm and verify first successful public releases;
   - replace “not published yet” language with versioned install docs and troubleshooting.
2. `done` Registry install verification matrix:
   - add clean-room install checks on Linux/macOS for Python + Node in CI release path;
   - capture publish provenance and signed artifact references in release notes.
3. `done` Agentic Onboarding benchmark kit:
   - ship one-command benchmark scenario for “new support agent day-0” with before/after metrics;
   - surface KPI cards in docs (`first useful answer`, `first approved draft`, `first policy-safe publish`).
4. `done` Multi-framework onboarding parity:
   - add canonical quickstarts for OpenClaw, LangGraph, LangChain, CrewAI with same 5-minute structure;
   - enforce parity via docs lint + smoke contracts.
5. `done` Positioning refresh (L2 narrative):
   - update README/docs hero language to “Cognitive State Layer (L2)” + “Agentic Wiki interface”;
   - keep dual framing: infra buyers (L2 reliability/quality) + operators (wiki governance UI).
6. `done` Buyer-facing packaging:
   - add concise “Why now / ROI / rollout modes” one-pager and architecture slide-ready diagram pack;
   - include side-by-side “raw RAG vs Synapse L2” operational comparison.

## Execution Queue Archive

Status: `done`

This section previously tracked the short-lived extraction queue (`canonical shell`, `legacy render removal`, `utility-gate observability polish`).
All items were completed and moved to `Recent Updates` for audit history.

## Risks to Watch

1. Low precision claim extraction in noisy logs.
2. Temporal parsing ambiguity for informal date phrases (locale and shorthand variants).
3. Integration overhead across agent frameworks.
4. Scope drift between OSS core and enterprise addons.
5. Wiki bloat without strict Gatekeeper thresholds and archival policy.
6. Local dev DB instability if Docker VM storage is saturated during heavy migration replay.
7. SDK API sprawl can reduce adoption if facade and plugin boundaries are not tightly controlled.
8. Product-message drift: technical docs can overshadow Agentic Wiki value narrative and reduce conversion.

## v0.1.5 Production Adoption DX (Q2 2026)

Status: `done`

Goal:
- сделать внедрение/операционное ведение Synapse максимально простым для production-команд;
- закрепить no-code операторский путь `sync -> diagnose -> moderate` через единый CLI.

Checklist:
1. `done` CLI adoption operations bundle:
   - expanded `synapse-cli adoption` with `sync-preset`, `pipeline`, `rejections` plus existing operator commands;
   - kept safe dry-run defaults and machine-readable JSON outputs.
2. `done` CI smoke for adoption CLI operations:
   - added offline end-to-end smoke (`scripts/check_synapse_cli_adoption_ops.py`) covering all adoption operator commands via stubbed API.
3. `done` API/worker explainability envelope in sync preset:
   - unify top-level reason buckets (`quality_gate`, `routing_policy`, `classification`) directly in preset summary payload.
4. `done` Operations route quick actions v2:
   - add direct deep-link actions (`Run Sync Preset`, `View Pipeline`, `View Rejections`) with opinionated defaults.
5. `done` Release playbook refresh for adoption ops:
   - align `getting-started`, `adoption-existing-memory`, and `self-hosted-deployment` with the new CLI-first operator flow.

## Step-0 Snapshot & Agent-Wiki Schema (April 2026)

Status: `done`

Goal:
- сделать `state`-snapshot первым классом в Synapse (не просто markdown-файл рядом);
- стандартизировать агент-читаемый wiki schema (`summary/status/last_updated`, backlinks, staleness, decisions log);
- дать OOTB Step-0 retrieval flow: сначала snapshot, потом точечный добор контекста.

Checklist:
1. `done` State Snapshot API:
   - `GET /v1/wiki/state` (сборка snapshot на лету из wiki/tasks/agent signals);
   - `POST /v1/wiki/state/sync` (upsert `state` page в space).
2. `done` MCP Step-0 native support:
   - добавить `get_state_snapshot` tool;
   - при `search_knowledge` приоритизировать state snippet в `context_injection`.
3. `done` Bootstrap integration:
   - включить `state` page в first-run/bootstrap flows как обязательную core страницу.
4. `done` Schema contracts:
   - enforce frontmatter contract (`summary/status/last_updated`) + backlinks для knowledge page types;
   - quality warnings при нарушении контракта.
5. `done` Staleness and decisions baseline:
   - авто-check stale меток для `index`/space listing;
   - обязательный `decisions/log` seed в bootstrap pack.
6. `done` SDK + docs:
   - SDK helpers for state snapshot (`get/sync`);
   - docs/playbooks “Step 0 = state snapshot first”.

## Recent Updates

- 2026-05-03: Strengthened the next content-richness layer on top of runtime-surface sync: Synapse now preserves first-class `source_binding_contracts` and `capability_contracts` inside agent profiles instead of collapsing everything to plain strings, uses those contracts to surface explicit or inferred `source -> agent / capability / process / tool` mappings in `Data Sources Catalog`, and generates per-task SOP pages under `agents/<id>/runbooks/*` directly from scheduled task / builtin-task contracts so recurring workflows become concrete runbooks rather than generic prose.
- 2026-05-03: Closed the next runtime-surface feedback loop from self-host verification: `POST /v1/agents/runtime-surface/sync` now refreshes existing core wiki spaces by default instead of only updating agent-space scaffolds, so control-plane contracts can immediately rehydrate `logistics/*` (or other domain spaces) without a manual `agent-wiki-bootstrap` rerun; source synthesis now falls back to runtime/control-plane profiles for knowledge-plane imports (`memory_items`, `ops_kb_items`, etc.) when explicit source bindings are sparse, which surfaces inferred `source -> agent / capability / process / tool` links in `Data Sources Catalog` and source detail pages; and agent-space `runbooks` pages now synthesize concrete recurring flows directly from scheduled task / builtin-task contracts rather than staying generic stubs.
- 2026-05-03: Hardened the clean-project runtime-surface path after the next `hw_ai_agents` verification round: `POST /v1/agents/runtime-surface/sync` now infers a shared domain wiki space from scheduled-task / capability / source contracts when no core space exists yet, so a fresh self-host run can materialize `logistics/*` (or another domain family) directly from sync instead of falling back to `operations/*`; bootstrap source-usage inference is now defensive against sparse/partial capability matrices, removing the `NoneType` crash reported before runtime sync; and core pages (`Agent Capability Profile`, `Tooling Map`, `Company Operating Context`) now fall back to direct `agent_directory_profiles` runtime metadata if the richer matrix path is temporarily empty, preventing obvious `0 agents / 0 instances` regressions after a successful runtime sync.
- 2026-05-03: Started the next content-depth pass after runtime/core materialization stabilized: scheduled-task SOP rendering now uses a reusable semantic compiler over `task_code`, `builtin_task`, source hints, authority, approval mode, and escalation semantics so task pages stop defaulting to generic lines like `runtime task context + bound sources`; the same task-contract semantics now feed shared `Process Playbooks`, which should make recurring workflows such as `driver_economy_sheet`, `incident_monitor`, `document_shift_readiness`, `daily_report`, and ERP/cargo syncs read more like concrete business SOPs and less like neutral scaffolding.
- 2026-05-03: Started the first structural extraction from domain heuristics to pack-level policy: scheduled-task semantics now flow through a dedicated `synthesis_packs` registry with `generic_ops` and `logistics_ops` implementations, keeping the current logistics-oriented SOP enrichment intact while moving the “what makes this task read like a domain SOP” logic out of `main.py`. This is the first no-behavior-change step toward a true `core engine + domain synthesis packs` architecture.
- 2026-05-03: Continued the `core engine + domain packs` extraction by moving runtime-surface shared-space inference behind the same `synthesis_packs` registry. Core sync/bootstrap flows still materialize the same `logistics/*` pages on the current pack, but `main.py` no longer owns the policy for choosing a domain wiki namespace from scheduled tasks / runtime contracts; that decision now lives beside task semantics as another pack-level concern.
- 2026-05-03: Pulled the next enrichment heuristic out of the compiler core: runtime/control-plane fallback for source usage (`source -> agent / capability / process / tool` inference when explicit mapping is sparse) now routes through `synthesis_packs` as a pack-level policy. The current `logistics_ops` behavior is preserved, but the `Data Sources Catalog` compiler no longer hardcodes how a domain should infer process impact from runtime matrices.
- 2026-05-03: Closed the next generic synthesis gap reported by self-host integrators: Synapse now accepts a first-class control-plane/runtime surface feed through `POST /v1/agents/runtime-surface/sync`, turning runtime overview (`running_instances`, mode, heartbeat), scheduled tasks, standing orders, capability registry, action surface, tool manifest, source hints, approvals, and model-routing contracts into normalized agent-directory profiles plus immediate wiki scaffold refresh. This gives `Agent Capability Profile`, `Tooling Map`, `Company Operating Context`, source usage, and process compilers a richer non-runtime-discovery input path so domains with strong control-plane metadata no longer need to wait for event-derived runtime discovery to produce meaningful wiki content.
- 2026-05-03: Tightened the next content-richness gap reported by integrators: bootstrap now derives more grounded wiki content from `tool_registry`, approval/guardrail contracts, prompt/model-routing metadata, source bindings, and standing orders instead of mostly relying on runtime discovery; `Tooling Map` renders tool -> capability/process/source relationships plus declared purpose/guardrails, `Agent Capability Profile` shows richer static contracts, and `sync-presets/execute` now defaults its starter pack to `standard` so domain deployments do not get surprise `support/*` starter pages unless they explicitly opt in.
- 2026-05-03: Strengthened content richness in the bootstrap compilers instead of only hardening infra: `Agent Capability Profile` now suppresses gratuitous `n/a` scaffolding and renders grounded operating scope/guardrails/toolset/data-source context from static passport metadata (`standing_orders`, `scheduled_tasks`, `registry_tools`, `source_bindings`, `approval_rules`, `model_routing`, prompt hints) plus reflection signals and bundle-backed insights; `Tooling Map` now links tools to capability/process/source context instead of a flat registry; `Process Playbooks` can synthesize SOP-style runbooks from agent profile declarations (standing orders, scheduled tasks, approvals, sources, tools) in addition to claims/bundles/reflections; `Operational Logic Map` now folds durable bundle patterns and agent-profile workflow rules into the first-pass logic table; and source-usage matching now recognizes profile/source-binding metadata better so `Data Sources Catalog` is less likely to collapse into `Used by Agents = none / Impact = n/a`.
- 2026-05-03: Reconciled `Knowledge Compiler v2` roadmap statuses with the codebase after the latest delivery wave. The track treats `bundles`, `taxonomy`, `negative routing`, `process/data/capability/decision compilers`, `reflection/debrief`, `knowledge gaps`, `synthesis prompts`, `hard page schemas`, `publish-time enrichment`, `freshness semantics`, `importance-aware publishing`, and `richness benchmark` as `done`; at that moment the one major item still left open was `Evidence layer as first-class model`, because Synapse already had first-class bundles and reflection signals but still did not expose a fully separate generalized evidence/episode storage contract with all desired source-shape/volatility/PII semantics.
- 2026-05-03: Closed the final remaining `Knowledge Compiler v2` architecture gap by adding a first-class `evidence_records` ledger with explicit source-shape, volatility, PII, transactionality, taxonomy, target-type, role, and bundle-link semantics. Synapse now exposes that layer through `/v1/adoption/evidence-ledger` and `/v1/adoption/evidence-ledger/stats`, and the worker persists normalized evidence records alongside bundles/claims so evidence is no longer only implicit inside claim JSON.
- 2026-05-03: Fixed the first integration regressions after the evidence-ledger rollout: `agent-wiki-bootstrap` no longer assumes `claims.evidence` exists on older/self-hosted schemas, self-host upgrades now add `claims.evidence` explicitly, project reset clears legacy import dedup fingerprints/runs together with backfill state, `/v1/adoption/rejections` works again as a compatibility alias, and the evidence-ledger APIs now fall back to proposal-stage evidence when claim processing has not materialized rows yet.
- 2026-05-03: Added a lightweight bundle-first control layer to the Drafts UI without turning it into an ops cockpit: operators now get compact recommendation chips (`approve first`, `review with context`, `human caution`) to slice the inbox, plus a one-line safe-bulk-approve hint that estimates how many weaker drafts will be skipped in the current scope by the default bundle guard.
- 2026-05-03: Surfaced bundle-first review signals in the web Drafts experience: the inbox now shows a compact queue summary from `GET /v1/wiki/drafts` (recommendation mix, bundle-status mix, ready-support total), each draft card shows bundle recommendation/status, and Draft Detail now renders a dedicated `Bundle Recommendation` block so operators can understand “why this draft is high-priority” without reading raw gatekeeper metadata.
- 2026-05-03: Promoted bundle recommendations into first-class review-queue signals: `GET /v1/wiki/drafts` now returns a `queue_summary` grouped by recommendation/status/page-family plus top bundle-backed items, draft detail exposes `recommended_action`, and bulk review now surfaces `skipped_by_bundle_guard` previews so operators can see exactly which drafts were withheld by the safe default instead of treating bundle-aware moderation as a hidden backend rule.
- 2026-05-03: Moved the moderation inbox itself closer to bundle-first behavior: draft APIs now rank items by bundle maturity (`ready/candidate`, support, quality, knowledge-like score, conflicts/risk penalties) and expose explicit `bundle_priority` recommendations (`approve_first`, `review_with_context`, `needs_human_caution`), while bulk approve now defaults to a safe bundle guard that only applies non-force approvals to drafts backed by `ready` or promotion-ready bundles unless the operator explicitly widens the filter.
- 2026-05-03: Pushed moderation and source-doc flows closer to bundle-first behavior: draft inbox/detail responses now expose resolved evidence-bundle context (status/support/quality/taxonomy/sample claims) instead of only opaque `bundle_key` hints, bulk draft review can safely filter by `bundle_status`, `bundle_support`, `knowledge_dimension`, and `suggested_page_type`, and `Data Sources Catalog` pages now render explicit downstream decisions plus `Reliability & Risk` blocks (`stale risk`, `ownership posture`, `human review boundary`) so source docs explain not just who uses the data, but how risky stale data would be for wiki promotion.
- 2026-05-03: Strengthened the content density of `Knowledge Compiler v2` instead of only its plumbing: `Agent Capability Profile` pages now consume reflection/debrief signals (`durable rules`, recorded decisions, observed workflow actions, missing documentation questions, open uncertainties, latest debrief summary, reflection coverage) in addition to static passport data and bundles; `Process Playbooks` now synthesize richer SOP blocks (`owners`, `verification`, `human-in-the-loop`, `artifacts/systems`, `decision trail`) and can mint runbooks directly from repeated reflection signals even when the knowledge first appears through post-task debrief instead of curated policy docs.
- 2026-05-02: Closed the next first-run quality loop in `Knowledge Compiler v2`: Synapse now ships `/v1/adoption/signal-noise/audit` for a compact operator-facing view of evidence rejection, bundle promotion, published/reviewed page mix, weak page families, missing signals, and noisy source families; `wiki-quality/report` now explains reviewed core backlog and missing synthesis signals instead of only pass/fail counters; Operations UI renders this as a `Knowledge Compiler Health` panel; and first-run/template bootstrap now includes an opinionated `AI Employee Org` pack (`Tool Catalog`, `Scheduled Tasks`, `Human-in-the-Loop Rules`, `Integrations Map`, `Escalation Rules`, `Agent Directory Index`).
- 2026-05-03: Tightened the knowledge compiler core instead of just its diagnostics: worker gatekeeper scoring now consumes existing `evidence_bundles` history and computes an explicit composite durable score (`durability / reusability / actionability / scope`) before promotion, so new claims are judged in bundle context rather than as isolated events; API now ships `/v1/adoption/stability-monitor` plus `/v1/adoption/safe-mode/recommend`, and both recommendation/apply flows persist `adoption_safe_mode_recommended` / `adoption_safe_mode_applied` audit events via queue-control history instead of leaving safe-mode decisions as ephemeral warnings only.
- 2026-05-02: Advanced `Knowledge Compiler v2` with explicit taxonomy and guided synthesis support: worker routing now stamps bundles/claims with `knowledge_taxonomy_class` (`operational / episodic / semantic / procedural`) and normalized target types, evidence-bundle API exposes those fields, and Synapse now ships `/v1/adoption/synthesis-prompts` to generate targeted follow-up questions from candidate bundles, repeated agent questions, and page-enrichment gaps. This closes the first production slice of human-guided synthesis instead of leaving gaps as raw diagnostics only.
- 2026-05-02: Extended `Knowledge Compiler v2` beyond page compilers: Synapse now exposes `/v1/adoption/knowledge-gaps` to surface repeated agent questions, escalation patterns, candidate bundles, and core-page enrichment gaps; freshness semantics are now page-type aware (`policy/process/runbook/agent_profile/data_map/decision_log`) in wiki listing/lifecycle endpoints instead of one global stale threshold; and SDK adoption helpers now expose both richness benchmark and knowledge-gap diagnostics.
- 2026-05-02: Implemented the next `Knowledge Compiler v2` production slice: publish-time enrichment now rehydrates thin/placeholder-heavy pages from canonical compilers before publish, hard page-type schema contracts were expanded for agent/data/process/decision pages, a new `decision-log` compiler and `/v1/agents/reflections` debrief contract landed, both SDKs gained first-class reflection submission methods, and `/v1/adoption/wiki-richness/benchmark` now measures useful wiki density beyond simple page existence.
- 2026-05-02: Made bootstrap synthesis bundle-aware: `Process Playbooks` and `Agent Capability Profile` now consume first-class `evidence_bundles` (status/support/sample claims), so core wiki pages can be grounded by durable knowledge clusters instead of only raw claims or runtime matrix fallbacks.
- 2026-05-02: Extended bundle-aware synthesis into `Data Sources Catalog`: source pages now pull durable source/process/capability signals from `evidence_bundles`, and Operations UI can inspect bundle health (`ready/candidate/suppressed`, preview evidence, suggested page types) without digging through raw drafts.
- 2026-05-02: Introduced first-class `evidence bundles` storage scaffolding: added Postgres bundle/link tables, worker-side bundle upsert from gatekeeper/compiler signals, persisted `compiler_v2` bundle hints into claim metadata, and shipped a read API (`/v1/adoption/evidence-bundles`) so integrations can inspect durable knowledge clusters separately from drafts/pages.
- 2026-05-02: Pushed `Knowledge Compiler v2` deeper into worker routing: gatekeeper now detects generic knowledge-like dimensions (`policy/process/capability/data_source/decision`), emits bundle-style hints (`bundle_key`, `bundle_support`, `suggested_page_type`), preserves knowledge-like operational notes from premature pre-draft blocking, and strengthens default negative routing for payload/event noise before it reaches wiki drafts.
- 2026-05-02: Landed the next `Knowledge Compiler v2` implementation slice: bootstrap now applies importance-aware publishing metadata and explicit warning blocks for force-published core pages, quality reports expose page importance / priority backlog / published-with-warning states, and self-host wiki UI auto-recovers from empty or stale saved spaces by switching to the richest published space.
- 2026-05-02: Started `Knowledge Compiler v2` implementation with richer bootstrap synthesis: agent capability pages now begin consuming broader static passport signals (scheduled tasks, standing orders/processes, source bindings, model routing/failover, integrations), and data-source catalog pages now surface stronger `source -> agent -> capability/process` linkage instead of only loose usage hints.
- 2026-05-02: Expanded `Knowledge Compiler v2` using fresh field feedback from a real integration: added rich agent passport bootstrap, canonical `source -> agent -> capability -> process` linkage, importance-aware core-page publishing with explicit low-confidence warnings, richness regression benchmarks/golden dataset, and first-run UX fixes for wrong default wiki space / stale persisted workspace state.
- 2026-05-02: Added new roadmap track `Knowledge Compiler v2` to fix the product’s core knowledge-selection model: Synapse should promote bundled durable knowledge from evidence (`facts/processes/data docs/agent capabilities/decisions`) instead of generating wiki drafts directly from raw runtime memory or event-like operational flow.
- 2026-04-17: Hardened Step-0 to full production defaults: retrieval now follows enforced `state-first` protocol (`phase0 snapshot -> phase1 targeted pages`), wiki write-paths (`POST/PUT /v1/wiki/pages`) now normalize and enforce schema contract/frontmatter automatically, publish quality gate now requires decision-focused content with chronological/source-attributed decision entries, typed skeleton sections added for `workstream/person/experiment/metric`, and stale defaults shifted to `7/14` days.
- 2026-04-17: Completed Step-0 state snapshot runtime plumbing (`GET /v1/wiki/state`, `POST /v1/wiki/state/sync`, MCP `get_state_snapshot` tool), added retrieval-time Step-0 snippet injection (`explainability.state_snapshot`) and test coverage for MCP tool registry/runtime cache + state snippet context behavior.
- 2026-04-17: Finished Step-0 bootstrap/schema rollout end-to-end: first-run and agent bootstrap now seed `state` + `decisions-log` pages, bootstrap markdown is normalized to schema contract (`frontmatter: summary/status/last_updated` + backlinks + decisions log for process pages), `/v1/wiki/pages` now exposes stale-age markers in listing responses, and Python/TypeScript SDKs ship state snapshot helpers (`get/sync`) with updated docs.
- 2026-04-10: Improved OOTB runtime agent discovery without explicit registry integration: added payload-based runtime `agent_id` inference (`events.agent_id` + `payload.agent_id` + metadata/agent fields) to capability matrix and source-usage mapping, and updated throughput `agents_active` metric to use the same normalized runtime identity filter so bootstrap pages stop defaulting to `runtime discovery pending` in mixed integrations.
- 2026-04-09: Fixed field-reported regressions from production adoption: `/v1/adoption/kpi` no longer references non-existent `wiki_page_versions.project_id` (now uses `wiki_page_versions -> wiki_pages.project_id` join), and bootstrap page insert now rewrites internal wiki links when `policy_space_fallback` reroutes slugs across spaces (prevents broken `/wiki/operations/...` links after fallback to `logistics`); added self-host integration regression coverage in `scripts/integration_legacy_sync_queue_processing.py`.
- 2026-04-09: Completed `Release trust (P0)` hardening for OSS publish reliability: added strict pre-publish registry collision gate (`prepublish-version-guard` + `--require-version-absent`), strengthened post-publish registry trust checks (`--require-latest-match`), introduced reusable install smoke verifiers (`scripts/check_python_package_install_smoke.py`, `scripts/check_npm_package_install_smoke.mjs`) wired into both artifact and registry install matrix jobs, added one-command multi-package version bump utility (`scripts/bump_release_version.py`), and upgraded RC dress rehearsal to assert exact installed versions + CLI availability.
- 2026-04-09: Delivered follow-up production DX closure for roadmap items `3/4/5`: added `GET /v1/enterprise/readiness` (auth/rbac/tenancy posture + enterprise table checks + scoped counters), shipped one-shot connector onboarding endpoint `POST /v1/adoption/import-connectors/bootstrap` (`resolve -> upsert source -> optional queue/processor diagnostics`), wired Python/TypeScript SDK helpers (`get_enterprise_readiness` / `getEnterpriseReadiness`, `bootstrap_adoption_import_connector` / `bootstrapAdoptionImportConnector`), extended `synapse-cli adoption` with `connect-source` + `enterprise-readiness`, and upgraded Operations UI migration mode to use connector bootstrap path with an enterprise readiness panel.
- 2026-04-09: Completed remaining `v0.1.5` adoption-DX closure items: `POST /v1/adoption/sync-presets/execute` now returns a unified explainability envelope (`reason_buckets`, `pipeline_gap`, primary blocker summary) plus embedded `pipeline_visibility` and `rejection_diagnostics`; Operations UI gained quick actions (`View pipeline`, `View rejections`, refresh controls) with a new rejection diagnostics panel; updated self-host + adoption playbooks for the new CLI-first operator loop.
- 2026-04-09: Started `v0.1.5 Production Adoption DX`: extended `synapse-cli adoption` with one-command `sync-preset` and diagnostics commands (`pipeline`, `rejections`), updated CLI docs/README examples, and added dedicated offline CI smoke coverage (`scripts/check_synapse_cli_adoption_ops.py`) wired into `scripts/ci_checks.sh`.
- 2026-04-09: Added no-code adoption operator commands to `synapse-cli`: new `adoption` group now supports `cursor-health`, `project-reset` (scoped + optional orphan draft page cascade), `list-drafts`, and `bulk-review-drafts` with safe dry-run defaults and advanced filters (category/source/connector/assertion/tier/confidence/risk); updated Python SDK README with concrete command recipes.
- 2026-04-09: Added explicit worker regression coverage for `postgres_sql` polling placeholder safety: `test_collect_records_binds_cursor_with_existing_named_params` now verifies SQL importer binds `cursor=None` alongside existing named params (e.g. `project_id`) so queries with `%(cursor)s` never execute as raw SQL and fail with `syntax error at or near "%"`.
- 2026-04-09: Added adoption recovery controls to SDKs (Python/TypeScript): exposed project-scope reset (`run_adoption_project_reset` / `runAdoptionProjectReset`) with scoped cleanup + orphan-draft cascade toggle, added cursor health diagnostics (`get_adoption_sync_cursor_health` / `getAdoptionSyncCursorHealth`), and extended sync preset APIs with processor safeguards (`sync_processor_lookback_minutes`, `fail_on_sync_processor_unavailable`); updated SDK READMEs and CI smoke assertions accordingly.
- 2026-04-09: Improved SDK moderation ergonomics for adoption operators: added project-scoped draft inbox helper in both SDKs (`list_wiki_drafts` / `listWikiDrafts`), introduced typed bulk-review filter contracts (`WikiDraftBulkReviewFilter` in Python and TS), documented safe bulk moderation recipes in SDK READMEs, and extended CI smoke/contracts to assert `/v1/wiki/drafts` + `/v1/wiki/drafts/bulk-review` usage across Python/TypeScript clients.
- 2026-04-09: Hardened adoption visibility + SDK ergonomics: `GET /v1/adoption/pipeline/visibility` now reports explicit `page_channels` and includes windowed published-page fallback for scoped filters (avoids false `pages=0` when starter/bootstrap pages are already published); added SDK parity methods in Python/TypeScript for `POST /v1/wiki/drafts/bulk-review`, `POST /v1/adoption/safe-mode/enable`, `GET /v1/adoption/pipeline/visibility`, and `GET /v1/adoption/rejections/diagnostics`, plus sync preset option `auto_apply_safe_mode_on_critical`.
- 2026-04-09: Added runtime-inferred Agent Capability fallback for bootstrap/orgchart paths: when `agent_directory_profiles` is absent or empty, Synapse now derives agent nodes/capabilities from runtime `events` + `synapse_tasks` signals to avoid empty `n/a` capability pages on first integration.
- 2026-04-09: Added high-signal auto-publish gate in `/v1/wiki/auto-publish/run`: drafts now require durable-profile match (assertion class/page type/category keyword) before policy-based auto-approval; diagnostics now expose `high_signal_gate` rationale per item.
- 2026-04-09: Added adoption safe-mode control surface: new endpoint `POST /v1/adoption/safe-mode/enable` (dry-run/apply with snapshot) and optional auto-trigger from `POST /v1/adoption/sync-presets/execute` via `auto_apply_safe_mode_on_critical` when critical sync diagnostics are detected.
- 2026-04-08: Completed `v0.1.3` adoption hardening release pack: shipped setup wizard v2 (`connect -> curated preview -> first publish`), new curated dry-run explain API (`POST /v1/backfill/curated-explain`), connector resolve endpoint with field overrides + validation hints (`POST /v1/adoption/import-connectors/resolve`), policy calibration quick loop (`GET/POST /v1/adoption/policy-calibration/quick-loop*`) with rollback-safe apply, onboarding KPI endpoint (`GET /v1/adoption/kpi`), self-host consistency gate (`GET /v1/adoption/selfhost/consistency`), and docs polish (`adoption-connector-cookbook`, `operator-first-24h`).
- 2026-04-06: Added `Real-World Adoption Backlog` from production integration feedback with explicit `P0/P1/P2` priorities: split knowledge/event ingest lanes, bootstrap import profile, reject diagnostics API, scoped project reset API, and self-host core wiki defaults; added exit criteria and execution order.
- 2026-04-06: Completed Agent Worklog Intelligence UI closure in core Operations route: added project-level worklog policy controls (timezone, local schedule, min activity score, idle-day mode, realtime trigger + lookback), `Sync worklogs now` action, and integrated live AI orgchart view (teams, handoffs, profile deep-links) backed by `GET /v1/agents/orgchart`.
- 2026-04-06: Started Agent Worklog Intelligence TODO track (5 items): upgraded worklog sync payload with timezone/trigger/noise-gating controls, added richer daily report composition (`Done/Impact/Blockers/Escalations` + authored-page highlights), introduced graph-ready orgchart API (`GET /v1/agents/orgchart`), and extended worker scheduler with daily-batch schedule gating + realtime session/task-close trigger mode.
- 2026-04-06: Completed self-hosted daily agent reporting automation: added worker job `agent_worklog_scheduler` (enabled by default) that discovers projects from `agent_directory_profiles` and calls `/v1/agents/worklogs/sync` on schedule; wired env/compose defaults (`SYNAPSE_WORKER_AGENT_WORKLOGS_*`), published runbook/docs updates, and added worker unit coverage for job wiring + scheduler helper behavior.
- 2026-04-06: Completed history UX upgrade for core wiki: `Recent versions` in right rail now deep-links directly into history drawer on selected version, and history drawer now renders colorized inline markdown diff (context/add/remove rows) for faster human review.
- 2026-04-06: Added core `Page history` drawer (Confluence-like): version selectors, unified markdown diff preview (`+/-` counters), and route-aware rollback controls (rollback CTA only in `/operations`, wiki route shows explicit handoff).
- 2026-04-06: Completed Confluence-like wiki navigation polish in core right rail: added context-first `Related pages` (same space quick-open) and `Recent versions` (author/date/change summary) blocks for `/wiki`, improving page exploration without opening operations tooling.
- 2026-04-06: Hardened web regression coverage for route split UX: Playwright core tests now assert `/wiki` keeps Drafts clean and right-rail operations controls are gated behind `/operations`, while Gatekeeper reason-code detail remains visible in core Draft detail.
- 2026-04-06: Completed right-rail route split in core wiki shell: `/wiki` now shows context-only right rail (page details + sections + open drafts + handoff to operations), while review/governance/policy editing controls are rendered only on `/operations`.
- 2026-04-06: Completed wiki-first IA simplification pass in core left rail: detailed lifecycle telemetry/remediation controls are now operations-only (`/operations`), while `/wiki` keeps a compact lifecycle summary card with explicit handoff (`Open ops diagnostics`) for deeper triage.
- 2026-04-06: Completed canonical shell extraction follow-up: right rail is now served by dedicated `CoreWikiRightRail` component, keeping `App.tsx` slimmer while preserving page details + governance context behavior.
- 2026-04-06: Completed compile-sink retirement in `App.tsx`: removed temporary `__legacyBranchRemovalCompileSink`, deleted remaining dead callbacks/state/helpers from non-canonical legacy moderation branch, and kept build + core e2e green.
- 2026-04-06: Completed another `App.tsx` dead-code reduction pass: removed unused triage-priority/retrieval-scoring helpers and core-only inactive derived flags/metrics (`showCore*`, queue/triage quick metrics, intent summary) and trimmed compile-sink references; build + core e2e stayed green.
- 2026-04-06: Removed dead retrieval-diagnostics legacy block from `App.tsx` (`runRetrievalExplain`, retrieval explain state/types, and sink references), further reducing non-canonical complexity without changing core Wiki/Drafts behavior.
- 2026-04-06: Removed another dead legacy cluster from `apps/web/src/App.tsx` (page aliases/comments/watchers/owners/uploads callbacks + related state/types + stale refresh/effect wiring) and trimmed compile-sink accordingly, keeping core wiki/drafts behavior intact.
- 2026-04-06: Continued wiki-first UX polish: moved right-rail heavy controls into collapsed accordions (`Review workflow`, `Space governance`) so default Wiki viewport stays page-first and less “control-center” on first open; kept governance actions available on demand.
- 2026-04-06: Continued legacy cleanup hardening in `App.tsx`: removed stale compile-sink references to deleted legacy symbols and kept strict build green while deeper dead-code extraction remains in progress.
- 2026-04-06: Added canonical core Draft detail pane inside `CoreDraftTab` (Inbox + Detail layout), wired mock API draft/detail/conflict endpoints for realistic gatekeeper payloads, and added Playwright assertion for Draft detail reason-code rendering (`reason override_skip_event|routing_policy_hard_block`).
- 2026-04-06: Removed legacy advanced render branch blocks from `App.tsx` and kept build green with a temporary strict-mode compile sink while dead state/helpers are being cleaned incrementally.
- 2026-04-06: Completed canonical shell extraction step by wiring `CoreWikiMain` into `App.tsx`, preserving page breadcrumbs/create/refresh/edit actions and keeping `/wiki` + `/operations` behavior parity.
- 2026-04-06: Started legacy branch retirement: disabled non-canonical advanced workspace panels via runtime gate so core users always follow one page-first Wiki/Drafts/Tasks path.
- 2026-04-06: Added operations runbook parity guardrail (`scripts/check_operations_runbook_parity.py`) and wired it into `scripts/ci_checks.sh` to enforce Utility Gate v2.1 control coverage in docs.
- 2026-04-05: Continued canonical shell refactor: extracted draft-tab main block into `components/core/CoreDraftTab.tsx` and wired confluence main switch to use the component without changing operations migration behavior.
- 2026-04-05: Advanced canonical shell extraction pass: moved core confluence top navigation into `components/core/CoreWorkspaceTopBar.tsx` and left rail wrapper into `components/core/CoreWorkspaceLeftRail.tsx` (slot-based lifecycle/tree), keeping route-split behavior and smoke e2e green.
- 2026-04-05: Completed Utility Gate v2.1 UX + explainability pass: added explicit web controls for `backfill_llm_classifier_mode`/confidence/ambiguous-only/model override in operations workflow, extended `GET /v1/wiki/drafts/{draft_id}` with normalized `gatekeeper` summary (`tier`, `score`, LLM reason-code, routing hard-block flags), and surfaced the new Gatekeeper Signal card in Draft detail UI without exposing raw feature payloads.
- 2026-04-05: Completed visual-gallery docs pass: added wiki UI visual gallery guide (`docs/wiki-ui-visual-gallery.md`) sourced from CI snapshot artifacts and linked it from README + self-hosted deployment guide.
- 2026-04-05: Completed visual snapshot CI pass for wiki-first shell: added Playwright visual capture spec (`apps/web/e2e/wiki-visual.spec.ts`) for `/wiki` and `/operations`, added dedicated `web-visual-snapshots` CI job, and published snapshot artifacts from CI for fast UI regression inspection.
- 2026-04-05: Completed self-hosted route-split runbook alignment: updated deployment guide with explicit `/wiki` and `/operations` validation flow and expected behavior for clean Drafts vs operations tooling.
- 2026-04-05: Completed route-level onboarding docs/examples pass: added explicit `/wiki` and `/operations` URL examples to README quickstart and published dedicated operations route runbook links in onboarding docs/tutorial index.
- 2026-04-05: Completed core left-rail simplification for user-friendly default: lifecycle panel now uses progressive disclosure (`Show details`) with compact summary first, reducing first-screen control density while keeping diagnostics/actions available on demand.
- 2026-04-05: Completed route/UX hardening track from wiki-first cleanup queue: simplified core header by removing duplicate KPI strip, added dedicated operations runbook (`docs/operations-route-runbook.md`) and linked it from onboarding docs, and added Playwright smoke coverage for `/wiki` vs `/operations` split (Drafts stays inbox/detail, migration tools stay on operations route).
- 2026-04-05: Completed core IA cleanup for wiki-first usability: moved reviewer/notifications controls into a right-side `Settings` drawer (removed from default core viewport), introduced dedicated `/operations` route for migration/gatekeeper workflows, and kept `Drafts` route focused on inbox + detail by default.
- 2026-04-05: Core wiki UX simplification pass (user-friendly default): collapsed workspace configuration into optional `Workspace settings`, reduced always-on diagnostics noise by default-collapsing lifecycle details behind `Show details`, and moved draft queue analytics behind explicit `Show advanced draft ops` toggle so primary experience stays page-first.
- 2026-04-05: Completed Utility Gate v2.1 core implementation: added routing-policy controls for ambiguous backfill classification (`backfill_llm_classifier_mode=off|assist|enforce`, confidence threshold, ambiguous-only flag, optional model override), integrated deterministic fallback behavior in worker suppression path, exposed structured LLM reason-codes in suppression metadata (`llm_mode`, `llm_reason_code`, `llm_applied`, status/provider/model/confidence), wired project-level routing policy into backfill extraction, and added regression tests for assist/enforce override semantics.
- 2026-04-05: Completed Existing-memory bridge ergonomics execution item: added reusable API contracts `GET /v1/legacy-import/mapper-templates` and `GET /v1/legacy-import/sync-contracts` (profile/sync-mode aware template patches + cron/CDC runner semantics), shipped Python/TypeScript SDK parity helpers, added contract tests, extended compat-matrix smoke checks, and updated adoption/API/SDK docs with no-custom-importer flow.
- 2026-04-05: Completed Adoption-first backfill preset service pass: added API `GET /v1/wiki/drafts/bootstrap-approve/recommendation` with project-aware migration defaults (trusted sources, queue pressure, backfill quality counters, safety hints), wired core wiki UI to consume server recommendations (with diagnostics badges/notes), added SDK helpers (`get_bootstrap_migration_recommendation`, `getBootstrapMigrationRecommendation`), and updated compat-matrix + docs.
- 2026-04-05: Started Existing-memory bridge ergonomics delivery: added native Python/TypeScript SDK legacy-sync adapters for `/v1/legacy-import/*` (`list profiles/sources`, `upsert source`, `queue sync run`, `list runs`), added SDK README adoption examples, and extended compat-matrix smoke checks to enforce helper contract parity.
- 2026-04-05: Completed Utility Gate v2 execution queue item: strengthened backfill pre-enqueue suppression in worker (`event-like` detection no longer depends on `category_hint == general`), added structured suppression reasons (`blocked_source_id`, `event_like_low_signal`, `event_transport_low_signal`), and shipped backfill batch explainability counters (`dropped_event_like`, `kept_durable`, `trusted_bypass`) via migration `055_backfill_batch_decision_counters.sql` and `GET /v1/backfill/batches/{batch_id}` response.
- 2026-04-05: Reprioritized execution queue away from telemetry-first tasks to ingestion quality + adoption ergonomics (`Utility Gate v2`, trusted-source migration mode, existing-memory bridge templates) per product feedback.
- 2026-04-05: Completed Utility Gate backfill hardening pass: `_should_skip_backfill_claim` now detects event-stream payloads with snake_case token expansion, numeric/kv/order-shape heuristics, and source-transport noise checks independent of `category_hint == general`; added regression coverage for `operations`-inferred event payload suppression while preserving explicit access-policy records.
- 2026-04-05: Completed execution queue item “SDK lifecycle helper contract checks in matrix CI”: extended `compat-matrix` with Python/Node smoke tests that execute lifecycle helper methods (`get stats`, `get telemetry`, `snapshot telemetry`) against dummy transports and assert normalized payload contracts.
- 2026-04-05: Completed execution queue item “TS/py SDK lifecycle telemetry client helpers”: added Python methods (`get_wiki_lifecycle_stats`, `get_wiki_lifecycle_telemetry`, `snapshot_wiki_lifecycle_telemetry`) and TypeScript parity (`getWikiLifecycleStats`, `getWikiLifecycleTelemetry`, `snapshotWikiLifecycleTelemetry`) with README usage examples.
- 2026-04-05: Completed execution queue item “CI ephemeral Postgres lifecycle telemetry integration”: added mandatory `lifecycle-telemetry-integration` GitHub Actions job in `ci.yml` with Postgres service and end-to-end execution of `scripts/integration_lifecycle_telemetry.py`.
- 2026-04-05: Completed execution queue item “dashboard action-key telemetry drill-down”: added API `action_key` filter support for `GET /v1/wiki/lifecycle/telemetry`, wired web URL/state param `wiki_lifecycle_action`, and added clickable action-mix badges with filtered drill-down panel plus Playwright coverage.
- 2026-04-05: Completed execution queue item “lifecycle telemetry API integration smoke on real Postgres schema”: added `scripts/integration_lifecycle_telemetry.py` (migrations + API boot + monotonic snapshot checks + summary assertions), wired script into compile checks and optional CI gate via `SYNAPSE_RUN_DB_INTEGRATION=1`.
- 2026-04-05: Completed execution queue item “telemetry-driven operator thresholds”: extended operator runbook with action-mix threshold rules (`apply_rate`, `review_open_drafts` friction, stale-window tuning via `lower_threshold`, bootstrap guidance for `create_page`).
- 2026-04-05: Completed execution queue item “server-side lifecycle telemetry persistence”: added migration `054_wiki_lifecycle_action_telemetry.sql` and API endpoints `POST /v1/wiki/lifecycle/telemetry/snapshot` + `GET /v1/wiki/lifecycle/telemetry` with monotonic session snapshots, delta aggregation, and daily project summaries.
- 2026-04-05: Completed execution queue item “CLI lifecycle telemetry command”: added `synapse-cli wiki-lifecycle telemetry --days ... --top ...` for operator-friendly action-mix summary and trend output.
- 2026-04-05: Completed execution queue item “UI mini-trend view for action mix”: core/wiki lifecycle diagnostics now show `Action mix (7d)` with top actions and daily `applied/shown` trend chips; web client syncs local empty-scope counters to API via debounced telemetry snapshots.
- 2026-04-05: Completed execution queue item “lifecycle empty-scope telemetry split by action type”: core wiki now tracks shown/applied counts per empty-scope action (`create_page`, `review_open_drafts`, `lower_threshold`) in lifecycle advisor metrics and surfaces summary badges in the core header.
- 2026-04-05: Completed execution queue item “lifecycle fixture scenarios in e2e mock”: added deterministic mock lifecycle fixtures for `fixture_no_published` and `fixture_all_open_drafts`, plus Playwright coverage for both empty-scope paths in core diagnostics.
- 2026-04-05: Completed execution queue item “operator decision rule for empty-scope actions”: extended governance deep-link runbook with explicit rule set for when to use `lower_threshold`, `review_open_drafts`, and `create_page`.
- 2026-04-05: Completed execution queue item “scope quick-link copy action”: added one-click `Copy scope link` control in core header breadcrumb (`core-copy-scope-link`) that shares current `project/wiki_space/wiki_page/core_tab` context and keeps wiki-first deep-link behavior.
- 2026-04-05: Completed execution queue item “lifecycle empty-scope suggested actions map”: API `GET /v1/wiki/lifecycle/stats` now returns actionable `meta.empty_scope.suggested_actions` with deep-link hints (`create_page`, `review_open_drafts`, `lower_threshold`), mirrored in web UI cards (core + wiki diagnostics) and e2e mock parity payloads.
- 2026-04-05: Completed execution queue item “CLI lifecycle empty-scope text rendering”: `synapse-cli wiki-lifecycle stale` now prints `empty_scope` reason/details and suggested actions in non-JSON mode, matching API semantics for operator triage.
- 2026-04-05: Completed execution queue item “scope breadcrumb in core header”: added `project / space / page` scope breadcrumb (`#core-scope-breadcrumb`) plus one-click `Clear space scope` action that removes `wiki_space` from URL while preserving current page context.
- 2026-04-05: Completed execution queue item “lifecycle empty-scope explanation”: extended `GET /v1/wiki/lifecycle/stats` with reasoned empty-scope diagnostics (`no_published|all_open_drafts|below_threshold`) and supporting counts; surfaced explanation cards in core lifecycle diagnostics and wiki diagnostics panel.
- 2026-04-05: Completed execution queue item “CLI lifecycle preset parity”: added `synapse-cli wiki-lifecycle stale --preset <stale_21|critical_45|custom>` aligned with web lifecycle query presets, with preset-aware threshold resolution and output metadata.
- 2026-04-05: Completed execution queue item “lifecycle query presets + URL persistence”: added preset controls (`Stale >=21d`, `Critical >=45d`, `Custom`) in core lifecycle diagnostics, wired stale/critical thresholds to API requests, and persisted settings via URL params (`wiki_lifecycle_preset`, `wiki_lifecycle_stale_days`, `wiki_lifecycle_critical_days`) across tab switches.
- 2026-04-05: Completed execution queue item “lifecycle debug meta”: extended `GET /v1/wiki/lifecycle/stats` with debug metadata (`searched_scope`, `filters_applied`) and surfaced scope/filter debug lines in wiki diagnostics UI.
- 2026-04-05: Completed execution queue item “CLI lifecycle space parity”: added `synapse-cli wiki-lifecycle stale --space <key>` support with API `space_key` forwarding and scoped deep-link generation (`wiki_space` included in drafts/policy links).
- 2026-04-05: Completed execution queue item “lifecycle `wiki_space` deep-link persistence”: lifecycle space chips now set workspace `wiki_space` scope, URL keeps scope while switching `Wiki/Drafts/Tasks`, and Playwright coverage now asserts `wiki_space` retention across tab switches.
- 2026-04-05: Completed execution queue item “server-side lifecycle scope filter”: added optional `space_key` support to `GET /v1/wiki/lifecycle/stats` with scoped SQL filtering in API, web client query wiring, and mock API parity for e2e/high-cardinality workspace behavior.
- 2026-04-05: Completed execution queue item “stale-to-resolved operator drill pack”: extended governance deep-link runbook with step-by-step URL presets and SLA timers for stale-page remediation flow.
- 2026-04-05: Completed execution queue item “per-space lifecycle triage chips”: added space-scoped stale-page filter chips (`All` + per-space) in core left lifecycle card and wiki diagnostics panel, wired filtering to stale list rendering, and added Playwright coverage for chip-based filtering behavior.
- 2026-04-05: Completed execution queue item “MCP smoke tool registration contract”: strengthened retrieval parity smoke script to assert `get_space_policy_adoption_summary` MCP tool registration/call fragments and runtime payload contract (normalization + cache path), and added unit smoke test for MCP server tool registry wiring (`test_mcp_runtime_tool_registry.py`).
- 2026-04-05: Completed execution queue item “incident response runbook extension”: expanded operator deep-link runbook with actionable incident playbooks for policy rollback and reviewer-assignment SLA breach handling (entry URLs, steps, and SLA targets).
- 2026-04-05: Completed execution queue item “core shell lifecycle discoverability parity”: added compact lifecycle diagnostics card to Confluence core left rail (`#core-left-lifecycle`) with stale/critical counters, top stale page list, and one-click page/policy drill-down actions; lifecycle refresh is now available directly from core left rail.
- 2026-04-05: Completed execution queue item “MCP adoption-summary test hardening”: extended MCP runtime coverage for space-policy adoption summary with unavailable-audit-table behavior and mixed-metadata/unknown-actor summary handling (`services/worker/tests/test_mcp_runtime_space_policy_adoption_summary.py`).
- 2026-04-05: Completed execution queue item “operator governance deep-link runbook”: published short operator guide with canonical `core_tab` + `wiki_focus` URL patterns, right-rail quick actions, and troubleshooting (`docs/operator-governance-deeplinks.md`), linked from tutorials and getting-started docs.
- 2026-04-05: Completed execution queue item “web governance summary API wiring”: `Policy timeline` widgets now use API-backed adoption summary with local audit fallback, and refresh/save flows reload summary consistently (`Refresh`, `saveSpacePolicy`, lifecycle policy drill-down).
- 2026-04-05: Completed execution queue item “MCP parity for policy adoption summary”: added MCP tool `get_space_policy_adoption_summary` backed by runtime/store support, normalized `space_key` handling, cached runtime responses, and docs update in `services/mcp/README.md`.
- 2026-04-05: Completed execution queue item “web e2e smoke for lifecycle drill-down + governance quick actions”: added Playwright coverage for deep-link lifecycle focus (`policy_timeline`, `review_assignments`, `draft_inbox`) and quick actions (`Assign reviewer`, `Create review task`), plus mock API support for lifecycle stats, space policy endpoints, adoption-summary, and review-assignment CRUD.
- 2026-04-05: Completed execution queue item “CLI helper for stale lifecycle triage”: added `synapse-cli wiki-lifecycle` command group with `stale` (fetch stale diagnostics + deep-link hints), `open-drafts`, and `open-policy` URL generators for self-hosted operator workflows; documented commands in Python SDK README.
- 2026-04-05: Completed execution queue item “Space policy adoption summary API”: added `GET /v1/wiki/spaces/{space_key}/policy/adoption-summary?project_id=...&limit=...` with aggregate metrics (`top_actor`, cadence, checklist usage, transitions, first/last update timestamps) and availability metadata for dashboard/MCP consumers; documented endpoint in API README.
- 2026-04-05: Completed execution queue item “Wiki governance quick actions from diagnostics”: stale rows now include one-click actions for `Assign reviewer`, `Create review task`, and `Open policy edit` in addition to page/timeline/draft drill-down; added anchored navigation targets (`wiki-governance-panel`, `wiki-review-assignments`) and URL deep-link support via `core_tab` + `wiki_focus` query params.
- 2026-04-05: Completed execution queue item “Lifecycle diagnostics drill-down links”: stale-page rows in `Wiki lifecycle diagnostics` now provide direct actions (`Open page`, `Policy timeline`, `Draft inbox`) with context-preserving navigation (auto-select page/space, tab switch) and anchored scrolling to target sections (`wiki-policy-timeline`, `wiki-draft-inbox`) for faster stale-page triage.
- 2026-04-05: Completed execution queue item “Space policy reviewer-adoption summary widgets”: Governance `Policy timeline` panel now includes analytics cards for `who updates policy` (top actor + actor count), `update cadence` (avg interval + total updates), and `checklist usage` (`none|ops_standard|policy_strict` distribution + transition count) computed from policy audit history for faster governance triage.
- 2026-04-05: Completed execution queue item “SDK+CLI helper for space publish checklist presets”: added Python SDK APIs (`get_wiki_space_policy`, `list_wiki_space_policy_audit`, `upsert_wiki_space_policy`, `get_wiki_space_publish_checklist_preset`, `set_wiki_space_publish_checklist_preset`) and TypeScript parity (`getWikiSpacePolicy`, `listWikiSpacePolicyAudit`, `upsertWikiSpacePolicy`, `getWikiSpacePublishChecklistPreset`, `setWikiSpacePublishChecklistPreset`), plus new `synapse-cli wiki-space-policy` command group (`get`, `audit`, `set`, `set-checklist-preset`) for no-code policy operations; updated SDK READMEs and regenerated TS API reference.
- 2026-04-05: Completed lifecycle stats exposure in web diagnostics panel: integrated `GET /v1/wiki/lifecycle/stats` into wiki tree diagnostics card with status counters (`draft/reviewed/published/archived`, stale warning/critical), stale candidate list with one-click page jump, project-scoped deep-link context, and manual refresh action.
- 2026-04-05: Completed `space policy audit timeline` track: added migration `053_wiki_space_policy_audit.sql`, shipped API endpoint `GET /v1/wiki/spaces/{space_key}/policy/audit`, recorded policy change audits from `PUT /v1/wiki/spaces/{space_key}/policy` (before/after snapshot + changed fields + actor + timestamp), and exposed timeline in Governance panel with changed-field badges and checklist preset transition hints.
- 2026-04-05: Completed lifecycle advisor telemetry baseline: added project-scoped lifecycle metrics storage (`suggestion_shown`, `suggestion_applied`, stale resolve durations) with automatic tracking in wiki page flow, wired lifecycle-action apply counters, and surfaced core badges (`Lifecycle shown/applied`, `Stale resolve avg`) for operator feedback loops.
- 2026-04-05: Completed wiki lifecycle API stats endpoint for ops diagnostics: added `GET /v1/wiki/lifecycle/stats` with configurable stale/critical thresholds, lifecycle status counters (`draft/reviewed/published/archived`, open-draft coverage), and stale candidate payloads (age/activity/severity) for dashboard and MCP troubleshooting use-cases; documented endpoint in API README.
- 2026-04-05: Completed next queue item “space-level publish checklist presets”: added per-space publish checklist policy (`none|ops_standard|policy_strict`) persisted in space-policy metadata, Governance UI selector/description, and publish-modal checklist enforcement with acknowledgment tracking before publish.
- 2026-04-05: Completed lifecycle advisor execution queue items #2/#3 in core wiki UX: added automatic stale-page detection and stale badges in tree/home, introduced page-level lifecycle advisor cards with actionable suggestions (`Open drafts`, `Promote to reviewed`, `Open publish`, `Archive`, `Restore`) driven by activity age + conflict signals + review assignment state, and wired quick lifecycle actions into existing status transition/update flows.
- 2026-04-05: Completed wiki quality UX item (moderation explainability): replaced raw moderation JSON timeline with human-readable action cards (`Approved/Rejected`, actor, decision/status transitions, “why” text from reason/note/result) while preserving payload/result trace payloads for audit-level debugging.
- 2026-04-05: Advanced self-hosted adoption UX polish in core wiki flow: reduced first-view filter clutter (progressive `Open filters` UX in `Wiki Tree`), added guided migration nudge in `Drafts` with one-click recommended bootstrap actions (`Preview recommended` / `Apply recommended`), introduced recommended batch preset resolver from connected legacy sources, and auto-prefill of trusted source systems for first migration runs.
- 2026-04-05: Completed release telemetry polish: `release-packages` now auto-creates/updates draft GitHub Releases from release evidence artifacts (`softprops/action-gh-release@v2`), composing body from `docs/releases/vX.Y.Z.md` (when present) plus `release-evidence.md`; release docs/checklist updated accordingly.
- 2026-04-05: Completed M15 #1 (registry/trusted publishing doc state closure): removed residual “not published yet” ambiguity from release surface, strengthened publish-hygiene CI to assert trusted publishing/provenance jobs and install-matrix verification in `.github/workflows/release-packages.yml`, and validated full offline CI pipeline (`SYNAPSE_SKIP_WEB_E2E=1 ./scripts/ci_checks.sh`) green.
- 2026-04-05: Hardened CI reliability: fixed transient broken-`pip` failures in `scripts/ci_checks.sh` by recreating isolated venv deterministically and bootstrapping `python -m pip` safely before SDK smoke stages.
- 2026-04-05: Improved Gatekeeper routing quality for repeated short operational signals: multi-source insufficiency no longer demotes repeated observations (`repeated_count >= 1`) to `operational_memory`; added regression test (`test_gatekeeper_repeated_short_operational_signal_moves_out_of_l1`) and restored evaluator metrics to 1.0 on `eval/gatekeeper_cases.json`.
- 2026-04-05: Completed Agent Directory Phase 3 item #10 (risk-tiered policy enforcement): added agent publish guardrail APIs (`GET/PUT /v1/agents/publish-policy`) with per-agent `default_mode` + `by_page_type` overrides, enforced `human_required` mode in wiki page create/update publish paths (returns `agent_publish_policy_requires_review`), and added Python/TypeScript SDK helpers for policy management.
- 2026-04-05: Completed Agent Directory Phase 3 item #9 (agent-level provenance + one-click rollback): added provenance activity feed API (`GET /v1/agents/provenance`) with rollback-readiness metadata, shipped one-click rollback endpoint (`POST /v1/agents/provenance/{activity_id}/rollback`) that safely reuses page-version rollback flow, added RBAC guard (`agent_provenance_rollback`), and exposed Python/TypeScript SDK methods (`list_agent_provenance`/`rollback_agent_activity`, TS parity).
- 2026-04-04: Completed Process Playbook item #7 (ticket/outcome linkage): auto-publish runner now enriches each draft with `ticket_outcome_signal` (`ticket_ids`, `outcome`, positive/negative flags), applies outcome-aware `effective_score` and adaptive source-diversity threshold (`effective_min_sources`), prioritizes resolved-ticket evidence in scan order, and exposes these fields in API results for operator explainability.
- 2026-04-04: Completed Agent Directory MVP Phase 1 (items #1-#4): added migration `051_agent_directory.sql`, shipped Agent Directory APIs (`GET /v1/agents`, `POST /v1/agents/register`), implemented automatic wiki scaffold sync (`agents/index` orgchart + per-agent `overview/runbooks/daily-reports/created-pages/incidents/changelog` pages), and wired attach-time profile registration in Python/TypeScript SDK facades (`attach(...register_agent_directory...)`).
- 2026-04-04: Completed Agent Directory Phase 2 item #5 (daily worklog synthesis): added migration `052_agent_daily_worklogs.sql`, shipped `POST /v1/agents/worklogs/sync`, generated per-agent daily summaries from runtime/task activity (`events`, sessions, task touches/completions), persisted worklog snapshots, and auto-refreshed `agents/*/daily-reports` wiki pages; added SDK helpers (`sync_agent_worklogs` / `syncAgentWorklogs`) and rendering tests.
- 2026-04-04: Completed Agent Directory Phase 2 item #6 (capability matrix): shipped capability APIs (`GET /v1/agents/capability-matrix`, `POST /v1/agents/capability-matrix/sync`), added confidence scoring from rolling worklog evidence (`tasks_done/touched`, runtime event volume), included last-success timestamps + evidence links, and published wiki page `agents/capability-matrix` through the sync pipeline with SDK helpers (`get_agent_capability_matrix`, `sync_agent_capability_matrix`, TS parity).
- 2026-04-04: Completed Agent Directory Phase 2 item #7 (handoff map): added handoff graph APIs (`GET /v1/agents/handoffs`, `POST /v1/agents/handoffs/sync`) that read structured handoff contracts from agent profile metadata and publish `agents/handoffs` wiki page with `from -> to`, input/output contracts, and SLA visibility; added SDK helpers (`get_agent_handoffs`, `sync_agent_handoffs`, TS parity) and markdown rendering tests.
- 2026-04-04: Completed Agent Directory Phase 3 item #8 (agent scorecards): shipped scorecard APIs (`GET /v1/agents/scorecards`, `POST /v1/agents/scorecards/sync`) with rolling quality/reliability metrics from worklogs + task posture (quality score, reliability score, escalation rate, active/blocked load), and auto-published `agents/scorecards` wiki page; added Python/TS SDK helpers and renderer coverage.
- 2026-04-04: Completed Process Playbook item #9 (simulation safety check): `PUT /v1/wiki/pages/{slug}` publish path now enforces process simulation for configured page types (`routing_policy.process_simulation_require_for_page_types`) and blocks risky publish with `409 publish_blocked_by_process_simulation` unless explicit `confirm_high_risk_publish=true`; publish modal now supports high-risk acknowledgment checkbox and inline simulation review before publish.
- 2026-04-04: Completed Process Playbook item #6 (auto onboarding packs): shipped role-aware day-0 packs in MCP (`get_onboarding_pack`) and API (`GET /v1/wiki/onboarding-pack`) with structured sections (`critical_playbooks`, `escalation_rules`, `forbidden_actions`, `fresh_changes`) and freshness window controls.
- 2026-04-04: Extended Process Playbook simulation UX: wiki publish modal now includes `Run safety simulation` action wired to `/v1/wiki/process/simulate`, showing risk badges, suggested publish mode, changed-term/impact metrics, high-risk keyword hits, and top impacted pages before publish.
- 2026-04-04: Completed Process Playbook item #9 (phase-1 delivery): added pre-publish process safety simulation endpoint `POST /v1/wiki/process/simulate` that computes change-term diff, scans impacted process/policy/incident pages, reports queue/conflict pressure, assigns risk tier, suggests publish mode (`auto_publish|conditional|human_required`), and returns rollback hints.
- 2026-04-04: Completed Process Playbook item #8 (process instruction provenance): retrieval explain now carries claim-linked provenance (`claim_id`, `source_ids`, `ticket_ids`, `outcome`) end-to-end, context-injection snippets include provenance payloads, and web Retrieval Diagnostics surfaces “Why this step exists” cards for each statement and injected snippet.
- 2026-04-04: Completed Process Playbook item #6 (phase-1 delivery): MCP runtime now exposes `get_onboarding_pack` with role-aware day-0 sections (`critical_playbooks`, `escalation_rules`, `forbidden_actions`, `fresh_changes`) generated from published wiki statements and freshness window controls.
- 2026-04-04: Advanced Process Playbook provenance track (phase-1 delivery): retrieval SQL now carries latest claim evidence context (`claim_id`, `claim_metadata`, `claim_evidence`, `claim_observed_at`) and MCP/API retrieval explain responses now expose normalized `provenance` payloads (`source_ids`, `ticket_ids`, `outcome`) for each statement so operators can trace why a process step exists.
- 2026-04-04: Completed Process Playbook Intelligence item #4 (risk-tiered publish + rollback): auto-publish runner now classifies each pending draft into `low|medium|high` risk using configurable routing-policy keywords (`auto_publish_risk_keywords_high|medium`) and force-level guardrails (`auto_publish_force_human_required_levels`), automatically forcing high-risk legal/financial/security-like updates into `human_required`; rollout remains rollback-safe via existing wiki version rollback path and gatekeeper rollback workflows.
- 2026-04-04: Completed Process Playbook Intelligence item #5 (intent-aware context injection): added shared retrieval intent engine (`auto|general|process|policy|incident|preference`) with deterministic intent inference + explainability, intent-aware result reranking (`intent_alignment`, `intent_rank_score`), and runtime/API `context_injection.snippets` (top-k verified snippets) via new controls (`retrieval_intent`, `max_context_snippets`, env defaults `SYNAPSE_MCP_RETRIEVAL_INTENT_DEFAULT`, `SYNAPSE_MCP_CONTEXT_MAX_SNIPPETS`); added retrieval intent unit tests and kept MCP/API parity smoke green.
- 2026-04-04: Advanced Process Playbook Intelligence online capture: API now accepts `claim.metadata`, worker normalizes operator decision context for all incoming claims (`process_triplet`, `ticket_ids`, `outcome`) and stores it in `claims.metadata` (`operator_decision`, `linked_ticket_ids`, `resolution_outcome`); process markdown patches now render structured Trigger/Action/Outcome lines for process sections.
- 2026-04-04: Completed Process Playbook Intelligence implementation (phase-1): extended knowledge compiler with process-aware page taxonomy (`triggers/steps/exceptions/escalation/verification`), process signal detection and assertion class (`process`) in Gatekeeper routing, process-oriented backfill category inference, trigger→action→outcome triplet extraction for process claims, and worker unit tests for process classification/section routing.
- 2026-04-04: Extended wiki template layer for process onboarding in UI: added `Issue Playbook`, `Escalation Rule`, `Customer Exception`, and `Known Incident` page templates and bound create-flow `pageType` to selected template for cleaner process-page scaffolding.
- 2026-04-04: Completed M15.2 automation hardening: added pre-publish clean-room install matrix from built artifacts (`verify-artifact-install-matrix`, Linux + macOS), added post-publish release evidence bundle generator (`scripts/generate_release_evidence_bundle.py`) and workflow artifact (`release-evidence-pack`) to produce markdown/json evidence for release notes with registry verification and install-proof references.
- 2026-04-04: Completed M15.5 positioning refresh: aligned top-level docs with dual framing (Agentic Wiki interface + L2 Cognitive State Layer), added positioning consistency guard (`scripts/check_positioning_consistency.py`) and wired it into CI to prevent message drift.
- 2026-04-04: Completed M15.6 buyer-facing packaging: added ROI + rollout one-pager (`docs/buyer-roi-rollout.md`) and architecture diagram pack (`docs/architecture-diagram-pack.md`) including raw-RAG-vs-Synapse-L2 comparison and slide-ready core-loop/adoption/governance diagrams.
- 2026-04-04: Advanced M15.2 release hardening: added clean-room install matrix job in release workflow (`verify-install-matrix`, Linux + macOS) that performs real registry install/import checks for both Python and npm packages at the tagged release version after registry propagation succeeds.
- 2026-04-04: Completed M15.3 + M15.4 implementation: added deterministic Agentic Onboarding benchmark kit (`scripts/benchmark_agentic_onboarding.py`, `eval/agentic_onboarding_cases.json`, `docs/agentic-onboarding-benchmark.md`) with KPI cards (`first_useful_answer`, `first_approved_draft`, `first_policy_safe_publish`) and CI guardrail thresholds; added framework quickstart parity validator (`scripts/check_framework_quickstart_parity.py`) wired into CI to enforce 5-minute structure consistency across OpenClaw/LangGraph/LangChain/CrewAI docs.
- 2026-04-04: Completed M15 implementation (phase-1): added registry availability validator (`scripts/check_registry_package_availability.py`) and release workflow post-publish verification job (`verify-registry`), removed static “not published yet” wording from core onboarding docs in favor of registry-first installs + fallback editable mode, added LangGraph/LangChain/CrewAI 5-minute quickstarts, and introduced explicit L2 positioning doc (`docs/cognitive-state-layer.md`) linked from README.
- 2026-04-04: Added roadmap milestone `M15: Public Launch & Positioning` to operationalize GTM feedback: eliminate “not published yet” friction via registry-verified releases, make Agentic Onboarding a measurable primary narrative, enforce OpenClaw/LangGraph/LangChain/CrewAI onboarding parity, and refresh product framing to “Cognitive State Layer (L2)” with wiki as the governance interface.
- 2026-04-04: Added new roadmap track `Agent Directory & Operations Intelligence` with phased delivery (`MVP -> Scale -> Governance`): AI orgchart index, attach-time self-profile updates, standard agent folder scaffold, agent-authored page index, daily worklog synthesis, capability/handoff maps, agent scorecards, provenance+rollback, and risk-tiered publish guardrails.
- 2026-04-04: Added new roadmap track `Process Playbook Intelligence (Support Ops Focus)` to move Synapse from fact-only wiki toward process-aware operational documentation; queued operator decision capture, template-first playbook pages, process-quality gatekeeper routing, risk-tiered auto-publish with rollback, intent-aware context injection, auto onboarding packs, ticket/outcome linkage, provenance for process steps, and pre-publish process simulation checks.
- 2026-04-04: Completed sticky page toolbar in core wiki view (`History`, `Watch/Watching`, `Share`, `Drafts`, `Edit`, `More`) with real actions wired to existing page flows, added smooth jump-to-revisions anchor (`#wiki-context-revisions`), and reduced header action clutter to keep page view wiki-first.
- 2026-04-04: Completed User-Friendly Wiki UX 12-point track (`done`): finalized slash-first rich editor parity (undo/redo), added stronger revision diff preview in core wiki context, cleaned core-mode language (`Workspace`, `Your name`, `Sync`), shipped friendly roles modal (`Viewer/Editor/Approver/Admin`) plus docs (`docs/wiki-ux-roles-metrics.md`), and added UX funnel telemetry badges (TTFV, first publish time, click-depth) persisted per project in browser storage.
- 2026-04-04: Closed remaining Knowledge Compiler roadmap items: added claim `assertion_class` typing (`policy|preference|incident|event|fact`) in Gatekeeper features/claim metadata, enabled assertion-class-aware publish control via `routing_policy.publish_mode_by_assertion_class`, introduced retrieval feedback loop APIs (`POST /v1/mcp/retrieval/feedback`, `GET /v1/mcp/retrieval/feedback/stats`) with new migration `050_retrieval_feedback_loop.sql`, and wired auto-publish guardrails to block autonomous publish when recent claim-level retrieval feedback is strongly negative.
- 2026-04-04: Added Knowledge Compiler v1 hardening: worker now suppresses low-signal backfill event records before claim enqueue, Gatekeeper routing adds `source_id` deny checks plus durable knowledge-signal thresholds and payload key/value density detection, API routing-policy normalization includes new knobs, and new worker unit tests cover noisy snapshot demotion vs valid policy/preference retention (`services/worker/tests/test_wiki_engine_routing.py`).
- 2026-04-04: Hardened universal wiki-ingestion routing against raw operational streams: routing policy now supports deny rules by `category`, `source_system`, `source_type`, and `entity_key`, plus backfill-specific policy gating (`backfill_requires_policy_signal`) and event-blob shape detection, preventing `order_snapshot`/invoice/status stream style memories from dominating wiki pages.
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
- 2026-04-08: Completed Real-World Adoption Backlog `P0.1` ingestion lane split: added dedicated API lane `POST /v1/backfill/knowledge` (source-ownership domain `synapse_wiki`) while keeping `/v1/backfill/memory` as event lane, tagged backfill events/evidence with `ingest_lane`, made worker suppression + gatekeeper lane-aware (knowledge lane no longer inherits source transport hard-block defaults), and shipped SDK fallback-aware knowledge-lane transport support (Python/TypeScript) with regression tests.
- 2026-04-08: Completed Real-World Adoption Backlog `P0.3` reject diagnostics: added `GET /v1/adoption/rejections/diagnostics` with project/window aggregates (top reject reasons, blocked source patterns, sample rejects, and policy-tuning hints) to remove DB-forensics dependency during field onboarding.
- 2026-04-08: Completed Real-World Adoption Backlog `P0.4` admin project reset: added migration-backed audit table (`056_adoption_project_resets.sql`) and safe API `POST /v1/adoption/project-reset` with scope normalization, `dry_run=true` preview default, explicit `confirm_project_id` guard for destructive mode, idempotency support, and per-table deleted-row counters.
- 2026-04-08: Completed Real-World Adoption Backlog `P0.2` bootstrap profile: added one-click API `POST /v1/adoption/bootstrap-profile/apply` (`dry_run` preview + explicit confirm guard + idempotency) that applies initial-import gatekeeper soft-threshold profile, preserves noise filters, returns config diff/excerpts, and bundles trusted-source bootstrap recommendation diagnostics for immediate `preview -> approve` migration flow.
- 2026-04-08: Completed Real-World Adoption Backlog `P0.5` self-host core defaults: bundled `web` service into `infra/docker-compose.selfhost.yml` (loopback default port `4173`), added SPA-safe `apps/web/Dockerfile` + `nginx` fallback for `/wiki` routes, updated `.env.selfhost.example` + self-host runbook, and extended `scripts/check_selfhost_stack_defaults.py` to fail CI when web/core-route defaults regress.
- 2026-04-08: Completed Real-World Adoption Backlog `P1.2` pipeline visibility: added `GET /v1/adoption/pipeline/visibility` with stage counters (`accepted -> events -> claims -> drafts -> pages`), conversion ratios, queue posture, and bottleneck hints; wired Operations Migration Mode UI card with one-click refresh and stage badges.
- 2026-04-08: Completed Real-World Adoption Backlog `P1.5` predictable page listing/search: normalized wildcard query mode (`q=*|all`) for both `GET /v1/wiki/pages` and `GET /v1/wiki/pages/search`, added explicit `query_mode=all_pages` filter metadata, and removed ambiguous “empty result for wildcard” behavior.
- 2026-04-08: Completed Real-World Adoption Backlog `P1.1` built-in import connectors: added `GET /v1/adoption/import-connectors` catalog that exposes profile-native `postgres_sql` connectors (`ops_kb_items` / `memory_items`) with ready `config_patch` payloads, sync contracts, and declarative mapper metadata to avoid custom importer scripts.
- 2026-04-08: Completed Real-World Adoption Backlog `P1.3` noise-filter presets: introduced reusable adoption presets (`off`, `balanced`, `strict`, `order_snapshots`, `telemetry`, `raw_event_payloads`) with API discovery endpoint `GET /v1/adoption/noise-presets` and deterministic pre-ingest signal suppression heuristics for event-like payloads.
- 2026-04-08: Completed Real-World Adoption Backlog `P1.4` curated import mode: extended backfill contract with batch-level `curated` controls (`enabled`, `source_systems`, `namespaces`, `noise_preset`, `drop_event_like`), enabled balanced curated defaults for knowledge-lane imports, propagated curated settings through legacy-sync + SDKs, and returned per-batch filter diagnostics (`accepted_input`, `filtered_out`, reason breakdown).
- 2026-04-08: Completed Real-World Adoption Backlog `P2.1` API/Web compatibility contract: added runtime endpoint `GET /v1/meta/compatibility` backed by `config/api_web_compat.json` (with env overrides) and CI guard `scripts/check_api_web_compat_contract.py` wired into `scripts/ci_checks.sh` to prevent API/web drift.
- 2026-04-08: Completed Real-World Adoption Backlog `P2.2` upgrade checklist: published `docs/upgrade-checklist.md` with pre-upgrade snapshot, migration/restart order, routing-policy safety checks, and rollback flow.
- 2026-04-08: Completed Real-World Adoption Backlog `P2.3` post-deploy smoke runbook: standardized smoke contract in `docs/post-deploy-smoke.md` and anchored it to `scripts/run_selfhost_core_acceptance.sh` (`import -> draft -> publish -> retrieval` verification).
- 2026-04-08: Started `v0.1.4 Adoption UX Hardening`: added `memory_api` source type support (`legacy-import` + connector catalog), introduced first-run starter wiki bootstrap API (`POST /v1/adoption/first-run/bootstrap`), upgraded setup wizard to optionally seed starter pages after first trusted batch, and made web build base-path resilient for `/synapse/...` routing without manual asset rebuild.
- 2026-04-08: Completed `v0.1.4 Adoption UX Hardening`: shipped one-command enterprise preset API (`POST /v1/adoption/sync-presets/execute`), added role-based wiki-space templates (`GET/POST /v1/adoption/wiki-space-templates*`), upgraded default knowledge ingest noise profile to `knowledge_v2`, and hardened wiki-first UI state by rotating local storage schema key (`synapse_web_console_v5`) with legacy-key cleanup.
- 2026-04-08: Added `Agent Wiki Bootstrap` out-of-box flow (`POST /v1/adoption/agent-wiki-bootstrap`) with preview/apply mode and DoD checks; bootstraps published wiki pages for `Data Sources Catalog` (+ per-source contracts), `Agent Capability Profile` (orgchart/capability/handoffs), and `Operational Logic Map` (`comment -> signal -> action candidate -> escalation rule`), plus new Operations UI buttons (`Preview Bootstrap Wiki` / `Bootstrap Wiki`) and SDK helpers (Python/TypeScript).
- 2026-04-09: Closed adoption feedback `P0` on ingest stability: switched backfill event identity to deterministic `project_id + source_id + record_fingerprint` (while preserving batch fallback), added per-batch duplicate-pair guard (`source_id + fingerprint`) and persisted `record_fingerprint`/`ingestion_classification` into backfill payload metadata to prevent linear growth on repeated sync uploads.
- 2026-04-09: Closed adoption feedback `P0` on pre-claim noise filtering: hardened worker backfill suppression to block `pii_sensitive_stream` and explicit deny-class ingestion classifications before claim/draft generation, while preserving trusted knowledge hints and durable knowledge-lane signals.
- 2026-04-09: Closed adoption feedback `P0/P1/P2` bootstrap + observability gaps: added policy-aware wiki-space fallback for first-run/agent/template bootstrap flows (with explicit 409 diagnostics when no writable space exists), enriched Data Sources Catalog pages with schema samples from connector mappings, strengthened Operational Logic synthesis to high-signal knowledge-only claims, and shipped sync cursor diagnostics endpoint (`GET /v1/adoption/sync/cursor-health`) plus pipeline signal/noise ratio telemetry.
- 2026-04-10: OOTB content-quality hardening pass: added worker pre-draft hard filter for `operational_stream`/payload-like/PII claims, enriched claim metadata from backfill suppression signals, enabled high-signal route override in gatekeeper (`events -> claims` rescue for policy/process/runbook signals), strengthened bootstrap quality-gate to downgrade template/short pages from `published` to `reviewed`, and expanded Agent Capability bootstrap with actionable per-agent sections (actions/escalations/constraints/scenarios) plus acceptance tests for required sections/fact density.
- 2026-04-10: OOTB bootstrap usefulness uplift (phase 2): expanded `agent-wiki-bootstrap` pack with `Tooling Map`, `Process Playbooks`, `Company Operating Context`, and aggregated `Daily Operations Digest`; enriched capability synthesis from static agent metadata (prompt/config/tool-registry/approval rules/allowed actions); added stronger source→agent usage/scenario mapping; introduced `bootstrap_publish_core` forced-core publish mode with warning annotations; and shipped structured bootstrap `quality_report` + explicit `preview_apply_flow` response contract for safer first-run UX.
- 2026-04-10: Added adoption endpoint `GET /v1/adoption/wiki-quality/report` and KPI integration for hard OOTB quality checks (core page coverage, placeholder ratio, daily-summary draft ratio), plus clean self-host regression assertion in `integration_legacy_sync_queue_processing.py` to keep release quality stable.
- 2026-04-10: Added UI adoption quality visibility in core workspace: Operations route now has a dedicated `Wiki quality report` panel (pass/fail, core coverage, placeholder ratio, daily-summary draft ratio, warnings), Migration quick-actions include `Refresh quality` + `View quality`, and wiki right rail shows a compact quality status card sourced from KPI quality report.
- 2026-05-03: Added bundle-level compiler promotion runner `POST /v1/adoption/bundle-promotion/run` with preview/apply flow, idempotency, evidence-bundle summary, core-page quality report, and compiler-page upsert refresh path so teams can materialize `data sources / agent capability / process playbooks / decisions / company context / operational logic` directly from durable knowledge bundles instead of relying only on raw draft moderation.
- 2026-05-03: Folded bundle-level promotion into the default enterprise adoption path: `POST /v1/adoption/sync-presets/execute` now previews/applies compiler-driven bundle promotion alongside starter/bootstrap flows, so first-run self-host onboarding can land on richer core wiki pages without a separate hidden operator step.
- 2026-05-03: Wired bundle-level promotion into the default post-approval paths: single draft approve, bootstrap approve, and auto-publish can now trigger inline compiler refresh scoped by page family, reducing the lag between “claim approved” and “core wiki became richer”.
- 2026-05-03: Added actionable knowledge-gap sync loop: `POST /v1/adoption/knowledge-gaps/tasks/sync` converts candidate bundles, weak pages, repeated agent questions, and repeated escalations into deduplicated Synapse tasks, so missing wiki knowledge now feeds directly into the task/execution layer instead of staying only in diagnostics.
