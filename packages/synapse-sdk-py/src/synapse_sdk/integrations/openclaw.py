from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
import hmac
import json
import os
from typing import Any, Callable, Protocol, Sequence
from uuid import uuid4

from synapse_sdk.types import BootstrapMemoryInput, BootstrapMemoryOptions, Claim, EvidenceRef

if False:  # pragma: no cover
    from synapse_sdk.client import SynapseClient


DEFAULT_OPENCLAW_EVENTS = (
    "tool:result",
    "message:received",
    "agent:completed",
    "session:reset",
)
OPENCLAW_BOOTSTRAP_PRESETS = ("runtime_memory", "event_log", "hybrid")


class SupportsEventOn(Protocol):
    def on(self, event_name: str, handler: Callable[[dict[str, Any]], Any]) -> Any: ...


class SupportsHookRegister(Protocol):
    def register_hook(self, event_name: str, handler: Callable[[dict[str, Any]], Any]) -> Any: ...


class SupportsToolRegister(Protocol):
    def register_tool(self, name: str, handler: Callable[..., Any], description: str | None = None) -> Any: ...


@dataclass
class OpenClawConnector:
    client: "SynapseClient"
    search_knowledge: Callable[..., Any] | None = None
    list_tasks: Callable[..., Any] | None = None
    update_task_status: Callable[..., Any] | None = None
    default_agent_id: str | None = None
    default_session_id: str | None = None
    provenance_secret: str | None = None
    provenance_key_id: str | None = None
    enable_default_search: bool = True
    last_registered_tools: tuple[str, ...] = field(default_factory=tuple, init=False)
    auto_search_enabled: bool = field(default=False, init=False)

    def attach(
        self,
        runtime: Any,
        *,
        hook_events: Sequence[str] = DEFAULT_OPENCLAW_EVENTS,
        register_tools: bool = True,
        tool_prefix: str = "synapse",
    ) -> None:
        self._attach_hooks(runtime, hook_events=hook_events)
        self.last_registered_tools = tuple()
        self.auto_search_enabled = False
        if register_tools:
            tools = self.register_tools(runtime, tool_prefix=tool_prefix)
            self.last_registered_tools = tuple(tools)

    def register_tools(self, runtime: Any, *, tool_prefix: str = "synapse") -> list[str]:
        register_tool = self._resolve_tool_registrar(runtime)
        registered: list[str] = []
        resolver = self._resolve_search_knowledge()
        if resolver is not None:
            register_tool(
                f"{tool_prefix}_search_wiki",
                self.search_wiki,
                "Search approved Synapse knowledge for the current task.",
            )
            registered.append(f"{tool_prefix}_search_wiki")
        else:
            self._emit_debug(
                "attach_openclaw_search_disabled",
                {
                    "reason": "missing_callback_and_auto_search",
                    "tool": f"{tool_prefix}_search_wiki",
                },
            )
        register_tool(
            f"{tool_prefix}_propose_to_wiki",
            self.propose_to_wiki,
            "Propose a new fact to Synapse for human review.",
        )
        registered.append(f"{tool_prefix}_propose_to_wiki")
        if self._can_list_tasks():
            register_tool(
                f"{tool_prefix}_get_open_tasks",
                self.get_open_tasks,
                "List active Synapse tasks relevant for the current operation.",
            )
            registered.append(f"{tool_prefix}_get_open_tasks")
        if self._can_update_task_status():
            register_tool(
                f"{tool_prefix}_update_task_status",
                self.set_task_status,
                "Update Synapse task status after execution progress.",
            )
            registered.append(f"{tool_prefix}_update_task_status")
        return registered

    def search_wiki(self, query: str, *, limit: int = 5, filters: dict[str, Any] | None = None) -> Any:
        resolver = self._resolve_search_knowledge()
        if resolver is None:
            raise RuntimeError("OpenClawConnector.search_knowledge callback is not configured.")

        result = resolver(query=query, limit=limit, filters=filters or {})
        self.client.capture(
            event_type="tool_result",
            payload={
                "integration": "openclaw",
                "phase": "search_wiki",
                "query": query,
                "limit": limit,
                "filters": filters or {},
                "result_preview": _preview(result),
            },
            agent_id=self.default_agent_id,
            session_id=self.default_session_id,
            tags=["integration:openclaw", "tool:search_wiki"],
        )
        return result

    def _resolve_search_knowledge(self) -> Callable[..., Any] | None:
        if self.search_knowledge is not None:
            self.auto_search_enabled = False
            return self.search_knowledge
        if not self.enable_default_search:
            self.auto_search_enabled = False
            return None
        client_search = getattr(self.client, "search_knowledge", None)
        if not callable(client_search):
            self.auto_search_enabled = False
            return None

        if not self.auto_search_enabled:
            self._emit_debug(
                "attach_openclaw_search_auto_enabled",
                {
                    "mode": "sdk_search_knowledge_api",
                },
            )
        self.auto_search_enabled = True

        def _resolver(*, query: str, limit: int, filters: dict[str, Any]) -> Any:
            related_entity_key = _coerce_optional_str(filters.get("entity_key")) if isinstance(filters, dict) else None
            return client_search(query, limit=limit, related_entity_key=related_entity_key)

        return _resolver

    def propose_to_wiki(
        self,
        *,
        entity_key: str,
        category: str,
        claim_text: str,
        source_id: str,
        source_type: str = "external_event",
        confidence: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        claim_id = str(uuid4())
        observed_at = datetime.now(UTC).isoformat()
        provenance = self._build_provenance(
            phase="propose_to_wiki",
            observed_at=observed_at,
            payload={
                "project_id": self.client.project_id,  # type: ignore[attr-defined]
                "entity_key": entity_key,
                "category": category,
                "claim_text": claim_text,
                "source_id": source_id,
                "source_type": source_type,
                "agent_id": self.default_agent_id,
                "session_id": self.default_session_id,
            },
        )
        claim_metadata = dict(metadata or {})
        claim_metadata["synapse_provenance"] = provenance
        claim = Claim(
            id=claim_id,
            schema_version="v1",
            project_id=self.client.project_id,  # type: ignore[attr-defined]
            entity_key=entity_key,
            category=category,
            claim_text=claim_text,
            status="draft",
            evidence=[
                EvidenceRef(
                    source_type=source_type,  # type: ignore[arg-type]
                    source_id=source_id,
                    observed_at=observed_at,
                    provenance=provenance,
                )
            ],
            confidence=confidence,
            metadata=claim_metadata,
        )
        self.client.propose_fact(claim)
        self.client.capture(
            event_type="fact_proposed",
            payload={
                "integration": "openclaw",
                "phase": "propose_to_wiki",
                "claim_id": claim_id,
                "entity_key": entity_key,
                "category": category,
                "provenance": {
                    "signature_alg": provenance.get("signature_alg"),
                    "signature": provenance.get("signature"),
                    "key_id": provenance.get("key_id"),
                    "mode": provenance.get("mode"),
                    "payload_sha256": provenance.get("payload_sha256"),
                },
            },
            agent_id=self.default_agent_id,
            session_id=self.default_session_id,
            tags=["integration:openclaw", "tool:propose_to_wiki"],
        )
        return {"status": "queued", "claim_id": claim_id}

    def get_open_tasks(
        self,
        *,
        limit: int = 20,
        assignee: str | None = None,
        entity_key: str | None = None,
    ) -> dict[str, Any]:
        resolver = self.list_tasks or (self.client.list_tasks if self._can_list_tasks() else None)
        if resolver is None:
            return {"tasks": []}
        tasks = resolver(limit=limit, assignee=assignee, entity_key=entity_key, include_closed=False)
        self.client.capture(
            event_type="tool_result",
            payload={
                "integration": "openclaw",
                "phase": "get_open_tasks",
                "limit": limit,
                "assignee": assignee,
                "entity_key": entity_key,
                "result_count": len(tasks) if isinstance(tasks, list) else None,
            },
            agent_id=self.default_agent_id,
            session_id=self.default_session_id,
            tags=["integration:openclaw", "tool:get_open_tasks"],
        )
        return {"tasks": tasks if isinstance(tasks, list) else []}

    def set_task_status(
        self,
        task_id: str,
        *,
        status: str,
        updated_by: str | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        updater = self.update_task_status or (self.client.update_task_status if self._can_update_task_status() else None)
        if updater is None:
            raise RuntimeError("Task status tool requires task API support or explicit update_task_status callback.")
        actor = updated_by or self.default_agent_id or "openclaw_agent"
        result = updater(task_id, status=status, updated_by=actor, note=note)
        self.client.capture(
            event_type="tool_result",
            payload={
                "integration": "openclaw",
                "phase": "update_task_status",
                "task_id": task_id,
                "status": status,
                "updated_by": actor,
            },
            agent_id=self.default_agent_id,
            session_id=self.default_session_id,
            tags=["integration:openclaw", "tool:update_task_status"],
        )
        return result if isinstance(result, dict) else {"status": "ok"}

    def _transport_supports_task_api(self) -> bool:
        transport = getattr(self.client, "_transport", None)
        return callable(getattr(transport, "request_json", None))

    def _can_list_tasks(self) -> bool:
        return self.list_tasks is not None or self._transport_supports_task_api()

    def _can_update_task_status(self) -> bool:
        return self.update_task_status is not None or self._transport_supports_task_api()

    def _emit_debug(self, event: str, details: dict[str, Any]) -> None:
        emitter = getattr(self.client, "_emit_debug", None)
        if not callable(emitter):
            return
        try:
            emitter(event, details)
        except Exception:
            return

    def _attach_hooks(self, runtime: Any, *, hook_events: Sequence[str]) -> None:
        register_hook = self._resolve_hook_registrar(runtime)
        for event_name in hook_events:
            register_hook(event_name, self._build_hook_handler(event_name))

    def _build_hook_handler(self, event_name: str) -> Callable[[dict[str, Any]], Any]:
        def _handler(event: dict[str, Any]) -> None:
            self.client.capture(
                event_type="system_signal",
                payload={
                    "integration": "openclaw",
                    "phase": "hook_event",
                    "event_name": event_name,
                    "event": _preview(event),
                },
                agent_id=self.default_agent_id,
                session_id=self.default_session_id or _event_session_id(event),
                tags=["integration:openclaw", f"event:{event_name}"],
            )

        return _handler

    def _resolve_hook_registrar(self, runtime: Any) -> Callable[[str, Callable[[dict[str, Any]], Any]], Any]:
        if hasattr(runtime, "on") and callable(runtime.on):
            return runtime.on
        if hasattr(runtime, "register_hook") and callable(runtime.register_hook):
            return runtime.register_hook
        raise TypeError("OpenClaw runtime must provide `on(event, handler)` or `register_hook(event, handler)`.")

    def _resolve_tool_registrar(self, runtime: Any) -> Callable[[str, Callable[..., Any], str | None], Any]:
        if not hasattr(runtime, "register_tool") or not callable(runtime.register_tool):
            raise TypeError("OpenClaw runtime must provide `register_tool(name, handler, description?)`.")

        def _register(name: str, handler: Callable[..., Any], description: str | None) -> Any:
            try:
                return runtime.register_tool(name, handler, description)
            except TypeError:
                return runtime.register_tool(name=name, handler=handler, description=description)

        return _register

    def _build_provenance(self, *, phase: str, observed_at: str, payload: dict[str, Any]) -> dict[str, Any]:
        canonical_payload = _canonical_json(payload)
        payload_sha256 = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
        secret = self._resolved_provenance_secret()
        key_id = self._resolved_provenance_key_id() if secret else None
        if secret:
            signature_alg = "hmac-sha256"
            signature = hmac.new(secret.encode("utf-8"), canonical_payload.encode("utf-8"), hashlib.sha256).hexdigest()
            mode = "signed"
        else:
            signature_alg = "sha256"
            signature = payload_sha256
            mode = "digest_only"

        return {
            "schema": "synapse.openclaw.provenance.v1",
            "phase": phase,
            "integration": "openclaw",
            "connector": "synapse-sdk-py",
            "agent_id": self.default_agent_id,
            "session_id": self.default_session_id,
            "captured_at": observed_at,
            "signature_alg": signature_alg,
            "signature": signature,
            "payload_sha256": payload_sha256,
            "key_id": key_id,
            "mode": mode,
        }

    def _resolved_provenance_secret(self) -> str | None:
        if self.provenance_secret is not None:
            resolved = str(self.provenance_secret).strip()
            return resolved or None
        env_value = str(
            os.getenv("SYNAPSE_OPENCLAW_PROVENANCE_SECRET") or os.getenv("SYNAPSE_PROVENANCE_SECRET") or ""
        ).strip()
        return env_value or None

    def _resolved_provenance_key_id(self) -> str:
        if self.provenance_key_id is not None:
            resolved = str(self.provenance_key_id).strip()
            if resolved:
                return resolved
        env_value = str(
            os.getenv("SYNAPSE_OPENCLAW_PROVENANCE_KEY_ID") or os.getenv("SYNAPSE_PROVENANCE_KEY_ID") or ""
        ).strip()
        if env_value:
            return env_value
        return "openclaw-default"


def _preview(value: Any, *, max_length: int = 2000) -> Any:
    text = repr(value)
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}...(truncated)"


def _event_session_id(event: dict[str, Any]) -> str:
    candidate = event.get("sessionKey") or event.get("session_id")
    if candidate:
        return str(candidate)
    return f"openclaw_{uuid4()}"


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True, default=str)


