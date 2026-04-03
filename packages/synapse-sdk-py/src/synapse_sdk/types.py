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
