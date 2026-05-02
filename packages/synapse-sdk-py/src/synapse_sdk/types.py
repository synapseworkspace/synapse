from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Sequence

SchemaVersion = Literal["v1"]
EventType = Literal["tool_result", "agent_message", "user_message", "system_signal", "fact_proposed", "memory_backfill"]
ClaimStatus = Literal["draft", "approved", "rejected", "expired"]
DegradationMode = Literal["buffer", "drop", "sync_flush"]
AdoptionMode = Literal["full_loop", "observe_only", "draft_only", "retrieve_only"]
TaskStatus = Literal["todo", "in_progress", "blocked", "done", "canceled"]
TaskPriority = Literal["low", "normal", "high", "critical"]
TaskSource = Literal["agent", "human", "system"]
WikiDraftStatus = Literal["pending_review", "blocked_conflict", "approved", "rejected"]
WikiDraftFilterMode = Literal["exact", "prefix", "regex", "contains"]
WikiDraftRiskLevel = Literal["low", "medium", "high"]


@dataclass
class EvidenceRef:
    source_type: Literal["dialog", "tool_output", "file", "human_note", "external_event"]
    source_id: str
    session_id: str | None = None
    tool_name: str | None = None
    snippet: str | None = None
    url: str | None = None
    observed_at: str | None = None
    provenance: dict[str, Any] | None = None


@dataclass
class ObservationEvent:
    id: str
    schema_version: SchemaVersion
    project_id: str
    event_type: EventType
    payload: dict[str, Any]
    observed_at: str
    agent_id: str | None = None
    session_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class Claim:
    id: str
    schema_version: SchemaVersion
    project_id: str
    entity_key: str
    category: str
    claim_text: str
    status: ClaimStatus
    evidence: list[EvidenceRef]
    confidence: float | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SynapseConfig:
    api_url: str
    project_id: str
    api_key: str | None = None
    retry: "RetryConfig" = field(default_factory=lambda: RetryConfig())
    degradation_mode: DegradationMode = "buffer"


@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay_seconds: float = 0.25
    max_delay_seconds: float = 5.0
    jitter_ratio: float = 0.2
    timeout_seconds: float = 10.0
    retryable_status_codes: tuple[int, ...] = (408, 409, 425, 429, 500, 502, 503, 504)


@dataclass
class MemoryBackfillRecord:
    source_id: str
    content: str
    observed_at: str | None = None
    entity_key: str | None = None
    category: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)


BootstrapMemoryInput = MemoryBackfillRecord | dict[str, Any] | str
BootstrapMemoryProvider = Callable[[Any], Sequence[BootstrapMemoryInput] | None]


@dataclass
class BootstrapMemoryOptions:
    records: Sequence[BootstrapMemoryInput] | None = None
    provider: BootstrapMemoryProvider | None = None
    source_system: str = "sdk_attach_bootstrap"
    created_by: str | None = "sdk_attach"
    cursor: str | None = None
    chunk_size: int = 100
    max_records: int = 1000


@dataclass
class Task:
    title: str
    description: str | None = None
    status: TaskStatus = "todo"
    priority: TaskPriority = "normal"
    source: TaskSource = "human"
    assignee: str | None = None
    entity_key: str | None = None
    category: str | None = None
    due_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskComment:
    comment: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskLink:
    link_type: Literal["claim", "draft", "page", "event", "external"]
    link_ref: str
    note: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentProfile:
    agent_id: str
    display_name: str | None = None
    team: str | None = None
    role: str | None = None
    status: Literal["active", "idle", "paused", "offline", "retired"] = "active"
    responsibilities: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    data_sources: list[str] = field(default_factory=list)
    limits: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    ensure_scaffold: bool = True
    include_daily_report_stub: bool = True
    last_seen_at: str | None = None


@dataclass
class AgentReflectionInsight:
    claim_text: str
    category: str | None = None
    confidence: float | None = None
    temporary: bool = False
    evidence: list[EvidenceRef] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentReflection:
    agent_id: str
    reflected_by: str
    task_id: str | None = None
    session_id: str | None = None
    trace_id: str | None = None
    outcome: str | None = None
    summary: str | None = None
    learned_rules: list[str] = field(default_factory=list)
    decisions_made: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    data_sources_used: list[str] = field(default_factory=list)
    follow_up_actions: list[str] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    insights: list[AgentReflectionInsight] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    observed_at: str | None = None


@dataclass
class WikiDraftBulkReviewFilter:
    statuses: list[WikiDraftStatus] | None = None
    category: str | None = None
    category_mode: WikiDraftFilterMode = "exact"
    source_system: str | None = None
    source_system_mode: WikiDraftFilterMode = "exact"
    connector: str | None = None
    connector_mode: WikiDraftFilterMode = "exact"
    page_type: str | None = None
    page_type_mode: WikiDraftFilterMode = "exact"
    assertion_class: str | None = None
    assertion_class_mode: WikiDraftFilterMode = "exact"
    tier: str | None = None
    tier_mode: WikiDraftFilterMode = "exact"
    min_confidence: float | None = None
    max_confidence: float | None = None
    min_risk_level: WikiDraftRiskLevel | None = None
    max_risk_level: WikiDraftRiskLevel | None = None
    include_open_conflicts: bool = False
    include_archived_pages: bool = False
    include_published_pages: bool = True
