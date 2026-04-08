# @synapseworkspace/sdk

Universal TypeScript SDK for Synapse.

Compatibility note:
- `init(config)` export is deprecated and will be removed in a future major release.
- Prefer `new Synapse(config)` directly.

## Example

```ts
import { Synapse } from "@synapseworkspace/sdk";

const synapse = new Synapse({
  apiUrl: "http://localhost:8080",
  projectId: "water_delivery_logistics",
  degradationMode: "buffer", // "buffer" | "drop" | "sync_flush"
  retry: {
    maxRetries: 4,
    timeoutMs: 8000
  }
});

synapse.capture({
  event_type: "agent_message",
  payload: { text: "Omega gate now requires access cards" },
  observed_at: new Date().toISOString()
});

await synapse.flush();
```

`flush()` is loss-safe: if delivery fails, events are returned back to the in-memory queue.

## Graceful Degradation Modes

`degradationMode` in config (or `synapse.setDegradationMode(...)`) defines behavior when transport fails:
- `buffer` (default): keep failed events/claims/backfill chunks in memory and retry on `flush()`.
- `drop`: swallow transport failures and drop unsent payloads.
- `sync_flush`: call `flush()` automatically on each `capture()` (best-effort, non-throwing).

## Monitoring Existing Runners

```ts
const monitored = synapse.monitor(existingRunner, {
  integration: "langgraph",
  includeMethods: ["invoke", "stream"],
  flushOnError: true
});

await monitored.invoke({ input: "hello" });
```

The monitor wrapper emits lifecycle + result events to Synapse without changing your runner code.
Nested monitored calls keep propagated `trace_id` / `span_id` for correlation.
`attach(...)` can auto-detect common runtime shapes for `langgraph`, `langchain`, and `crewai`.

Native framework binding helpers:

```ts
const lcHandler = synapse.langchainCallbackHandler({ sessionId: "langchain-session-1" });
const langchainRuntime = synapse.bindLangchain(existingLangChainRuntime, {
  handler: lcHandler,
  fallbackMonitor: true
});

const langgraphRuntime = synapse.bindLanggraph(existingLangGraphRuntime, {
  fallbackMonitor: true
});

const crewRuntime = synapse.bindCrewAi(existingCrewRuntime, {
  monitorRuntime: true
});
```

If native callback/event surfaces are unavailable, `bindLangchain`/`bindLanggraph` can fall back to monitor wrappers.

Facade shortcut:

```ts
const attached = synapse.attach(existingRunner, {
  bootstrapMemory: {
    records: [
      "Warehouse #1 is temporarily closed for sanitation.",
      {
        source_id: "dialog-12",
        content: "BC Omega gate switched to card-only access after 10:00",
        entity_key: "bc_omega",
        category: "access"
      }
    ],
    sourceSystem: "agent_runtime_memory",
    createdBy: "sdk_attach",
    chunkSize: 200
  }
});
await attached.invoke({ input: "hello" });
```

When `bootstrapMemory` is configured, `attach(...)` backfills existing runtime memory before normal live monitoring starts.

OpenClaw day-0 preset shortcut:

```ts
const attachedOpenClaw = synapse.attach(openclawRuntime, {
  integration: "openclaw",
  openclawBootstrapPreset: "hybrid", // runtime_memory | event_log | hybrid
  adoptionMode: "observe_only", // full_loop | observe_only | draft_only | retrieve_only
  openclawBootstrapMaxRecords: 2000
});
```

`adoptionMode` rollout behavior:
- `observe_only`: capture/ingest only, no runtime tools.
- `draft_only`: propose facts, keep retrieval behavior unchanged.
- `retrieve_only`: retrieval tools only, no capture/bootstrap writes.
- `full_loop`: full observe -> synthesize -> execute loop.

When `integration: "openclaw"` is used with an OpenClaw-compatible runtime, `attach(...)` automatically:
- registers lifecycle hooks (`tool:result`, `message:received`, `agent:completed`, `session:reset`);
- wires runtime tools:
  - `synapse_search_wiki`
  - `synapse_propose_to_wiki`
  - `synapse_get_open_tasks`
  - `synapse_update_task_status`
- enables default `search_wiki` retrieval via `synapse.searchKnowledge(...)` unless overridden.

Override runtime wiring behavior if needed:

```ts
synapse.attach(openclawRuntime, {
  integration: "openclaw",
  openclawToolPrefix: "ops",
  openclawRegisterTools: true,
  openclawHookEvents: ["tool:result", "agent:completed"],
  openclawSearchKnowledge: (query, limit, filters) => customSearch(query, limit, filters)
});
```

Preset metadata/helpers:

