# Synapse Cookbook (Python)

Three runnable cookbook scenarios for common adoption paths.

## Which Example Should I Run?

1. **OpenClaw operators / runtime integration:** `openclaw_playbook_sync.py`
2. **Backend + SQL-heavy ops teams:** `sql_ops_guardrails.py`
3. **Support/CRM workflow teams:** `support_ops_triage.py`

Estimated time per example: 2-4 minutes.

## Prerequisites

```bash
cd /Users/maksimborisov/synapse
python3 -m venv /tmp/synapse-cookbook-venv
source /tmp/synapse-cookbook-venv/bin/activate
pip install requests
```

Each example runs offline with in-memory transport (no API/DB required).

Need a dedicated OpenClaw day-0 onboarding flow instead of cookbook scenarios?
- Start with `/Users/maksimborisov/synapse/docs/openclaw-quickstart-5-min.md`.
- For local fixture details, see `/Users/maksimborisov/synapse/demos/openclaw_onboarding/README.md`.

## 1) Synapse + OpenClaw

```bash
PYTHONPATH=/Users/maksimborisov/synapse/packages/synapse-sdk-py/src \
python3 /Users/maksimborisov/synapse/demos/cookbook/openclaw_playbook_sync.py
```

Shows:
- OpenClaw runtime attachment (`attach(..., integration="openclaw")`)
- Hook capture + tool usage (`search_wiki`, `propose_to_wiki`)
- Backfill bootstrap from historical memory
- Quick success signal: output includes proposed claim payload and backfill acceptance.

## 2) Synapse + SQL

```bash
PYTHONPATH=/Users/maksimborisov/synapse/packages/synapse-sdk-py/src \
python3 /Users/maksimborisov/synapse/demos/cookbook/sql_ops_guardrails.py
```

Shows:
- SQL query result -> policy insight
- `collect_insight` wrapper around deterministic SQL logic
- Claim proposal pipeline with typed evidence
- Quick success signal: output includes extracted insight and proposal dispatch.

## 3) Synapse + Support Ops

```bash
PYTHONPATH=/Users/maksimborisov/synapse/packages/synapse-sdk-py/src \
python3 /Users/maksimborisov/synapse/demos/cookbook/support_ops_triage.py
```

Shows:
- Custom extractor plugin for escalation signals
- Custom synthesizer plugin for confidence normalization
- Support ticket triage to reusable knowledge proposals
- Quick success signal: output includes escalation-classified claim proposals.
