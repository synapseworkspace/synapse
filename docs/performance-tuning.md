# Synapse Performance Tuning Runbook

Last updated: 2026-04-02

This runbook tunes core runtime behavior in three areas:
1. MCP retrieval graph knobs.
2. Worker sizing heuristics.
3. Queue control profiles.
4. MCP context-policy profile + thresholds.

The main entrypoint is:

```bash
python3 scripts/run_performance_tuning_advisor.py --project-id <project_id>
```

## 1) Run Advisor (JSON + Markdown report)

```bash
python3 scripts/run_performance_tuning_advisor.py \
  --project-id omega_demo \
  --database-url postgresql://synapse:synapse@localhost:55432/synapse \
  --window-hours 6 \
  --mcp-run-benchmark \
  --mcp-append-history \
  --write-report artifacts/perf/omega_demo.md \
  > artifacts/perf/omega_demo.json
```

What the advisor does:
1. Reads live queue metrics from Postgres (`claim_proposals`, `wiki_draft_changes`, `wiki_conflicts`).
2. Computes arrival/processing rates and backlog age.
3. Selects a queue profile (`conserve`, `balanced`, `burst`).
4. Recommends worker replicas using throughput + backlog-clear targets.
5. Runs MCP trend analysis (`scripts/check_mcp_retrieval_trend.py`) and suggests graph knobs.
6. Pulls trend-based `recommended_context_policy_profile` hints (`advisory|enforced|strict_enforced` + thresholds).
7. Produces ready-to-run apply commands.

## 2) Queue Profiles

`conserve` (steady/low traffic):
- `SYNAPSE_WORKER_SYNTHESIS_INTERVAL_SEC=20`
- `SYNAPSE_WORKER_SYNTHESIS_LIMIT=80`
- `SYNAPSE_WORKER_SYNTHESIS_EXTRACT_LIMIT=120`
- Queue controls: `worker_lag_sla_minutes=30`, `queue_depth_warn=60`

`balanced` (regular load):
- `SYNAPSE_WORKER_SYNTHESIS_INTERVAL_SEC=12`
- `SYNAPSE_WORKER_SYNTHESIS_LIMIT=140`
- `SYNAPSE_WORKER_SYNTHESIS_EXTRACT_LIMIT=240`
- Queue controls: `worker_lag_sla_minutes=20`, `queue_depth_warn=120`

`burst` (high backlog or high queue age):
- `SYNAPSE_WORKER_SYNTHESIS_INTERVAL_SEC=6`
- `SYNAPSE_WORKER_SYNTHESIS_LIMIT=260`
- `SYNAPSE_WORKER_SYNTHESIS_EXTRACT_LIMIT=420`
- Queue controls: `worker_lag_sla_minutes=10`, `queue_depth_warn=250`

## 3) Apply Recommendations

The advisor output contains four commands:
1. scale worker replicas;
2. apply queue control via API;
3. export MCP graph env knobs.
4. export context-policy profile/threshold hints.

Example:

```bash
docker compose --env-file .env.selfhost -f infra/docker-compose.selfhost.yml up -d --scale worker=2

curl -fsS -X PUT "http://localhost:8080/v1/gatekeeper/calibration/operations/throughput/control" \
  -H 'Content-Type: application/json' \
  -d '{"project_id":"omega_demo","worker_lag_sla_minutes":20,"queue_depth_warn":120,"updated_by":"synapse_perf_advisor"}'

export SYNAPSE_MCP_GRAPH_MAX_HOPS=3
export SYNAPSE_MCP_GRAPH_BOOST_HOP1=0.2000
export SYNAPSE_MCP_GRAPH_BOOST_HOP2=0.1200
export SYNAPSE_MCP_GRAPH_BOOST_HOP3=0.0600
export SYNAPSE_MCP_GRAPH_BOOST_OTHER=0.0300

export SYNAPSE_CONTEXT_POLICY_PROFILE=enforced
export SYNAPSE_CONTEXT_POLICY_MODE=enforced
export SYNAPSE_CONTEXT_MIN_RETRIEVAL_CONFIDENCE=0.4500
export SYNAPSE_CONTEXT_MIN_TOTAL_SCORE=0.2000
export SYNAPSE_CONTEXT_MIN_LEXICAL_SCORE=0.0800
export SYNAPSE_CONTEXT_MIN_TOKEN_OVERLAP_RATIO=0.1500
```

Then restart affected services:

```bash
docker compose --env-file .env.selfhost -f infra/docker-compose.selfhost.yml restart worker mcp
```

## 4) Validate After Tuning

Run acceptance and trend checks:

```bash
./scripts/integration_core_loop.py --worker-mode poll --mcp-probe-mode local
```

```bash
PYTHONPATH=services/mcp python3 scripts/check_mcp_retrieval_trend.py \
  --project-id mcp_bench \
  --history-file eval/mcp_retrieval_benchmark_history.jsonl
```

```bash
python3 scripts/check_queue_governance_policy.py --window-hours 24
```

## 5) Rollback

If regression appears:
1. revert MCP graph values to previous known-good env.
2. reduce worker scale to previous replica count.
3. reapply previous queue control thresholds.
4. rerun core acceptance and trend checks.
