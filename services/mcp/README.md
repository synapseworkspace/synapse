# synapse-mcp

MCP runtime server that exposes published Synapse knowledge to agent frameworks.

## Tools

1. `search_knowledge`
- Semantic search over approved statements with optional filters (`entity_key`, `category`, `page_type`) and graph hint (`related_entity_key`).
- Graph-aware mode performs up to 3-hop traversal over `wiki_pages.metadata.related_entities` and adds hop-based relevance boost.
- Per-result explainability payload includes:
  - `retrieval_reason`,
  - `score_breakdown.total|lexical|graph`,
  - `score_breakdown.lexical_components` (token overlap and exact/phrase match signals),
  - `retrieval_confidence` + `confidence_breakdown`,
  - `context_policy` eligibility markers (`eligible`, `blocked_by`, thresholds).
- Optional context policy controls:
  - `context_policy_mode=off|advisory|enforced`
  - `min_retrieval_confidence`
  - `min_total_score`
  - `min_lexical_score`
  - `min_token_overlap_ratio`

2. `get_entity_facts`
- Retrieve current facts for a specific entity (for deterministic context injection).

3. `get_recent_changes`
- Recent moderation and publish activity (`moderation_actions` + `knowledge_snapshots`).

4. `explain_conflicts`
- Explain contradiction items with claim/statement evidence context.

5. `get_open_tasks`
- Active execution queue (`todo`, `in_progress`, `blocked`) for a project with optional `assignee` / `entity_key` filters.

6. `get_task_details`
- Full task context: metadata + timeline events + linked entities (`claim`, `draft`, `page`, `event`, `external`).

## Runtime cache + invalidation

- Read cache is project-scoped and TTL-based (default: `5s`).
- Before each tool response, server checks latest project revision:
  - newest `knowledge_snapshots` record;
  - fallback to latest `wiki_pages.updated_at` for projects without snapshots.
- If revision changed, cache is invalidated immediately for that project.

Env vars:
- `DATABASE_URL` (default `postgresql://synapse:synapse@localhost:55432/synapse`)
- `SYNAPSE_MCP_CACHE_TTL_SEC` (default `5`)
- `SYNAPSE_MCP_CACHE_MAX_ENTRIES` (default `5000`)
- `SYNAPSE_MCP_GRAPH_MAX_HOPS` (default `3`)
- `SYNAPSE_MCP_GRAPH_BOOST_HOP1` (default `0.20`)
- `SYNAPSE_MCP_GRAPH_BOOST_HOP2` (default `0.12`)
- `SYNAPSE_MCP_GRAPH_BOOST_HOP3` (default `0.06`)
- `SYNAPSE_MCP_GRAPH_BOOST_OTHER` (default `0.03`)
- `SYNAPSE_MCP_CONTEXT_POLICY_MODE` (default `advisory`)
- `SYNAPSE_MCP_CONTEXT_MIN_CONFIDENCE` (default `0.45`)
- `SYNAPSE_MCP_CONTEXT_MIN_TOTAL_SCORE` (default `0.20`)
- `SYNAPSE_MCP_CONTEXT_MIN_LEXICAL_SCORE` (default `0.08`)
- `SYNAPSE_MCP_CONTEXT_MIN_TOKEN_OVERLAP_RATIO` (default `0.15`)
- `SYNAPSE_MCP_TRANSPORT` (`stdio` by default, also `http`/`streamable-http`)
- `SYNAPSE_MCP_HOST` / `SYNAPSE_MCP_PORT` for HTTP transports

## Run locally

```bash
cd services/mcp
python -m venv .venv && source .venv/bin/activate
pip install -e .
PYTHONPATH=. python scripts/run_mcp_server.py --transport stdio
```

Retrieval regression evaluator:

```bash
PYTHONPATH=services/mcp python scripts/eval_mcp_retrieval_regression.py --dataset eval/mcp_retrieval_cases.json
```

MCP/API retrieval parity smoke:

```bash
python3 scripts/check_mcp_api_retrieval_parity.py
```

Latency/quality benchmark on seeded production-like snapshot:

```bash
PYTHONPATH=services/mcp python scripts/benchmark_mcp_retrieval.py \
  --project-id mcp_bench \
  --replace \
  --seed-pages 1200 \
  --statements-per-page 3 \
  --iterations 200
```

Weekly trend monitor (history + regression alerts):

```bash
PYTHONPATH=services/mcp python scripts/check_mcp_retrieval_trend.py \
  --run-benchmark \
  --project-id mcp_bench \
  --replace \
  --append-history \
  --history-file eval/mcp_retrieval_benchmark_history.jsonl
```
