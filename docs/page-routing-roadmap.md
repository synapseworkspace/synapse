# Synapse Page Routing Roadmap

Last updated: 2026-04-03

This roadmap focuses on improving how Synapse routes incoming claims to wiki pages and decides when to create a new page.

## Goals

- Reduce false `new_page` decisions.
- Improve routing precision for existing pages.
- Keep human moderation in control for ambiguous cases.
- Build measurable feedback loop from moderation outcomes.

## Phase 1 (Start Now): Safer Deterministic Routing

Status: `completed`

Scope:
- Prefer active pages over archived pages during candidate routing.
- Add ambiguity guard near `threshold_mid` to avoid premature `new_page` creation.
- Include top-score diagnostics in routing rationale for easier moderation/debugging.

Expected impact:
- Fewer accidental page splits.
- Better reviewer trust in draft rationale.

## Phase 2: Entity Registry + Alias Governance

Status: `completed (registry-lite in worker routing)`

Scope:
- Introduce canonical `entity_id` with alias table (`entity_key`, slug aliases, legacy names).
- Route by canonical entity first, lexical similarity second.
- Add merge/split workflows for entity hygiene.

Expected impact:
- Stable routing across naming drift.
- Lower dependency on ad-hoc `entity_key` formatting.

## Phase 3: Hybrid Reranking

Status: `completed (deterministic + contextual rerank)`

Scope:
- Keep deterministic candidate generation.
- Add reranker over top-K candidates using semantic similarity + moderation history signals.
- Output calibrated confidence and top-2 margin.

Expected impact:
- Higher routing precision in dense projects.
- Better handling of near-duplicate pages.

## Phase 4: Learning Loop from Moderation

Status: `completed (adaptive threshold policy from moderation feedback)`

Scope:
- Capture reviewer corrections (`reassign_page`, forced new page, reject reason classes).
- Recalibrate routing thresholds per project.
- Add periodic drift checks and threshold recommendations.

Expected impact:
- System adapts to project-specific wiki topology.
- Continuous quality gains without hardcoded retuning.

## Phase 5: Routing SLOs and Operational Controls

Status: `completed`

Scope:
- Add routing quality metrics:
  - `route_precision_at_1`
  - `new_page_false_positive_rate`
  - `manual_reassign_rate`
  - `time_to_publish_after_route`
- Expose dashboards and alert thresholds.

Expected impact:
- Routing quality becomes observable and governable.

## Current Execution Note

Implemented in:
- `services/worker/app/wiki_engine.py` (routing, rerank, adaptive thresholds)
- `services/api/app/main.py` (`/v1/wiki/routing/metrics`, `/v1/wiki/routing/recommendations`)
- `services/worker/scripts/run_wiki_synthesis.py` (CLI/env controls)
