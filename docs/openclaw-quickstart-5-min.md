# OpenClaw Quickstart (5 Minutes)

Last updated: 2026-04-02

Goal: connect OpenClaw runtime to Synapse and generate first wiki draft from real/seeded memory.

## 0. Prerequisites

- Python 3.10+
- local Synapse API (`http://localhost:8080`) or a reachable Synapse instance
- OpenClaw runtime object exposing hook + tool registration methods

## 1. Install SDK

```bash
pip install synapse-sdk
```

Repo-local development mode:

```bash
pip install -e packages/synapse-sdk-py
```

## 2. Attach Synapse To OpenClaw

```python
from synapse_sdk import Synapse

# Reads SYNAPSE_API_URL / SYNAPSE_PROJECT_ID / SYNAPSE_API_KEY.
synapse = Synapse.from_env()
synapse.attach(openclaw_runtime, integration="openclaw")
```

Registered runtime tools:
- `synapse_search_wiki`
- `synapse_propose_to_wiki`
- `synapse_get_open_tasks`
- `synapse_update_task_status`

Optional search override:

```python
synapse.attach(
    openclaw_runtime,
    integration="openclaw",
    openclaw_search_knowledge=lambda query, limit, filters: my_custom_search(query, limit, filters),
)
```

## 3. Day-0 Bootstrap Existing Runtime Memory

Default behavior: OpenClaw attach auto-enables `hybrid` bootstrap preset.

To override:

```python
synapse.attach(
    openclaw_runtime,
    integration="openclaw",
    openclaw_bootstrap_preset="runtime_memory",  # runtime_memory | event_log | hybrid
    openclaw_bootstrap_max_records=2000,
)
```

Or explicit batch API via SDK:

```python
from synapse_sdk import MemoryBackfillRecord

synapse.backfill_memory(
    [
        MemoryBackfillRecord(
            source_id="seed-1",
            content="BC Omega gate requires physical key-card after 10:00",
            entity_key="bc_omega",
            category="access",
        )
    ],
    source_system="openclaw_memory",
)
```

## 4. Verify Loop

Core acceptance:

```bash
./scripts/run_selfhost_core_acceptance.sh
```

OpenClaw + MCP integration check:

```bash
python scripts/integration_openclaw_mcp_runtime.py
```

## 5. Optional Demo Kit (Repo)

If you want a ready local fixture/runtime template:

```bash
python3 -m venv /tmp/synapse-onboarding-venv
source /tmp/synapse-onboarding-venv/bin/activate
pip install requests
PYTHONPATH=/Users/maksimborisov/synapse/packages/synapse-sdk-py/src \
python3 /Users/maksimborisov/synapse/demos/openclaw_onboarding/run_onboarding_demo.py
```

See:
- [OpenClaw Onboarding Kit](../demos/openclaw_onboarding/README.md)
