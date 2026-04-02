from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import hashlib
import inspect
import os
from contextvars import ContextVar, Token
from pathlib import Path
import re
from threading import Lock
from typing import Any, Callable, Protocol, Sequence
from uuid import UUID, uuid4

from synapse_sdk.extractors import ExtractedInsight, Extractor, InsightContext, default_extractors
from synapse_sdk.synthesizers import SynthesisContext, Synthesizer, default_synthesizers
from synapse_sdk.transports.http import HttpTransport
from synapse_sdk.types import (
    BootstrapMemoryInput,
    BootstrapMemoryOptions,
    Claim,
    EventType,
    EvidenceRef,
    MemoryBackfillRecord,
    ObservationEvent,
    SynapseConfig,
    Task,
    TaskComment,
    TaskLink,
)

_TRACE_ID: ContextVar[str | None] = ContextVar("synapse_trace_id", default=None)
_SPAN_ID: ContextVar[str | None] = ContextVar("synapse_span_id", default=None)


class Transport(Protocol):
    def send_events(self, events: list[ObservationEvent], *, idempotency_key: str | None = None) -> None: ...
    def propose_fact(self, claim: Claim, *, idempotency_key: str | None = None) -> None: ...
    def ingest_memory_backfill(self, batch_payload: dict[str, Any], *, idempotency_key: str | None = None) -> None: ...


