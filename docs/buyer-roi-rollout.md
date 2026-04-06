# Synapse Buyer One-Pager: Why Now, ROI, Rollout Modes

Last updated: 2026-04-04

## Why Now

Teams are moving from single chatbot pilots to multi-agent operational systems.
The bottleneck is no longer model quality. The bottleneck is **knowledge control**:

- runtime learnings disappear after sessions;
- static RAG docs drift from real operations;
- teams cannot safely govern what agents learn.

Synapse provides an L2 cognitive state layer: durable, reviewable, runtime-injectable knowledge.

## ROI Model (Practical)

Primary measurable outcomes:

1. Faster onboarding:
   - KPI: `time_to_first_useful_answer`
2. Better knowledge reuse:
   - KPI: `approved_drafts_total`, `published_knowledge_new`
3. Safer operations:
   - KPI: `rollback_rate`, `conflict_resolution_time`, `policy-safe publish ratio`
4. Lower support handling cost:
   - KPI: ticket resolution rate uplift after playbook publication

Suggested baseline calculation:

`weekly_value = (tickets_resolved_delta * avg_ticket_value) + (hours_saved * blended_hourly_cost) - synapse_operational_cost`

## Rollout Modes

1. `observe_only`:
   - capture events and insights; no runtime behavior change.
   - best for week-1 trust building.
2. `draft_only`:
   - generate wiki drafts + human moderation, still no autonomous publish.
   - best for policy-sensitive teams.
3. `retrieve_only`:
   - use Synapse wiki in runtime context injection, without writing back.
   - best for controlled retrieval adoption.
4. `full_loop`:
   - observe + synthesize + curate + execute.
   - best for mature teams with governance in place.

## Suggested 30-Day Rollout

Week 1:
- connect SDK in `observe_only`;
- run onboarding benchmark and capture baseline KPIs.

Week 2:
- switch to `draft_only` for process/policy domains;
- enable reviewer workflow in wiki.

Week 3:
- enable `retrieve_only` for selected intents (support runbooks, incident SOPs).

Week 4:
- enable `full_loop` with risk-tier guardrails and rollback readiness.

## Decision Checklist For Buyers

- Do we need humans in every publish step or risk-tiered auto-publish?
- Which domain owns source-of-truth per category?
- What KPI gates move us from `observe_only` to `full_loop`?
- What rollback SLO do we require before autonomous mode expansion?
