# Synapse Wiki Engine Design

This document defines the wiki engine, UI model, and business logic for how Synapse decides where and how to write knowledge.

## 1. Engine Choice (OSS-first)

Use a custom Markdown-native wiki engine in Synapse instead of external wiki platforms.

Primary stack:
- Storage: Postgres (source of truth)
- Document format: Markdown (plus normalized AST for machine operations)
- Retrieval index: Postgres FTS + pgvector embeddings
- UI: Next.js app with structured diff + editor

Why this choice:
- Full control over provenance, moderation, and version graph
- No hard dependency on third-party wiki APIs
- Easy self-hosted operation for OSS users
- Deterministic publish/replay model for agents

## 2. UI Model

The UI is split into explicit operator workflows.

Views:
1. Draft Inbox: incoming candidate updates generated from claims.
2. Conflict Queue: explicit contradiction items requiring resolution.
3. Page Editor: canonical page edit view with evidence panel.
4. Semantic Diff: proposed meaning-level change vs published page.
5. Audit Timeline: who changed what, when, and why.

Editor behavior:
- Markdown is canonical, but UI edits at section/block level.
- Every inserted statement can keep evidence links.
- Human actions are explicit: Approve, Edit+Approve, Reject, Merge.

## 3. Core Data Model (Wiki layer)

Required entities:
1. `wiki_pages`
- id, project_id, page_type, title, slug, entity_key, status

2. `wiki_page_versions`
- page_id, version, markdown, ast_json, source (`agent` or `human`), created_by

3. `wiki_sections`
- page_id, section_key, heading, order_index

4. `wiki_claim_links`
- claim_id, page_id, section_key, insertion_status

5. `wiki_page_aliases`
- page_id, alias_text

6. `wiki_conflicts`
- conflict_id, claim_a, claim_b, page_id, conflict_type, resolution_status

7. `knowledge_snapshots`
- snapshot_id, project_id, published_at, version_set

## 4. Decision Logic: Where New Knowledge Goes

For each incoming claim, the engine runs a deterministic resolver pipeline.

Step A: Canonicalize claim
- Normalize entities, time range, and predicate form.
- Produce a stable claim fingerprint.

Step B: Find candidate page
- Retrieve top candidates from:
  1. exact `entity_key`
  2. title/alias lexical match
  3. semantic nearest pages via embeddings
  4. graph-neighbor pages by entity relations

Step C: Page decision
- If best candidate score >= threshold_high: update existing page.
- If score between threshold_mid and threshold_high: create draft with human review required.
- If score < threshold_mid: propose new page draft.

Step D: Section decision
- Try to map to existing section taxonomy by page_type.
- If no confident section match, propose new section draft.

Before Step A, Gatekeeper triage decides whether claim is even eligible for wiki promotion:
1. `operational_memory`: execution noise, not promoted to draft wiki pages.
2. `insight_candidate`: useful but requires standard moderation.
3. `golden_candidate`: high-value pattern/policy fact, prioritized in moderation queues.
4. `assertion_class`: every claim is typed as `policy | process | preference | incident | event | fact` for routing clarity.

Knowledge Utility Gate (default):
1. deny-list checks by `category`, `source_system`, `source_type`, `entity_key`, and `source_id`;
2. event-stream shape detection (token hits + numeric ratio + key/value payload density);
3. durable-signal checks (`policy/process/rule/preference/incident` style semantics);
4. backfill-specific guardrails (records without durable signal are held in `operational_memory`).

This is what prevents `order_snapshot`/invoice/status streams from flooding wiki drafts.

Assertion-class aware publication:
1. project policy can define `publish_mode_by_assertion_class` in `routing_policy`;
2. class mode is resolved before category fallback;
3. typical default: `event -> human_required`, `policy/process/incident/fact -> conditional`, `preference -> auto_publish`.

Auto-promotion from `insight_candidate` to `golden_candidate` can happen when:
1. source diversity reaches configured threshold;
2. claim remains conflict-free in recent horizon;
3. gatekeeper confidence score is above configured floor.

## 5. Duplicate and Redundancy Logic

Synapse prevents repeated writes at two levels.

1. Claim-level dedup:
- Compare claim fingerprint and semantic similarity.
- If same meaning already present and still valid (temporal windows overlap), mark as reinforcement, not insertion.

2. Section-level dedup:
- Compare candidate insertion against section statements.
- If near-duplicate above threshold, attach evidence to existing statement.

Outcome states:
- `new_statement`
- `reinforcement`
- `duplicate_ignored`

## 6. Conflict Logic

Conflict is explicit and first-class.

Conflict detection checks:
1. Same entity + same predicate + incompatible value.
2. New temporal fact invalidates active current fact, but only when validity windows overlap.
3. Operational policy contradiction (e.g., card-only vs open access).

When conflict is found:
- create conflict item in `wiki_conflicts`
- block auto-publish
- surface side-by-side evidence in Conflict Queue

Temporal guardrails:
1. Claims and statements keep `valid_from`/`valid_to` windows.
2. Expired active statements are auto-superseded during synthesis.
3. Runtime retrieval returns only currently valid active statements.