```ts
import { buildOpenClawBootstrapOptions, listOpenClawBootstrapPresets } from "@synapseworkspace/sdk";

console.log(listOpenClawBootstrapPresets());
const manual = buildOpenClawBootstrapOptions({ preset: "event_log", maxRecords: 500 });
synapse.attach(openclawRuntime, { integration: "openclaw", bootstrapMemory: manual });
```

## Wiki Space Policy Helpers

```ts
const policy = await synapse.getWikiSpacePolicy("operations");
console.log(policy.policy.metadata?.publish_checklist_preset);

await synapse.setWikiSpacePublishChecklistPreset("operations", {
  preset: "ops_standard", // none | ops_standard | policy_strict
  updatedBy: "ops_admin",
  reason: "Enable standard publish checklist for support rollout"
});

const audit = await synapse.listWikiSpacePolicyAudit("operations", { limit: 20 });
console.log(audit.entries.length);
```

These APIs map to `/v1/wiki/spaces/{space_key}/policy*` and let you automate governance without custom scripts.

## collectInsight Wrapper

```ts
const checkGateAccess = synapse.collectInsight((buildingId: string) => {
  return `Gate closed for ${buildingId}: needs physical key-card`;
}, {
  category: "delivery_rules",
  entityKey: "bc_omega"
});

checkGateAccess("bc_omega");
```

## MCP Context Injection Helper

```ts
import { MCPContextHelper } from "@synapseworkspace/sdk";

const helper = new MCPContextHelper(
  "water_delivery_logistics",
  async (toolName, argumentsPayload) => mcpClient.callTool(toolName, argumentsPayload),
  { defaultContextPolicyProfile: "enforced" } // advisory | enforced | strict_enforced
);

const contextMarkdown = await helper.buildContextMarkdown({
  query: "How should we deliver to BC Omega?",
  entityKey: "bc_omega",
  includeRecentChanges: true,
  contextPolicyProfile: "enforced"
});

const searchCallback = helper.makeOpenClawSearchCallback(
  { entity_key: "bc_omega" },
  { contextPolicyProfile: "enforced" }
);
const results = await searchCallback("omega gate", 5, { category: "access" });
```

Helper capabilities:
- normalizes MCP tool payload variations;
- composes retrieval context (`search_knowledge`, `get_entity_facts`, `get_recent_changes`);
- provides OpenClaw-compatible `search_knowledge` callback signature.
- supports context policy profiles (`advisory`, `enforced`, `strict_enforced`) and manual overrides (`contextPolicyMode`, `minRetrievalConfidence`, score floors).

## Extractor Plugins

```ts
synapse.registerExtractor({
  name: "priority_rules",
  extract(context) {
    const text = String(context.result ?? "");
    if (!text.toLowerCase().includes("priority")) return [];
    return [{ claim_text: text, category: "operations", confidence: 0.9 }];
  }
});
```

## Synthesizer Plugins

```ts
synapse.registerSynthesizer({
  name: "confidence_floor",
  contractVersion: "v1",
  synthesize(context) {
    return context.extractedInsights.map((item) => ({
      ...item,
      confidence: Math.max(item.confidence ?? 0, 0.8)
    }));
  }
});
```

Synthesizers run after extractors and before claim proposal submission.
Use `listSynthesizers()` / `unregisterSynthesizer(name)` for lifecycle management.

## Introspection / Debug Mode

```ts
synapse.setDebugMode({ enabled: true, maxRecords: 2000 });

// ... run monitor / collectInsight ...
const records = synapse.getDebugRecords(20);
for (const item of records) {
  console.log(item.event, item.details);
}
```

Debug records are machine-readable (`event`, `traceId`, `details`) and can be forwarded through a custom sink.

## OpenTelemetry Bridge

```ts
import { Synapse, createOpenTelemetryBridge } from "@synapseworkspace/sdk";
import { metrics, trace } from "@opentelemetry/api";

const synapse = new Synapse({
  apiUrl: "http://localhost:8080",
  projectId: "water_delivery_logistics"
});

const bridge = createOpenTelemetryBridge({
  projectId: synapse.projectId,
  tracer: trace.getTracer("synapse-sdk"),
  meter: metrics.getMeter("synapse-sdk")
});

synapse.setTelemetrySink(bridge.sink());
```

The bridge maps SDK lifecycle events to OTel counters/histograms and operation spans.
Datadog/Prometheus export is handled by your standard OpenTelemetry collector/exporter setup.
Starter dashboards and local collector stack: `/Users/maksimborisov/synapse/docs/sdk-trace-observability.md`.

## Bootstrap Existing Agent Memory

