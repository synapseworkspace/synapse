# Adopting Synapse in Existing Memory Stacks

This guide is for teams that already run production agent memory (for example `memory_items`, `ops_kb_items`, custom MCP services) and want to add Synapse without replacing what already works.

## Core Principle

Do **not** replace existing memory first.  
Run Synapse as a **knowledge synthesis and governance layer**:
- existing memory stays source for runtime/episodic state;
- Synapse ingests + synthesizes + moderates;
- approved wiki knowledge becomes policy-grade context for retrieval.

## Coexistence Modes

`Synapse.attach(..., adoption_mode=...)` (Python) / `adoptionMode` (TypeScript):

- `observe_only`:
  - capture/ingest from runtime;
  - no OpenClaw runtime tools registered;
  - safest Day-0 mode.
- `draft_only`:
  - capture + `propose_to_wiki`;
  - no retrieval tool injection yet;
  - good for moderation calibration.
- `retrieve_only`:
  - retrieval/search tools only;
  - no capture hooks/bootstrap writes;
  - use for shadow retrieval checks.
- `full_loop`:
  - full observe -> synthesize -> curate -> execute loop.

## Source Ownership Policy

Define one write-master per knowledge domain:

- `runtime_memory`: existing system is write-master; Synapse is ingest/synthesis consumer.
- `ops_kb_static`: existing system is write-master (or mirrored); Synapse references.
- `synapse_wiki`: Synapse is write-master for approved operational knowledge.

If two systems can mutate the same domain, expect source-of-truth drift.

## Recommended Rollout

1. `observe_only`:
   - enable attach in production;
   - collect drafts and conflict signals;
   - keep agent behavior unchanged.
2. `draft_only`:
   - enable proposal path;
   - moderate drafts and tune gatekeeper thresholds.
3. `retrieve_only` shadow:
   - enable retrieval tools in controlled slice;
   - compare answer quality with existing retrieval path.
4. `full_loop`:
   - enable category-by-category;
   - use publish policy (`human_required|conditional|auto_publish`) by risk level.

## CLI Workflow

Generate a migration plan + snippet:

```bash
synapse-cli adopt \
  --dir . \
  --memory-system ops_kb_items \
  --memory-source hybrid \
  --adoption-mode observe_only \
  --sample-file ./memory_export.jsonl
```

Generate attach snippet directly:

```bash
synapse-cli connect openclaw --dir . --adoption-mode observe_only
```

## Operational Guardrails

- Keep `source_id` stable for idempotent backfill and dedup safety.
- Keep provenance metadata enabled (`synapse_provenance`) for auditability.
- Start with `human_required` publish mode, then open `conditional/auto_publish` only for low-risk categories.
- Track moderation latency and conflict rates before enabling full-loop rollout.
