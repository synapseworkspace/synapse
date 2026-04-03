# synapseworkspace-sdk

Universal Python SDK for Synapse.

Compatibility note:
- `synapse_sdk.init(...)` is deprecated and will be removed in a future major release.
- Prefer `Synapse(...)` constructor directly.

## Example

```python
from synapse_sdk import RetryConfig, Synapse, SynapseConfig

synapse = Synapse(
    SynapseConfig(
        api_url="http://localhost:8080",
        project_id="water_delivery_logistics",
        retry=RetryConfig(max_retries=4, timeout_seconds=8.0),
        degradation_mode="buffer",  # "buffer" | "drop" | "sync_flush"
    )
)

synapse.capture(
    event_type="agent_message",
    payload={"text": "Omega gate now requires access cards"},
)

synapse.flush()
```

`flush()` is loss-safe: if delivery fails, events are restored back to the in-memory queue.

## Graceful Degradation Modes

`SynapseConfig.degradation_mode` (or `synapse.set_degradation_mode(...)`) controls behavior when transport is unavailable:
- `buffer` (default): queue failed events/claims/backfill chunks and retry on next `flush()`.
- `drop`: never raise for transport failures, drop unsent payloads.
- `sync_flush`: run `flush()` automatically after each `capture()` (best-effort, non-throwing).

## Framework Adapters

```python
# LangGraph / generic runnable wrappers
monitored_graph = synapse.monitor_langgraph(graph)
result = monitored_graph.invoke({"input": "hello"})

# LangChain-like runnable wrappers
monitored_chain = synapse.monitor_langchain(chain)
result = monitored_chain.invoke({"input": "hello"})

# CrewAI wrappers
monitored_crew = synapse.monitor_crewai(crew)
result = monitored_crew.kickoff()
```

Native binding helpers (callbacks/event hooks):

```python
# LangChain: native callback handler + bind
handler = synapse.langchain_callback_handler(session_id="langchain-session-1")
chain = synapse.bind_langchain(chain, handler=handler, fallback_monitor=True)

# LangGraph: same native callback pipeline with langgraph integration tag
graph = synapse.bind_langgraph(graph, fallback_monitor=True)

# CrewAI: register native event/step hooks + optional monitor wrapper
crew = synapse.bind_crewai(crew, monitor_runtime=True)
```

If native surfaces are not available on target runtime, `bind_langchain(..., fallback_monitor=True)` falls back to monitor wrappers.

You can also use a generic adapter:

```python
monitored_runner = synapse.monitor(
    runner,
    integration="generic",
    include_methods=["run", "execute"],
)
```

All captured events inside monitored call chains include propagated `trace_id` / `span_id`.

## Decorator: collect_insight

```python
@synapse.collect_insight(category="delivery_rules")
def check_gate_access(building_id: str) -> str:
    return "Gate closed: needs physical key-card"

check_gate_access("bc_omega")
```

This decorator runs extractor plugins on function result and auto-submits typed claim proposals.

## Extractor Plugins

```python
from synapse_sdk import ExtractedInsight, InsightContext

class CustomExtractor:
    name = "custom_rules"

    def extract(self, context: InsightContext):
        text = str(context.result)
        if "priority" in text.lower():
            return [ExtractedInsight(claim_text=text, category="operations", confidence=0.9)]
        return []

synapse.register_extractor(CustomExtractor())
```

## Synthesizer Plugins

```python
from synapse_sdk import ExtractedInsight, SynthesisContext

class ConfidenceFloorSynthesizer:
    name = "confidence_floor"
    contract_version = "v1"

    def synthesize(self, context: SynthesisContext):
        out = []
        for item in context.extracted_insights:
            confidence = item.confidence if item.confidence is not None else 0.0
            out.append(
                ExtractedInsight(
                    claim_text=item.claim_text,
                    category=item.category,
                    entity_key=item.entity_key,
                    confidence=max(confidence, 0.8),
                    metadata=dict(item.metadata),
                )
            )
        return out

synapse.register_synthesizer(ConfidenceFloorSynthesizer())
```