def list_openclaw_bootstrap_presets() -> list[dict[str, Any]]:
    return [
        {
            "preset": "runtime_memory",
            "description": "Read historical records from runtime memory exporter methods.",
            "default_source_system": "openclaw_runtime_memory",
        },
        {
            "preset": "event_log",
            "description": "Build bootstrap records from runtime event log replay payloads.",
            "default_source_system": "openclaw_event_log",
        },
        {
            "preset": "hybrid",
            "description": "Combine runtime memory export + event log replay (deduplicated).",
            "default_source_system": "openclaw_hybrid_bootstrap",
        },
    ]


def build_openclaw_bootstrap_options(
    *,
    preset: str = "runtime_memory",
    max_records: int = 1000,
    source_system: str | None = None,
    created_by: str | None = "sdk_attach",
    cursor: str | None = None,
    chunk_size: int = 100,
) -> BootstrapMemoryOptions:
    normalized_preset = _normalize_openclaw_bootstrap_preset(preset)
    resolved_source_system = source_system or _default_source_system_for_preset(normalized_preset)

    def _provider(runtime: Any) -> list[BootstrapMemoryInput]:
        return _collect_openclaw_bootstrap_records(
            runtime=runtime,
            preset=normalized_preset,
            max_records=max_records,
        )

    return BootstrapMemoryOptions(
        provider=_provider,
        source_system=resolved_source_system,
        created_by=created_by,
        cursor=cursor,
        chunk_size=max(1, int(chunk_size)),
        max_records=max(1, int(max_records)),
    )


