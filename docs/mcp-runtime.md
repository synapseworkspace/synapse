# Synapse MCP Runtime

This document describes runtime retrieval for approved Synapse knowledge.

## Purpose

`services/mcp` exposes curated knowledge via MCP tools so agents can read the latest approved facts without prompt rewrites.

Implemented tools:
1. `search_knowledge`
2. `get_entity_facts`
3. `get_recent_changes`
4. `explain_conflicts`
5. `get_open_tasks`
6. `get_task_details`

`search_knowledge` supports graph hint `related_entity_key`:
- runtime builds an in-query undirected entity graph from `wiki_pages.metadata.related_entities`.
- recursive traversal expands neighbors up to 3 hops.
- results get hop-based boost (`1-hop: +0.20`, `2-hop: +0.12`, `3-hop: +0.06`).
- response includes `graph_hops` and `graph_boost` for introspection/debug.
- response also includes explainability fields per result:
  - `retrieval_reason` (human-readable reason trace),
  - `score_breakdown.total|lexical|graph`,
  - `score_breakdown.lexical_components.*` (token overlap + exact/phrase match signals),
  - `retrieval_confidence` with `confidence_breakdown.*`,
  - `context_policy` (`mode`, `eligible`, `blocked_by`, thresholds).

Operator diagnostics endpoint in API:
- `GET /v1/mcp/retrieval/explain?project_id=...&q=...&related_entity_key=...`
- returns MCP-compatible retrieval rows with the same explainability payload used by the web diagnostics panel.
- includes effective graph tuning snapshot in response body (`graph_config.max_graph_hops`, `boost_hop1|2|3|other`).
- includes effective context-injection policy snapshot in body (`context_policy.*`) plus `policy_filtered_out`.
- supports policy controls:
  - `context_policy_mode=off|advisory|enforced`
  - `min_retrieval_confidence`
  - `min_total_score`
  - `min_lexical_score`
  - `min_token_overlap_ratio`
- mirrors the same tuning snapshot in response headers:
  - `X-Synapse-Retrieval-Graph-Max-Hops`
  - `X-Synapse-Retrieval-Graph-Boost-Hop1`
  - `X-Synapse-Retrieval-Graph-Boost-Hop2`
  - `X-Synapse-Retrieval-Graph-Boost-Hop3`
  - `X-Synapse-Retrieval-Graph-Boost-Other`
  - `X-Synapse-Retrieval-Context-Policy-Mode`
  - `X-Synapse-Retrieval-Context-Min-Confidence`
  - `X-Synapse-Retrieval-Context-Min-Total-Score`
  - `X-Synapse-Retrieval-Context-Min-Lexical-Score`
  - `X-Synapse-Retrieval-Context-Min-Token-Overlap-Ratio`

## Data model usage

The runtime reads from:
1. `wiki_pages`, `wiki_statements`, `wiki_page_aliases`
2. `claims` (category enrichment via `claim_fingerprint`)
3. `moderation_actions`
4. `knowledge_snapshots`, `knowledge_snapshot_pages`
5. `wiki_conflicts`
6. `synapse_tasks`, `synapse_task_events`, `synapse_task_links`

Only `published` pages and `active` statements are returned by default.
Temporal guardrails are enforced (`valid_from`/`valid_to`).

## Cache invalidation path

Each request:
1. Reads the current project revision marker:
   - latest `knowledge_snapshots` record, or
   - fallback to `MAX(wiki_pages.updated_at)` if no snapshots exist.
2. Compares marker with in-memory project revision.
3. If changed, invalidates all cached entries for that project.
4. Executes query and caches response with TTL.

This guarantees publish-to-retrieval consistency without forcing every request to bypass cache.

## Retrieval quality regression

Deterministic evaluator dataset for MCP retrieval quality:

```bash
PYTHONPATH=services/mcp python scripts/eval_mcp_retrieval_regression.py --dataset eval/mcp_retrieval_cases.json
```

MCP/API retrieval parity smoke (shared SQL plan + explainability contract):

```bash
python3 scripts/check_mcp_api_retrieval_parity.py
```

## Retrieval latency benchmark

Use seeded production-like snapshot benchmark to tune graph weights and DB indexes:

```bash
PYTHONPATH=services/mcp python scripts/benchmark_mcp_retrieval.py \
  --project-id mcp_bench \
  --replace \
  --seed-pages 1200 \
  --statements-per-page 3 \
  --iterations 200 \
  --max-graph-hops 3 \
  --graph-boost-hop1 0.20 \
  --graph-boost-hop2 0.12 \
  --graph-boost-hop3 0.06
```

The output includes per-case `p50/p95/p99` and top-1 quality checks for one-hop and two-hop graph retrieval scenarios.

## Weekly trend monitor

Use trend check to compare latest benchmark against recent baseline and raise alert on measured regressions:

```bash
PYTHONPATH=services/mcp python scripts/check_mcp_retrieval_trend.py \
  --run-benchmark \
  --project-id mcp_bench \
  --replace \
  --append-history \
  --history-file eval/mcp_retrieval_benchmark_history.jsonl
```

Behavior:
- exits `0` when latency/quality are inside thresholds;
- exits `1` when regression alert is detected;
- suggests graph profile adjustments only when quality regression is actually measured;
- emits `recommended_context_policy_profile` (`profile`, `thresholds`, `reason`, SDK hints) for context-injection policy tuning.

## Context Policy Tuning Cookbook

Use `recommended_context_policy_profile` from trend output as the default runtime posture:

- `advisory`: keep full recall while diagnosing quality drops (no hard filtering).
- `enforced`: balanced production default (`min_retrieval_confidence=0.45`, `min_total_score=0.20`, `min_lexical_score=0.08`, `min_token_overlap_ratio=0.15`).
- `strict_enforced`: high-precision mode for stable/high-quality workloads (`0.60`, `0.30`, `0.10`, `0.20`).

Apply it in SDK helper defaults:

```python
helper = MCPContextHelper(
    project_id="omega_demo",
    call_tool=tool_caller,
    default_context_policy_profile="enforced",  # or advisory / strict_enforced
)
```

```ts
const helper = new MCPContextHelper(projectId, toolCaller, {
  defaultContextPolicyProfile: "enforced"
});
```

## Unified tuning advisor

For combined MCP + worker + queue recommendations, use:

```bash
python3 scripts/run_performance_tuning_advisor.py --project-id omega_demo
```

See full runbook: `/Users/maksimborisov/synapse/docs/performance-tuning.md`.

## Local run

```bash
cd services/mcp
python -m venv .venv && source .venv/bin/activate
pip install -e .
PYTHONPATH=. python scripts/run_mcp_server.py --transport stdio
```

HTTP transport:

```bash
SYNAPSE_MCP_TRANSPORT=streamable-http \
SYNAPSE_MCP_HOST=0.0.0.0 \
SYNAPSE_MCP_PORT=8091 \
PYTHONPATH=. python scripts/run_mcp_server.py
```
