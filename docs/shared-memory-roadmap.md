# Shared Memory Roadmap

Goal: move Synapse from “durable governed knowledge agents can pull” toward “shared operational memory agents can reliably hydrate before every task”.

Core product principle:

- `auto by default, human on exception`
- agents and runtimes should normally absorb, refresh, retry, and age shared memory without a human in the loop
- human operators should mainly correct, override, or recover when quality/risk/health signals show the autonomous loop is no longer behaving well

## Current reality

Today Synapse is strongest at:

1. capturing new knowledge from humans and agents into the wiki compiler
2. governing promotion into `reviewed` / `published` knowledge
3. exposing approved knowledge back to runtimes through retrieval, onboarding packs, and state snapshots

This is already useful shared knowledge, but it is not yet a realtime cross-agent memory bus.

## Target architecture

We want three layers:

1. `change feed`
   - machine-readable stream of newly published/reviewed wiki changes
   - scoped by project, space, role, and time cursor

2. `task-start hydration`
   - one call that gives an agent:
     - current state snapshot
     - role-aware onboarding pack
     - fresh wiki changes
     - retrieval hints for changed entities/pages

3. `context invalidation + fanout`
   - when important knowledge changes, relevant agents know their cached context is stale
   - not a full push of markdown, but a small invalidation and relevance signal

## Ideal rollout

### Phase 1: Shared-memory substrate

Status: started

Deliverables:

1. `GET /v1/wiki/change-feed`
2. `POST /v1/agents/shared-memory/hydrate`
3. SDK helpers for both
4. role-aware fresh-change consumption using existing `published` / optional `reviewed` knowledge

Why first:

- gives every runtime a stable “what changed?” and “hydrate me” surface
- does not require new storage tables
- builds on existing `wiki_page_versions`, `wiki_pages`, onboarding packs, and state snapshots

### Phase 2: Better freshness and lower lag

Status: started

Deliverables:

1. auto-sync `Wiki State Snapshot` after important publishes
2. explicit retrieval modes:
   - `published_only`
   - `reviewed_plus_published`
3. shared-memory quality metrics:
   - hydration freshness
   - changed-page coverage
   - stale snapshot lag
4. cheap invalidation polling surface for runtimes

Why:

- reduces the gap between “page was published” and “agents got the compressed state”
- keeps conservative governance while lowering operational lag

### Phase 3: Context invalidation

Status: planned

Deliverables:

1. invalidation tokens for agent cached context
2. relevance routing:
   - by `space_key`
   - by role
   - by changed entity/page type
3. machine-readable `delta` objects:
   - rule changed
   - escalation changed
   - source ownership changed
   - playbook changed

Why:

- lets runtimes refresh only when needed
- avoids every agent blindly reloading the whole wiki

### Phase 4: True shared memory tiers

Status: started

Deliverables:

1. explicit visibility tiers:
   - `draft/private working memory`
   - `reviewed team memory`
   - `published org memory`
2. per-agent / per-role read policy across tiers
3. task-start hydration aware of allowed tier

Why:

- some agents need trusted-but-not-yet-published team knowledge
- others should stay on conservative org-level memory only

### Phase 5: Fanout, observability, and recovery

Status: started

Deliverables:

1. operator-facing shared-memory health panel
2. publish-time impact preview:
   - which agents / roles / spaces are affected
3. optional push/fanout hooks to runtimes
4. recovery controls as a secondary path, not as the default operating model

Why:

- closes the loop between wiki publishing and runtime impact
- makes shared memory observable and safe
- keeps humans in a corrective/governance role instead of turning them into a required approval hop for normal memory refresh

## First implementation slice in repo

Started on 2026-05-03.

Implemented:

1. `GET /v1/wiki/change-feed`
2. `POST /v1/agents/shared-memory/hydrate`
3. Python/TypeScript SDK helpers
4. `POST /v1/agents/shared-memory/invalidation`
5. best-effort `Wiki State Snapshot` refresh after published page create/update
6. role-aware review scope resolution (`auto` -> trusted roles may read `reviewed`)
7. change-feed delta classification + relevance scoring for agent-facing freshness checks
8. `POST /v1/agents/shared-memory/impact`
9. `GET /v1/agents/shared-memory/health`
10. compact `Operations` panel for shared-memory freshness / impacted agents
11. explicit tier contract for shared-memory runtime surfaces:
   - `published_org`
   - `reviewed_team`
   - `draft_private`
12. publish-time impact preview for planned wiki changes before they land
13. `draft_private` now reads real draft-backed deltas from `wiki_draft_changes` for trusted roles, instead of staying a pure degraded no-op
14. shared-memory changes now carry typed `delta_objects` plus compact `fanout_plan` summaries for publish preview / operator routing
15. long-lived `shared_memory_entries` now back private/team memory with materialized entries that runtimes can write and later hydrate alongside wiki deltas
16. optional `shared_memory_fanout_hooks` now let operators configure push-style invalidation / impact / publish-preview delivery to external runtimes, with dry-run dispatch before going live
17. fanout deliveries now persist audit history plus retry support, so failed runtime pushes can be inspected and re-dispatched without reconstructing payloads by hand
18. hook-level retry policy (`max attempts` + `backoff`) and due-retry processing now let shared-memory fanout move from ad-hoc retries toward a real delivery loop
19. runtime fanout payloads now carry per-delivery correlation IDs, and runtimes can report `accepted/refreshed/ignored/failed` acknowledgements back through `POST /v1/agents/shared-memory/fanout-acks`, so health can distinguish “sent” from “actually applied”
20. fanout dispatch now supports queued delivery (`enqueue_only=true`) plus a dedicated pending-delivery processor, so shared-memory push can move from inline-only execution toward a real delivery queue
21. materialized private/team memory entries now support richer lifecycle states (`superseded`, `resolved`, `expired`, `archived`) plus lifecycle metadata (`superseded_by`, `resolved_at`, `expires_at`, `reason`), so working memory can age out or close cleanly instead of living forever as `active`
22. shared-memory entries now have a lifecycle processor for due expirations, so long-lived private/team memory can automatically age from `active` to `expired` instead of relying entirely on manual cleanup
23. worker loop now includes shared-memory maintenance, so pending fanout deliveries, due retries, and expiring lifecycle entries can be processed on a regular cadence in self-host deployments instead of depending on manual endpoint calls
24. shared-memory maintenance now acquires per-project advisory locks before running, so multi-worker/self-host deployments are less likely to double-process the same queue/lifecycle workload concurrently
25. Operations now exposes shared-memory maintenance controls with dry-run and live execution for queue processing, due retries, and lifecycle expiry, but these are intentionally framed as recovery tools rather than the primary operating path
26. queued fanout deliveries now acquire short-lived per-delivery leases before processing, so future parallel or manual queue processors are less likely to double-send the same pending runtime notification

Current limitation:
- private/team memory now has materialized entry backing, lifecycle states, due-expiry processing, fanout retry/backoff, runtime ack freshness, queued delivery foundation, scheduler integration, advisory lock protection, and short-lived per-delivery leases, but still lacks richer delivery guarantees such as explicit lease heartbeats or more advanced stuck-delivery reclamation if maintenance work needs to scale far beyond a single self-host worker pool

These endpoints are intentionally conservative:

- they operate on `published` knowledge by default
- they can optionally include `reviewed`
- they reuse existing state snapshot and onboarding pack builders

## Exit criteria for “shared memory works”

We should consider this track successful when:

1. an agent can start a task with one hydration call
2. hydration includes both stable baseline and fresh deltas
3. important wiki publishes invalidate stale agent context
4. operators can see which agents are behind on fresh knowledge
