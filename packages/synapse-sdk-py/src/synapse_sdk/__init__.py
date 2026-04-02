import warnings

from synapse_sdk.client import Synapse, SynapseClient
from synapse_sdk.extractors import (
    ExtractedInsight,
    Extractor,
    InsightContext,
    KeywordExtractor,
    StructuredResultExtractor,
)
from synapse_sdk.synthesizers import (
    ConfidenceClampSynthesizer,
    SynthesisContext,
    Synthesizer,
)
from synapse_sdk.telemetry import OpenTelemetryBridge, build_opentelemetry_bridge
from synapse_sdk.errors import SynapseTransportError
from synapse_sdk.mcp import (
    MCP_CONTEXT_POLICY_PROFILES,
    MCPContextHelper,
    MCPToolCaller,
    list_context_policy_profiles,
)
from synapse_sdk.integrations import (
    MonitorOptions,
    OPENCLAW_BOOTSTRAP_PRESETS,
    OpenClawConnector,
    build_openclaw_bootstrap_options,
    list_openclaw_bootstrap_presets,
    monitor_crewai,
    monitor_langgraph,
    monitor_object,
    monitor_openclaw_runtime,
)
from synapse_sdk.types import (
    Claim,
    BootstrapMemoryOptions,
    DegradationMode,
    EvidenceRef,
    MemoryBackfillRecord,
    ObservationEvent,
    RetryConfig,
    SynapseConfig,
    Task,
    TaskComment,
    TaskLink,
)


__all__ = [
    "SynapseClient",
    "Synapse",
    "SynapseConfig",
    "DegradationMode",
    "RetryConfig",
    "Claim",
    "BootstrapMemoryOptions",
    "ObservationEvent",
    "EvidenceRef",
    "MemoryBackfillRecord",
    "Task",
    "TaskComment",
    "TaskLink",
    "SynapseTransportError",
    "MCPContextHelper",
    "MCPToolCaller",
    "MCP_CONTEXT_POLICY_PROFILES",
    "list_context_policy_profiles",
    "Extractor",
    "InsightContext",
    "ExtractedInsight",
    "StructuredResultExtractor",
    "KeywordExtractor",
    "Synthesizer",
    "SynthesisContext",
    "ConfidenceClampSynthesizer",
    "OpenTelemetryBridge",
    "build_opentelemetry_bridge",
    "MonitorOptions",
    "monitor_object",
    "monitor_langgraph",
    "monitor_crewai",
    "monitor_openclaw_runtime",
    "OpenClawConnector",
    "OPENCLAW_BOOTSTRAP_PRESETS",
    "build_openclaw_bootstrap_options",
    "list_openclaw_bootstrap_presets",
]


def init(config: SynapseConfig) -> Synapse:
    warnings.warn(
        "synapse_sdk.init(...) is deprecated; instantiate Synapse(...) directly.",
        DeprecationWarning,
        stacklevel=2,
    )
    return Synapse(config)
