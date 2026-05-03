# Shared Memory Roadmap

Goal: move Synapse from “durable governed knowledge agents can pull” toward “shared operational memory agents can reliably hydrate before every task”.

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

Status: planned

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

### Phase 5: Fanout and operator controls

Status: planned

Deliverables:

1. operator-facing shared-memory health panel
2. publish-time impact preview:
   - which agents / roles / spaces are affected
3. optional push/fanout hooks to runtimes

Why:

- closes the loop between wiki publishing and runtime impact
- makes shared memory observable and safe

## First implementation slice in repo

Started on 2026-05-03.

Implemented:

1. `GET /v1/wiki/change-feed`
2. `POST /v1/agents/shared-memory/hydrate`
3. Python/TypeScript SDK helpers
4. `POST /v1/agents/shared-memory/invalidation`
5. best-effort `Wiki State Snapshot` refresh after published page create/update

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
