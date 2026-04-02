from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime
import inspect
from typing import Any, Callable, Iterable, Mapping, Sequence
from uuid import uuid4

if False:  # pragma: no cover
    from synapse_sdk.client import SynapseClient


LANGGRAPH_DEFAULT_METHODS = ("invoke", "ainvoke", "stream", "astream", "batch", "abatch")
LANGCHAIN_DEFAULT_METHODS = ("invoke", "ainvoke", "stream", "astream", "batch", "abatch", "call", "acall")
CREWAI_DEFAULT_METHODS = ("kickoff", "kickoff_async", "run", "execute", "execute_async")
OPENCLAW_DEFAULT_METHODS = ("run", "run_task", "execute_action", "invoke_tool", "dispatch")


@dataclass
class MonitorOptions:
    integration: str = "generic"
    include_methods: Sequence[str] | None = None
    agent_id: str | None = None
    session_id: str | None = None
    flush_on_success: bool = False
    flush_on_error: bool = True
    capture_arguments: bool = True
    capture_results: bool = True
    capture_stream_items: bool = True
    max_stream_items: int = 25


class MonitoringProxy:
    def __init__(
        self,
        client: "SynapseClient",
        target: Any,
        options: MonitorOptions,
    ) -> None:
        self._client = client
        self._target = target
        self._options = options
        self._include_methods = set(options.include_methods or _default_methods_for_integration(options.integration))

    def __getattr__(self, item: str) -> Any:
        value = getattr(self._target, item)
        if not callable(value) or item not in self._include_methods:
            return value
        return self._wrap_method(item, value)

    def __repr__(self) -> str:
        return f"MonitoringProxy(target={self._target!r}, integration={self._options.integration!r})"

    def _wrap_method(self, method_name: str, method: Callable[..., Any]) -> Callable[..., Any]:
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            call_id = str(uuid4())
            session_id = self._options.session_id or call_id
            trace_context, tokens = self._client._push_trace_span(span_id=call_id)
            self._capture(
                event_type="system_signal",
                payload={
                    "integration": self._options.integration,
                    "phase": "call_started",
                    "method": method_name,
                    "call_id": call_id,
                    "args": _safe_serialize(args) if self._options.capture_arguments else None,
                    "kwargs": _safe_serialize(kwargs) if self._options.capture_arguments else None,
                },
                session_id=session_id,
                trace_context=trace_context,
            )
            try:
                result = method(*args, **kwargs)
            except Exception as exc:
                self._on_error(method_name, call_id, session_id, exc, trace_context=trace_context, finalize=lambda: self._client._pop_trace_span(tokens))
                raise

            if inspect.isawaitable(result):
                async def _awaited() -> Any:
                    try:
                        resolved = await result
                    except Exception as exc:
                        self._on_error(
                            method_name,
                            call_id,
                            session_id,
                            exc,
                            trace_context=trace_context,
                            finalize=lambda: self._client._pop_trace_span(tokens),
                        )
                        raise
                    return self._on_success(
                        method_name,
                        call_id,
                        session_id,
                        resolved,
                        trace_context=trace_context,
                        finalize=lambda: self._client._pop_trace_span(tokens),
                    )

                return _awaited()

            return self._on_success(
                method_name,
                call_id,
                session_id,
                result,
                trace_context=trace_context,
                finalize=lambda: self._client._pop_trace_span(tokens),
            )

        return wrapped

    def _on_success(
        self,
        method_name: str,
        call_id: str,
        session_id: str,
        result: Any,
        *,
        trace_context: dict[str, str | None],
        finalize: Callable[[], None],
    ) -> Any:
        if inspect.isgenerator(result):
            return self._wrap_generator(
                method_name=method_name,
                call_id=call_id,
                session_id=session_id,
                generator=result,
                trace_context=trace_context,
                finalize=finalize,
            )
        if inspect.isasyncgen(result):
            return self._wrap_async_generator(
                method_name=method_name,
                call_id=call_id,
                session_id=session_id,
                generator=result,
                trace_context=trace_context,
                finalize=finalize,
            )

        try:
            self._capture(
                event_type="tool_result",
                payload={
                    "integration": self._options.integration,
                    "phase": "call_succeeded",
                    "method": method_name,
                    "call_id": call_id,
                    "result": _safe_serialize(result) if self._options.capture_results else None,
                },
                session_id=session_id,
                trace_context=trace_context,
            )
            if self._options.flush_on_success:
                self._client.flush()
        finally:
            finalize()
        return result

    def _on_error(
        self,
        method_name: str,
        call_id: str,
        session_id: str,
        exc: Exception,
        *,
        trace_context: dict[str, str | None],
        finalize: Callable[[], None],
    ) -> None:
        try:
            self._capture(
                event_type="system_signal",
                payload={
                    "integration": self._options.integration,
                    "phase": "call_failed",
                    "method": method_name,
                    "call_id": call_id,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
                session_id=session_id,
                trace_context=trace_context,
            )
            if self._options.flush_on_error:
                self._client.flush()
        finally:
            finalize()

    def _wrap_generator(
        self,
        *,
        method_name: str,
        call_id: str,
        session_id: str,
        generator: Iterable[Any],
        trace_context: dict[str, str | None],
        finalize: Callable[[], None],
    ) -> Iterable[Any]:
        def _gen() -> Iterable[Any]:
            emitted = 0
            try:
                for item in generator:
                    emitted += 1
                    if self._options.capture_stream_items and emitted <= self._options.max_stream_items:
                        self._capture(
                            event_type="tool_result",
                            payload={
                                "integration": self._options.integration,
                                "phase": "stream_item",
                                "method": method_name,
                                "call_id": call_id,
                                "index": emitted - 1,
                                "item": _safe_serialize(item),
                            },
                            session_id=session_id,
                            trace_context=trace_context,
                        )
                    yield item
                self._capture(
                    event_type="system_signal",
                    payload={
                        "integration": self._options.integration,
                        "phase": "stream_completed",
                        "method": method_name,
                        "call_id": call_id,
                        "emitted_items": emitted,
                    },
                    session_id=session_id,
                    trace_context=trace_context,
                )
                if self._options.flush_on_success:
                    self._client.flush()
            finally:
                finalize()

        return _gen()

    def _wrap_async_generator(
        self,
        *,
        method_name: str,
        call_id: str,
        session_id: str,
        generator: Any,
        trace_context: dict[str, str | None],
        finalize: Callable[[], None],
    ) -> Any:
        async def _agen() -> Any:
            emitted = 0
            try:
                async for item in generator:
                    emitted += 1
                    if self._options.capture_stream_items and emitted <= self._options.max_stream_items:
                        self._capture(
                            event_type="tool_result",
                            payload={
                                "integration": self._options.integration,
                                "phase": "stream_item",
                                "method": method_name,
                                "call_id": call_id,
                                "index": emitted - 1,
                                "item": _safe_serialize(item),
                            },
                            session_id=session_id,
                            trace_context=trace_context,
                        )
                    yield item
                self._capture(
                    event_type="system_signal",
                    payload={
                        "integration": self._options.integration,
                        "phase": "stream_completed",
                        "method": method_name,
                        "call_id": call_id,
                        "emitted_items": emitted,
                    },
                    session_id=session_id,
                    trace_context=trace_context,
                )
                if self._options.flush_on_success:
                    self._client.flush()
            finally:
                finalize()

        return _agen()

    def _capture(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        session_id: str,
        trace_context: dict[str, str | None],
    ) -> None:
        self._client.capture(
            event_type=event_type,  # type: ignore[arg-type]
            payload=payload,
            session_id=session_id,
            agent_id=self._options.agent_id,
            trace_id=trace_context.get("trace_id"),
            span_id=trace_context.get("span_id"),
            parent_span_id=trace_context.get("parent_span_id"),
            tags=[f"integration:{self._options.integration}"],
        )


def monitor_object(
    client: "SynapseClient",
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
    return MonitoringProxy(
        client=client,
        target=target,
        options=MonitorOptions(
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
        ),
    )


def monitor_langgraph(client: "SynapseClient", graph: Any, **kwargs: Any) -> Any:
    return monitor_object(
        client,
        graph,
        integration="langgraph",
        include_methods=kwargs.pop("include_methods", LANGGRAPH_DEFAULT_METHODS),
        **kwargs,
    )


def monitor_langchain(client: "SynapseClient", chain_or_runnable: Any, **kwargs: Any) -> Any:
    return monitor_object(
        client,
        chain_or_runnable,
        integration="langchain",
        include_methods=kwargs.pop("include_methods", LANGCHAIN_DEFAULT_METHODS),
        **kwargs,
    )


def monitor_crewai(client: "SynapseClient", crew_or_agent: Any, **kwargs: Any) -> Any:
    return monitor_object(
        client,
        crew_or_agent,
        integration="crewai",
        include_methods=kwargs.pop("include_methods", CREWAI_DEFAULT_METHODS),
        **kwargs,
    )


def monitor_openclaw_runtime(client: "SynapseClient", runtime: Any, **kwargs: Any) -> Any:
    return monitor_object(
        client,
        runtime,
        integration="openclaw",
        include_methods=kwargs.pop("include_methods", OPENCLAW_DEFAULT_METHODS),
        **kwargs,
    )


def _default_methods_for_integration(integration: str) -> tuple[str, ...]:
    if integration == "langgraph":
        return LANGGRAPH_DEFAULT_METHODS
    if integration == "langchain":
        return LANGCHAIN_DEFAULT_METHODS
    if integration == "crewai":
        return CREWAI_DEFAULT_METHODS
    if integration == "openclaw":
        return OPENCLAW_DEFAULT_METHODS
    return ("invoke", "run", "execute", "stream")


def _safe_serialize(value: Any, *, _depth: int = 0, _max_depth: int = 4, _max_items: int = 25) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value if len(value) <= 5000 else f"{value[:5000]}...(truncated)"
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if _depth >= _max_depth:
        return repr(value)
    if is_dataclass(value):
        return _safe_serialize(asdict(value), _depth=_depth + 1)
    if hasattr(value, "model_dump") and callable(value.model_dump):
        try:
            return _safe_serialize(value.model_dump(mode="json"), _depth=_depth + 1)
        except TypeError:
            return _safe_serialize(value.model_dump(), _depth=_depth + 1)
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for idx, (k, v) in enumerate(value.items()):
            if idx >= _max_items:
                out["__truncated__"] = f"{len(value) - _max_items} more items"
                break
            out[str(k)] = _safe_serialize(v, _depth=_depth + 1)
        return out
    if isinstance(value, (list, tuple, set, frozenset)):
        items = list(value)
        serialized = [_safe_serialize(x, _depth=_depth + 1) for x in items[:_max_items]]
        if len(items) > _max_items:
            serialized.append({"__truncated__": len(items) - _max_items})
        return serialized
    if hasattr(value, "__dict__"):
        return _safe_serialize(vars(value), _depth=_depth + 1)
    return repr(value)
