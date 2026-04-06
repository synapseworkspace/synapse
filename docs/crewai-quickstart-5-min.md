# CrewAI Quickstart (5 Minutes)

Last updated: 2026-04-04

Goal: attach Synapse to CrewAI execution flow and capture reusable process knowledge from task outcomes.

## 0. Prerequisites

- Python 3.10+
- reachable Synapse API (`http://localhost:8080` locally)
- CrewAI runtime/crew object

## 1. Install SDK

```bash
pip install synapseworkspace-sdk
```

Monorepo dev fallback:

```bash
pip install -e packages/synapse-sdk-py
```

## 2. Attach Synapse to CrewAI

```python
from synapse_sdk import Synapse

synapse = Synapse.from_env()
crew = build_crewai_runtime()

instrumented = synapse.attach(crew, integration="crewai")
result = instrumented.kickoff()
```

Native hook bind alternative:

```python
from synapse_sdk import bind_crewai

bind_crewai(crew, synapse=synapse)
result = crew.kickoff()
```

## 3. Optional Day-0 Bootstrap

```python
from synapse_sdk import MemoryBackfillRecord

synapse.backfill_memory(
    [
        MemoryBackfillRecord(
            source_id="crewai-seed-1",
            content="VIP complaints must be escalated to Tier-2 within 15 minutes.",
            entity_key="vip_support",
            category="escalation",
        )
    ],
    source_system="crewai_memory",
)
```

## 4. Verify Loop

```bash
./scripts/run_selfhost_core_acceptance.sh
```

Cookbook sample:

```bash
PYTHONPATH=packages/synapse-sdk-py/src python3 demos/cookbook/crewai_playbook_sync.py
```