```ts
const batchId = await synapse.backfillMemory([
  {
    source_id: "dialog-12",
    content: "BC Omega gate switched to card-only access after 10:00",
    entity_key: "bc_omega",
    category: "access",
    observed_at: "2026-03-30T08:10:00Z"
  },
  {
    source_id: "driver-note-77",
    content: "Driver Sidorov does not accept orders after 17:00",
    entity_key: "driver_sidorov",
    category: "operations"
  }
], {
  sourceSystem: "openclaw_memory",
  createdBy: "bootstrap_job",
  chunkSize: 100
});

console.log("Backfill batch:", batchId);
```

Historical memory is uploaded via `/v1/backfill/knowledge` by default; final chunk is automatically marked `finalize=true`.
Use `ingestLane: "event"` only for runtime/event stream replay.

You can also bootstrap during attach:

```ts
const attached = synapse.attach(existingRunner, {
  bootstrapMemory: {
    provider: (runner) => runner.memory?.exportAll?.() ?? [],
    sourceSystem: "openclaw_memory",
    createdBy: "sdk_attach",
    chunkSize: 200
  }
});
```

## Legacy Memory Sync (No Custom Importer)

```ts
// Optional: ask server for safe bootstrap migration defaults
const preset = await synapse.getBootstrapMigrationRecommendation();
console.log((preset as any).recommended);

// 1) discover built-in Postgres profiles
const profiles = await synapse.listLegacyImportProfiles({ sourceType: "postgres_sql" });

// 2) discover mapper templates + sync contracts
const templates = await synapse.listLegacyImportMapperTemplates({
  sourceType: "postgres_sql",
  profile: "ops_kb_items"
});
const contracts = await synapse.listLegacyImportSyncContracts({ sourceType: "postgres_sql" });

console.log((templates as any).templates?.[0]?.runner_contract_key);
console.log((contracts as any).contracts?.[0]?.runner?.scheduler_script);

// 3) create/update a reusable legacy source
const upserted = await synapse.upsertLegacyImportSource({
  sourceType: "postgres_sql",
  sourceRef: "hw_memory",
  updatedBy: "ops_admin",
  syncIntervalMinutes: 5,
  config: {
    sql_dsn_env: "HW_MEMORY_DSN",
    sql_profile: "ops_kb_items",
    max_records: 5000,
    chunk_size: 100
  }
});

const sourceId = String((upserted as any).source.id);

// 4) queue a run + inspect status history
await synapse.queueLegacyImportSourceSync({ sourceId, requestedBy: "ops_admin" });
const runs = await synapse.listLegacyImportSyncRuns({ sourceId, limit: 20 });
console.log((runs as any).runs?.[0]?.status);
```

These SDK calls map to `/v1/legacy-import/*` and remove the need for per-project importer scripts by using reusable mapping templates and sync runner contracts.

## Task Core Helpers

```ts
const created = await synapse.upsertTask(
  {
    title: "Verify Omega gate policy",
    description: "Confirm card-only access after 10:00",
    priority: "high",
    entityKey: "bc_omega",
    category: "access_policy"
  },
  { createdBy: "ops_manager" }
);

const taskId = String((created.task as { id: string }).id);
await synapse.updateTaskStatus(taskId, { status: "in_progress", updatedBy: "ops_manager" });
await synapse.commentTask(taskId, { comment: "Driver confirmed at gate." }, { createdBy: "ops_manager" });
await synapse.linkTask(taskId, { linkType: "draft", linkRef: "draft-id-123" }, { createdBy: "ops_manager" });
```

Task helpers map to `/v1/tasks*` and are designed for agentic execution loops.

## Wiki Lifecycle Telemetry Helpers

```ts
// Read stale-page diagnostics (same contract as /v1/wiki/lifecycle/stats)
const lifecycleStats = await synapse.getWikiLifecycleStats({
  staleDays: 21,
  criticalDays: 45,
  staleLimit: 20,
  spaceKey: "operations"
});
console.log((lifecycleStats as { counts?: { stale_warning_pages?: number } }).counts?.stale_warning_pages);

// Push monotonic per-session counters (server computes delta)
await synapse.snapshotWikiLifecycleTelemetry({
  sessionId: "web-session-42",
  emptyScopeActionShown: { create_page: 3, review_open_drafts: 2 },
  emptyScopeActionApplied: { create_page: 1 },
  source: "wiki_ui"
});

// Pull telemetry summary, optionally filtered by one action key
const actionTelemetry = await synapse.getWikiLifecycleTelemetry({
  days: 7,
  actionKey: "create_page"
});
console.log((actionTelemetry as { summary?: { apply_rate?: number } }).summary?.apply_rate);
```

These helpers map to `/v1/wiki/lifecycle/stats` and `/v1/wiki/lifecycle/telemetry*`.

## Cookbook Examples

See repository cookbook scenarios (OpenClaw, SQL, Support Ops):
- `/Users/maksimborisov/synapse/demos/cookbook/README.md`
