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

## CI Enforcement

`scripts/ci_checks.sh` runs:
1. MCP trend guardrail (`check_mcp_retrieval_trend.py`).
2. Core SLO threshold guardrail (`check_core_slo_guardrails.py`).

This gives deterministic pass/fail enforcement on latency/quality budgets in contributor flow.

## Next Reliability Steps

1. Add ingest latency SLO and moderation decision-latency SLO checks from live API snapshots.
2. Add error-budget policy (rolling 7d) and promotion gates.
3. Add load profile checks (steady, burst, degraded dependency scenarios).
4. Add incident runbooks linked to SLO violation codes.