## 7. Draft Generation Logic

Draft generator outputs structured change proposals.

Draft includes:
1. target page and target section
2. exact markdown patch
3. semantic summary (before vs after meaning)
4. linked evidence bundle
5. confidence and rationale

No direct write to published wiki from raw claims.
All candidate changes go through draft or policy-approved fast lane.

## 8. Publish and Agent Runtime

After approval:
1. Create new `wiki_page_versions`.
2. Rebuild retrieval indexes (FTS + embeddings delta update).
3. Create new `knowledge_snapshot`.
4. Invalidate runtime caches.
5. MCP retrieval serves only latest published snapshot.

This guarantees stable, reviewable context for agents.

## 9. Policy Modes

Per category, choose one mode:
1. `manual_only`: always human approval.
2. `assisted_auto`: auto-apply only when confidence high and no conflict.
3. `auto`: fully automatic (for low-risk telemetry-like facts).

Default for operations/policies should be `manual_only`.

Project-level Gatekeeper thresholds are runtime-configurable through Synapse API:
1. `min_sources_for_golden`
2. `conflict_free_days`
3. `min_score_for_golden`
4. `operational_short_text_len`
5. `operational_short_token_len`
6. `llm_assist_enabled`
7. `llm_provider`
8. `llm_model`
9. `llm_score_weight`
10. `llm_min_confidence`
11. `llm_timeout_ms`

This allows business-specific tuning without redeploying worker code.

## 10. How This Layers with OpenClaw

OpenClaw provides events and tool runtime.
Synapse adds:
1. persistence and structure
2. moderation workflow
3. canonical wiki pages and versions
4. shared memory across all agents

OpenClaw agents become producers and consumers of curated wiki knowledge instead of isolated short-term logs.

## 11. Bootstrap Existing Memory on SDK Onboarding

When an agent already has historical memory at the moment Synapse SDK is connected, use bootstrap/backfill mode.
Both SDKs support this directly on attach (`bootstrap_memory` in Python, `bootstrapMemory` in TypeScript), so day-0 import can happen in the same one-line integration step.

Flow:
1. SDK uploads historical records in chunks to `/v1/backfill/memory` under one `batch_id`.
2. API stores each record as `events.event_type = memory_backfill` with deterministic event IDs.
3. Worker extracts candidate claims from those events and enqueues `claim_proposals`.
   - If historical records miss explicit `entity_key` or `category`, worker infers them from text patterns/keywords (EN/RU) with deterministic fallback.
   - Event-like records with low durable signal are dropped before claim-proposal enqueue (unless marked as trusted knowledge via metadata/record kind).
4. Standard synthesis pipeline produces `wiki_draft_changes` with evidence links.
5. Human operators review/approve in the same Draft Inbox flow.

Control and safety:
1. Chunk-level idempotency keys prevent duplicate ingestion retries.
2. `memory_backfill_batches` tracks lifecycle (`collecting`, `ready`, `processing`, `completed`, `failed`) and routing-quality counters (`dropped_event_like`, `kept_durable`, `trusted_bypass`).
3. `event_pipeline_state` tracks extraction checkpoint per event for resume/retry semantics.
4. Backfill records can include explicit `valid_from`/`valid_to` fields; worker uses them with highest precedence.

## 12. Knowledge Intelligence Layer (Digest + Velocity)

Synapse has a management-facing layer on top of wiki moderation flow:
1. `knowledge_daily_metrics` stores daily counters per project (claims, drafts, approvals, conflicts, velocity).
2. `intelligence_digests` stores rendered summaries for operators and management.
3. Worker job `run_intelligence_digest.py` computes metrics and publishes a daily digest snapshot.

Business outcome:
1. Team does not need to read full wiki to understand AI learning progress.
2. Backlog and contradiction pressure become visible (`pending_drafts`, `open_conflicts`).
3. "Knowledge Velocity" trend can be charted to show ROI of Synapse adoption.

## 13. Retrieval Feedback Loop

Synapse accepts runtime usefulness feedback for retrieved context:
1. `POST /v1/mcp/retrieval/feedback` stores `positive|negative|neutral` signals per claim/page.
2. `GET /v1/mcp/retrieval/feedback/stats` exposes aggregate quality by claim.
3. Auto-publish policy can block autonomous approval when recent feedback is strongly negative (`retrieval_feedback_*` thresholds in routing policy).

Delivery layer:
1. `intelligence_delivery_targets` stores channel configs per project (`slack_webhook`, `email_smtp`).
2. `intelligence_delivery_attempts` stores immutable delivery outcomes for observability.
3. Scheduler runs generation + delivery in one pass (`run_intelligence_scheduler.py`).
4. Weekly digest mode provides rollup metrics and week-over-week trend breakdown for leadership reporting.

## 13. Moderation Audit Trail

Every approve/reject action is persisted to `moderation_actions` with:
1. actor (`reviewed_by`)
2. draft/claim/page linkage
3. decision transition (`before -> after`)
4. moderation payload and result metadata

UI timeline can read this stream via `/v1/wiki/moderation/actions`.