Synthesizers run after extractors and before claim proposal submission.
Use `list_synthesizers()` / `unregister_synthesizer(name)` for lifecycle management.

## Introspection / Debug Mode

```python
synapse.set_debug_mode(True)

# ... run monitored or collect_insight flows ...
records = synapse.get_debug_records(limit=20)
for item in records:
    print(item["event"], item["details"])
```

Debug records are structured JSON-like entries (`event`, `trace_id`, `details`) suitable for machine parsing.

## OpenTelemetry Bridge

```python
from synapse_sdk import Synapse, SynapseConfig, build_opentelemetry_bridge

# Optional dependency: pip install "synapseworkspace-sdk[otel]"
from opentelemetry import metrics, trace

synapse = Synapse(SynapseConfig(api_url="http://localhost:8080", project_id="water_delivery_logistics"))
bridge = build_opentelemetry_bridge(
    project_id=synapse.project_id,
    tracer=trace.get_tracer("synapse-sdk"),
    meter=metrics.get_meter("synapse-sdk"),
)
synapse.set_telemetry_sink(bridge)
```

The bridge maps SDK lifecycle events to OTel counters/histograms and operation spans.
Export to Datadog/Prometheus is handled by your standard OpenTelemetry collector/exporter pipeline.
Starter dashboards and local collector stack: `/Users/maksimborisov/synapse/docs/sdk-trace-observability.md`.

## OpenClaw Connector

```python
import os

from synapse_sdk import OpenClawConnector

connector = OpenClawConnector(
    synapse,
    search_knowledge=lambda query, limit, filters: knowledge_service.search(query, limit=limit, filters=filters),
    provenance_secret=os.getenv("SYNAPSE_OPENCLAW_PROVENANCE_SECRET"),
    provenance_key_id="ops-key-2026-04",
)
connector.attach(openclaw_runtime)
```

Facade shortcut:

```python
synapse.attach(
    openclaw_runtime,
    integration="openclaw",
    openclaw_bootstrap_preset="hybrid",  # runtime_memory | event_log | hybrid
    adoption_mode="observe_only",  # full_loop | observe_only | draft_only | retrieve_only
    openclaw_bootstrap_max_records=2000,
)
```

`adoption_mode` helps safe rollout into mature stacks:
- `observe_only`: capture/ingest only, no runtime tools.
- `draft_only`: propose facts, keep retrieval behavior unchanged.
- `retrieve_only`: retrieval tools only, no capture/bootstrap writes.
- `full_loop`: full observe -> synthesize -> execute loop.

Preset metadata helpers:

```python
from synapse_sdk import build_openclaw_bootstrap_options, list_openclaw_bootstrap_presets

print(list_openclaw_bootstrap_presets())
manual = build_openclaw_bootstrap_options(preset="event_log", max_records=500)
synapse.attach(openclaw_runtime, integration="openclaw", bootstrap_memory=manual)
```

After `attach(...)`, connector registers:
- `synapse_search_wiki`
- `synapse_propose_to_wiki`
- `synapse_get_open_tasks`
- `synapse_update_task_status`

and subscribes to configured OpenClaw runtime hook events.

`synapse_propose_to_wiki` writes signed provenance into:
- `claim.metadata["synapse_provenance"]`
- `claim.evidence[0].provenance`

If no provenance secret is configured, connector falls back to digest-only mode.

When `bootstrap_memory` is set, `attach(...)` also imports existing runtime memory via `/v1/backfill/memory` before normal live monitoring starts.

## Task Core Helpers

```python
from synapse_sdk import Task, TaskComment, TaskLink

created = synapse.upsert_task(
    Task(
        title="Verify Omega gate policy",
        description="Confirm card-only access after 10:00",
        priority="high",
        entity_key="bc_omega",
        category="access_policy",
    ),
    created_by="ops_manager",
)
task_id = str(created["task"]["id"])

synapse.update_task_status(task_id, status="in_progress", updated_by="ops_manager")
synapse.comment_task(task_id, created_by="ops_manager", comment=TaskComment(comment="Driver confirmed at gate."))
synapse.link_task(task_id, created_by="ops_manager", link=TaskLink(link_type="draft", link_ref="draft-id-123"))
```

