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

When `bootstrap_memory` is set, `attach(...)` imports existing memory via the knowledge lane (`/v1/backfill/knowledge`) before normal live monitoring starts.

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

## Wiki Space Policy Helpers

```python
# Read current policy for a wiki space
policy = synapse.get_wiki_space_policy("operations")
print(policy["policy"]["metadata"].get("publish_checklist_preset"))

# Update only checklist preset while preserving write/comment/review policy fields
synapse.set_wiki_space_publish_checklist_preset(
    space_key="operations",
    preset="ops_standard",  # none | ops_standard | policy_strict
    updated_by="ops_admin",
    reason="Enable standard publish checklist for support rollout",
)

# Read policy audit history
audit = synapse.list_wiki_space_policy_audit("operations", limit=20)
print(len(audit.get("entries", [])))
```

These helpers map to `/v1/wiki/spaces/{space_key}/policy*` and are safe for programmatic governance automation.

## Wiki Lifecycle Telemetry Helpers

```python
# Read stale-page diagnostics (same contract as /v1/wiki/lifecycle/stats)
lifecycle_stats = synapse.get_wiki_lifecycle_stats(
    stale_days=21,
    critical_days=45,
    stale_limit=20,
    space_key="operations",
)
print(lifecycle_stats["counts"]["stale_warning_pages"])

# Push monotonic per-session action counters (delta is computed server-side)
synapse.snapshot_wiki_lifecycle_telemetry(
    session_id="web-session-42",
    empty_scope_action_shown={"create_page": 3, "review_open_drafts": 2},
    empty_scope_action_applied={"create_page": 1},
    source="wiki_ui",
)

# Pull 7-day telemetry summary (optionally filter by action key)
telemetry = synapse.get_wiki_lifecycle_telemetry(days=7, action_key="create_page")
print(telemetry["summary"]["apply_rate"])
```

These helpers map to `/v1/wiki/lifecycle/stats` and `/v1/wiki/lifecycle/telemetry*`.

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

By default this sends historical memory into `/v1/backfill/knowledge` and marks the final chunk as `finalize=true`.
Use `ingest_lane="event"` only for runtime/event stream replay.

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

## Legacy Memory Sync (No Custom Importer)

```python
# Optional: fetch server-side safe migration defaults for draft bootstrap
preset = synapse.get_bootstrap_migration_recommendation()
print(preset["recommended"])

# 1) inspect built-in SQL profiles
profiles = synapse.list_legacy_import_profiles(source_type="postgres_sql")

# 2) fetch template + sync contract (cron/CDC friendly)
templates = synapse.list_legacy_import_mapper_templates(
    source_type="postgres_sql",
    profile="ops_kb_items",
)
contracts = synapse.list_legacy_import_sync_contracts(source_type="postgres_sql")

template = templates["templates"][0]
print(template["runner_contract_key"])
print(contracts["contracts"][0]["runner"]["scheduler_script"])

# 3) register reusable source config
source = synapse.upsert_legacy_import_source(
    source_type="postgres_sql",
    source_ref="hw_memory",
    updated_by="ops_admin",
    sync_interval_minutes=5,
    config={
        "sql_dsn_env": "HW_MEMORY_DSN",
        "sql_profile": "ops_kb_items",
        "max_records": 5000,
        "chunk_size": 100,
    },
)

source_id = source["source"]["id"]

# 4) queue sync run and check history
synapse.queue_legacy_import_source_sync(source_id, requested_by="ops_admin")
runs = synapse.list_legacy_import_sync_runs(source_id=source_id, limit=20)
print(runs["runs"][0]["status"])

# 5) check cursor health and run safe project reset before clean rerun
cursor_health = synapse.get_adoption_sync_cursor_health(stale_after_hours=24)
print(cursor_health.get("status"))

reset_preview = synapse.run_adoption_project_reset(
    requested_by="ops_admin",
    scopes=["drafts", "wiki", "claims", "events", "backfill"],
    cascade_cleanup_orphan_draft_pages=True,
    dry_run=True,
)
print(reset_preview.get("summary"))
```

This maps to `/v1/legacy-import/*` and is intended to replace project-specific one-off import scripts with reusable profile/template contracts.

## Draft Moderation Ops (Safe Bulk Review)

```python
from synapse_sdk import WikiDraftBulkReviewFilter

# 1) inspect draft inbox (project-scoped)
drafts = synapse.list_wiki_drafts(status="pending_review", limit=50)
print(len(drafts.get("drafts", [])))

# 2) dry-run a safe bulk approve window
preview = synapse.bulk_review_wiki_drafts(
    reviewed_by="ops_reviewer",
    action="approve",
    dry_run=True,
    limit=100,
    filter=WikiDraftBulkReviewFilter(
        category="policy",
        category_mode="prefix",
        source_system="postgres_sql",
        assertion_class="process",
        min_confidence=0.85,
        min_risk_level="medium",
    ),
)
print(preview["summary"])
```

These helpers map to `/v1/wiki/drafts` and `/v1/wiki/drafts/bulk-review`.

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

```bash
synapse-cli adoption cursor-health --api-url http://localhost:8080 --project-id omega_demo --stale-after-hours 24
```

```bash
synapse-cli adoption project-reset --api-url http://localhost:8080 --project-id omega_demo --requested-by ops_admin --scopes drafts,wiki,claims,events,backfill --cascade-cleanup-orphan-draft-pages
```

```bash
synapse-cli adoption list-drafts --api-url http://localhost:8080 --project-id omega_demo --status pending_review --limit 50
```

```bash
synapse-cli adoption bulk-review-drafts --api-url http://localhost:8080 --project-id omega_demo --reviewed-by ops_reviewer --action approve --category policy --category-mode prefix --source-system postgres_sql --min-confidence 0.85
```

```bash
synapse-cli adoption sync-preset --api-url http://localhost:8080 --project-id omega_demo --updated-by ops_admin --with-pipeline
```

```bash
synapse-cli adoption pipeline --api-url http://localhost:8080 --project-id omega_demo --days 14
```

```bash
synapse-cli adoption rejections --api-url http://localhost:8080 --project-id omega_demo --days 14 --sample-limit 5
```

```bash
synapse-cli wiki-space-policy get --api-url http://localhost:8080 --project-id omega_demo --space-key operations
```

```bash
synapse-cli wiki-space-policy set-checklist-preset --api-url http://localhost:8080 --project-id omega_demo --space-key operations --updated-by ops_admin --preset ops_standard --reason "Support rollout baseline"
```

```bash
synapse-cli wiki-lifecycle stale --api-url http://localhost:8080 --project-id omega_demo --space operations --preset stale_21 --limit 20
```

```bash
synapse-cli wiki-lifecycle telemetry --api-url http://localhost:8080 --project-id omega_demo --days 7 --top 5
```

```bash
synapse-cli wiki-lifecycle open-drafts --project-id omega_demo --page-slug operations/customer-onboarding
```
