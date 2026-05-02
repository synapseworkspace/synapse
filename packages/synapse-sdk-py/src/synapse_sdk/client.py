from __future__ import annotations

from dataclasses import asdict, is_dataclass, replace
from datetime import datetime, timezone
import hashlib
import inspect
import os
from contextvars import ContextVar, Token
from pathlib import Path
import re
from threading import Lock
from typing import Any, Callable, Mapping, Protocol, Sequence
from urllib.parse import quote
from uuid import UUID, uuid4

from synapse_sdk.extractors import ExtractedInsight, Extractor, InsightContext, default_extractors
from synapse_sdk.synthesizers import SynthesisContext, Synthesizer, default_synthesizers
from synapse_sdk.transports.http import HttpTransport
from synapse_sdk.types import (
    AgentReflection,
    AgentReflectionInsight,
    AgentProfile,
    AdoptionMode,
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
    WikiDraftBulkReviewFilter,
)

_TRACE_ID: ContextVar[str | None] = ContextVar("synapse_trace_id", default=None)
_SPAN_ID: ContextVar[str | None] = ContextVar("synapse_span_id", default=None)
UTC = timezone.utc
_WIKI_PUBLISH_CHECKLIST_PRESETS = {"none", "ops_standard", "policy_strict"}


class Transport(Protocol):
    def send_events(self, events: list[ObservationEvent], *, idempotency_key: str | None = None) -> None: ...
    def propose_fact(self, claim: Claim, *, idempotency_key: str | None = None) -> None: ...
    def ingest_memory_backfill(self, batch_payload: dict[str, Any], *, idempotency_key: str | None = None) -> None: ...
    def ingest_knowledge_backfill(self, batch_payload: dict[str, Any], *, idempotency_key: str | None = None) -> None: ...


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
            ingest_lane = self._resolve_backfill_ingest_lane_from_payload(payload)
            try:
                self._transport_ingest_backfill(
                    payload,
                    ingest_lane=ingest_lane,
                    idempotency_key=idempotency_key,
                )
            except Exception as exc:
                if self._degradation_mode == "drop":
                    self._emit_debug(
                        "flush_pending_backfill_dropped",
                        {
                            "ingest_lane": ingest_lane,
                            "error_type": type(exc).__name__,
                            "error_message": str(exc),
                        },
                    )
                    continue
                self._push_pending_backfill(payload, idempotency_key=idempotency_key, to_front=True)
                self._emit_debug(
                    "flush_pending_backfill_requeued",
                    {
                        "ingest_lane": ingest_lane,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    },
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
        ingest_lane: str = "knowledge",
        source_system: str = "sdk_bootstrap",
        agent_id: str | None = None,
        session_id: str | None = None,
        created_by: str | None = None,
        cursor: str | None = None,
        chunk_size: int = 100,
        curated_enabled: bool | None = None,
        curated_source_systems: Sequence[str] | None = None,
        curated_namespaces: Sequence[str] | None = None,
        noise_preset: str | None = None,
        curated_drop_event_like: bool | None = None,
    ) -> str:
        resolved_ingest_lane = str(ingest_lane or "knowledge").strip().lower()
        if resolved_ingest_lane not in {"event", "knowledge"}:
            raise ValueError("ingest_lane must be either 'event' or 'knowledge'")
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
                    "ingest_lane": resolved_ingest_lane,
                    "agent_id": agent_id,
                    "session_id": session_id,
                    "cursor": cursor if is_last else None,
                    "finalize": is_last,
                    "created_by": created_by,
                    "records": [self._serialize_backfill_record(record) for record in chunk],
                }
            }
            curated_payload: dict[str, Any] = {}
            if curated_enabled is not None:
                curated_payload["enabled"] = bool(curated_enabled)
            if curated_source_systems is not None:
                curated_payload["source_systems"] = [
                    str(item).strip() for item in curated_source_systems if str(item).strip()
                ]
            if curated_namespaces is not None:
                curated_payload["namespaces"] = [str(item).strip() for item in curated_namespaces if str(item).strip()]
            if noise_preset is not None and str(noise_preset).strip():
                curated_payload["noise_preset"] = str(noise_preset).strip().lower()
            if curated_drop_event_like is not None:
                curated_payload["drop_event_like"] = bool(curated_drop_event_like)
            if curated_payload:
                batch_payload["batch"]["curated"] = curated_payload
            try:
                self._transport_ingest_backfill(
                    batch_payload,
                    ingest_lane=resolved_ingest_lane,
                    idempotency_key=idempotency_key,
                )
                self._emit_debug(
                    "backfill_chunk_sent",
                    {
                        "batch_id": resolved_batch_id,
                        "ingest_lane": resolved_ingest_lane,
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
                            "ingest_lane": resolved_ingest_lane,
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
                        "ingest_lane": resolved_ingest_lane,
                        "start": start,
                        "size": len(chunk),
                        "finalized": is_last,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    },
                )
        self._emit_debug(
            "backfill_completed",
            {
                "batch_id": resolved_batch_id,
                "ingest_lane": resolved_ingest_lane,
                "records": total,
                "chunk_size": chunk_size,
            },
        )
        return resolved_batch_id

    def backfill_knowledge(
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
        return self.backfill_memory(
            records,
            batch_id=batch_id,
            ingest_lane="knowledge",
            source_system=source_system,
            agent_id=agent_id,
            session_id=session_id,
            created_by=created_by,
            cursor=cursor,
            chunk_size=chunk_size,
        )

    def explain_curated_backfill(
        self,
        records: Sequence[MemoryBackfillRecord],
        *,
        ingest_lane: str = "knowledge",
        source_system: str = "sdk_bootstrap",
        agent_id: str | None = None,
        session_id: str | None = None,
        created_by: str | None = None,
        cursor: str | None = None,
        curated_enabled: bool | None = None,
        curated_source_systems: Sequence[str] | None = None,
        curated_namespaces: Sequence[str] | None = None,
        noise_preset: str | None = None,
        curated_drop_event_like: bool | None = None,
        sample_limit: int = 12,
    ) -> dict[str, Any]:
        resolved_ingest_lane = str(ingest_lane or "knowledge").strip().lower()
        if resolved_ingest_lane not in {"event", "knowledge"}:
            raise ValueError("ingest_lane must be either 'event' or 'knowledge'")
        if not records:
            raise ValueError("records must not be empty")
        payload: dict[str, Any] = {
            "batch": {
                "project_id": self._config.project_id,
                "source_system": source_system,
                "ingest_lane": resolved_ingest_lane,
                "agent_id": agent_id,
                "session_id": session_id,
                "cursor": cursor,
                "finalize": True,
                "created_by": created_by,
                "records": [self._serialize_backfill_record(record) for record in records],
            }
        }
        curated_payload: dict[str, Any] = {}
        if curated_enabled is not None:
            curated_payload["enabled"] = bool(curated_enabled)
        if curated_source_systems is not None:
            curated_payload["source_systems"] = [str(item).strip() for item in curated_source_systems if str(item).strip()]
        if curated_namespaces is not None:
            curated_payload["namespaces"] = [str(item).strip() for item in curated_namespaces if str(item).strip()]
        if noise_preset is not None and str(noise_preset).strip():
            curated_payload["noise_preset"] = str(noise_preset).strip().lower()
        if curated_drop_event_like is not None:
            curated_payload["drop_event_like"] = bool(curated_drop_event_like)
        if curated_payload:
            payload["batch"]["curated"] = curated_payload
        return self._request_json(
            "/v1/backfill/curated-explain",
            method="POST",
            payload=payload,
            params={"sample_limit": max(1, min(100, int(sample_limit)))},
        )

    def list_adoption_import_connectors(
        self,
        *,
        source_type: str = "postgres_sql",
        profile: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "source_type": str(source_type or "postgres_sql").strip().lower() or "postgres_sql",
        }
        if profile is not None and str(profile).strip():
            params["profile"] = str(profile).strip()
        return self._request_json(
            "/v1/adoption/import-connectors",
            method="GET",
            params=params,
        )

    def resolve_adoption_import_connector(
        self,
        *,
        connector_id: str,
        source_type: str = "postgres_sql",
        field_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_connector_id = str(connector_id or "").strip()
        if not normalized_connector_id:
            raise ValueError("connector_id is required")
        return self._request_json(
            "/v1/adoption/import-connectors/resolve",
            method="POST",
            payload={
                "source_type": str(source_type or "postgres_sql").strip().lower() or "postgres_sql",
                "connector_id": normalized_connector_id,
                "project_id": self._config.project_id,
                "field_overrides": dict(field_overrides or {}),
            },
        )

    def bootstrap_adoption_import_connector(
        self,
        *,
        updated_by: str,
        connector_id: str,
        source_type: str = "postgres_sql",
        source_ref: str | None = None,
        field_overrides: dict[str, Any] | None = None,
        enabled: bool = True,
        sync_interval_minutes: int = 60,
        queue_sync: bool = True,
        dry_run: bool = True,
        sync_processor_lookback_minutes: int = 30,
        fail_on_sync_processor_unavailable: bool = False,
    ) -> dict[str, Any]:
        actor = str(updated_by or "").strip()
        if not actor:
            raise ValueError("updated_by is required")
        normalized_connector_id = str(connector_id or "").strip()
        if not normalized_connector_id:
            raise ValueError("connector_id is required")
        normalized_source_type = str(source_type or "postgres_sql").strip().lower() or "postgres_sql"
        if normalized_source_type not in {"postgres_sql", "memory_api"}:
            raise ValueError("source_type must be one of: postgres_sql, memory_api")
        payload: dict[str, Any] = {
            "project_id": self._config.project_id,
            "updated_by": actor,
            "source_type": normalized_source_type,
            "connector_id": normalized_connector_id,
            "source_ref": str(source_ref).strip() if source_ref is not None and str(source_ref).strip() else None,
            "field_overrides": dict(field_overrides or {}),
            "enabled": bool(enabled),
            "sync_interval_minutes": max(1, min(10080, int(sync_interval_minutes))),
            "queue_sync": bool(queue_sync),
            "dry_run": bool(dry_run),
            "confirm_project_id": self._config.project_id if not dry_run else None,
            "sync_processor_lookback_minutes": max(1, min(1440, int(sync_processor_lookback_minutes))),
            "fail_on_sync_processor_unavailable": bool(fail_on_sync_processor_unavailable),
        }
        return self._request_json(
            "/v1/adoption/import-connectors/bootstrap",
            method="POST",
            payload=payload,
            idempotency_key=str(uuid4()),
        )

    def list_adoption_noise_presets(
        self,
        *,
        lane: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if lane is not None and str(lane).strip():
            normalized_lane = str(lane).strip().lower()
            if normalized_lane not in {"event", "knowledge"}:
                raise ValueError("lane must be one of: event, knowledge")
            params["lane"] = normalized_lane
        return self._request_json(
            "/v1/adoption/noise-presets",
            method="GET",
            params=params,
        )

    def get_adoption_kpi(self, *, days: int = 30) -> dict[str, Any]:
        return self._request_json(
            "/v1/adoption/kpi",
            method="GET",
            params={
                "project_id": self._config.project_id,
                "days": max(1, min(180, int(days))),
            },
        )

    def get_adoption_knowledge_gaps(
        self,
        *,
        days: int = 14,
        max_items_per_bucket: int = 8,
    ) -> dict[str, Any]:
        return self._request_json(
            "/v1/adoption/knowledge-gaps",
            method="GET",
            params={
                "project_id": self._config.project_id,
                "days": max(1, min(90, int(days))),
                "max_items_per_bucket": max(1, min(50, int(max_items_per_bucket))),
            },
        )

    def sync_adoption_knowledge_gap_tasks(
        self,
        *,
        created_by: str,
        updated_by: str | None = None,
        assignee: str | None = None,
        dry_run: bool = True,
        confirm_project_id: str | None = None,
        days: int = 14,
        limit_per_kind: int = 6,
        include_candidate_bundles: bool = True,
        include_page_enrichment_gaps: bool = True,
        include_unresolved_questions: bool = True,
        include_repeated_escalations: bool = True,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        actor = str(created_by or "").strip()
        if not actor:
            raise ValueError("created_by is required")
        return self._request_json(
            "/v1/adoption/knowledge-gaps/tasks/sync",
            method="POST",
            payload={
                "project_id": self._config.project_id,
                "created_by": actor,
                "updated_by": str(updated_by).strip() if updated_by is not None and str(updated_by).strip() else None,
                "assignee": str(assignee).strip() if assignee is not None and str(assignee).strip() else None,
                "dry_run": bool(dry_run),
                "confirm_project_id": (
                    self._config.project_id if not dry_run and confirm_project_id is None else confirm_project_id
                ),
                "days": max(1, min(90, int(days))),
                "limit_per_kind": max(1, min(25, int(limit_per_kind))),
                "include_candidate_bundles": bool(include_candidate_bundles),
                "include_page_enrichment_gaps": bool(include_page_enrichment_gaps),
                "include_unresolved_questions": bool(include_unresolved_questions),
                "include_repeated_escalations": bool(include_repeated_escalations),
            },
            idempotency_key=idempotency_key or str(uuid4()),
        )

    def get_adoption_signal_noise_audit(
        self,
        *,
        days: int = 14,
        max_items_per_bucket: int = 8,
    ) -> dict[str, Any]:
        return self._request_json(
            "/v1/adoption/signal-noise/audit",
            method="GET",
            params={
                "project_id": self._config.project_id,
                "days": max(1, min(90, int(days))),
                "max_items_per_bucket": max(1, min(50, int(max_items_per_bucket))),
            },
        )

    def get_adoption_stability_monitor(
        self,
        *,
        days: int = 14,
        max_items_per_bucket: int = 8,
    ) -> dict[str, Any]:
        return self._request_json(
            "/v1/adoption/stability-monitor",
            method="GET",
            params={
                "project_id": self._config.project_id,
                "days": max(1, min(90, int(days))),
                "max_items_per_bucket": max(1, min(50, int(max_items_per_bucket))),
            },
        )

    def get_adoption_synthesis_prompts(
        self,
        *,
        days: int = 14,
        max_items: int = 8,
    ) -> dict[str, Any]:
        return self._request_json(
            "/v1/adoption/synthesis-prompts",
            method="GET",
            params={
                "project_id": self._config.project_id,
                "days": max(1, min(90, int(days))),
                "max_items": max(1, min(50, int(max_items))),
            },
        )

    def run_adoption_bundle_promotion(
        self,
        *,
        updated_by: str,
        dry_run: bool = True,
        confirm_project_id: str | None = None,
        publish: bool = True,
        bootstrap_publish_core: bool = True,
        space_key: str = "operations",
        include_data_sources_catalog: bool = True,
        include_agent_capability_profile: bool = True,
        include_process_playbooks: bool = True,
        include_decisions_log: bool = True,
        include_company_operating_context: bool = True,
        include_operational_logic_map: bool = True,
        max_sources: int = 20,
        max_agents: int = 12,
        max_signals: int = 50,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self._request_json(
            "/v1/adoption/bundle-promotion/run",
            method="POST",
            payload={
                "project_id": self._config.project_id,
                "updated_by": updated_by,
                "dry_run": bool(dry_run),
                "confirm_project_id": (
                    self._config.project_id if not dry_run and confirm_project_id is None else confirm_project_id
                ),
                "publish": bool(publish),
                "bootstrap_publish_core": bool(bootstrap_publish_core),
                "space_key": _normalize_space_key(space_key),
                "include_data_sources_catalog": bool(include_data_sources_catalog),
                "include_agent_capability_profile": bool(include_agent_capability_profile),
                "include_process_playbooks": bool(include_process_playbooks),
                "include_decisions_log": bool(include_decisions_log),
                "include_company_operating_context": bool(include_company_operating_context),
                "include_operational_logic_map": bool(include_operational_logic_map),
                "max_sources": max(1, min(200, int(max_sources))),
                "max_agents": max(1, min(100, int(max_agents))),
                "max_signals": max(1, min(500, int(max_signals))),
            },
            idempotency_key=idempotency_key or str(uuid4()),
        )

    def get_adoption_policy_calibration_quick_loop(self, *, days: int = 14) -> dict[str, Any]:
        return self._request_json(
            "/v1/adoption/policy-calibration/quick-loop",
            method="GET",
            params={
                "project_id": self._config.project_id,
                "days": max(1, min(90, int(days))),
            },
        )

    def apply_adoption_policy_calibration_quick_loop(
        self,
        *,
        updated_by: str,
        preset_key: str | None = None,
        dry_run: bool = True,
        note: str | None = None,
    ) -> dict[str, Any]:
        actor = str(updated_by or "").strip()
        if not actor:
            raise ValueError("updated_by is required")
        payload: dict[str, Any] = {
            "project_id": self._config.project_id,
            "updated_by": actor,
            "dry_run": bool(dry_run),
            "confirm_project_id": self._config.project_id if not dry_run else None,
            "preset_key": str(preset_key).strip() if preset_key is not None and str(preset_key).strip() else None,
            "note": str(note).strip() if note is not None and str(note).strip() else None,
        }
        return self._request_json(
            "/v1/adoption/policy-calibration/quick-loop/apply",
            method="POST",
            payload=payload,
            idempotency_key=str(uuid4()),
        )

    def get_selfhost_consistency_gate(
        self,
        *,
        web_build: str | None = None,
        ui_profile: str | None = None,
        route_path: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if web_build is not None and str(web_build).strip():
            params["web_build"] = str(web_build).strip()
        if ui_profile is not None and str(ui_profile).strip():
            params["ui_profile"] = str(ui_profile).strip()
        if route_path is not None and str(route_path).strip():
            params["route_path"] = str(route_path).strip()
        return self._request_json(
            "/v1/adoption/selfhost/consistency",
            method="GET",
            params=params,
        )

    def get_enterprise_readiness(self, *, project_id: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if project_id is not None and str(project_id).strip():
            params["project_id"] = str(project_id).strip()
        return self._request_json(
            "/v1/enterprise/readiness",
            method="GET",
            params=params,
        )

    def run_adoption_first_run_bootstrap(
        self,
        *,
        created_by: str,
        profile: str = "standard",
        space_key: str | None = None,
        publish: bool = True,
        include_state_snapshot: bool = True,
    ) -> dict[str, Any]:
        actor = str(created_by or "").strip()
        if not actor:
            raise ValueError("created_by is required")
        normalized_profile = str(profile or "standard").strip().lower() or "standard"
        if normalized_profile not in {"standard", "support_ops", "logistics_ops", "sales_ops", "compliance_ops"}:
            raise ValueError("profile must be one of: standard, support_ops, logistics_ops, sales_ops, compliance_ops")
        request_payload: dict[str, Any] = {
            "project_id": self._config.project_id,
            "created_by": actor,
            "profile": normalized_profile,
            "publish": bool(publish),
            "include_state_snapshot": bool(include_state_snapshot),
        }
        if space_key is not None and str(space_key).strip():
            request_payload["space_key"] = str(space_key).strip()
        return self._request_json(
            "/v1/adoption/first-run/bootstrap",
            method="POST",
            payload=request_payload,
            idempotency_key=str(uuid4()),
        )

    def list_adoption_wiki_space_templates(self) -> dict[str, Any]:
        return self._request_json(
            "/v1/adoption/wiki-space-templates",
            method="GET",
        )

    def apply_adoption_wiki_space_template(
        self,
        *,
        updated_by: str,
        template_key: str,
        space_key: str | None = None,
        publish: bool = True,
    ) -> dict[str, Any]:
        actor = str(updated_by or "").strip()
        if not actor:
            raise ValueError("updated_by is required")
        key = str(template_key or "").strip().lower()
        if key not in {"support_ops", "logistics_ops", "sales_ops", "compliance_ops"}:
            raise ValueError("template_key must be one of: support_ops, logistics_ops, sales_ops, compliance_ops")
        payload: dict[str, Any] = {
            "project_id": self._config.project_id,
            "updated_by": actor,
            "template_key": key,
            "publish": bool(publish),
        }
        if space_key is not None and str(space_key).strip():
            payload["space_key"] = str(space_key).strip()
        return self._request_json(
            "/v1/adoption/wiki-space-templates/apply",
            method="POST",
            payload=payload,
            idempotency_key=str(uuid4()),
        )

    def execute_adoption_sync_preset(
        self,
        *,
        updated_by: str,
        reviewed_by: str | None = None,
        dry_run: bool = True,
        apply_bootstrap_profile: bool = True,
        queue_enabled_sources: bool = True,
        run_bootstrap_approve: bool = True,
        include_starter_pages: bool = True,
        starter_profile: str = "support_ops",
        include_role_template: bool = False,
        role_template_key: str | None = None,
        role_template_space_key: str | None = None,
        run_bundle_promotion: bool = True,
        bundle_promotion_space_key: str = "operations",
        bundle_promotion_publish: bool = True,
        bundle_promotion_bootstrap_publish_core: bool = True,
        sync_processor_lookback_minutes: int = 30,
        fail_on_sync_processor_unavailable: bool = False,
        auto_apply_safe_mode_on_critical: bool = True,
    ) -> dict[str, Any]:
        actor = str(updated_by or "").strip()
        if not actor:
            raise ValueError("updated_by is required")
        profile = str(starter_profile or "support_ops").strip().lower() or "support_ops"
        if profile not in {"standard", "support_ops", "logistics_ops", "sales_ops", "compliance_ops"}:
            raise ValueError("starter_profile is invalid")
        payload: dict[str, Any] = {
            "project_id": self._config.project_id,
            "updated_by": actor,
            "reviewed_by": str(reviewed_by).strip() if reviewed_by is not None and str(reviewed_by).strip() else None,
            "preset_key": "enterprise_curated_safe",
            "dry_run": bool(dry_run),
            "confirm_project_id": self._config.project_id if not dry_run else None,
            "apply_bootstrap_profile": bool(apply_bootstrap_profile),
            "queue_enabled_sources": bool(queue_enabled_sources),
            "run_bootstrap_approve": bool(run_bootstrap_approve),
            "include_starter_pages": bool(include_starter_pages),
            "starter_profile": profile,
            "include_role_template": bool(include_role_template),
            "role_template_key": (
                str(role_template_key).strip().lower() if role_template_key is not None and str(role_template_key).strip() else None
            ),
            "role_template_space_key": (
                str(role_template_space_key).strip()
                if role_template_space_key is not None and str(role_template_space_key).strip()
                else None
            ),
            "run_bundle_promotion": bool(run_bundle_promotion),
            "bundle_promotion_space_key": _normalize_space_key(bundle_promotion_space_key or "operations"),
            "bundle_promotion_publish": bool(bundle_promotion_publish),
            "bundle_promotion_bootstrap_publish_core": bool(bundle_promotion_bootstrap_publish_core),
            "sync_processor_lookback_minutes": max(1, min(1440, int(sync_processor_lookback_minutes))),
            "fail_on_sync_processor_unavailable": bool(fail_on_sync_processor_unavailable),
            "auto_apply_safe_mode_on_critical": bool(auto_apply_safe_mode_on_critical),
        }
        return self._request_json(
            "/v1/adoption/sync-presets/execute",
            method="POST",
            payload=payload,
            idempotency_key=str(uuid4()),
        )

    def enable_adoption_safe_mode(
        self,
        *,
        updated_by: str,
        dry_run: bool = True,
        note: str | None = None,
    ) -> dict[str, Any]:
        actor = str(updated_by or "").strip()
        if not actor:
            raise ValueError("updated_by is required")
        payload: dict[str, Any] = {
            "project_id": self._config.project_id,
            "updated_by": actor,
            "dry_run": bool(dry_run),
            "confirm_project_id": self._config.project_id if not dry_run else None,
            "note": str(note).strip() if note is not None and str(note).strip() else None,
        }
        return self._request_json(
            "/v1/adoption/safe-mode/enable",
            method="POST",
            payload=payload,
            idempotency_key=str(uuid4()),
        )

    def recommend_adoption_safe_mode(
        self,
        *,
        recommended_by: str,
        days: int = 14,
        dry_run: bool = True,
        note: str | None = None,
    ) -> dict[str, Any]:
        actor = str(recommended_by or "").strip()
        if not actor:
            raise ValueError("recommended_by is required")
        payload: dict[str, Any] = {
            "project_id": self._config.project_id,
            "recommended_by": actor,
            "days": max(1, min(90, int(days))),
            "dry_run": bool(dry_run),
            "confirm_project_id": self._config.project_id if not dry_run else None,
            "note": str(note).strip() if note is not None and str(note).strip() else None,
        }
        return self._request_json(
            "/v1/adoption/safe-mode/recommend",
            method="POST",
            payload=payload,
            idempotency_key=str(uuid4()),
        )

    def run_adoption_project_reset(
        self,
        *,
        requested_by: str,
        scopes: list[str] | None = None,
        reason: str | None = None,
        cascade_cleanup_orphan_draft_pages: bool = False,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        actor = str(requested_by or "").strip()
        if not actor:
            raise ValueError("requested_by is required")
        normalized_scopes: list[str] = []
        for item in scopes or []:
            token = str(item or "").strip().lower()
            if token and token not in normalized_scopes:
                normalized_scopes.append(token)
        payload: dict[str, Any] = {
            "project_id": self._config.project_id,
            "requested_by": actor,
            "reason": str(reason).strip() if reason is not None and str(reason).strip() else None,
            "scopes": normalized_scopes or None,
            "cascade_cleanup_orphan_draft_pages": bool(cascade_cleanup_orphan_draft_pages),
            "dry_run": bool(dry_run),
            "confirm_project_id": self._config.project_id if not dry_run else None,
        }
        return self._request_json(
            "/v1/adoption/project-reset",
            method="POST",
            payload=payload,
            idempotency_key=str(uuid4()),
        )

    def get_adoption_sync_cursor_health(
        self,
        *,
        stale_after_hours: int = 24,
    ) -> dict[str, Any]:
        return self._request_json(
            "/v1/adoption/sync/cursor-health",
            method="GET",
            params={
                "project_id": self._config.project_id,
                "stale_after_hours": max(1, min(24 * 30, int(stale_after_hours))),
            },
        )

    def list_wiki_drafts(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "project_id": self._config.project_id,
            "limit": max(1, min(200, int(limit))),
        }
        if status is not None and str(status).strip():
            params["status"] = str(status).strip().lower()
        return self._request_json(
            "/v1/wiki/drafts",
            method="GET",
            params=params,
        )

    def _normalize_bulk_review_filter_payload(
        self,
        filter: Mapping[str, Any] | WikiDraftBulkReviewFilter | None,
    ) -> dict[str, Any]:
        if filter is None:
            return {}
        if isinstance(filter, Mapping):
            return dict(filter)
        if isinstance(filter, WikiDraftBulkReviewFilter):
            payload = asdict(filter)
            return {key: value for key, value in payload.items() if value is not None}
        if is_dataclass(filter):
            payload = asdict(filter)
            return {str(key): value for key, value in payload.items() if value is not None}
        raise TypeError("filter must be a mapping or WikiDraftBulkReviewFilter")

    def bulk_review_wiki_drafts(
        self,
        *,
        reviewed_by: str,
        action: str = "approve",
        dry_run: bool = True,
        limit: int = 200,
        filter: Mapping[str, Any] | WikiDraftBulkReviewFilter | None = None,
        note: str | None = None,
        reason: str | None = None,
        force: bool = False,
        dismiss_conflicts: bool = True,
    ) -> dict[str, Any]:
        actor = str(reviewed_by or "").strip()
        if not actor:
            raise ValueError("reviewed_by is required")
        normalized_action = str(action or "").strip().lower()
        if normalized_action not in {"approve", "reject"}:
            raise ValueError("action must be one of: approve, reject")
        payload: dict[str, Any] = {
            "project_id": self._config.project_id,
            "reviewed_by": actor,
            "action": normalized_action,
            "dry_run": bool(dry_run),
            "limit": max(1, min(2000, int(limit))),
            "filter": self._normalize_bulk_review_filter_payload(filter),
            "note": str(note).strip() if note is not None and str(note).strip() else None,
            "reason": str(reason).strip() if reason is not None and str(reason).strip() else None,
            "force": bool(force),
            "dismiss_conflicts": bool(dismiss_conflicts),
        }
        return self._request_json(
            "/v1/wiki/drafts/bulk-review",
            method="POST",
            payload=payload,
            idempotency_key=str(uuid4()),
        )

    def run_adoption_agent_wiki_bootstrap(
        self,
        *,
        updated_by: str,
        dry_run: bool = True,
        publish: bool = True,
        bootstrap_publish_core: bool = True,
        space_key: str = "operations",
        include_data_sources_catalog: bool = True,
        include_agent_capability_profile: bool = True,
        include_tooling_map: bool = True,
        include_process_playbooks: bool = True,
        include_company_operating_context: bool = True,
        include_operational_logic: bool = True,
        include_first_run_starter: bool = True,
        include_state_snapshot: bool = True,
        max_sources: int = 25,
        max_agents: int = 100,
        max_signals: int = 40,
    ) -> dict[str, Any]:
        actor = str(updated_by or "").strip()
        if not actor:
            raise ValueError("updated_by is required")
        normalized_space_key = str(space_key or "").strip() or "operations"
        payload: dict[str, Any] = {
            "project_id": self._config.project_id,
            "updated_by": actor,
            "dry_run": bool(dry_run),
            "confirm_project_id": self._config.project_id if not dry_run else None,
            "publish": bool(publish),
            "bootstrap_publish_core": bool(bootstrap_publish_core),
            "space_key": normalized_space_key,
            "include_data_sources_catalog": bool(include_data_sources_catalog),
            "include_agent_capability_profile": bool(include_agent_capability_profile),
            "include_tooling_map": bool(include_tooling_map),
            "include_process_playbooks": bool(include_process_playbooks),
            "include_company_operating_context": bool(include_company_operating_context),
            "include_operational_logic": bool(include_operational_logic),
            "include_first_run_starter": bool(include_first_run_starter),
            "include_state_snapshot": bool(include_state_snapshot),
            "max_sources": max(1, min(150, int(max_sources))),
            "max_agents": max(1, min(5000, int(max_agents))),
            "max_signals": max(1, min(200, int(max_signals))),
        }
        return self._request_json(
            "/v1/adoption/agent-wiki-bootstrap",
            method="POST",
            payload=payload,
            idempotency_key=str(uuid4()),
        )

    def get_wiki_state_snapshot(
        self,
        *,
        space_key: str | None = None,
        max_workstreams: int = 12,
        max_open_items: int = 25,
        max_people_watch: int = 15,
        max_metrics: int = 12,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "project_id": self._config.project_id,
            "max_workstreams": max(1, min(50, int(max_workstreams))),
            "max_open_items": max(1, min(200, int(max_open_items))),
            "max_people_watch": max(1, min(100, int(max_people_watch))),
            "max_metrics": max(1, min(100, int(max_metrics))),
        }
        if space_key is not None and str(space_key).strip():
            params["space_key"] = str(space_key).strip()
        return self._request_json(
            "/v1/wiki/state",
            method="GET",
            params=params,
        )

    def sync_wiki_state_snapshot(
        self,
        *,
        updated_by: str,
        space_key: str | None = None,
        status: str = "published",
        max_workstreams: int = 12,
        max_open_items: int = 25,
        max_people_watch: int = 15,
        max_metrics: int = 12,
    ) -> dict[str, Any]:
        actor = str(updated_by or "").strip()
        if not actor:
            raise ValueError("updated_by is required")
        normalized_status = str(status or "published").strip().lower() or "published"
        if normalized_status not in {"draft", "reviewed", "published", "archived"}:
            raise ValueError("status must be one of: draft, reviewed, published, archived")
        payload: dict[str, Any] = {
            "project_id": self._config.project_id,
            "updated_by": actor,
            "status": normalized_status,
            "max_workstreams": max(1, min(50, int(max_workstreams))),
            "max_open_items": max(1, min(200, int(max_open_items))),
            "max_people_watch": max(1, min(100, int(max_people_watch))),
            "max_metrics": max(1, min(100, int(max_metrics))),
        }
        if space_key is not None and str(space_key).strip():
            payload["space_key"] = str(space_key).strip()
        return self._request_json(
            "/v1/wiki/state/sync",
            method="POST",
            payload=payload,
            idempotency_key=str(uuid4()),
        )

    def get_bootstrap_migration_recommendation(self) -> dict[str, Any]:
        return self._request_json(
            "/v1/wiki/drafts/bootstrap-approve/recommendation",
            method="GET",
            params={"project_id": self._config.project_id},
        )

    def get_adoption_pipeline_visibility(
        self,
        *,
        days: int = 14,
        source_systems: list[str] | None = None,
        namespaces: list[str] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "project_id": self._config.project_id,
            "days": max(1, min(90, int(days))),
        }
        if source_systems:
            params["source_systems"] = ",".join([str(item).strip().lower() for item in source_systems if str(item).strip()])
        if namespaces:
            params["namespaces"] = ",".join([str(item).strip().lower() for item in namespaces if str(item).strip()])
        return self._request_json(
            "/v1/adoption/pipeline/visibility",
            method="GET",
            params=params,
        )

    def get_adoption_wiki_quality_report(
        self,
        *,
        days: int = 14,
        placeholder_ratio_max: float = 0.10,
        daily_summary_draft_ratio_max: float = 0.20,
        min_core_published: int = 6,
    ) -> dict[str, Any]:
        return self._request_json(
            "/v1/adoption/wiki-quality/report",
            method="GET",
            params={
                "project_id": self._config.project_id,
                "days": max(1, min(90, int(days))),
                "placeholder_ratio_max": max(0.0, min(1.0, float(placeholder_ratio_max))),
                "daily_summary_draft_ratio_max": max(0.0, min(1.0, float(daily_summary_draft_ratio_max))),
                "min_core_published": max(1, min(50, int(min_core_published))),
            },
        )

    def get_adoption_wiki_richness_benchmark(
        self,
        *,
        days: int = 14,
        placeholder_ratio_max: float = 0.10,
        daily_summary_draft_ratio_max: float = 0.20,
        min_core_published: int = 6,
        min_contract_pass_ratio: float = 0.80,
        min_average_page_score: float = 0.72,
    ) -> dict[str, Any]:
        return self._request_json(
            "/v1/adoption/wiki-richness/benchmark",
            method="GET",
            params={
                "project_id": self._config.project_id,
                "days": max(1, min(90, int(days))),
                "placeholder_ratio_max": max(0.0, min(1.0, float(placeholder_ratio_max))),
                "daily_summary_draft_ratio_max": max(0.0, min(1.0, float(daily_summary_draft_ratio_max))),
                "min_core_published": max(1, min(50, int(min_core_published))),
                "min_contract_pass_ratio": max(0.0, min(1.0, float(min_contract_pass_ratio))),
                "min_average_page_score": max(0.0, min(1.0, float(min_average_page_score))),
            },
        )

    def get_adoption_rejection_diagnostics(
        self,
        *,
        days: int = 14,
        sample_limit: int = 5,
    ) -> dict[str, Any]:
        return self._request_json(
            "/v1/adoption/rejections/diagnostics",
            method="GET",
            params={
                "project_id": self._config.project_id,
                "days": max(1, min(90, int(days))),
                "sample_limit": max(1, min(25, int(sample_limit))),
            },
        )

    def list_legacy_import_profiles(
        self,
        *,
        source_type: str = "postgres_sql",
    ) -> dict[str, Any]:
        return self._request_json(
            "/v1/legacy-import/profiles",
            method="GET",
            params={
                "source_type": str(source_type or "postgres_sql").strip().lower() or "postgres_sql",
            },
        )

    def list_legacy_import_mapper_templates(
        self,
        *,
        source_type: str = "postgres_sql",
        profile: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "source_type": str(source_type or "postgres_sql").strip().lower() or "postgres_sql",
        }
        if profile is not None and str(profile).strip():
            params["profile"] = str(profile).strip()
        return self._request_json(
            "/v1/legacy-import/mapper-templates",
            method="GET",
            params=params,
        )

    def list_legacy_import_sync_contracts(
        self,
        *,
        source_type: str = "postgres_sql",
        profile: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "source_type": str(source_type or "postgres_sql").strip().lower() or "postgres_sql",
        }
        if profile is not None and str(profile).strip():
            params["profile"] = str(profile).strip()
        return self._request_json(
            "/v1/legacy-import/sync-contracts",
            method="GET",
            params=params,
        )

    def list_legacy_import_sources(
        self,
        *,
        enabled: bool | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "project_id": self._config.project_id,
            "limit": max(1, min(500, int(limit))),
        }
        if enabled is not None:
            params["enabled"] = "true" if enabled else "false"
        return self._request_json(
            "/v1/legacy-import/sources",
            method="GET",
            params=params,
        )

    def upsert_legacy_import_source(
        self,
        *,
        source_type: str,
        source_ref: str,
        updated_by: str,
        enabled: bool = True,
        sync_interval_minutes: int = 60,
        next_run_at: str | None = None,
        config: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "project_id": self._config.project_id,
            "source_type": str(source_type or "").strip().lower(),
            "source_ref": str(source_ref or "").strip(),
            "enabled": bool(enabled),
            "sync_interval_minutes": max(1, min(10080, int(sync_interval_minutes))),
            "updated_by": str(updated_by or "").strip(),
            "config": dict(config or {}),
        }
        if not payload["source_type"]:
            raise ValueError("source_type is required")
        if not payload["source_ref"]:
            raise ValueError("source_ref is required")
        if not payload["updated_by"]:
            raise ValueError("updated_by is required")
        if next_run_at is not None and str(next_run_at).strip():
            payload["next_run_at"] = str(next_run_at).strip()
        return self._request_json(
            "/v1/legacy-import/sources",
            method="PUT",
            payload=payload,
            idempotency_key=idempotency_key or str(uuid4()),
        )

    def queue_legacy_import_source_sync(
        self,
        source_id: str,
        *,
        requested_by: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        normalized_source_id = str(source_id or "").strip()
        if not normalized_source_id:
            raise ValueError("source_id is required")
        normalized_requested_by = str(requested_by or "").strip()
        if not normalized_requested_by:
            raise ValueError("requested_by is required")
        return self._request_json(
            f"/v1/legacy-import/sources/{quote(normalized_source_id)}/sync",
            method="POST",
            payload={
                "project_id": self._config.project_id,
                "requested_by": normalized_requested_by,
            },
            idempotency_key=idempotency_key or str(uuid4()),
        )

    def list_legacy_import_sync_runs(
        self,
        *,
        source_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "project_id": self._config.project_id,
            "limit": max(1, min(500, int(limit))),
        }
        if source_id is not None and str(source_id).strip():
            params["source_id"] = str(source_id).strip()
        if status is not None and str(status).strip():
            params["status"] = str(status).strip().lower()
        return self._request_json(
            "/v1/legacy-import/runs",
            method="GET",
            params=params,
        )

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

    def list_agents(
        self,
        *,
        status: str | None = None,
        team: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "project_id": self._config.project_id,
            "limit": max(1, min(500, int(limit))),
        }
        if status:
            params["status"] = status
        if team:
            params["team"] = team
        return self._request_json("/v1/agents", method="GET", params=params)

    def get_agent_publish_policy(self, *, agent_id: str) -> dict[str, Any]:
        return self._request_json(
            "/v1/agents/publish-policy",
            method="GET",
            params={
                "project_id": self._config.project_id,
                "agent_id": agent_id,
            },
        )

    def upsert_agent_publish_policy(
        self,
        *,
        agent_id: str,
        updated_by: str,
        default_mode: str = "auto_publish",
        by_page_type: dict[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self._request_json(
            "/v1/agents/publish-policy",
            method="PUT",
            payload={
                "project_id": self._config.project_id,
                "agent_id": agent_id,
                "updated_by": updated_by,
                "default_mode": default_mode,
                "by_page_type": dict(by_page_type or {}),
            },
            idempotency_key=idempotency_key or str(uuid4()),
        )

    def get_wiki_space_policy(self, space_key: str) -> dict[str, Any]:
        normalized_space_key = _normalize_space_key(space_key)
        return self._request_json(
            f"/v1/wiki/spaces/{quote(normalized_space_key, safe='')}/policy",
            method="GET",
            params={
                "project_id": self._config.project_id,
            },
        )

    def list_wiki_space_policy_audit(self, space_key: str, *, limit: int = 40) -> dict[str, Any]:
        normalized_space_key = _normalize_space_key(space_key)
        return self._request_json(
            f"/v1/wiki/spaces/{quote(normalized_space_key, safe='')}/policy/audit",
            method="GET",
            params={
                "project_id": self._config.project_id,
                "limit": max(1, min(200, int(limit))),
            },
        )

    def upsert_wiki_space_policy(
        self,
        *,
        space_key: str,
        updated_by: str,
        write_mode: str = "open",
        comment_mode: str = "open",
        review_assignment_required: bool = False,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        normalized_space_key = _normalize_space_key(space_key)
        normalized_write_mode = _normalize_wiki_space_mode(write_mode)
        normalized_comment_mode = _normalize_wiki_space_mode(comment_mode)
        return self._request_json(
            f"/v1/wiki/spaces/{quote(normalized_space_key, safe='')}/policy",
            method="PUT",
            payload={
                "project_id": self._config.project_id,
                "space_key": normalized_space_key,
                "updated_by": str(updated_by or "").strip(),
                "write_mode": normalized_write_mode,
                "comment_mode": normalized_comment_mode,
                "review_assignment_required": bool(review_assignment_required),
                "metadata": dict(metadata or {}),
            },
            idempotency_key=idempotency_key or str(uuid4()),
        )

    def get_wiki_space_publish_checklist_preset(
        self,
        *,
        space_key: str,
        fallback: str = "none",
    ) -> str:
        normalized_fallback = _normalize_publish_checklist_preset(fallback)
        policy = self.get_wiki_space_policy(space_key)
        policy_payload = policy.get("policy") if isinstance(policy.get("policy"), dict) else {}
        metadata = policy_payload.get("metadata") if isinstance(policy_payload.get("metadata"), dict) else {}
        return _normalize_publish_checklist_preset(metadata.get("publish_checklist_preset"), fallback=normalized_fallback)

    def set_wiki_space_publish_checklist_preset(
        self,
        *,
        space_key: str,
        preset: str,
        updated_by: str,
        reason: str | None = None,
        metadata_patch: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        normalized_space_key = _normalize_space_key(space_key)
        normalized_preset = _normalize_publish_checklist_preset(preset)
        current = self.get_wiki_space_policy(normalized_space_key)
        current_policy = current.get("policy") if isinstance(current.get("policy"), dict) else {}
        current_metadata = current_policy.get("metadata") if isinstance(current_policy.get("metadata"), dict) else {}
        merged_metadata = dict(current_metadata)
        merged_metadata["publish_checklist_preset"] = normalized_preset
        if reason is not None and str(reason).strip():
            merged_metadata["policy_change_reason"] = str(reason).strip()
        if metadata_patch:
            merged_metadata.update(dict(metadata_patch))

        return self.upsert_wiki_space_policy(
            space_key=normalized_space_key,
            updated_by=updated_by,
            write_mode=str(current_policy.get("write_mode") or "open"),
            comment_mode=str(current_policy.get("comment_mode") or "open"),
            review_assignment_required=bool(current_policy.get("review_assignment_required")),
            metadata=merged_metadata,
            idempotency_key=idempotency_key,
        )

    def get_wiki_lifecycle_stats(
        self,
        *,
        stale_days: int = 21,
        critical_days: int = 45,
        stale_limit: int = 20,
        space_key: str | None = None,
        page_type_aware: bool = True,
    ) -> dict[str, Any]:
        normalized_stale_days = max(1, min(365, int(stale_days)))
        normalized_critical_days = max(normalized_stale_days, min(365, int(critical_days)))
        normalized_stale_limit = max(1, min(200, int(stale_limit)))
        params: dict[str, Any] = {
            "project_id": self._config.project_id,
            "stale_days": normalized_stale_days,
            "critical_days": normalized_critical_days,
            "stale_limit": normalized_stale_limit,
            "page_type_aware": bool(page_type_aware),
        }
        if space_key is not None and str(space_key).strip():
            params["space_key"] = _normalize_space_key(str(space_key))
        return self._request_json(
            "/v1/wiki/lifecycle/stats",
            method="GET",
            params=params,
        )

    def get_wiki_lifecycle_telemetry(
        self,
        *,
        days: int = 7,
        action_key: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "project_id": self._config.project_id,
            "days": max(1, min(90, int(days))),
        }
        normalized_action_key = _normalize_lifecycle_action_key(action_key)
        if normalized_action_key:
            params["action_key"] = normalized_action_key
        return self._request_json(
            "/v1/wiki/lifecycle/telemetry",
            method="GET",
            params=params,
        )

    def snapshot_wiki_lifecycle_telemetry(
        self,
        *,
        session_id: str,
        empty_scope_action_shown: dict[str, int] | None = None,
        empty_scope_action_applied: dict[str, int] | None = None,
        observed_at: str | None = None,
        source: str = "sdk_client",
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            raise ValueError("session_id is required")
        payload: dict[str, Any] = {
            "project_id": self._config.project_id,
            "session_id": normalized_session_id,
            "source": str(source or "sdk_client").strip() or "sdk_client",
            "empty_scope_action_shown": _normalize_lifecycle_action_counts(empty_scope_action_shown),
            "empty_scope_action_applied": _normalize_lifecycle_action_counts(empty_scope_action_applied),
        }
        if observed_at is not None and str(observed_at).strip():
            payload["observed_at"] = str(observed_at).strip()
        return self._request_json(
            "/v1/wiki/lifecycle/telemetry/snapshot",
            method="POST",
            payload=payload,
            idempotency_key=idempotency_key or str(uuid4()),
        )

    def register_agent_profile(
        self,
        profile: AgentProfile,
        *,
        updated_by: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "project_id": self._config.project_id,
            "agent_id": profile.agent_id,
            "updated_by": updated_by,
            "display_name": profile.display_name,
            "team": profile.team,
            "role": profile.role,
            "status": profile.status,
            "responsibilities": list(profile.responsibilities),
            "tools": list(profile.tools),
            "data_sources": list(profile.data_sources),
            "limits": list(profile.limits),
            "metadata": dict(profile.metadata),
            "ensure_scaffold": bool(profile.ensure_scaffold),
            "include_daily_report_stub": bool(profile.include_daily_report_stub),
            "last_seen_at": profile.last_seen_at,
        }
        return self._request_json(
            "/v1/agents/register",
            method="POST",
            payload=payload,
            idempotency_key=idempotency_key or str(uuid4()),
        )

    def submit_agent_reflection(
        self,
        reflection: AgentReflection,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        insights_payload: list[dict[str, Any]] = []
        for item in reflection.insights:
            insight = item if isinstance(item, AgentReflectionInsight) else AgentReflectionInsight(**dict(item))
            insights_payload.append(
                {
                    "claim_text": str(insight.claim_text or "").strip(),
                    "category": str(insight.category).strip() if insight.category is not None else None,
                    "confidence": float(insight.confidence) if isinstance(insight.confidence, (int, float)) else None,
                    "temporary": bool(insight.temporary),
                    "evidence": [asdict(evidence) if is_dataclass(evidence) else dict(evidence) for evidence in insight.evidence],
                    "metadata": dict(insight.metadata),
                }
            )
        payload: dict[str, Any] = {
            "project_id": self._config.project_id,
            "agent_id": str(reflection.agent_id or "").strip(),
            "reflected_by": str(reflection.reflected_by or "").strip(),
            "task_id": str(reflection.task_id).strip() if reflection.task_id is not None else None,
            "session_id": str(reflection.session_id).strip() if reflection.session_id is not None else None,
            "trace_id": str(reflection.trace_id).strip() if reflection.trace_id is not None else None,
            "outcome": str(reflection.outcome).strip() if reflection.outcome is not None else None,
            "summary": str(reflection.summary).strip() if reflection.summary is not None else None,
            "learned_rules": [str(item).strip() for item in reflection.learned_rules if str(item).strip()],
            "decisions_made": [str(item).strip() for item in reflection.decisions_made if str(item).strip()],
            "tools_used": [str(item).strip() for item in reflection.tools_used if str(item).strip()],
            "data_sources_used": [str(item).strip() for item in reflection.data_sources_used if str(item).strip()],
            "follow_up_actions": [str(item).strip() for item in reflection.follow_up_actions if str(item).strip()],
            "uncertainties": [str(item).strip() for item in reflection.uncertainties if str(item).strip()],
            "insights": insights_payload,
            "metadata": dict(reflection.metadata),
            "observed_at": str(reflection.observed_at).strip() if reflection.observed_at is not None else None,
        }
        if not payload["agent_id"]:
            raise ValueError("reflection.agent_id is required")
        if not payload["reflected_by"]:
            raise ValueError("reflection.reflected_by is required")
        return self._request_json(
            "/v1/agents/reflections",
            method="POST",
            payload=payload,
            idempotency_key=idempotency_key or str(uuid4()),
        )

    def sync_agent_worklogs(
        self,
        *,
        generated_by: str,
        worklog_date: str | None = None,
        timezone: str | None = None,
        days_back: int = 1,
        max_agents: int = 200,
        include_retired: bool = False,
        include_idle_days: bool = False,
        min_activity_score: int = 1,
        trigger_mode: str = "daily_batch",
        trigger_reason: str | None = None,
        max_logs_per_agent_page: int = 14,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self._request_json(
            "/v1/agents/worklogs/sync",
            method="POST",
            payload={
                "project_id": self._config.project_id,
                "generated_by": generated_by,
                "worklog_date": worklog_date,
                "timezone": timezone,
                "days_back": max(1, min(30, int(days_back))),
                "max_agents": max(1, min(2000, int(max_agents))),
                "include_retired": bool(include_retired),
                "include_idle_days": bool(include_idle_days),
                "min_activity_score": max(0, min(1000, int(min_activity_score))),
                "trigger_mode": str(trigger_mode or "daily_batch"),
                "trigger_reason": str(trigger_reason).strip() if trigger_reason is not None else None,
                "max_logs_per_agent_page": max(1, min(60, int(max_logs_per_agent_page))),
            },
            idempotency_key=idempotency_key or str(uuid4()),
        )

    def get_agent_capability_matrix(
        self,
        *,
        min_confidence: float = 0.0,
        max_agents: int = 500,
    ) -> dict[str, Any]:
        return self._request_json(
            "/v1/agents/capability-matrix",
            method="GET",
            params={
                "project_id": self._config.project_id,
                "min_confidence": max(0.0, min(1.0, float(min_confidence))),
                "max_agents": max(1, min(5000, int(max_agents))),
            },
        )

    def sync_agent_capability_matrix(
        self,
        *,
        generated_by: str,
        min_confidence: float = 0.0,
        max_agents: int = 500,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self._request_json(
            "/v1/agents/capability-matrix/sync",
            method="POST",
            payload={
                "project_id": self._config.project_id,
                "generated_by": generated_by,
                "min_confidence": max(0.0, min(1.0, float(min_confidence))),
                "max_agents": max(1, min(5000, int(max_agents))),
            },
            idempotency_key=idempotency_key or str(uuid4()),
        )

    def get_agent_handoffs(
        self,
        *,
        max_edges: int = 1000,
        include_retired: bool = False,
    ) -> dict[str, Any]:
        return self._request_json(
            "/v1/agents/handoffs",
            method="GET",
            params={
                "project_id": self._config.project_id,
                "max_edges": max(1, min(10000, int(max_edges))),
                "include_retired": "true" if include_retired else "false",
            },
        )

    def sync_agent_handoffs(
        self,
        *,
        generated_by: str,
        max_edges: int = 1000,
        include_retired: bool = False,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self._request_json(
            "/v1/agents/handoffs/sync",
            method="POST",
            payload={
                "project_id": self._config.project_id,
                "generated_by": generated_by,
                "max_edges": max(1, min(10000, int(max_edges))),
                "include_retired": bool(include_retired),
            },
            idempotency_key=idempotency_key or str(uuid4()),
        )

    def get_agent_scorecards(
        self,
        *,
        max_agents: int = 500,
        lookback_days: int = 14,
        include_retired: bool = False,
    ) -> dict[str, Any]:
        return self._request_json(
            "/v1/agents/scorecards",
            method="GET",
            params={
                "project_id": self._config.project_id,
                "max_agents": max(1, min(5000, int(max_agents))),
                "lookback_days": max(1, min(90, int(lookback_days))),
                "include_retired": "true" if include_retired else "false",
            },
        )

    def sync_agent_scorecards(
        self,
        *,
        generated_by: str,
        max_agents: int = 500,
        lookback_days: int = 14,
        include_retired: bool = False,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self._request_json(
            "/v1/agents/scorecards/sync",
            method="POST",
            payload={
                "project_id": self._config.project_id,
                "generated_by": generated_by,
                "max_agents": max(1, min(5000, int(max_agents))),
                "lookback_days": max(1, min(90, int(lookback_days))),
                "include_retired": bool(include_retired),
            },
            idempotency_key=idempotency_key or str(uuid4()),
        )

    def list_agent_provenance(
        self,
        *,
        agent_id: str | None = None,
        page_slug: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "project_id": self._config.project_id,
            "limit": max(1, min(500, int(limit))),
        }
        if agent_id:
            params["agent_id"] = agent_id
        if page_slug:
            params["page_slug"] = page_slug
        return self._request_json(
            "/v1/agents/provenance",
            method="GET",
            params=params,
        )

    def rollback_agent_activity(
        self,
        activity_id: str,
        *,
        rolled_back_by: str,
        require_latest_activity: bool = True,
        status: str | None = None,
        change_summary: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self._request_json(
            f"/v1/agents/provenance/{activity_id}/rollback",
            method="POST",
            payload={
                "project_id": self._config.project_id,
                "rolled_back_by": rolled_back_by,
                "require_latest_activity": bool(require_latest_activity),
                "status": status,
                "change_summary": change_summary,
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

    def monitor_langchain(self, chain_or_runnable: Any, **kwargs: Any) -> Any:
        from synapse_sdk.integrations.monitoring import monitor_langchain

        return monitor_langchain(self, chain_or_runnable, **kwargs)

    def monitor_crewai(self, crew_or_agent: Any, **kwargs: Any) -> Any:
        from synapse_sdk.integrations.monitoring import monitor_crewai

        return monitor_crewai(self, crew_or_agent, **kwargs)

    def monitor_openclaw(self, runtime: Any, **kwargs: Any) -> Any:
        from synapse_sdk.integrations.monitoring import monitor_openclaw_runtime

        return monitor_openclaw_runtime(self, runtime, **kwargs)

    def langchain_callback_handler(self, **kwargs: Any) -> Any:
        from synapse_sdk.integrations.native import create_langchain_callback_handler

        return create_langchain_callback_handler(self, **kwargs)

    def build_langchain_config(self, handler: Any) -> dict[str, list[Any]]:
        from synapse_sdk.integrations.native import build_langchain_config

        return build_langchain_config(handler)

    def bind_langchain(self, target: Any, **kwargs: Any) -> Any:
        from synapse_sdk.integrations.native import bind_langchain

        return bind_langchain(self, target, **kwargs)

    def bind_langgraph(self, target: Any, **kwargs: Any) -> Any:
        from synapse_sdk.integrations.native import bind_langgraph

        return bind_langgraph(self, target, **kwargs)

    def bind_crewai(self, target: Any, **kwargs: Any) -> Any:
        from synapse_sdk.integrations.native import bind_crewai

        return bind_crewai(self, target, **kwargs)

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

    def _resolve_backfill_ingest_lane_from_payload(self, payload: dict[str, Any]) -> str:
        batch = payload.get("batch")
        if isinstance(batch, dict):
            lane = str(batch.get("ingest_lane") or "").strip().lower()
            if lane in {"event", "knowledge"}:
                return lane
        return "event"

    def _transport_ingest_backfill(
        self,
        payload: dict[str, Any],
        *,
        ingest_lane: str,
        idempotency_key: str | None,
    ) -> None:
        if ingest_lane == "knowledge":
            method = getattr(self._transport, "ingest_knowledge_backfill", None)
            if callable(method):
                try:
                    method(payload, idempotency_key=idempotency_key)
                    return
                except Exception as exc:
                    status_code = int(getattr(exc, "status_code", 0) or 0)
                    if status_code not in {404, 405}:
                        raise
                    self._emit_debug(
                        "backfill_knowledge_endpoint_fallback",
                        {"status_code": status_code, "fallback_endpoint": "/v1/backfill/memory"},
                    )
        self._transport.ingest_memory_backfill(payload, idempotency_key=idempotency_key)

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
        adoption_mode: AdoptionMode | str | None = None,
        openclaw_hook_events: Sequence[str] | None = None,
        openclaw_capture_hook_events: bool | None = None,
        openclaw_register_tools: bool | None = None,
        openclaw_register_search_tool: bool | None = None,
        openclaw_register_propose_tool: bool | None = None,
        openclaw_register_task_tools: bool | None = None,
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
        register_agent_directory: bool | None = None,
        agent_profile: AgentProfile | dict[str, Any] | None = None,
        agent_display_name: str | None = None,
        agent_team: str | None = None,
        agent_role: str | None = None,
        agent_responsibilities: Sequence[str] | None = None,
        agent_tools: Sequence[str] | None = None,
        agent_data_sources: Sequence[str] | None = None,
        agent_limits: Sequence[str] | None = None,
        agent_directory_status: str = "active",
    ) -> Any:
        resolved_integration = integration or self._detect_integration(target)
        resolved_adoption_mode = _normalize_adoption_mode(
            _coerce_str_or_none(adoption_mode) or _coerce_str_or_none(os.getenv("SYNAPSE_ADOPTION_MODE"))
        )
        resolved_register_agent_directory = (
            _coerce_bool_or_default(
                register_agent_directory,
                default=_coerce_bool_or_default(
                    _coerce_str_or_none(os.getenv("SYNAPSE_AGENT_DIRECTORY_AUTO_REGISTER")),
                    default=True,
                ),
            )
            and bool(_coerce_str_or_none(agent_id))
        )
        self._emit_debug(
            "attach_started",
            {
                "integration": resolved_integration,
                "target_type": type(target).__name__,
                "auto_bootstrap_enabled": bool(openclaw_auto_bootstrap),
                "adoption_mode": resolved_adoption_mode,
                "agent_directory_auto_register": bool(resolved_register_agent_directory),
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
        openclaw_capture_hooks = openclaw_capture_hook_events
        openclaw_register_tools_resolved = openclaw_register_tools
        openclaw_register_search_tool_resolved = openclaw_register_search_tool
        openclaw_register_propose_tool_resolved = openclaw_register_propose_tool
        openclaw_register_task_tools_resolved = openclaw_register_task_tools
        if resolved_integration == "openclaw" and self._looks_like_openclaw_runtime(target):
            if openclaw_capture_hooks is None:
                openclaw_capture_hooks = resolved_adoption_mode != "retrieve_only"
            if openclaw_register_tools_resolved is None:
                openclaw_register_tools_resolved = resolved_adoption_mode != "observe_only"
            if openclaw_register_search_tool_resolved is None:
                openclaw_register_search_tool_resolved = resolved_adoption_mode in {"full_loop", "retrieve_only"}
            if openclaw_register_propose_tool_resolved is None:
                openclaw_register_propose_tool_resolved = resolved_adoption_mode in {"full_loop", "draft_only"}
            if openclaw_register_task_tools_resolved is None:
                openclaw_register_task_tools_resolved = resolved_adoption_mode == "full_loop"
        if resolved_adoption_mode == "retrieve_only":
            if resolved_integration == "openclaw" and self._looks_like_openclaw_runtime(target):
                self._emit_debug(
                    "attach_bootstrap_skipped",
                    {
                        "integration": resolved_integration,
                        "reason": "adoption_mode_retrieve_only",
                        "adoption_mode": resolved_adoption_mode,
                    },
                )
            else:
                self._emit_debug(
                    "attach_completed",
                    {
                        "integration": resolved_integration,
                        "mode": "noop_retrieve_only",
                        "bootstrap_requested": resolved_bootstrap_memory is not None,
                        "adoption_mode": resolved_adoption_mode,
                    },
                )
                return target
        else:
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
                hook_events=(openclaw_hook_events or DEFAULT_OPENCLAW_EVENTS) if bool(openclaw_capture_hooks) else (),
                register_tools=bool(openclaw_register_tools_resolved),
                tool_prefix=openclaw_tool_prefix,
                register_search_tool=bool(openclaw_register_search_tool_resolved),
                register_propose_tool=bool(openclaw_register_propose_tool_resolved),
                register_task_tools=bool(openclaw_register_task_tools_resolved),
            )
            self._emit_debug(
                "attach_completed",
                {
                    "integration": resolved_integration,
                    "mode": "openclaw_connector",
                    "registered_tools": list(connector.last_registered_tools),
                    "bootstrap_requested": resolved_bootstrap_memory is not None,
                    "adoption_mode": resolved_adoption_mode,
                    "capture_hooks": bool(openclaw_capture_hooks),
                    "register_tools": bool(openclaw_register_tools_resolved),
                    "register_search_tool": bool(openclaw_register_search_tool_resolved),
                    "register_propose_tool": bool(openclaw_register_propose_tool_resolved),
                    "register_task_tools": bool(openclaw_register_task_tools_resolved),
                    "search_mode": (
                        "callback"
                        if openclaw_search_knowledge is not None
                        else ("auto" if connector.auto_search_enabled else "disabled")
                    ),
                },
            )
            return target

        if resolved_register_agent_directory and _coerce_str_or_none(agent_id):
            try:
                profile_obj: AgentProfile
                if isinstance(agent_profile, AgentProfile):
                    profile_obj = agent_profile
                elif isinstance(agent_profile, dict):
                    profile_obj = AgentProfile(
                        agent_id=_coerce_str_or_none(agent_profile.get("agent_id")) or str(agent_id),
                        display_name=_coerce_str_or_none(agent_profile.get("display_name") or agent_display_name),
                        team=_coerce_str_or_none(agent_profile.get("team") or agent_team),
                        role=_coerce_str_or_none(agent_profile.get("role") or agent_role),
                        status=_coerce_str_or_none(agent_profile.get("status")) or str(agent_directory_status or "active"),
                        responsibilities=[
                            str(item).strip()
                            for item in (
                                agent_profile.get("responsibilities")
                                if isinstance(agent_profile.get("responsibilities"), list)
                                else (agent_responsibilities or [])
                            )
                            if str(item).strip()
                        ],
                        tools=[
                            str(item).strip()
                            for item in (
                                agent_profile.get("tools")
                                if isinstance(agent_profile.get("tools"), list)
                                else (agent_tools or [])
                            )
                            if str(item).strip()
                        ],
                        data_sources=[
                            str(item).strip()
                            for item in (
                                agent_profile.get("data_sources")
                                if isinstance(agent_profile.get("data_sources"), list)
                                else (agent_data_sources or [])
                            )
                            if str(item).strip()
                        ],
                        limits=[
                            str(item).strip()
                            for item in (
                                agent_profile.get("limits")
                                if isinstance(agent_profile.get("limits"), list)
                                else (agent_limits or [])
                            )
                            if str(item).strip()
                        ],
                        metadata=dict(agent_profile.get("metadata")) if isinstance(agent_profile.get("metadata"), dict) else {},
                        ensure_scaffold=bool(agent_profile.get("ensure_scaffold", True)),
                        include_daily_report_stub=bool(agent_profile.get("include_daily_report_stub", True)),
                        last_seen_at=_coerce_str_or_none(agent_profile.get("last_seen_at")),
                    )
                else:
                    profile_obj = AgentProfile(
                        agent_id=str(agent_id),
                        display_name=agent_display_name,
                        team=agent_team,
                        role=agent_role,
                        status=str(agent_directory_status or "active"),
                        responsibilities=[str(item).strip() for item in (agent_responsibilities or []) if str(item).strip()],
                        tools=[str(item).strip() for item in (agent_tools or []) if str(item).strip()],
                        data_sources=[str(item).strip() for item in (agent_data_sources or []) if str(item).strip()],
                        limits=[str(item).strip() for item in (agent_limits or []) if str(item).strip()],
                        metadata={"integration": resolved_integration, "attached_via": "synapse_sdk_py"},
                        ensure_scaffold=True,
                        include_daily_report_stub=True,
                        last_seen_at=datetime.now(UTC).isoformat(),
                    )
                self.register_agent_profile(
                    profile_obj,
                    updated_by=_coerce_str_or_none(agent_id) or "synapse_sdk_attach",
                )
                self._emit_debug(
                    "attach_agent_directory_registered",
                    {
                        "agent_id": profile_obj.agent_id,
                        "integration": resolved_integration,
                        "status": profile_obj.status,
                    },
                )
            except Exception as exc:
                self._emit_debug(
                    "attach_agent_directory_register_failed",
                    {
                        "agent_id": _coerce_str_or_none(agent_id),
                        "integration": resolved_integration,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    },
                )
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
                "adoption_mode": resolved_adoption_mode,
            },
        )
        return monitored

    def _detect_integration(self, target: Any) -> str:
        if self._looks_like_openclaw_runtime(target):
            return "openclaw"
        if self._looks_like_crewai_runtime(target):
            return "crewai"
        if self._looks_like_langgraph_runnable(target):
            return "langgraph"
        if self._looks_like_langchain_runnable(target):
            return "langchain"
        return "generic"

    def _looks_like_openclaw_runtime(self, target: Any) -> bool:
        has_hook_api = (hasattr(target, "on") and callable(target.on)) or (
            hasattr(target, "register_hook") and callable(target.register_hook)
        )
        has_tool_api = hasattr(target, "register_tool") and callable(target.register_tool)
        return bool(has_hook_api and has_tool_api)

    def _looks_like_langgraph_runnable(self, target: Any) -> bool:
        for name in ("ainvoke", "astream", "abatch"):
            value = getattr(target, name, None)
            if callable(value):
                return True
        return False

    def _looks_like_langchain_runnable(self, target: Any) -> bool:
        invoke_fn = getattr(target, "invoke", None)
        if not callable(invoke_fn):
            return False
        for name in ("call", "stream", "batch", "ainvoke"):
            value = getattr(target, name, None)
            if callable(value):
                return True
        return False

    def _looks_like_crewai_runtime(self, target: Any) -> bool:
        for name in ("kickoff", "kickoff_async"):
            value = getattr(target, name, None)
            if callable(value):
                return True
        return False

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


def _normalize_space_key(space_key: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(space_key or "").strip().lower())
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    if not normalized:
        raise ValueError("space_key cannot be empty")
    return normalized


def _normalize_wiki_space_mode(mode: str, *, fallback: str = "open") -> str:
    normalized = str(mode or fallback).strip().lower()
    if normalized not in {"open", "owners_only"}:
        raise ValueError(f"unsupported wiki space mode: {mode}")
    return normalized


def _normalize_publish_checklist_preset(value: Any, *, fallback: str = "none") -> str:
    normalized_fallback = str(fallback or "none").strip().lower() or "none"
    if normalized_fallback not in _WIKI_PUBLISH_CHECKLIST_PRESETS:
        normalized_fallback = "none"
    normalized = str(value or normalized_fallback).strip().lower()
    if normalized not in _WIKI_PUBLISH_CHECKLIST_PRESETS:
        return normalized_fallback
    return normalized


def _normalize_lifecycle_action_key(value: str | None) -> str:
    normalized = re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    if not normalized:
        return ""
    return normalized[:96]


def _normalize_lifecycle_action_counts(raw: dict[str, int] | None) -> dict[str, int]:
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, int] = {}
    for key, value in raw.items():
        action_key = _normalize_lifecycle_action_key(str(key or ""))
        if not action_key:
            continue
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            continue
        normalized[action_key] = max(0, min(1_000_000_000, numeric))
    return normalized


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


def _normalize_adoption_mode(value: str | None) -> str:
    normalized = str(value or "full_loop").strip().lower()
    aliases = {
        "full": "full_loop",
        "observe": "observe_only",
        "draft": "draft_only",
        "retrieve": "retrieve_only",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in {"full_loop", "observe_only", "draft_only", "retrieve_only"}:
        raise ValueError(f"invalid adoption mode: {value!r}")
    return normalized


def _coerce_str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _coerce_bool_or_default(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    text = _coerce_str_or_none(value)
    if text is None:
        return bool(default)
    normalized = text.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def _infer_project_id_from_cwd() -> str:
    raw = Path.cwd().name
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", raw).strip("_").lower()
    return normalized or "synapse_project"