Helpers map to core Task API endpoints (`/v1/tasks*`) with idempotent writes.

## MCP Context Injection Helper

```python
from synapse_sdk import MCPContextHelper, OpenClawConnector

def call_mcp_tool(tool_name: str, arguments: dict):
    # replace with your MCP client invocation
    return mcp_client.call_tool(tool_name, arguments)

helper = MCPContextHelper(
    project_id="water_delivery_logistics",
    call_tool=call_mcp_tool,
    default_context_policy_profile="enforced",  # advisory | enforced | strict_enforced
)

context_md = helper.build_context_markdown(
    query="How should we deliver to BC Omega?",
    entity_key="bc_omega",
    include_recent_changes=True,
)
print(context_md)

connector = OpenClawConnector(
    synapse,
    search_knowledge=helper.make_openclaw_search_callback(
        default_filters={"entity_key": "bc_omega"},
        context_policy_profile="enforced",
    ),
)
connector.attach(openclaw_runtime)
```

This helper standardizes MCP tool payloads and returns stable search/facts/change context for prompt injection.
Use `list_context_policy_profiles()` to inspect available profile defaults.

## Bootstrap Existing Agent Memory

```python
from synapse_sdk import MemoryBackfillRecord

batch_id = synapse.backfill_memory(
    records=[
        MemoryBackfillRecord(
            source_id="dialog-12",
            content="BC Omega gate switched to card-only access after 10:00",
            entity_key="bc_omega",
            category="access",
            observed_at="2026-03-30T08:10:00Z",
        ),
        MemoryBackfillRecord(
            source_id="driver-note-77",
            content="Driver Sidorov does not accept orders after 17:00",
            entity_key="driver_sidorov",
            category="operations",
        ),
    ],
    source_system="openclaw_memory",
    created_by="bootstrap_job",
    chunk_size=100,
)
print("Backfill batch:", batch_id)
```

This sends historical memory into `/v1/backfill/memory` and marks the final chunk as `finalize=true`.

You can also do this during `attach(...)`:

```python
from synapse_sdk import BootstrapMemoryOptions

synapse.attach(
    existing_agent,
    bootstrap_memory=BootstrapMemoryOptions(
        records=[
            "Warehouse #1 is temporarily closed for sanitation.",
            {
                "source_id": "dialog-12",
                "content": "BC Omega gate switched to card-only access after 10:00",
                "entity_key": "bc_omega",
                "category": "access",
            },
        ],
        source_system="agent_runtime_memory",
        created_by="sdk_attach",
    ),
)
```

## Cookbook Examples

See runnable scenarios in:
- `/Users/maksimborisov/synapse/demos/cookbook/openclaw_playbook_sync.py`
- `/Users/maksimborisov/synapse/demos/cookbook/sql_ops_guardrails.py`
- `/Users/maksimborisov/synapse/demos/cookbook/support_ops_triage.py`

## synapse-cli

`synapse-cli` provides local extraction simulation, trace replay, and readiness diagnostics.

```bash
synapse-cli extract --text "BC Omega gate now requires access cards" --category access_policy --entity-key bc_omega --pretty
```

```bash
synapse-cli replay --input ./debug_records.jsonl --trace-id 5fe2... --json
```

```bash
synapse-cli doctor --api-url http://localhost:8080 --project-id omega_demo --strict
```

```bash
synapse-cli init --dir . --project-id omega_demo --api-url http://localhost:8080
```

```bash
synapse-cli connect openclaw --dir . --env-file .env.synapse
```

```bash
synapse-cli adopt --dir . --memory-system ops_kb_items --memory-source hybrid --adoption-mode observe_only --sample-file ./memory_export.jsonl
```
