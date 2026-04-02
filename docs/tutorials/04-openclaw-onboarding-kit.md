# Tutorial: OpenClaw Onboarding Kit (5 Minutes)

Goal: connect existing OpenClaw runtime to Synapse with minimal code and seed day-0 wiki drafts from historical memory.

## 1. Run the local onboarding scenario

```bash
cd /Users/maksimborisov/synapse
python3 -m venv /tmp/synapse-onboarding-venv
source /tmp/synapse-onboarding-venv/bin/activate
pip install requests
PYTHONPATH=/Users/maksimborisov/synapse/packages/synapse-sdk-py/src \
python3 /Users/maksimborisov/synapse/demos/openclaw_onboarding/run_onboarding_demo.py
```

You will see JSON summary with:
- registered OpenClaw tools;
- captured runtime events;
- proposed wiki claim;
- backfill batch id from historical memory import.

## 2. Use runtime template in your integration

Starter runtime contract lives here:

`/Users/maksimborisov/synapse/demos/openclaw_onboarding/runtime_template.py`

It matches connector expectations:
- hook registration: `on(event_name, handler)` or `register_hook(...)`;
- tool registration: `register_tool(name, handler, description?)`.

## 3. Seed your own historical memory on day 0

Edit dataset:

`/Users/maksimborisov/synapse/demos/openclaw_onboarding/dataset/openclaw_seed_memory.jsonl`

Supported rows:
- `{"kind":"memory", ...}` for bootstrap ingestion;
- `{"kind":"event", ...}` for runtime hook replay.

The demo calls `synapse.backfill_memory(...)` once and flushes.

For production runtime attach, you can bootstrap immediately with a preset:

```python
synapse.attach(
    openclaw_runtime,
    integration="openclaw",
    openclaw_bootstrap_preset="hybrid",
    openclaw_bootstrap_max_records=5000,
)
```

## 4. Move from local search to MCP search

Replace local callback with MCP helper:

```python
from synapse_sdk import MCPContextHelper, OpenClawConnector

helper = MCPContextHelper(
    project_id="your_project",
    call_tool=lambda name, args: mcp_client.call_tool(name, args),
)

connector = OpenClawConnector(
    synapse,
    search_knowledge=helper.make_openclaw_search_callback(
        default_filters={"entity_key": "bc_omega"},
    ),
)
connector.attach(openclaw_runtime)
```

## 5. Validate with live MCP runtime check

```bash
python /Users/maksimborisov/synapse/scripts/integration_openclaw_mcp_runtime.py
```

This script runs a real stdio MCP session and verifies connector + context injection end-to-end.
