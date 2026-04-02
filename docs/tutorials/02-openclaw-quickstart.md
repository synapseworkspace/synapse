# Tutorial: OpenClaw Quickstart

Goal: attach Synapse to OpenClaw runtime and expose wiki/task tools.

Shortcut (snippet generator):

```bash
synapse-cli connect openclaw --dir . --env-file .env.synapse
```

## 1. Initialize SDK

```python
from synapse_sdk import Synapse, SynapseConfig

synapse = Synapse(
    SynapseConfig(
        api_url="http://localhost:8080",
        project_id="omega_demo",
    )
)
```

## 2. Attach connector

```python
from synapse_sdk import OpenClawConnector

connector = OpenClawConnector(
    synapse,
    search_knowledge=lambda query, limit, filters: [],
)
connector.attach(openclaw_runtime)
```

Registered tools include:
- `synapse_search_wiki`
- `synapse_propose_to_wiki`
- `synapse_get_open_tasks`
- `synapse_update_task_status`

## 3. Optional MCP-backed search callback

```python
from synapse_sdk import MCPContextHelper

helper = MCPContextHelper(
    project_id="omega_demo",
    call_tool=lambda name, args: mcp_client.call_tool(name, args),
)
connector = OpenClawConnector(
    synapse,
    search_knowledge=helper.make_openclaw_search_callback(default_filters={"entity_key": "bc_omega"}),
)
connector.attach(openclaw_runtime)
```

## 3.1 Optional day-0 memory bootstrap on attach

```python
synapse.attach(
    openclaw_runtime,
    integration="openclaw",
    openclaw_bootstrap_preset="hybrid",  # runtime_memory | event_log | hybrid
    openclaw_bootstrap_max_records=2000,
)
```

If you need full manual control (custom provider / static records), pass `bootstrap_memory=BootstrapMemoryOptions(...)` instead.

## 4. Validate end-to-end wiring

Run integration check:

```bash
python scripts/integration_openclaw_mcp_runtime.py
```

For a full day-0 onboarding path (runtime template + seed memory dataset), continue with:
- [OpenClaw Onboarding Kit (5 Minutes)](04-openclaw-onboarding-kit.md)
