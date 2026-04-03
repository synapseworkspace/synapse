# Reliability & SLO Guardrails

Last updated: 2026-04-03

This page defines baseline reliability checks for Synapse OSS runtime loops.

## Why This Exists

Feedback from early users is consistent:
- "no battle-tested infra"
- "no normal observability"
- "no SLA/latency control"

This runbook is the first hard guardrail layer to make reliability measurable and enforceable.

## Baseline SLO Targets (OSS)

| Signal | Target | Source |
| --- | --- | --- |
| MCP retrieval average p95 latency | <= 250ms | retrieval benchmark snapshot (`benchmark_mcp_retrieval.py`) |
| MCP retrieval per-case p95 latency | <= 450ms | same benchmark payload |
| MCP retrieval average top1 accuracy | >= 0.90 | same benchmark payload |
| Benchmark case coverage | >= 2 cases | same benchmark payload |
| Event ingest p95 latency | <= 1200ms | `/v1/events/throughput` snapshot |
| Event ingest p99 latency | <= 2500ms | `/v1/events/throughput` snapshot |
| Moderation decision p90 latency | <= 720 min | `/v1/wiki/moderation/throughput` snapshot |
| Moderation open backlog | <= 30 drafts | `/v1/wiki/moderation/throughput` snapshot |
| Moderation blocked conflicts | <= 10 drafts | `/v1/wiki/moderation/throughput` snapshot |

## Guardrail Script

Use:

```bash
python3 scripts/check_core_slo_guardrails.py \
  --benchmark-json eval/mcp_benchmark_latest_sample.json \
  --max-average-p95-ms 250 \
  --max-case-p95-ms 450 \
  --min-top1-accuracy 0.90 \
  --min-cases 2
```

Output contract:
- `status: ok` when all thresholds pass.
- `status: failed` with structured `violations[]` when thresholds are exceeded.

Operational guardrail:

```bash
python3 scripts/check_operational_slo_guardrails.py \
  --snapshot-json eval/operational_slo_snapshot_sample.json \
  --max-ingest-p95-ms 1200 \
  --max-ingest-p99-ms 2500 \
  --min-ingest-events 1 \
  --max-moderation-p90-minutes 720 \
  --max-moderation-open-backlog 30 \
  --max-moderation-blocked-conflicts 10
```

To capture live snapshots from running API:

```bash
python3 scripts/capture_operational_slo_snapshots.py \
  --api-base-url http://localhost:8080 \
  --project-id omega_demo \
  --window-hours 24 \
  --output eval/operational_slo_snapshot_latest.json
```

## CI Enforcement

`scripts/ci_checks.sh` runs:
1. MCP trend guardrail (`check_mcp_retrieval_trend.py`).
2. Core SLO threshold guardrail (`check_core_slo_guardrails.py`).
3. Operational SLO threshold guardrail (`check_operational_slo_guardrails.py`).

This gives deterministic pass/fail enforcement on latency/quality budgets in contributor flow.

Release error-budget gate (rolling policy):

```bash
python3 scripts/check_release_error_budget.py \
  --history-jsonl eval/reliability_error_budget_sample.jsonl \
  --window-days 7 \
  --min-samples 4 \
  --max-failure-rate 0.20 \
  --max-consecutive-failures 2
```

Degraded/load-profile drills:

```bash
python3 scripts/run_reliability_drills.py \
  --snapshot-json eval/operational_slo_snapshot_sample.json \
  --burst-latency-multiplier 1.35
```

`run_reliability_drills.py` includes:
- steady profile validation,
- burst load synthetic stress profile,
- degraded dependency detection profile.

## Next Reliability Steps

1. Expand release gate from fixture-backed checks to auto-appended live history snapshots per environment.
2. Add incident runbooks linked to SLO violation codes.
3. Add chaos-style dependency fault injection in pre-prod.
