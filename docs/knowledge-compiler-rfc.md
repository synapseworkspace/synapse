# RFC: Synapse Knowledge Compiler v1

Status: Draft  
Date: 2026-04-04  
Owner: Synapse Core

## Problem

When teams connect existing agent memory, raw event streams (orders, invoices, status updates, telemetry) can dominate Wiki output.  
This breaks the main promise of Synapse: useful, curated, reusable corporate knowledge.

## Goal

Make Synapse write *knowledge*, not *event noise*, by default across any integration (OpenClaw, LangGraph, CrewAI, custom runtimes).

## Architecture (Compiler Pipeline)

1. Raw Events (runtime + backfill)  
2. Utility Gate (noise rejection + signal scoring)  
3. Claim Proposals (eligible candidates only)  
4. Draft Changes (page/section/diff proposals)  
5. Published Wiki (approved or policy-driven auto-publish)

## Utility Gate (Core Rules)

Deterministic policy checks:
- hard deny by keyword on `category`, `source_system`, `source_type`, `entity_key`, `source_id`;
- event-stream shape detection (keyword hits, numeric ratio, key/value density);
- durable-signal requirement (policy/process/preference/incident/runbook semantics);
- backfill-specific low-signal rejection before claim enqueue.

Project-tunable `routing_policy` keys:
- `blocked_*_keywords` (including `blocked_source_id_keywords`);
- `event_stream_min_*` thresholds;
- `durable_signal_keywords`;
- `min_durable_signal_hits`;
- `min_durable_signal_hits_for_backfill`.

## Human Control Model

Default publish mode remains configurable:
- `auto_publish` for autonomous teams with rollback;
- `human_required` for strict moderation teams;
- `conditional` for hybrid.

Regardless of mode, all accepted edits preserve audit trail and rollback path.

## LLM Role

LLM assistance is optional and secondary:
- deterministic policy/gate checks run first;
- LLM can re-rank/adjust near-boundary cases;
- LLM never bypasses routing hard blocks.

## Rollout

Phase 1 (now):
- deterministic Utility Gate hardening;
- source-id + payload-shape suppression;
- unit tests for noisy backfill and valid policy facts.

Phase 2:
- assertion classes (`policy`, `preference`, `incident`, `event`);
- per-class publish matrix and confidence calibration.

Phase 3:
- retrieval feedback loop (accepted/rejected context usefulness);
- adaptive policy suggestions from real usage.

## Success Metrics

- <= 10% of new drafts classified as raw event noise.
- >= 70% of approved drafts reused in retrieval within 14 days.
- median time-to-first-useful-page after onboarding <= 15 minutes.
- rollback-safe autonomous mode in production without wiki bloat regressions.
