# synapse-web

Human-in-the-loop review UI for draft knowledge.

Stack (open-source):
- React + Vite
- Mantine UI components (MIT)
- Mantine Charts + Recharts (MIT)
- Tabler Icons (MIT)

Capabilities:
- `Core Workspace` (default): focused wiki workflow for daily operations:
  - wiki-centric command bar (`Wiki`, `Drafts`, `Tasks`) with wiki-first default and direct page routing (`/wiki/<space>/<page>`)
  - core hero messaging now centered on `Company Wiki, Written by Agents` (operations controls intentionally de-emphasized)
  - page-centric wiki layout with left `Wiki Tree` navigation and draft breadcrumb context
  - dedicated `Wiki Page` preview panel (read-only article canvas) for page-first browsing
  - `Wiki Home` state for no-page selection: spaces directory + recent pages quick-jump
  - page header card with status/type/version, latest-update metadata, and quick page actions (`Refresh Page`, `Open Page Drafts`)
  - direct `Move/Rename` page workflow from page header (parent path + slug leaf + optional subtree move) with immediate tree refresh
  - page lifecycle controls in header (`Archive` / `Restore`) for clean wiki curation without leaving the page view
  - dedicated `Page Context` rail (sections, revision timeline, open drafts on selected page)
  - page collaboration cards in context rail: aliases (slug redirects), watchers, and reviewer comments
  - page review-assignment workflow in context rail (assign reviewer / resolve assignment)
  - governance controls in context rail: space policy (`write/comment mode`, review-required publish), space owners, and page owners
  - reviewer notification inbox (`/v1/wiki/notifications*`) with unread counters, quick mark-read, and mention/watcher delivery visibility
  - Confluence-like hierarchical `Space -> Folder -> Page` tree fed by `GET /v1/wiki/pages` (page index first, draft metrics overlaid), plus recent pages strip and open-only filter
  - draft inbox and moderation
  - migration tools in `Drafts` are gated behind explicit `Migration Mode` toggle in core UI
  - bootstrap migration flow for trusted-source dry-run + phased batch approval after legacy backfill
  - phased migration presets (`25/50/200`) with safer default batch size and apply soft cap alignment
  - bootstrap batch-approve guardrails: apply is enabled only after a matching dry-run preview, requires trusted sources, and is soft-capped per run by API policy
  - bootstrap migration settings are collapsed by default (`Open tools`) to keep Drafts first-view compact
  - triage/intent analytics cards are expert-only; core keeps queue-first moderation flow
  - Draft Inbox operations controls (filtering, bootstrap, queue tuning) are collapsed under `Open operations` in core
  - Drafts/Tasks stay secondary to page view but remain one-click tabs in the command bar
  - API URL override uses `VITE_SYNAPSE_API_URL` (default `http://localhost:8080`)
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
  - wiki editor command palette (`Ctrl/Cmd + /`) with slash-like quick actions and no-code templates (callouts, incident/decision blocks)
  - rich table authoring in wiki editor (insert table, add row/column, delete table)
  - attachment/media preview in wiki canvas (inline image gallery + linked files extracted from markdown)
  - page-edit asset upload flow (`POST /v1/wiki/uploads`) with automatic markdown snippet insertion
  - statement-level visual diff (`before`/`after`) based on semantic payload
  - conflict resolver panel with one-click `Force Approve` / `Reject + Dismiss`
  - Agentic Todo tracker (`/v1/tasks*`) with task lifecycle, comments, and claim/draft/page link context

Legacy control-center workspace is removed from OSS UI. Synapse Web now ships a single wiki-first experience.

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

UI is wiki-first by default (legacy control-center profile removed).

To override API endpoint in core mode without exposing API URL field in UI:

```bash
export VITE_SYNAPSE_API_URL=http://127.0.0.1:8080
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
