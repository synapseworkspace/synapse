# OpenClaw Onboarding Kit (5 Minutes)

Canonical onboarding path: `/Users/maksimborisov/synapse/docs/openclaw-quickstart-5-min.md`

Production-like local starter for Synapse x OpenClaw integration:
- runtime connector template (`runtime_template.py`);
- seed dataset for day-0 memory bootstrap (`dataset/openclaw_seed_memory.jsonl`);
- runnable onboarding scenario (`run_onboarding_demo.py`).

## Run

```bash
cd /Users/maksimborisov/synapse
python3 -m venv /tmp/synapse-onboarding-venv
source /tmp/synapse-onboarding-venv/bin/activate
pip install requests
PYTHONPATH=/Users/maksimborisov/synapse/packages/synapse-sdk-py/src \
python3 /Users/maksimborisov/synapse/demos/openclaw_onboarding/run_onboarding_demo.py
```

Expected outcome:
- OpenClaw hooks captured by Synapse observer.
- Wiki/task tools auto-registered (`synapse_search_wiki`, `synapse_propose_to_wiki`, task tools).
- Initial memory is backfilled in one call.
- A draft proposal is emitted with evidence metadata.

## Customize for real runtime

1. Copy `runtime_template.py` into your OpenClaw plugin package and map `on/register_tool` to your real runtime object.
2. Replace local search callback in `run_onboarding_demo.py` with MCP-backed search (`MCPContextHelper.make_openclaw_search_callback(...)`).
3. Replace in-memory transport with API transport by removing custom `MemoryTransport` and pointing `SynapseConfig.api_url` to your Synapse API.
