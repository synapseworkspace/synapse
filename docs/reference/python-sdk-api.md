# Python SDK API Reference

Canonical entrypoint: `from synapse_sdk import ...`

## Public Exports (`synapse_sdk.__all__`)

| Symbol | Source Module |
| --- | --- |
| `SynapseClient` | `synapse_sdk.client` |
| `Synapse` | `synapse_sdk.client` |
| `SynapseConfig` | `synapse_sdk.types` |
| `DegradationMode` | `synapse_sdk.types` |
| `RetryConfig` | `synapse_sdk.types` |
| `Claim` | `synapse_sdk.types` |
| `BootstrapMemoryOptions` | `synapse_sdk.types` |
| `ObservationEvent` | `synapse_sdk.types` |
| `EvidenceRef` | `synapse_sdk.types` |
| `MemoryBackfillRecord` | `synapse_sdk.types` |
| `Task` | `synapse_sdk.types` |
| `TaskComment` | `synapse_sdk.types` |
| `TaskLink` | `synapse_sdk.types` |
| `SynapseTransportError` | `synapse_sdk.errors` |
| `MCPContextHelper` | `synapse_sdk.mcp` |
| `MCPToolCaller` | `synapse_sdk.mcp` |
| `MCP_CONTEXT_POLICY_PROFILES` | `synapse_sdk.mcp` |
| `list_context_policy_profiles` | `synapse_sdk.mcp` |
| `Extractor` | `synapse_sdk.extractors` |
| `InsightContext` | `synapse_sdk.extractors` |
| `ExtractedInsight` | `synapse_sdk.extractors` |
| `StructuredResultExtractor` | `synapse_sdk.extractors` |
| `KeywordExtractor` | `synapse_sdk.extractors` |
| `Synthesizer` | `synapse_sdk.synthesizers` |
| `SynthesisContext` | `synapse_sdk.synthesizers` |
| `ConfidenceClampSynthesizer` | `synapse_sdk.synthesizers` |
| `OpenTelemetryBridge` | `synapse_sdk.telemetry` |
| `build_opentelemetry_bridge` | `synapse_sdk.telemetry` |
| `MonitorOptions` | `synapse_sdk.integrations` |
| `monitor_object` | `synapse_sdk.integrations` |
| `monitor_langgraph` | `synapse_sdk.integrations` |
| `monitor_langchain` | `synapse_sdk.integrations` |
| `monitor_crewai` | `synapse_sdk.integrations` |
| `monitor_openclaw_runtime` | `synapse_sdk.integrations` |
| `OpenClawConnector` | `synapse_sdk.integrations` |
| `OPENCLAW_BOOTSTRAP_PRESETS` | `synapse_sdk.integrations` |
| `build_openclaw_bootstrap_options` | `synapse_sdk.integrations` |
| `list_openclaw_bootstrap_presets` | `synapse_sdk.integrations` |
| `from_env` | `synapse_sdk` |

## Notes

- `init(config)` is deprecated; use `Synapse(config)` directly.
- Keep this file generated via `scripts/generate_sdk_api_reference.py`.