class SynapseClient:
    def __init__(self, config: SynapseConfig, transport: Transport | None = None) -> None:
        self._config = config
        self._transport = transport or HttpTransport(config.api_url, config.api_key, retry=config.retry)
        self._degradation_mode = _normalize_degradation_mode(config.degradation_mode)
        self._queue: list[ObservationEvent] = []
        self._queue_lock = Lock()
        self._pending_claims: list[Claim] = []
        self._pending_backfill: list[tuple[dict[str, Any], str | None]] = []
        self._pending_lock = Lock()
        self._extractors: dict[str, Extractor] = {extractor.name: extractor for extractor in default_extractors()}
        self._synthesizers: dict[str, Synthesizer] = {synthesizer.name: synthesizer for synthesizer in default_synthesizers()}
        self._debug_mode = False
        self._debug_records: list[dict[str, Any]] = []
        self._debug_lock = Lock()
        self._debug_sink: Callable[[dict[str, Any]], None] | None = None
        self._telemetry_sink: Callable[[dict[str, Any]], None] | None = None
        self._debug_max_records = 1000

    @property
    def project_id(self) -> str:
        return self._config.project_id

    @property
    def debug_mode(self) -> bool:
        return self._debug_mode

    @property
    def degradation_mode(self) -> str:
        return self._degradation_mode

    def set_degradation_mode(self, mode: str) -> None:
        self._degradation_mode = _normalize_degradation_mode(mode)

    def set_debug_mode(
        self,
        enabled: bool,
        *,
        sink: Callable[[dict[str, Any]], None] | None = None,
        max_records: int | None = None,
    ) -> None:
        self._debug_mode = bool(enabled)
        if sink is not None:
            self._debug_sink = sink
        if max_records is not None:
            self._debug_max_records = max(10, int(max_records))

    def set_telemetry_sink(self, sink: Callable[[dict[str, Any]], None] | None) -> None:
        self._telemetry_sink = sink

    def get_debug_records(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        with self._debug_lock:
            if limit is None or limit <= 0:
                return list(self._debug_records)
            return list(self._debug_records[-limit:])

    def clear_debug_records(self) -> None:
        with self._debug_lock:
            self._debug_records.clear()

    def get_onboarding_metrics(self, *, limit: int = 500) -> dict[str, Any]:
        records = self.get_debug_records(limit=max(1, int(limit)))
        attach_events: list[dict[str, Any]] = []
        counts: dict[str, int] = {}
        friction_events: list[str] = []
        friction_prefixes = (
            "attach_bootstrap_failed",
            "attach_bootstrap_provider_failed",
            "attach_bootstrap_skipped",
            "attach_openclaw_bootstrap_preset_failed",
            "attach_openclaw_bootstrap_preset_skipped",
            "attach_openclaw_search_disabled",
        )
        for item in records:
            event_name = str(item.get("event") or "")
            if not event_name.startswith("attach_"):
                continue
            attach_events.append(item)
            counts[event_name] = counts.get(event_name, 0) + 1
            if event_name in friction_prefixes:
                friction_events.append(event_name)

        return {
            "project_id": self._config.project_id,
            "window": {"limit": max(1, int(limit)), "events_observed": len(records)},
            "attach_events_total": len(attach_events),
            "attach_started": counts.get("attach_started", 0),
            "attach_completed": counts.get("attach_completed", 0),
            "bootstrap_completed": counts.get("attach_bootstrap_completed", 0),
            "friction_total": len(friction_events),
            "friction_events": friction_events,
            "events_by_name": counts,
        }

    def capture(
        self,
        *,
        event_type: EventType,
        payload: dict[str, object],
        event_id: str | None = None,
        observed_at: str | None = None,
        agent_id: str | None = None,
        session_id: str | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
        parent_span_id: str | None = None,
        tags: list[str] | None = None,
    ) -> None:
        resolved_trace_id, resolved_span_id, resolved_parent_span_id = self._resolve_trace_fields(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
        )
        payload_with_trace = self._payload_with_trace(
            payload=payload,
            trace_id=resolved_trace_id,
            span_id=resolved_span_id,
            parent_span_id=resolved_parent_span_id,
        )
        with self._queue_lock:
            self._queue.append(
                ObservationEvent(
                    id=event_id or str(uuid4()),
                    schema_version="v1",
                    project_id=self._config.project_id,
                    event_type=event_type,
                    payload=payload_with_trace,
                    observed_at=observed_at or datetime.now(UTC).isoformat(),
                    agent_id=agent_id,
                    session_id=session_id,
                    trace_id=resolved_trace_id,
                    span_id=resolved_span_id,
                    parent_span_id=resolved_parent_span_id,
                    tags=tags or [],
                )
            )
            queue_size = len(self._queue)
        self._emit_debug(
            "capture_queued",
            {
                "event_type": event_type,
                "queue_size": queue_size,
                "agent_id": agent_id,
                "session_id": session_id,
            },
            trace_context={
                "trace_id": resolved_trace_id,
                "span_id": resolved_span_id,
                "parent_span_id": resolved_parent_span_id,
            },
        )
        if self._degradation_mode == "sync_flush":
            self.flush()

    def propose_fact(self, claim: Claim) -> None:
        prepared = replace(claim, schema_version="v1", project_id=self._config.project_id)
        trace_context = {
            "trace_id": _coerce_str_or_none(prepared.metadata.get("trace_id")),
            "span_id": _coerce_str_or_none(prepared.metadata.get("span_id")),
            "parent_span_id": _coerce_str_or_none(prepared.metadata.get("parent_span_id")),
        }
        self._emit_debug(
            "propose_fact_attempt",
            {
                "claim_id": prepared.id,
                "entity_key": prepared.entity_key,
                "category": prepared.category,
                "confidence": prepared.confidence,
            },
            trace_context=trace_context,
        )
        try:
            self._transport.propose_fact(prepared, idempotency_key=_make_claim_idempotency_key(prepared.id))
            self._emit_debug(
                "propose_fact_sent",
                {"claim_id": prepared.id},
                trace_context=trace_context,
            )
        except Exception as exc:
            if self._degradation_mode == "drop":
                self._emit_debug(
                    "propose_fact_dropped",
                    {
                        "claim_id": prepared.id,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    },
                    trace_context=trace_context,
                )
                return
            with self._pending_lock:
                self._pending_claims.append(prepared)
                pending_count = len(self._pending_claims)
            self._emit_debug(
                "propose_fact_buffered",
                {
                    "claim_id": prepared.id,
                    "pending_claims": pending_count,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
                trace_context=trace_context,
            )

    def flush(self) -> None:
        pending_backfill = self._pop_pending_backfill()
        if pending_backfill:
            self._emit_debug("flush_pending_backfill_start", {"count": len(pending_backfill)})
        for payload, idempotency_key in pending_backfill:
            try:
                self._transport.ingest_memory_backfill(payload, idempotency_key=idempotency_key)
            except Exception as exc:
                if self._degradation_mode == "drop":
                    self._emit_debug(
                        "flush_pending_backfill_dropped",
                        {"error_type": type(exc).__name__, "error_message": str(exc)},
                    )
                    continue
                self._push_pending_backfill(payload, idempotency_key=idempotency_key, to_front=True)
                self._emit_debug(
                    "flush_pending_backfill_requeued",
                    {"error_type": type(exc).__name__, "error_message": str(exc)},
                )
                break
        else:
            if pending_backfill:
                self._emit_debug("flush_pending_backfill_success", {"count": len(pending_backfill)})

        pending_claims = self._pop_pending_claims()
        if pending_claims:
            self._emit_debug("flush_pending_claims_start", {"count": len(pending_claims)})
        for claim in pending_claims:
            try:
                self._transport.propose_fact(claim, idempotency_key=_make_claim_idempotency_key(claim.id))
            except Exception as exc:
                if self._degradation_mode == "drop":
                    self._emit_debug(
                        "flush_pending_claim_dropped",
                        {
                            "claim_id": claim.id,
                            "error_type": type(exc).__name__,
                            "error_message": str(exc),
                        },
                    )
                    continue
                self._push_pending_claim(claim, to_front=True)
                self._emit_debug(
                    "flush_pending_claim_requeued",
                    {
                        "claim_id": claim.id,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    },
                )
                break
        else:
            if pending_claims:
                self._emit_debug("flush_pending_claims_success", {"count": len(pending_claims)})

        with self._queue_lock:
            if not self._queue:
                self._emit_debug("flush_skipped_empty", {})
                return
            batch = list(self._queue)
            self._queue.clear()
        self._emit_debug("flush_start", {"batch_size": len(batch)})

        try:
            self._transport.send_events(batch, idempotency_key=_make_batch_idempotency_key(batch))
            self._emit_debug("flush_success", {"batch_size": len(batch)})
        except Exception as exc:
            if self._degradation_mode == "drop":
                self._emit_debug(
                    "flush_failed_dropped",
                    {
                        "batch_size": len(batch),
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    },
                )
                return
            with self._queue_lock:
                self._queue = batch + self._queue
            self._emit_debug(
                "flush_failed_requeued",
                {
                    "batch_size": len(batch),
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
            )
            return

    def backfill_memory(
        self,
        records: Sequence[MemoryBackfillRecord],
        *,
        batch_id: str | None = None,
        source_system: str = "sdk_bootstrap",
        agent_id: str | None = None,
        session_id: str | None = None,
        created_by: str | None = None,
        cursor: str | None = None,
        chunk_size: int = 100,
    ) -> str:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")
        if not records:
            if batch_id is not None:
                return batch_id
            return str(uuid4())

        resolved_batch_id = str(UUID(batch_id)) if batch_id else str(uuid4())
        total = len(records)
        for start in range(0, total, chunk_size):
            chunk = [record for record in records[start : start + chunk_size]]
            is_last = start + len(chunk) >= total
            idempotency_key = _make_backfill_idempotency_key(
                batch_id=resolved_batch_id,
                start=start,
                size=len(chunk),
                finalized=is_last,
            )
            batch_payload = {
                "batch": {
                    "batch_id": resolved_batch_id,
                    "project_id": self._config.project_id,
                    "source_system": source_system,
                    "agent_id": agent_id,
                    "session_id": session_id,
                    "cursor": cursor if is_last else None,
                    "finalize": is_last,
                    "created_by": created_by,
                    "records": [self._serialize_backfill_record(record) for record in chunk],
                }
            }
            try:
                self._transport.ingest_memory_backfill(batch_payload, idempotency_key=idempotency_key)
                self._emit_debug(
                    "backfill_chunk_sent",
                    {
                        "batch_id": resolved_batch_id,
                        "start": start,
                        "size": len(chunk),
                        "finalized": is_last,
                    },
                )
            except Exception as exc:
                if self._degradation_mode == "drop":
                    self._emit_debug(
                        "backfill_chunk_dropped",
                        {
                            "batch_id": resolved_batch_id,
                            "start": start,
                            "size": len(chunk),
                            "finalized": is_last,
                            "error_type": type(exc).__name__,
                            "error_message": str(exc),
                        },
                    )
                    continue
                self._push_pending_backfill(batch_payload, idempotency_key=idempotency_key)
                self._emit_debug(
                    "backfill_chunk_buffered",
                    {
                        "batch_id": resolved_batch_id,
                        "start": start,
                        "size": len(chunk),
                        "finalized": is_last,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    },
                )
        self._emit_debug(
            "backfill_completed",
            {"batch_id": resolved_batch_id, "records": total, "chunk_size": chunk_size},
        )
        return resolved_batch_id

    def list_tasks(
        self,
        *,
        status: str | None = None,
        assignee: str | None = None,
        entity_key: str | None = None,
        include_closed: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "project_id": self._config.project_id,
            "include_closed": "true" if include_closed else "false",
            "limit": max(1, min(500, int(limit))),
        }
        if status:
            params["status"] = status
        if assignee:
            params["assignee"] = assignee
        if entity_key:
            params["entity_key"] = entity_key
        response = self._request_json("/v1/tasks", method="GET", params=params)
        return response.get("tasks", []) if isinstance(response.get("tasks"), list) else []

    def get_task(
        self,
        task_id: str,
        *,
        events_limit: int = 100,
        links_limit: int = 100,
    ) -> dict[str, Any]:
        return self._request_json(
            f"/v1/tasks/{task_id}",
            method="GET",
            params={
                "project_id": self._config.project_id,
                "events_limit": max(0, min(500, int(events_limit))),
                "links_limit": max(0, min(500, int(links_limit))),
            },
        )

    def upsert_task(
        self,
        task: Task,
        *,
        created_by: str,
        task_id: str | None = None,
        updated_by: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "project_id": self._config.project_id,
            "task_id": task_id,
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "priority": task.priority,
            "source": task.source,
            "assignee": task.assignee,
            "entity_key": task.entity_key,
            "category": task.category,
            "due_at": task.due_at,
            "metadata": dict(task.metadata),
            "created_by": created_by,
            "updated_by": updated_by,
        }
        return self._request_json(
            "/v1/tasks",
            method="POST",
            payload=payload,
            idempotency_key=idempotency_key or str(uuid4()),
        )

    def update_task_status(
        self,
        task_id: str,
        *,
        status: str,
        updated_by: str,
        note: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self._request_json(
            f"/v1/tasks/{task_id}/status",
            method="POST",
            payload={
                "project_id": self._config.project_id,
                "status": status,
                "updated_by": updated_by,
                "note": note,
            },
            idempotency_key=idempotency_key or str(uuid4()),
        )

    def comment_task(
        self,
        task_id: str,
        *,
        created_by: str,
        comment: TaskComment,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self._request_json(
            f"/v1/tasks/{task_id}/comments",
            method="POST",
            payload={
                "project_id": self._config.project_id,
                "created_by": created_by,
                "comment": comment.comment,
                "metadata": dict(comment.metadata),
            },
            idempotency_key=idempotency_key or str(uuid4()),
        )

    def link_task(
        self,
        task_id: str,
        *,
        created_by: str,
        link: TaskLink,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self._request_json(
            f"/v1/tasks/{task_id}/links",
            method="POST",
            payload={
                "project_id": self._config.project_id,
                "created_by": created_by,
                "link_type": link.link_type,
                "link_ref": link.link_ref,
                "note": link.note,
                "metadata": dict(link.metadata),
            },
            idempotency_key=idempotency_key or str(uuid4()),
        )

    def search_knowledge(
        self,
        query: str,
        *,
        limit: int = 5,
        related_entity_key: str | None = None,
        context_policy_mode: str | None = None,
        min_retrieval_confidence: float | None = None,
        min_total_score: float | None = None,
        min_lexical_score: float | None = None,
        min_token_overlap_ratio: float | None = None,
    ) -> list[dict[str, Any]]:
        normalized_query = str(query or "").strip()
        if not normalized_query:
            return []

        params: dict[str, Any] = {
            "project_id": self._config.project_id,
            "q": normalized_query,
            "limit": max(1, min(100, int(limit))),
        }
        if related_entity_key:
            params["related_entity_key"] = related_entity_key
        if context_policy_mode:
            params["context_policy_mode"] = context_policy_mode
        if min_retrieval_confidence is not None:
            params["min_retrieval_confidence"] = min_retrieval_confidence
        if min_total_score is not None:
            params["min_total_score"] = min_total_score
        if min_lexical_score is not None:
            params["min_lexical_score"] = min_lexical_score
        if min_token_overlap_ratio is not None:
            params["min_token_overlap_ratio"] = min_token_overlap_ratio

        response = self._request_json("/v1/mcp/retrieval/explain", method="GET", params=params)
        rows = response.get("results")
        if not isinstance(rows, list):
            rows = response.get("ranked")
        if not isinstance(rows, list):
            return []
        out: list[dict[str, Any]] = []
        for row in rows:
            if isinstance(row, dict):
                out.append(dict(row))
        return out

    def monitor(
        self,
        target: Any,
        *,
        integration: str = "generic",
        include_methods: Sequence[str] | None = None,
        agent_id: str | None = None,
        session_id: str | None = None,
        flush_on_success: bool = False,
        flush_on_error: bool = True,
        capture_arguments: bool = True,
        capture_results: bool = True,
        capture_stream_items: bool = True,
        max_stream_items: int = 25,
    ) -> Any:
        from synapse_sdk.integrations.monitoring import monitor_object

        return monitor_object(
            self,
            target,
            integration=integration,
            include_methods=include_methods,
            agent_id=agent_id,
            session_id=session_id,
            flush_on_success=flush_on_success,
            flush_on_error=flush_on_error,
            capture_arguments=capture_arguments,
            capture_results=capture_results,
            capture_stream_items=capture_stream_items,
            max_stream_items=max_stream_items,
        )

    def monitor_langgraph(self, graph: Any, **kwargs: Any) -> Any:
        from synapse_sdk.integrations.monitoring import monitor_langgraph

        return monitor_langgraph(self, graph, **kwargs)

    def monitor_crewai(self, crew_or_agent: Any, **kwargs: Any) -> Any:
        from synapse_sdk.integrations.monitoring import monitor_crewai

        return monitor_crewai(self, crew_or_agent, **kwargs)

    def monitor_openclaw(self, runtime: Any, **kwargs: Any) -> Any:
        from synapse_sdk.integrations.monitoring import monitor_openclaw_runtime

        return monitor_openclaw_runtime(self, runtime, **kwargs)

    def register_extractor(self, extractor: Extractor, *, replace: bool = True) -> None:
        if not replace and extractor.name in self._extractors:
            raise ValueError(f"extractor already registered: {extractor.name}")
        self._extractors[extractor.name] = extractor
        self._emit_debug("extractor_registered", {"name": extractor.name, "replace": replace})

    def unregister_extractor(self, name: str) -> bool:
        removed = self._extractors.pop(name, None) is not None
        self._emit_debug("extractor_unregistered", {"name": name, "removed": removed})
        return removed

    def list_extractors(self) -> list[str]:
        names = sorted(self._extractors.keys())
        self._emit_debug("extractor_listed", {"count": len(names)})
        return names

    def register_synthesizer(self, synthesizer: Synthesizer, *, replace: bool = True) -> None:
        if not replace and synthesizer.name in self._synthesizers:
            raise ValueError(f"synthesizer already registered: {synthesizer.name}")
        self._synthesizers[synthesizer.name] = synthesizer
        self._emit_debug(
            "synthesizer_registered",
            {
                "name": synthesizer.name,
                "replace": replace,
                "contract_version": getattr(synthesizer, "contract_version", None),
            },
        )

    def unregister_synthesizer(self, name: str) -> bool:
        removed = self._synthesizers.pop(name, None) is not None
        self._emit_debug("synthesizer_unregistered", {"name": name, "removed": removed})
        return removed

    def list_synthesizers(self) -> list[str]:
        names = sorted(self._synthesizers.keys())
        self._emit_debug("synthesizer_listed", {"count": len(names)})
        return names

    def _pop_pending_claims(self) -> list[Claim]:
        with self._pending_lock:
            if not self._pending_claims:
                return []
            claims = list(self._pending_claims)
            self._pending_claims.clear()
        return claims

    def _push_pending_claim(self, claim: Claim, *, to_front: bool = False) -> None:
        with self._pending_lock:
            if to_front:
                self._pending_claims.insert(0, claim)
            else:
                self._pending_claims.append(claim)

    def _pop_pending_backfill(self) -> list[tuple[dict[str, Any], str | None]]:
        with self._pending_lock:
            if not self._pending_backfill:
                return []
            payloads = list(self._pending_backfill)
            self._pending_backfill.clear()
        return payloads

    def _push_pending_backfill(self, payload: dict[str, Any], *, idempotency_key: str | None, to_front: bool = False) -> None:
        with self._pending_lock:
            item = (payload, idempotency_key)
            if to_front:
                self._pending_backfill.insert(0, item)
            else:
                self._pending_backfill.append(item)

    def collect_insight(
        self,
        *,
        category: str | None = None,
        entity_key: str | None = None,
        extractor_names: Sequence[str] | None = None,
        synthesizer_names: Sequence[str] | None = None,
        min_confidence: float = 0.0,
        integration: str = "collect_insight",
        source_type: str = "tool_output",
        agent_id: str | None = None,
        session_id: str | None = None,
        flush_after_propose: bool = False,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        min_conf = max(0.0, min(1.0, float(min_confidence)))

        def _decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            is_async = inspect.iscoroutinefunction(func)
            function_name = f"{func.__module__}.{func.__qualname__}"

            async def _async_wrapped(*args: Any, **kwargs: Any) -> Any:
                call_id = str(uuid4())
                trace_context, tokens = self._push_trace_span(span_id=call_id)
                resolved_session_id = session_id or call_id
                resolved_entity_key = self._resolve_entity_key(entity_key, args=args, kwargs=kwargs, function_name=function_name)
                source_id = f"{function_name}:{call_id}"
                self._emit_debug(
                    "collect_insight_started",
                    {
                        "function": function_name,
                        "integration": integration,
                        "source_id": source_id,
                    },
                    trace_context=trace_context,
                )
                self.capture(
                    event_type="system_signal",
                    payload={
                        "integration": integration,
                        "phase": "collect_insight_started",
                        "function": function_name,
                        "source_id": source_id,
                    },
                    agent_id=agent_id,
                    session_id=resolved_session_id,
                    trace_id=trace_context["trace_id"],
                    span_id=trace_context["span_id"],
                    parent_span_id=trace_context["parent_span_id"],
                    tags=[f"integration:{integration}", "collect_insight"],
                )
                try:
                    result = await func(*args, **kwargs)
                    self._propose_insights_from_result(
                        function_name=function_name,
                        result=result,
                        args=args,
                        kwargs=kwargs,
                        integration=integration,
                        category=category,
                        entity_key=resolved_entity_key,
                        source_type=source_type,
                        source_id=source_id,
                        agent_id=agent_id,
                        session_id=resolved_session_id,
                        extractor_names=extractor_names,
                        synthesizer_names=synthesizer_names,
                        min_confidence=min_conf,
                        trace_context=trace_context,
                        flush_after_propose=flush_after_propose,
                    )
                    return result
                except Exception as exc:
                    self._emit_debug(
                        "collect_insight_failed",
                        {
                            "function": function_name,
                            "integration": integration,
                            "error_type": type(exc).__name__,
                            "error_message": str(exc),
                        },
                        trace_context=trace_context,
                    )
                    self.capture(
                        event_type="system_signal",
                        payload={
                            "integration": integration,
                            "phase": "collect_insight_failed",
                            "function": function_name,
                            "error_type": type(exc).__name__,
                            "error_message": str(exc),
                        },
                        agent_id=agent_id,
                        session_id=resolved_session_id,
                        trace_id=trace_context["trace_id"],
                        span_id=trace_context["span_id"],
                        parent_span_id=trace_context["parent_span_id"],
                        tags=[f"integration:{integration}", "collect_insight"],
                    )
                    raise
                finally:
                    self._pop_trace_span(tokens)

            def _sync_wrapped(*args: Any, **kwargs: Any) -> Any:
                call_id = str(uuid4())
                trace_context, tokens = self._push_trace_span(span_id=call_id)
                resolved_session_id = session_id or call_id
                resolved_entity_key = self._resolve_entity_key(entity_key, args=args, kwargs=kwargs, function_name=function_name)
                source_id = f"{function_name}:{call_id}"
                self._emit_debug(
                    "collect_insight_started",
                    {
                        "function": function_name,
                        "integration": integration,
                        "source_id": source_id,
                    },
                    trace_context=trace_context,
                )
                self.capture(
                    event_type="system_signal",
                    payload={
                        "integration": integration,
                        "phase": "collect_insight_started",
                        "function": function_name,
                        "source_id": source_id,
                    },
                    agent_id=agent_id,
                    session_id=resolved_session_id,
                    trace_id=trace_context["trace_id"],
                    span_id=trace_context["span_id"],
                    parent_span_id=trace_context["parent_span_id"],
                    tags=[f"integration:{integration}", "collect_insight"],
                )
                try:
                    result = func(*args, **kwargs)
                    self._propose_insights_from_result(
                        function_name=function_name,
                        result=result,
                        args=args,
                        kwargs=kwargs,
                        integration=integration,
                        category=category,
                        entity_key=resolved_entity_key,
                        source_type=source_type,
                        source_id=source_id,
                        agent_id=agent_id,
                        session_id=resolved_session_id,
                        extractor_names=extractor_names,
                        synthesizer_names=synthesizer_names,
                        min_confidence=min_conf,
                        trace_context=trace_context,
                        flush_after_propose=flush_after_propose,
                    )
                    return result
                except Exception as exc:
                    self._emit_debug(
                        "collect_insight_failed",
                        {
                            "function": function_name,
                            "integration": integration,
                            "error_type": type(exc).__name__,
                            "error_message": str(exc),
                        },
                        trace_context=trace_context,
                    )
                    self.capture(
                        event_type="system_signal",
                        payload={
                            "integration": integration,
                            "phase": "collect_insight_failed",
                            "function": function_name,
                            "error_type": type(exc).__name__,
                            "error_message": str(exc),
                        },
                        agent_id=agent_id,
                        session_id=resolved_session_id,
                        trace_id=trace_context["trace_id"],
                        span_id=trace_context["span_id"],
                        parent_span_id=trace_context["parent_span_id"],
                        tags=[f"integration:{integration}", "collect_insight"],
                    )
                    raise
                finally:
                    self._pop_trace_span(tokens)

            if is_async:
                return _async_wrapped
            return _sync_wrapped

        return _decorator

    def _serialize_backfill_record(self, record: MemoryBackfillRecord) -> dict[str, Any]:
        return {
            "source_id": record.source_id,
            "content": record.content,
            "observed_at": record.observed_at,
            "entity_key": record.entity_key,
            "category": record.category,
            "metadata": dict(record.metadata),
            "tags": list(record.tags),
        }

    def _request_json(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        request_json = getattr(self._transport, "request_json", None)
        if not callable(request_json):
            raise RuntimeError("Task API methods require HttpTransport-compatible transport with `request_json`.")
        response = request_json(
            path,
            method=method,
            payload=payload,
            params=params,
            idempotency_key=idempotency_key,
        )
        return response if isinstance(response, dict) else {}

    def _propose_insights_from_result(
        self,
        *,
        function_name: str,
        result: Any,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        integration: str,
        category: str | None,
        entity_key: str,
        source_type: str,
        source_id: str,
        agent_id: str | None,
        session_id: str,
        extractor_names: Sequence[str] | None,
        synthesizer_names: Sequence[str] | None,
        min_confidence: float,
        trace_context: dict[str, str | None],
        flush_after_propose: bool,
    ) -> None:
        context = InsightContext(
            function_name=function_name,
            integration=integration,
            args=args,
            kwargs=kwargs,
            result=result,
            category_hint=category,
            entity_hint=entity_key,
            trace_id=trace_context.get("trace_id"),
            span_id=trace_context.get("span_id"),
            parent_span_id=trace_context.get("parent_span_id"),
            source_id=source_id,
        )
        extracted = self._run_extractors(context, extractor_names=extractor_names)
        synthesized = self._run_synthesizers(
            context=context,
            extracted=extracted,
            synthesizer_names=synthesizer_names,
        )
        dedup: set[tuple[str, str, str]] = set()
        proposed = 0
        skipped_low_confidence = 0
        skipped_duplicate = 0
        skipped_empty = 0
        self._emit_debug(
            "collect_insight_extracted",
            {
                "function": function_name,
                "integration": integration,
                "extracted_count": len(extracted),
                "extractor_names": list(extractor_names) if extractor_names else self.list_extractors(),
            },
            trace_context=trace_context,
        )
        self._emit_debug(
            "collect_insight_synthesized",
            {
                "function": function_name,
                "integration": integration,
                "input_count": len(extracted),
                "output_count": len(synthesized),
                "synthesizer_names": list(synthesizer_names) if synthesizer_names else self.list_synthesizers(),
            },
            trace_context=trace_context,
        )
        for insight in synthesized:
            claim_text = str(insight.claim_text).strip()
            if not claim_text:
                skipped_empty += 1
                self._emit_debug(
                    "collect_insight_skipped_empty_claim",
                    {
                        "function": function_name,
                        "integration": integration,
                        "extractor": insight.metadata.get("extractor"),
                    },
                    trace_context=trace_context,
                )
                continue
            insight_confidence = insight.confidence if insight.confidence is not None else 0.65
            if insight_confidence < min_confidence:
                skipped_low_confidence += 1
                self._emit_debug(
                    "collect_insight_skipped_low_confidence",
                    {
                        "function": function_name,
                        "integration": integration,
                        "extractor": insight.metadata.get("extractor"),
                        "confidence": insight_confidence,
                        "min_confidence": min_confidence,
                    },
                    trace_context=trace_context,
                )
                continue
            resolved_category = str(insight.category or category or "general").strip() or "general"
            resolved_entity = str(insight.entity_key or entity_key or "unknown_entity").strip() or "unknown_entity"
            key = (resolved_entity.lower(), resolved_category.lower(), claim_text.lower())
            if key in dedup:
                skipped_duplicate += 1
                self._emit_debug(
                    "collect_insight_skipped_duplicate",
                    {
                        "function": function_name,
                        "integration": integration,
                        "extractor": insight.metadata.get("extractor"),
                        "entity_key": resolved_entity,
                        "category": resolved_category,
                    },
                    trace_context=trace_context,
                )
                continue
            dedup.add(key)

            metadata = {
                "integration": integration,
                "function": function_name,
                "extractor": insight.metadata.get("extractor"),
                "source_id": source_id,
                "trace_id": trace_context.get("trace_id"),
                "span_id": trace_context.get("span_id"),
                "parent_span_id": trace_context.get("parent_span_id"),
            }
            metadata.update(dict(insight.metadata))
            claim = Claim(
                id=str(uuid4()),
                schema_version="v1",
                project_id=self._config.project_id,
                entity_key=resolved_entity,
                category=resolved_category,
                claim_text=claim_text,
                status="draft",
                evidence=[
                    EvidenceRef(
                        source_type=source_type,  # type: ignore[arg-type]
                        source_id=source_id,
                        session_id=session_id,
                        tool_name=function_name,
                        snippet=claim_text[:280],
                        observed_at=datetime.now(UTC).isoformat(),
                    )
                ],
                confidence=max(0.0, min(1.0, float(insight_confidence))),
                valid_from=insight.valid_from,
                valid_to=insight.valid_to,
                metadata=metadata,
            )
            self.propose_fact(claim)
            proposed += 1
            self._emit_debug(
                "collect_insight_proposed",
                {
                    "function": function_name,
                    "integration": integration,
                    "claim_id": claim.id,
                    "extractor": metadata.get("extractor"),
                    "entity_key": resolved_entity,
                    "category": resolved_category,
                    "confidence": claim.confidence,
                },
                trace_context=trace_context,
            )
            self.capture(
                event_type="fact_proposed",
                payload={
                    "integration": integration,
                    "phase": "collect_insight_proposed",
                    "function": function_name,
                    "claim_id": claim.id,
                    "category": resolved_category,
                    "entity_key": resolved_entity,
                    "confidence": claim.confidence,
                    "source_id": source_id,
                    "extractor": metadata.get("extractor"),
                },
                agent_id=agent_id,
                session_id=session_id,
                trace_id=trace_context.get("trace_id"),
                span_id=trace_context.get("span_id"),
                parent_span_id=trace_context.get("parent_span_id"),
                tags=[f"integration:{integration}", "collect_insight"],
            )
        if flush_after_propose and proposed > 0:
            self.flush()
            self._emit_debug(
                "collect_insight_flush_after_propose",
                {"function": function_name, "integration": integration, "proposed_count": proposed},
                trace_context=trace_context,
            )
        self._emit_debug(
            "collect_insight_completed",
            {
                "function": function_name,
                "integration": integration,
                "proposed_count": proposed,
                "skipped_low_confidence": skipped_low_confidence,
                "skipped_duplicate": skipped_duplicate,
                "skipped_empty": skipped_empty,
            },
            trace_context=trace_context,
        )

    def _run_extractors(
        self,
        context: InsightContext,
        *,
        extractor_names: Sequence[str] | None,
    ) -> list[ExtractedInsight]:
        if extractor_names:
            extractors: list[Extractor] = []
            for name in extractor_names:
                extractor = self._extractors.get(name)
                if extractor is None:
                    raise ValueError(f"unknown extractor: {name}")
                extractors.append(extractor)
        else:
            extractors = list(self._extractors.values())

        results: list[ExtractedInsight] = []
        for extractor in extractors:
            try:
                self._emit_debug(
                    "extractor_started",
                    {
                        "extractor": extractor.name,
                        "integration": context.integration,
                        "function": context.function_name,
                    },
                    trace_context={
                        "trace_id": context.trace_id,
                        "span_id": context.span_id,
                        "parent_span_id": context.parent_span_id,
                    },
                )
                extracted = extractor.extract(context)
                self._emit_debug(
                    "extractor_completed",
                    {
                        "extractor": extractor.name,
                        "integration": context.integration,
                        "function": context.function_name,
                        "produced_count": len(extracted),
                    },
                    trace_context={
                        "trace_id": context.trace_id,
                        "span_id": context.span_id,
                        "parent_span_id": context.parent_span_id,
                    },
                )
            except Exception as exc:
                self._emit_debug(
                    "extractor_failed",
                    {
                        "extractor": extractor.name,
                        "integration": context.integration,
                        "function": context.function_name,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    },
                    trace_context={
                        "trace_id": context.trace_id,
                        "span_id": context.span_id,
                        "parent_span_id": context.parent_span_id,
                    },
                )
                self.capture(
                    event_type="system_signal",
                    payload={
                        "integration": context.integration,
                        "phase": "extractor_failed",
                        "extractor": extractor.name,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    },
                    session_id=context.source_id or str(uuid4()),
                    trace_id=context.trace_id,
                    span_id=context.span_id,
                    parent_span_id=context.parent_span_id,
                    tags=[f"integration:{context.integration}", "collect_insight", "extractor_failed"],
                )
                continue
            for item in extracted:
                metadata = dict(item.metadata)
                metadata.setdefault("extractor", extractor.name)
                results.append(
                    ExtractedInsight(
                        claim_text=item.claim_text,
                        category=item.category,
                        entity_key=item.entity_key,
                        confidence=item.confidence,
                        metadata=metadata,
                        valid_from=item.valid_from,
                        valid_to=item.valid_to,
                    )
                )
        return results

    def _run_synthesizers(
        self,
        *,
        context: InsightContext,
        extracted: Sequence[ExtractedInsight],
        synthesizer_names: Sequence[str] | None,
    ) -> list[ExtractedInsight]:
        if synthesizer_names:
            synthesizers: list[Synthesizer] = []
            for name in synthesizer_names:
                synthesizer = self._synthesizers.get(name)
                if synthesizer is None:
                    raise ValueError(f"unknown synthesizer: {name}")
                synthesizers.append(synthesizer)
        else:
            synthesizers = list(self._synthesizers.values())

        current: list[ExtractedInsight] = list(extracted)
        for synthesizer in synthesizers:
            trace_context = {
                "trace_id": context.trace_id,
                "span_id": context.span_id,
                "parent_span_id": context.parent_span_id,
            }
            self._emit_debug(
                "synthesizer_started",
                {
                    "synthesizer": synthesizer.name,
                    "contract_version": getattr(synthesizer, "contract_version", None),
                    "integration": context.integration,
                    "function": context.function_name,
                    "input_count": len(current),
                },
                trace_context=trace_context,
            )
            synthesis_context = SynthesisContext(
                function_name=context.function_name,
                integration=context.integration,
                extracted_insights=tuple(current),
                args=context.args,
                kwargs=context.kwargs,
                result=context.result,
                category_hint=context.category_hint,
                entity_hint=context.entity_hint,
                trace_id=context.trace_id,
                span_id=context.span_id,
                parent_span_id=context.parent_span_id,
                source_id=context.source_id,
            )
            try:
                synthesized = synthesizer.synthesize(synthesis_context)
            except Exception as exc:
                self._emit_debug(
                    "synthesizer_failed",
                    {
                        "synthesizer": synthesizer.name,
                        "integration": context.integration,
                        "function": context.function_name,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    },
                    trace_context=trace_context,
                )
                self.capture(
                    event_type="system_signal",
                    payload={
                        "integration": context.integration,
                        "phase": "synthesizer_failed",
                        "synthesizer": synthesizer.name,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    },
                    session_id=context.source_id or str(uuid4()),
                    trace_id=context.trace_id,
                    span_id=context.span_id,
                    parent_span_id=context.parent_span_id,
                    tags=[f"integration:{context.integration}", "collect_insight", "synthesizer_failed"],
                )
                continue

            normalized: list[ExtractedInsight] = []
            for item in synthesized:
                metadata = dict(item.metadata)
                metadata.setdefault("synthesizer", synthesizer.name)
                normalized.append(
                    ExtractedInsight(
                        claim_text=item.claim_text,
                        category=item.category,
                        entity_key=item.entity_key,
                        confidence=item.confidence,
                        metadata=metadata,
                        valid_from=item.valid_from,
                        valid_to=item.valid_to,
                    )
                )
            current = normalized
            self._emit_debug(
                "synthesizer_completed",
                {
                    "synthesizer": synthesizer.name,
                    "integration": context.integration,
                    "function": context.function_name,
                    "output_count": len(current),
                },
                trace_context=trace_context,
            )
        return current

    def _resolve_entity_key(
        self,
        explicit_entity_key: str | None,
        *,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        function_name: str,
    ) -> str:
        if explicit_entity_key:
            return explicit_entity_key.strip()
        for key in ("entity_key", "entity", "resource_id", "customer_id", "building_id", "order_id"):
            raw = kwargs.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
        if args and isinstance(args[0], str) and args[0].strip():
            return args[0].strip()
        slug = function_name.lower().replace(".", "_").replace(":", "_")
        return slug[:128] or "unknown_entity"

    def current_trace_context(self) -> dict[str, str | None]:
        return {
            "trace_id": _TRACE_ID.get(),
            "span_id": _SPAN_ID.get(),
        }

    def _push_trace_span(
        self,
        *,
        trace_id: str | None = None,
        span_id: str | None = None,
    ) -> tuple[dict[str, str | None], tuple[Token[str | None], Token[str | None]]]:
        parent_trace_id = _TRACE_ID.get()
        parent_span_id = _SPAN_ID.get()
        resolved_trace_id = trace_id or parent_trace_id or str(uuid4())
        resolved_span_id = span_id or str(uuid4())
        trace_token = _TRACE_ID.set(resolved_trace_id)
        span_token = _SPAN_ID.set(resolved_span_id)
        context = {
            "trace_id": resolved_trace_id,
            "span_id": resolved_span_id,
            "parent_span_id": parent_span_id,
        }
        return context, (trace_token, span_token)

    def _pop_trace_span(self, tokens: tuple[Token[str | None], Token[str | None]]) -> None:
        trace_token, span_token = tokens
        _SPAN_ID.reset(span_token)
        _TRACE_ID.reset(trace_token)

    def _resolve_trace_fields(
        self,
        *,
        trace_id: str | None,
        span_id: str | None,
        parent_span_id: str | None,
    ) -> tuple[str | None, str | None, str | None]:
        current_trace_id = _TRACE_ID.get()
        current_span_id = _SPAN_ID.get()
        resolved_trace_id = trace_id or current_trace_id
        resolved_span_id = span_id or current_span_id
        resolved_parent_span_id = parent_span_id
        if resolved_parent_span_id is None and current_span_id and resolved_span_id and resolved_span_id != current_span_id:
            resolved_parent_span_id = current_span_id
        return resolved_trace_id, resolved_span_id, resolved_parent_span_id

    def _payload_with_trace(
        self,
        *,
        payload: dict[str, object],
        trace_id: str | None,
        span_id: str | None,
        parent_span_id: str | None,
    ) -> dict[str, object]:
        payload_out = dict(payload)
        if trace_id is None and span_id is None and parent_span_id is None:
            return payload_out
        synapse_meta = payload_out.get("_synapse")
        meta: dict[str, Any] = dict(synapse_meta) if isinstance(synapse_meta, dict) else {}
        if trace_id is not None:
            meta["trace_id"] = trace_id
        if span_id is not None:
            meta["span_id"] = span_id
        if parent_span_id is not None:
            meta["parent_span_id"] = parent_span_id
        payload_out["_synapse"] = meta
        return payload_out

    def _emit_debug(
        self,
        event: str,
        details: dict[str, Any],
        *,
        trace_context: dict[str, str | None] | None = None,
    ) -> None:
        if not self._debug_mode and self._telemetry_sink is None:
            return
        trace = trace_context or self.current_trace_context()
        record = {
            "ts": datetime.now(UTC).isoformat(),
            "event": event,
            "project_id": self._config.project_id,
            "trace_id": trace.get("trace_id"),
            "span_id": trace.get("span_id"),
            "parent_span_id": trace.get("parent_span_id"),
            "details": details,
        }
        if self._telemetry_sink is not None:
            try:
                self._telemetry_sink(record)
            except Exception:
                pass
        if not self._debug_mode:
            return
        with self._debug_lock:
            self._debug_records.append(record)
            overflow = len(self._debug_records) - self._debug_max_records
            if overflow > 0:
                del self._debug_records[:overflow]
        if self._debug_sink is not None:
            try:
                self._debug_sink(record)
            except Exception:
                return


class Synapse(SynapseClient):
    """High-level developer-first facade over SynapseClient."""

    @classmethod
    def from_env(
        cls,
        *,
        api_url: str | None = None,
        project_id: str | None = None,
        api_key: str | None = None,
        degradation_mode: str | None = None,
        transport: Transport | None = None,
    ) -> "Synapse":
        resolved_api_url = _coerce_str_or_none(api_url) or _coerce_str_or_none(os.getenv("SYNAPSE_API_URL"))
        if resolved_api_url is None:
            resolved_api_url = "http://localhost:8080"

        resolved_project_id = _coerce_str_or_none(project_id) or _coerce_str_or_none(os.getenv("SYNAPSE_PROJECT_ID"))
        if resolved_project_id is None:
            resolved_project_id = _infer_project_id_from_cwd()

        resolved_api_key = _coerce_str_or_none(api_key)
        if resolved_api_key is None:
            resolved_api_key = _coerce_str_or_none(os.getenv("SYNAPSE_API_KEY"))

        resolved_degradation_mode = _coerce_str_or_none(degradation_mode)
        if resolved_degradation_mode is None:
            resolved_degradation_mode = _coerce_str_or_none(os.getenv("SYNAPSE_DEGRADATION_MODE")) or "buffer"

        return cls(
            SynapseConfig(
                api_url=resolved_api_url,
                project_id=resolved_project_id,
                api_key=resolved_api_key,
                degradation_mode=resolved_degradation_mode,  # type: ignore[arg-type]
            ),
            transport=transport,
        )

    def attach(
        self,
        target: Any,
        *,
        integration: str | None = None,
        include_methods: Sequence[str] | None = None,
        agent_id: str | None = None,
        session_id: str | None = None,
        flush_on_success: bool = False,
        flush_on_error: bool = True,
        capture_arguments: bool = True,
        capture_results: bool = True,
        capture_stream_items: bool = True,
        max_stream_items: int = 25,
        openclaw_hook_events: Sequence[str] | None = None,
        openclaw_register_tools: bool = True,
        openclaw_tool_prefix: str = "synapse",
        openclaw_search_knowledge: Callable[..., Any] | None = None,
        bootstrap_memory: BootstrapMemoryOptions | None = None,
        openclaw_bootstrap_preset: str | None = None,
        openclaw_bootstrap_max_records: int = 1000,
        openclaw_bootstrap_source_system: str | None = None,
        openclaw_bootstrap_created_by: str | None = "sdk_attach",
        openclaw_bootstrap_cursor: str | None = None,
        openclaw_bootstrap_chunk_size: int = 100,
        openclaw_auto_bootstrap: bool = True,
    ) -> Any:
        resolved_integration = integration or self._detect_integration(target)
        self._emit_debug(
            "attach_started",
            {
                "integration": resolved_integration,
                "target_type": type(target).__name__,
                "auto_bootstrap_enabled": bool(openclaw_auto_bootstrap),
            },
        )
        resolved_bootstrap_memory = bootstrap_memory
        resolved_openclaw_bootstrap_preset = openclaw_bootstrap_preset
        if (
            resolved_openclaw_bootstrap_preset is None
            and openclaw_auto_bootstrap
            and bootstrap_memory is None
            and resolved_integration == "openclaw"
            and self._looks_like_openclaw_runtime(target)
        ):
            resolved_openclaw_bootstrap_preset = (
                _coerce_str_or_none(os.getenv("SYNAPSE_OPENCLAW_BOOTSTRAP_PRESET")) or "hybrid"
            )
            self._emit_debug(
                "attach_openclaw_bootstrap_auto_enabled",
                {
                    "integration": resolved_integration,
                    "preset": resolved_openclaw_bootstrap_preset,
                    "source": (
                        "env"
                        if _coerce_str_or_none(os.getenv("SYNAPSE_OPENCLAW_BOOTSTRAP_PRESET")) is not None
                        else "default"
                    ),
                },
            )
        if resolved_openclaw_bootstrap_preset is not None:
            if bootstrap_memory is not None:
                self._emit_debug(
                    "attach_openclaw_bootstrap_preset_ignored",
                    {
                        "integration": resolved_integration,
                        "preset": resolved_openclaw_bootstrap_preset,
                        "reason": "bootstrap_memory_provided",
                    },
                )
            elif resolved_integration == "openclaw" and self._looks_like_openclaw_runtime(target):
                from synapse_sdk.integrations.openclaw import build_openclaw_bootstrap_options

                resolved_bootstrap_memory = build_openclaw_bootstrap_options(
                    preset=resolved_openclaw_bootstrap_preset,
                    max_records=openclaw_bootstrap_max_records,
                    source_system=openclaw_bootstrap_source_system,
                    created_by=openclaw_bootstrap_created_by,
                    cursor=openclaw_bootstrap_cursor,
                    chunk_size=openclaw_bootstrap_chunk_size,
                )
                self._emit_debug(
                    "attach_openclaw_bootstrap_preset_enabled",
                    {
                        "integration": resolved_integration,
                        "preset": resolved_openclaw_bootstrap_preset,
                        "source_system": resolved_bootstrap_memory.source_system,
                        "max_records": resolved_bootstrap_memory.max_records,
                        "chunk_size": resolved_bootstrap_memory.chunk_size,
                    },
                )
            else:
                self._emit_debug(
                    "attach_openclaw_bootstrap_preset_skipped",
                    {
                        "integration": resolved_integration,
                        "preset": resolved_openclaw_bootstrap_preset,
                        "reason": "target_is_not_openclaw_runtime",
                    },
                )
        self._run_attach_bootstrap(
            target=target,
            integration=resolved_integration,
            bootstrap_memory=resolved_bootstrap_memory,
            agent_id=agent_id,
            session_id=session_id,
        )
        if resolved_integration == "openclaw" and self._looks_like_openclaw_runtime(target):
            from synapse_sdk.integrations.openclaw import DEFAULT_OPENCLAW_EVENTS, OpenClawConnector

            connector = OpenClawConnector(
                self,
                search_knowledge=openclaw_search_knowledge,
                default_agent_id=agent_id,
                default_session_id=session_id,
            )
            connector.attach(
                target,
                hook_events=openclaw_hook_events or DEFAULT_OPENCLAW_EVENTS,
                register_tools=openclaw_register_tools,
                tool_prefix=openclaw_tool_prefix,
            )
            self._emit_debug(
                "attach_completed",
                {
                    "integration": resolved_integration,
                    "mode": "openclaw_connector",
                    "registered_tools": list(connector.last_registered_tools),
                    "bootstrap_requested": resolved_bootstrap_memory is not None,
                    "search_mode": (
                        "callback"
                        if openclaw_search_knowledge is not None
                        else ("auto" if connector.auto_search_enabled else "disabled")
                    ),
                },
            )
            return target
        monitored = self.monitor(
            target,
            integration=resolved_integration,
            include_methods=include_methods,
            agent_id=agent_id,
            session_id=session_id,
            flush_on_success=flush_on_success,
            flush_on_error=flush_on_error,
            capture_arguments=capture_arguments,
            capture_results=capture_results,
            capture_stream_items=capture_stream_items,
            max_stream_items=max_stream_items,
        )
        self._emit_debug(
            "attach_completed",
            {
                "integration": resolved_integration,
                "mode": "monitor",
                "bootstrap_requested": resolved_bootstrap_memory is not None,
            },
        )
        return monitored

    def _detect_integration(self, target: Any) -> str:
        if self._looks_like_openclaw_runtime(target):
            return "openclaw"
        return "generic"

    def _looks_like_openclaw_runtime(self, target: Any) -> bool:
        has_hook_api = (hasattr(target, "on") and callable(target.on)) or (
            hasattr(target, "register_hook") and callable(target.register_hook)
        )
        has_tool_api = hasattr(target, "register_tool") and callable(target.register_tool)
        return bool(has_hook_api and has_tool_api)

    def _run_attach_bootstrap(
        self,
        *,
        target: Any,
        integration: str,
        bootstrap_memory: BootstrapMemoryOptions | None,
        agent_id: str | None,
        session_id: str | None,
    ) -> None:
        if bootstrap_memory is None:
            return

        if bootstrap_memory.chunk_size <= 0:
            raise ValueError("bootstrap_memory.chunk_size must be > 0")

        raw_records: Sequence[BootstrapMemoryInput] | None = None
        if bootstrap_memory.provider is not None:
            try:
                raw_records = bootstrap_memory.provider(target)
            except Exception as exc:
                self._emit_debug(
                    "attach_bootstrap_provider_failed",
                    {
                        "integration": integration,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    },
                )
                return
        elif bootstrap_memory.records is not None:
            raw_records = bootstrap_memory.records
        else:
            self._emit_debug(
                "attach_bootstrap_skipped",
                {
                    "integration": integration,
                    "reason": "missing_records_and_provider",
                },
            )
            return

        normalized_records = self._normalize_attach_bootstrap_records(
            raw_records or [],
            max_records=bootstrap_memory.max_records,
        )
        if not normalized_records:
            self._emit_debug(
                "attach_bootstrap_empty",
                {
                    "integration": integration,
                    "source_system": bootstrap_memory.source_system,
                },
            )
            return

        try:
            batch_id = self.backfill_memory(
                normalized_records,
                source_system=bootstrap_memory.source_system,
                created_by=bootstrap_memory.created_by,
                cursor=bootstrap_memory.cursor,
                chunk_size=bootstrap_memory.chunk_size,
                agent_id=agent_id,
                session_id=session_id,
            )
        except Exception as exc:
            self._emit_debug(
                "attach_bootstrap_failed",
                {
                    "integration": integration,
                    "records": len(normalized_records),
                    "source_system": bootstrap_memory.source_system,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
            )
            return

        self._emit_debug(
            "attach_bootstrap_completed",
            {
                "integration": integration,
                "records": len(normalized_records),
                "batch_id": batch_id,
                "source_system": bootstrap_memory.source_system,
            },
        )

    def _normalize_attach_bootstrap_records(
        self,
        records: Sequence[BootstrapMemoryInput],
        *,
        max_records: int,
    ) -> list[MemoryBackfillRecord]:
        limit = max(1, min(int(max_records), 10_000))
        out: list[MemoryBackfillRecord] = []
        dedupe: set[tuple[str, str]] = set()
        for index, item in enumerate(records):
            if len(out) >= limit:
                break
            record = self._coerce_attach_bootstrap_record(item, index=index)
            if record is None:
                continue
            dedupe_key = (record.source_id, record.content.strip())
            if dedupe_key in dedupe:
                continue
            dedupe.add(dedupe_key)
            out.append(record)
        return out

    def _coerce_attach_bootstrap_record(
        self,
        record: BootstrapMemoryInput,
        *,
        index: int,
    ) -> MemoryBackfillRecord | None:
        if isinstance(record, MemoryBackfillRecord):
            source_id = record.source_id.strip()
            content = record.content.strip()
            if not source_id or not content:
                return None
            return MemoryBackfillRecord(
                source_id=source_id,
                content=content,
                observed_at=_coerce_str_or_none(record.observed_at),
                entity_key=_coerce_str_or_none(record.entity_key),
                category=_coerce_str_or_none(record.category),
                metadata=dict(record.metadata or {}),
                tags=[str(item).strip() for item in (record.tags or []) if str(item).strip()],
            )

        if isinstance(record, str):
            content = record.strip()
            if not content:
                return None
            return MemoryBackfillRecord(
                source_id=f"attach_bootstrap_{index + 1}",
                content=content,
            )

        if not isinstance(record, dict):
            return None

        source_id = _coerce_str_or_none(
            record.get("source_id") or record.get("id") or record.get("key") or record.get("memory_id")
        ) or f"attach_bootstrap_{index + 1}"
        content = _coerce_str_or_none(
            record.get("content")
            or record.get("text")
            or record.get("fact")
            or record.get("message")
            or record.get("summary")
        )
        if content is None:
            return None
        metadata_value = record.get("metadata")
        metadata = dict(metadata_value) if isinstance(metadata_value, dict) else {}
        raw_tags = record.get("tags")
        tags: list[str] = []
        if isinstance(raw_tags, list):
            for item in raw_tags:
                text = str(item).strip()
                if text:
                    tags.append(text)
        return MemoryBackfillRecord(
            source_id=source_id,
            content=content,
            observed_at=_coerce_str_or_none(record.get("observed_at") or record.get("timestamp")),
            entity_key=_coerce_str_or_none(record.get("entity_key") or record.get("entity")),
            category=_coerce_str_or_none(record.get("category")),
            metadata=metadata,
            tags=tags,
        )


def _make_claim_idempotency_key(claim_id: str) -> str:
    return f"claim:v1:{claim_id}"


def _make_batch_idempotency_key(events: list[ObservationEvent]) -> str:
    material = "|".join(event.id for event in events)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
    return f"events:v1:{digest}:{len(events)}"


def _make_backfill_idempotency_key(*, batch_id: str, start: int, size: int, finalized: bool) -> str:
    suffix = "final" if finalized else "part"
    return f"backfill:v1:{batch_id}:{start}:{size}:{suffix}"


def _normalize_degradation_mode(value: str | None) -> str:
    normalized = str(value or "buffer").strip().lower()
    if normalized not in {"buffer", "drop", "sync_flush"}:
        raise ValueError(f"invalid degradation mode: {value!r}")
    return normalized


def _coerce_str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _infer_project_id_from_cwd() -> str:
    raw = Path.cwd().name
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", raw).strip("_").lower()
    return normalized or "synapse_project"