def _normalize_openclaw_bootstrap_preset(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in OPENCLAW_BOOTSTRAP_PRESETS:
        allowed = ", ".join(OPENCLAW_BOOTSTRAP_PRESETS)
        raise ValueError(f"unsupported openclaw bootstrap preset `{value}` (allowed: {allowed})")
    return normalized


def _default_source_system_for_preset(preset: str) -> str:
    if preset == "runtime_memory":
        return "openclaw_runtime_memory"
    if preset == "event_log":
        return "openclaw_event_log"
    return "openclaw_hybrid_bootstrap"


def _collect_openclaw_bootstrap_records(
    *,
    runtime: Any,
    preset: str,
    max_records: int,
) -> list[BootstrapMemoryInput]:
    limit = max(1, min(int(max_records), 10_000))
    records: list[BootstrapMemoryInput] = []
    if preset in {"runtime_memory", "hybrid"}:
        records.extend(_records_from_runtime_memory(runtime))
    if preset in {"event_log", "hybrid"}:
        records.extend(_records_from_runtime_event_log(runtime))
    dedupe: set[tuple[str, str]] = set()
    out: list[BootstrapMemoryInput] = []
    for item in records:
        normalized = _coerce_bootstrap_item(item)
        if normalized is None:
            continue
        source_id = str(normalized.get("source_id") or "").strip()
        content = str(normalized.get("content") or "").strip()
        if not source_id or not content:
            continue
        key = (source_id, content)
        if key in dedupe:
            continue
        dedupe.add(key)
        out.append(normalized)
        if len(out) >= limit:
            break
    return out


def _records_from_runtime_memory(runtime: Any) -> list[BootstrapMemoryInput]:
    sources = [
        _resolve_openclaw_memory_export(runtime),
    ]
    out: list[BootstrapMemoryInput] = []
    for source in sources:
        if source is None:
            continue
        raw = source()
        out.extend(_coerce_iterable_payload(raw))
    return out


def _resolve_openclaw_memory_export(runtime: Any) -> Callable[[], Any] | None:
    memory_obj = getattr(runtime, "memory", None)
    candidates: list[Callable[[], Any]] = []
    for holder in [memory_obj, runtime]:
        if holder is None:
            continue
        for attr in (
            "export_all",
            "exportAll",
            "export_memory",
            "exportMemory",
            "dump",
            "list",
            "list_all",
            "to_records",
            "records",
        ):
            value = getattr(holder, attr, None)
            if callable(value):
                candidates.append(value)
    for candidate in candidates:
        return candidate
    return None


def _records_from_runtime_event_log(runtime: Any) -> list[BootstrapMemoryInput]:
    event_log = getattr(runtime, "event_log", None)
    if callable(event_log):
        event_log = event_log()
    rows = _coerce_iterable_payload(event_log)
    out: list[BootstrapMemoryInput] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            text = str(row).strip()
            if not text:
                continue
            out.append(
                {
                    "source_id": f"openclaw_event_{index}",
                    "content": text,
                    "metadata": {"openclaw_bootstrap_origin": "event_log"},
                    "tags": ["origin:event_log"],
                }
            )
            continue
        event_name = str(row.get("event_name") or row.get("event") or "").strip() or "event"
        payload = row.get("payload")
        payload_obj = payload if isinstance(payload, dict) else {}
        content = (
            _coerce_optional_str(
                payload_obj.get("result")
                or payload_obj.get("message")
                or payload_obj.get("summary")
                or payload_obj.get("text")
                or row.get("message")
                or row.get("summary")
            )
            or _coerce_optional_str(row.get("content"))
        )
        if content is None:
            payload_preview = _coerce_optional_str(_preview(payload_obj or row, max_length=800))
            content = payload_preview
        if content is None:
            continue
        source_id = (
            _coerce_optional_str(row.get("source_id"))
            or _coerce_optional_str(payload_obj.get("source_id"))
            or _coerce_optional_str(payload_obj.get("sessionKey"))
            or f"openclaw_event_{index}"
        )
        out.append(
            {
                "source_id": source_id,
                "content": content,
                "entity_key": _coerce_optional_str(payload_obj.get("entity_key") or row.get("entity_key")),
                "category": _coerce_optional_str(payload_obj.get("category") or row.get("category")),
                "observed_at": _coerce_optional_str(row.get("observed_at") or payload_obj.get("observed_at")),
                "metadata": {
                    "openclaw_bootstrap_origin": "event_log",
                    "event_name": event_name,
                },
                "tags": [f"event:{event_name}", "origin:event_log"],
            }
        )
    return out


def _coerce_bootstrap_item(item: BootstrapMemoryInput) -> dict[str, Any] | None:
    if isinstance(item, str):
        text = item.strip()
        if not text:
            return None
        return {
            "source_id": f"openclaw_memory_{hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]}",
            "content": text,
            "metadata": {"openclaw_bootstrap_origin": "runtime_memory"},
            "tags": ["origin:runtime_memory"],
        }
    if not isinstance(item, dict):
        return None
    source_id = (
        _coerce_optional_str(item.get("source_id"))
        or _coerce_optional_str(item.get("id"))
        or _coerce_optional_str(item.get("key"))
        or _coerce_optional_str(item.get("memory_id"))
    )
    content = _coerce_optional_str(
        item.get("content")
        or item.get("text")
        or item.get("fact")
        or item.get("message")
        or item.get("summary")
        or item.get("result")
    )
    if content is None:
        return None
    if source_id is None:
        source_id = f"openclaw_memory_{hashlib.sha256(content.encode('utf-8')).hexdigest()[:12]}"
    metadata_value = item.get("metadata")
    metadata = dict(metadata_value) if isinstance(metadata_value, dict) else {}
    metadata.setdefault("openclaw_bootstrap_origin", "runtime_memory")
    tags = _coerce_tags(item.get("tags"))
    if "origin:runtime_memory" not in tags:
        tags.append("origin:runtime_memory")
    return {
        "source_id": source_id,
        "content": content,
        "observed_at": _coerce_optional_str(item.get("observed_at") or item.get("timestamp") or item.get("created_at")),
        "entity_key": _coerce_optional_str(item.get("entity_key") or item.get("entity")),
        "category": _coerce_optional_str(item.get("category")),
        "metadata": metadata,
        "tags": tags,
    }


def _coerce_iterable_payload(payload: Any) -> list[Any]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return list(payload)
    if isinstance(payload, tuple):
        return list(payload)
    if isinstance(payload, dict):
        for key in ("items", "records", "data", "events", "rows"):
            value = payload.get(key)
            if isinstance(value, list):
                return list(value)
            if isinstance(value, tuple):
                return list(value)
        return [payload]
    return [payload]


def _coerce_tags(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            out.append(text)
    return out


def _coerce_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None
