# Agentic Onboarding Benchmark Kit

Last updated: 2026-04-04

Goal: reproduce day-0 support onboarding metrics (`first useful answer`, `first approved draft`, `first policy-safe publish`) with a deterministic dataset.

## Run In One Command

```bash
python3 scripts/benchmark_agentic_onboarding.py --scenario all --summary-only
```

JSON output:

```bash
python3 scripts/benchmark_agentic_onboarding.py --scenario all --summary-only --json
```

## Included Scenarios

- `baseline_static`: no Synapse capture/publish loop (seed memory only).
- `synapse_balanced`: default autonomous mode with risk-tier guardrails.
- `synapse_human_required`: strict moderation mode.

## KPI Cards

The benchmark emits these KPI cards per scenario:

- `first_useful_answer`
- `first_approved_draft`
- `first_policy_safe_publish`

Each card includes `ticket_index` and simulated `minutes`.

## CI Gate Example

Use deterministic thresholds for regression guardrails:

```bash
python3 scripts/benchmark_agentic_onboarding.py \
  --scenario all \
  --summary-only \
  --min-balanced-useful-rate 0.40 \
  --max-balanced-first-approved-minutes 40 \
  --min-balanced-published-new 4
```

## Dataset

- default dataset: [`eval/agentic_onboarding_cases.json`](../eval/agentic_onboarding_cases.json)
- shape: support tickets with required knowledge plus discovery evidence events.

You can replace the dataset via `--dataset` for domain-specific onboarding baselines.
