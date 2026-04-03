# TypeScript SDK API Reference

Canonical entrypoint: `import { ... } from "@synapseworkspace/sdk"`

## Re-exported Modules (`src/index.ts`)

### `./types`

Source: `packages/synapse-sdk-ts/src/types.ts`

Exports:
- `AdoptionMode`
- `AttachBootstrapMemoryOptions`
- `AttachOptions`
- `BindCrewAiOptions`
- `BindLangChainOptions`
- `BindLangGraphOptions`
- `BootstrapMemoryInput`
- `Claim`
- `CollectInsightOptions`
- `DebugOptions`
- `DebugRecord`
- `DebugSink`
- `DegradationMode`
- `DraftPage`
- `EvidenceRef`
- `ExtractedInsight`
- `InsightContext`
- `InsightExtractor`
- `InsightSynthesizer`
- `LangChainCallbackHandler`
- `LangChainCallbackHandlerOptions`
- `MemoryBackfillOptions`
- `MemoryBackfillRecord`
- `MonitorOptions`
- `OTelCounterLike`
- `OTelHistogramLike`
- `OTelMeterLike`
- `OTelSpanLike`
- `OTelTracerLike`
- `ObservationEvent`
- `OnboardingMetrics`
- `OpenClawBootstrapPreset`
- `OpenClawListTasksResolver`
- `OpenClawSearchKnowledgeResolver`
- `OpenClawUpdateTaskStatusResolver`
- `RequestOptions`
- `RetryPolicyConfig`
- `SchemaVersion`
- `SynapseConfig`
- `SynapseTransport`
- `SynthesisContext`
- `TaskCommentInput`
- `TaskInput`
- `TaskLinkInput`
- `TaskPriority`
- `TaskSource`
- `TaskStatus`
- `TelemetrySink`

### `./client`

Source: `packages/synapse-sdk-ts/src/client.ts`

Exports:
- `Synapse`
- `SynapseClient`

### `./mcp`

Source: `packages/synapse-sdk-ts/src/mcp.ts`

Exports:
- `BuildContextMarkdownOptions`
- `BuildContextOptions`
- `EntityFactOptions`
- `MCPContextHelper`
- `MCPContextHelperOptions`
- `MCPContextPolicyMode`
- `MCPContextPolicyProfile`
- `MCPContextPolicyProfileName`
- `MCPToolCaller`
- `MCP_CONTEXT_POLICY_PROFILES`
- `SearchKnowledgeOptions`
- `listContextPolicyProfiles`

### `./openclaw`

Source: `packages/synapse-sdk-ts/src/openclaw.ts`

Exports:
- `BuildOpenClawBootstrapOptionsInput`
- `CollectOpenClawBootstrapRecordsInput`
- `OPENCLAW_BOOTSTRAP_PRESETS`
- `OpenClawBootstrapPresetDescriptor`
- `buildOpenClawBootstrapOptions`
- `collectOpenClawBootstrapRecords`
- `listOpenClawBootstrapPresets`
- `normalizeOpenClawBootstrapPreset`

### `./telemetry`

Source: `packages/synapse-sdk-ts/src/telemetry.ts`

Exports:
- `OpenTelemetryBridge`
- `createOpenTelemetryBridge`

### `./transports/http`

Source: `packages/synapse-sdk-ts/src/transports/http.ts`

Exports:
- `HttpTransport`
- `SynapseTransportError`

## Notes

- `init(config)` is deprecated; use `new Synapse(config)` directly.
- Keep this file generated via `scripts/generate_sdk_api_reference.py`.
