# synapse-web

Human-in-the-loop review UI for draft knowledge.

Stack (open-source):
- React + Vite
- Mantine UI components (MIT)
- Mantine Charts + Recharts (MIT)
- Tabler Icons (MIT)

Capabilities:
- `Core Mode` (default): focused wiki workflow for daily operations:
  - page-centric wiki layout with left `Wiki Tree` navigation and draft breadcrumb context
  - Confluence-like `Space -> Page` navigation with collapsible space groups, recent pages strip, and open-only page filter
  - draft inbox and moderation
  - draft inbox filtering by space/page/text query
  - review queue presets (`Open queue`, `SLA breaches`, `Conflicts`, `High confidence`, `Full timeline`)
  - moderation SLA widgets (open count, breaches, conflict load, high-confidence load, oldest/median wait)
  - compact moderation throughput analytics card (24h actions, approve rate, p50 decision latency, backlog delta, and top reviewers)
  - triage lane with top-priority open drafts (conflict-first + SLA-aware ordering) and queue-priority reason badges
  - one-click inbox moderation actions (`Quick approve` / `Quick reject`) from triage and draft cards
  - operator walkthrough panel for first-run core flow (`connect workspace -> refresh inbox -> select draft`) with inline docs previews before navigation
  - walkthrough telemetry strip with per-step first-completion timers (`workspace`, `inbox`, `first draft`) and onboarding action counters
  - session-level intent signals card for triage + quick moderation behavior tracking
  - accessibility baseline for non-mouse moderation: explicit aria labels on icon-only moderation actions + high-contrast `focus-visible` ring styling
  - inline risky-action confirmations (double-confirm within 6s) for force-approve and reject-dismiss moderation paths
  - section TOC navigation in Draft Detail with quick "use section in approve form"
  - no-code page templates for common moderation updates (Access policy, Operations incident, Customer preference)
  - saved workspace views (persist/apply/delete current space/page/filter context)
  - pinned pages quick-jump list for high-frequency wiki pages
  - guided page builder (autofill from current draft, slug normalization, duplicate detection via page search, one-click page create)
  - page history compare tab with version-to-version markdown diff and fast restore into approve form
  - bulk moderation controls for visible drafts (`select all`, batch approve/reject, force-approve conflicts)
  - fast cross-page moderation jumps (`Shift+J/K` pages, `Shift+C` conflict pages)
  - detailed draft inspection (`semantic_diff`, `markdown_patch`, evidence, conflicts)
  - confluence-like wiki reading canvas with article typography and read-time/word-count metadata
  - statement-level visual diff (`before`/`after`) based on semantic payload
  - conflict resolver panel with one-click `Force Approve` / `Reject + Dismiss`
  - Agentic Todo tracker (`/v1/tasks*`) with task lifecycle, comments, and claim/draft/page link context
- `Advanced Mode` (opt-in): analytics, calibration, queue, incident, rollback, and governance controls.

