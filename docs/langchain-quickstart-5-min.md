# LangChain Quickstart (5 Minutes)

Last updated: 2026-04-04

Goal: connect Synapse to a LangChain runnable/callback path and publish first operational draft.

## 0. Prerequisites

- Python 3.10+
- reachable Synapse API (`http://localhost:8080` locally)
- LangChain runnable or chain with callback support

## 1. Install SDK

```bash
pip install synapseworkspace-sdk
```

Monorepo dev fallback:

```bash
pip install -e packages/synapse-sdk-py
```

## 2. Attach Synapse to LangChain

```python
from synapse_sdk import Synapse

synapse = Synapse.from_env()
chain = build_langchain_runnable()

instrumented = synapse.attach(chain, integration="langchain")
response = instrumented.invoke({"input": "What is the current BC Omega gate policy?"})
```

Native callback bind alternative:

```python
from synapse_sdk import bind_langchain

bound_chain = bind_langchain(chain, synapse=synapse)
response = bound_chain.invoke({"input": "Summarize delivery constraints for BC Omega."})
```

## 3. Optional Day-0 Bootstrap

```python
from synapse_sdk import MemoryBackfillRecord

synapse.backfill_memory(
    [
        MemoryBackfillRecord(
            source_id="lc-seed-1",
            content="Chargeback refunds require risk review before payout.",
            entity_key="billing_chargeback",
            category="billing_policy",
        )
    ],
    source_system="langchain_memory",
)
```

## 4. Verify Loop

```bash
./scripts/run_selfhost_core_acceptance.sh
```

Cookbook sample:

```bash
PYTHONPATH=packages/synapse-sdk-py/src python3 demos/cookbook/langchain_playbook_sync.py
```
