# LangGraph Quickstart (5 Minutes)

Last updated: 2026-04-04

Goal: attach Synapse to an existing LangGraph runnable and capture first reusable knowledge draft.

## 0. Prerequisites

- Python 3.10+
- reachable Synapse API (`http://localhost:8080` for local stack)
- LangGraph runnable with `invoke`/`ainvoke`

## 1. Install SDK

```bash
pip install synapseworkspace-sdk
```

Monorepo dev fallback:

```bash
pip install -e packages/synapse-sdk-py
```

## 2. Attach Synapse to LangGraph

```python
from synapse_sdk import Synapse

synapse = Synapse.from_env()
graph = build_langgraph_runnable()

instrumented = synapse.attach(graph, integration="langgraph")
result = instrumented.invoke({"input": "How should dispatch handle BC Omega access?"})
```

## 3. Optional Day-0 Bootstrap

```python
from synapse_sdk import MemoryBackfillRecord

synapse.backfill_memory(
    [
        MemoryBackfillRecord(
            source_id="lg-seed-1",
            content="BC Omega requires key-card after 10:00.",
            entity_key="bc_omega",
            category="access",
        )
    ],
    source_system="langgraph_memory",
)
```

## 4. Verify Loop

```bash
./scripts/run_selfhost_core_acceptance.sh
```

Cookbook sample:

```bash
PYTHONPATH=packages/synapse-sdk-py/src python3 demos/cookbook/langgraph_playbook_sync.py
```