Advanced mode capabilities:
- MCP-compatible conflict enrichment from API (`GET /v1/wiki/drafts/{draft_id}/conflicts/explain`)
- MCP retrieval diagnostics panel (`GET /v1/mcp/retrieval/explain`) with per-result reason traces, lexical/graph score breakdown, and visible runtime graph tuning snapshot (`max hops` + hop boosts).
- Intelligence Pulse dashboard with live KPI cards (`Knowledge Velocity`, `pending approvals`, `open conflicts`)
- Daily/weekly analytics charts from intelligence APIs
- Conflict drill-down board (weekly conflict classes + MTTR)
- Latest daily digest panel (`/v1/intelligence/digests/latest`)
- Digest delivery observability (`/v1/intelligence/delivery/targets`, `/v1/intelligence/delivery/attempts`)
- calibration snapshot history (`/v1/gatekeeper/config/snapshots`) with guardrail status and artifact refs
- calibration guardrail trend board (`/v1/gatekeeper/calibration/trends`) with precision/recall KPI deltas and approval gate signal
- calibration scheduler run-history board (`/v1/gatekeeper/calibration/runs*`) with pass/alert trend and top alert codes
- calibration schedule management UI (`/v1/gatekeeper/calibration/schedules*`) with preset profiles, validation hints, and CRUD actions
- calibration operations controls (`/v1/gatekeeper/calibration/operations/*`) with due-state preview, async queue execution, live progress timeline, and scheduler command preview
- calibration operation safety rails: project-level run lock, confirmation checkpoint (`RUN <project_id>`), and idempotency token workflow for live runs
- calibration async run governance: queue-backed runs (`/v1/gatekeeper/calibration/operations/runs*`) with cancel/retry actions and event-stream progress feed
- calibration queue throughput controls (`/v1/gatekeeper/calibration/operations/throughput*`) with worker-lag/depth health, configurable thresholds, and pause/resume windows
- calibration queue command center (`/v1/gatekeeper/calibration/operations/throughput/compare`, `.../bulk_pause`, `.../bulk_resume`, `.../compare/export*`) with cross-project health leaderboard, bulk pause/resume, CSV export, and webhook snapshot delivery
- queue ownership routing (`/v1/gatekeeper/calibration/operations/ownership`) to map each project to on-call owner/contact/escalation channels
- queue incident auto-ticket hooks (`/v1/gatekeeper/calibration/operations/incidents/*`) with provider adapters (`webhook`, `PagerDuty`, `Jira`), open/resolve automation, and incident state sync
- incident provider secret management with masked adapter secrets (`********`), rotation-safe updates, and RBAC-scoped edit permissions (`X-Synapse-Roles`)
- alert-to-incident policy templates (`/v1/gatekeeper/calibration/operations/incidents/policies`) with per-alert routing overrides, priority ordering, and severity mapping
- alert policy simulation (`/v1/gatekeeper/calibration/operations/incidents/policies/simulate`) with dry-run route tracing and no ticket side effects
- incident sync schedule command center (`/v1/gatekeeper/calibration/operations/incidents/sync/schedules*`) with persisted cadence profiles, due backlog visibility, run controls, hourly failure heatmap, and fleet-table UX backed by server-side filters/sorting/pagination (`project/name/status/enabled`, `sort_by`, `sort_dir`, `offset/cursor`, compact mode)
- incident sync run drill-down with per-run trace payload viewer, linked queue audit event jump, and one-click retry shortcuts
- incident sync schedule timeline view (`/v1/gatekeeper/calibration/operations/incidents/sync/schedules/{schedule_id}/timeline`) with multi-run status trends, failure-class breakdown, and recent audit-linked run feed
- owner-level queue performance rollups (`/v1/gatekeeper/calibration/operations/throughput/owners`) with SLA-breach and MTTR metrics by owner/on-call channel
- governance drift dashboard (`/v1/gatekeeper/calibration/operations/governance/drift`) with ownership coverage rates and unresolved pause-age bucket distribution
- calibration queue autoscaling recommendations (`/v1/gatekeeper/calibration/operations/throughput/recommendations`) with rolling-history worker concurrency and lag/depth tuning guidance + one-click `Apply controls` workflow
- calibration queue governance audit timeline (`/v1/gatekeeper/calibration/operations/throughput/audit`) for pause/resume/control actor traceability
- queue audit escalation actions (`.../throughput/audit/{event_id}/acknowledge|resolve`) with follow-up owner annotations
- daily queue governance digest card (`/v1/intelligence/queue/governance_digest`) with top congestion projects and unreviewed pause windows
- incident escalation digest card (`/v1/intelligence/queue/incident_escalation_digest`) with unresolved ticket prioritization, SLA-age buckets, and ownership gap triage
- calibration queue live stream mode (`/v1/gatekeeper/calibration/operations/runs/{run_id}/stream`) with SSE subscription toggle and automatic polling fallback
- schedule observability drill-down (`/v1/gatekeeper/calibration/schedules/observability`) with per-schedule SLO health, trend window, and top failure classes
- cross-project observability compare (`/v1/gatekeeper/calibration/observability/compare`) with project leaderboard, drift index, and failure hotspots
- compare drill-down navigation (`/v1/gatekeeper/calibration/observability/compare/drilldown`) from leaderboard project card to schedule-level timelines with rank-neighbor context
- gatekeeper alert delivery observability (`/v1/gatekeeper/alerts/*`) with targets, attempts, success ratio, and last failure context
- gatekeeper alert routing management UI (create/update/delete targets, enable/disable, severity/code filters)
- rollback approval workflow with previewed impact/risk, request queue, multi-approver actions, and audit trail (`/v1/gatekeeper/config/rollback/preview`, `/v1/gatekeeper/config/rollback/requests*`)
- rollback governance metrics panel (approval/resolution lead time, rejection causes, risk-level and risk-driver rollups) powered by `/v1/gatekeeper/config/rollback/metrics`
- rollback drill-down actions: SLA-breach badges, 7/30/90/custom window presets, and CSV export for governance analytics
- rollback attribution analytics (`/v1/gatekeeper/config/rollback/attribution`) with reviewer cohort lead-time and decision-outcome trend
- rollback attribution causal drill-down (`/v1/gatekeeper/config/rollback/attribution/drilldown`) with request-level traces (cohort -> impacted requests -> approval/reject timeline)
- approve/edit/reject workflow using live moderation API
- keyboard-first moderation flow (`J/K`, `Ctrl|Cmd+Enter`, `Ctrl|Cmd+Backspace`, `Ctrl|Cmd+R`)
- bulk moderation shortcuts (`Ctrl|Cmd+Shift+Enter` approve selected, `Ctrl|Cmd+Shift+Backspace` reject selected)
- optimized cold-load bundle: moderation console loads first, intelligence charts are lazy-loaded

## Run locally

1. Start API:

```bash
cd services/api
python -m venv .venv && source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --port 8080
```

2. Install web dependencies:

```bash
cd apps/web
npm install
```

3. Start web UI:

```bash
npm run dev
```

4. Open:

`http://localhost:5173`

Optional: lock UI to core-only workflow (hide advanced mode and expert controls):

```bash
export VITE_SYNAPSE_UI_PROFILE=core-only
```

By default API allows CORS from any local UI origin. To restrict allowed origins:

```bash
export SYNAPSE_UI_ORIGINS="http://localhost:5173,http://127.0.0.1:5173"
```

## Browser E2E

Run Playwright e2e (mock API + real browser):

```bash
cd apps/web
npm run e2e:install
npm run e2e
```
