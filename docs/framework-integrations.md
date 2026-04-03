# Framework Integrations

Last updated: 2026-04-03

This page tracks integration maturity for major agent frameworks.

## Current Integration Matrix

| Framework | Status | Notes |
| --- | --- | --- |
| OpenClaw | Production path | Native runtime connector, tool wiring, bootstrap presets, provenance chain. |
| LangGraph | Supported | Monitor/attach wrappers plus native callback binding helpers (`bind_langgraph`). |
| CrewAI | Supported | Monitor/attach wrappers plus native event/step hook helpers (`bind_crewai`). |
| LangChain | Supported | Auto-detection + monitor wrappers, plus native callback binding (`langchain_callback_handler`, `bind_langchain`). |

Cookbook-backed examples:
- OpenClaw: `demos/cookbook/openclaw_playbook_sync.py`
- LangGraph: `demos/cookbook/langgraph_playbook_sync.py`
- LangChain: `demos/cookbook/langchain_playbook_sync.py`
- CrewAI: `demos/cookbook/crewai_playbook_sync.py`

## Version Compatibility (Adapter Level)

These ranges describe compatibility targets for Synapse adapter surfaces (hook/monitor APIs), not framework-internal feature parity.

| Framework | Target version range | Verification mode |
| --- | --- | --- |
| LangGraph | `>=0.2,<1.0` | Adapter contract checks + cookbook snapshot regression |
| LangChain | `>=0.1,<1.0` | Adapter contract checks + cookbook snapshot regression |
| CrewAI | `>=0.70,<1.0` | Adapter contract checks + cookbook snapshot regression |
| OpenClaw | `>=0.1,<1.0` | Runtime contract matrix + OpenClaw MCP integration checks |

## Integration Contract Guarantees

1. One-line attach path is available through `Synapse.attach(...)`.
2. Captured events are tagged by integration (`integration:<name>`).
3. `trace_id` / `span_id` propagation is preserved across monitored call chains.
4. Integration contracts are validated in CI with offline smoke checks:
   - TypeScript attach/detection smoke in `scripts/ci_checks.sh`.
   - Python adapter contract check: `scripts/check_framework_adapter_contracts.py`.
   - Python native binding contract check: `scripts/check_framework_native_bindings.py`.

## Python Quick Examples

```python
from synapse_sdk import Synapse

synapse = Synapse.from_env()

# LangGraph-like runnable
graph = synapse.attach(my_graph)  # auto-detect -> langgraph

# LangChain-like runnable
chain = synapse.attach(my_chain)  # auto-detect -> langchain

# CrewAI-like runtime
crew = synapse.attach(my_crew)  # auto-detect -> crewai
```

You can force integration mode when needed:

```python
synapse.attach(my_runner, integration="langchain")
```

## TypeScript Quick Examples

```ts
import { Synapse } from "@synapseworkspace/sdk";

const synapse = Synapse.fromEnv();

const graph = synapse.attach(myGraph); // langgraph
const chain = synapse.attach(myChain); // langchain
const crew = synapse.attach(myCrew);   // crewai
```

To override:

```ts
synapse.attach(myRunner, { integration: "langchain" });
```
