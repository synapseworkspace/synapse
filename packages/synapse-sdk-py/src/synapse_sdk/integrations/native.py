from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from typing import Any, Callable, Mapping, Sequence
from uuid import uuid4

from synapse_sdk.integrations.monitoring import monitor_crewai, monitor_langchain, monitor_langgraph

try:  # optional dependency
    from langchain_core.callbacks.base import BaseCallbackHandler as _LangChainBaseCallbackHandler
except Exception:  # pragma: no cover - executed when langchain is absent
    _LangChainBaseCallbackHandler = object

DEFAULT_CREWAI_EVENTS = (
    "crew_started",
    "crew_completed",
    "crew_failed",
    "task_started",
    "task_completed",
    "task_failed",
    "agent_step",
)


class SynapseLangChainCallbackHandler(_LangChainBaseCallbackHandler):
    """LangChain/LangGraph callback handler that forwards native runtime events to Synapse."""

    raise_error = False
    run_inline = True

    def __init__(
        self,
        *,
        client: Any,
        integration: str = "langchain",
        agent_id: str | None = None,
        session_id: str | None = None,
        flush_on_success: bool = False,
        flush_on_error: bool = True,
        capture_inputs: bool = True,
        capture_outputs: bool = True,
    ) -> None:
        self._client = client
        self._integration = integration
        self._agent_id = agent_id
        self._session_id = session_id
        self._flush_on_success = bool(flush_on_success)
        self._flush_on_error = bool(flush_on_error)
        self._capture_inputs = bool(capture_inputs)
        self._capture_outputs = bool(capture_outputs)

    def _resolve_session_id(self, kwargs: Mapping[str, Any]) -> str:
        if self._session_id:
            return self._session_id
        run_id = kwargs.get("run_id")
        if run_id is not None:
            return str(run_id)
        return str(uuid4())

    def _capture(
        self,
        *,
        phase: str,
        payload: dict[str, Any],
        kwargs: Mapping[str, Any],
        event_type: str = "system_signal",
    ) -> None:
        merged = {
            "integration": self._integration,
            "phase": phase,
            **payload,
        }
        run_id = kwargs.get("run_id")
        parent_run_id = kwargs.get("parent_run_id")
        if run_id is not None:
            merged["run_id"] = str(run_id)
        if parent_run_id is not None:
            merged["parent_run_id"] = str(parent_run_id)
        self._client.capture(
            event_type=event_type,
            payload=_safe_serialize(merged),
            agent_id=self._agent_id,
            session_id=self._resolve_session_id(kwargs),
            tags=[f"integration:{self._integration}", "native_callback"],
        )

    def _flush_on_terminal(self, *, is_error: bool) -> None:
        if (is_error and self._flush_on_error) or ((not is_error) and self._flush_on_success):
            self._client.flush()

    # Signatures intentionally permissive: LangChain callback API may evolve.
    def on_chain_start(self, serialized: Any, inputs: Any, **kwargs: Any) -> None:
        self._capture(
            phase="chain_started",
            payload={
                "serialized": serialized if self._capture_inputs else None,
                "inputs": inputs if self._capture_inputs else None,
            },
            kwargs=kwargs,
        )

    def on_chain_end(self, outputs: Any, **kwargs: Any) -> None:
        self._capture(
            phase="chain_completed",
            payload={"outputs": outputs if self._capture_outputs else None},
            kwargs=kwargs,
            event_type="tool_result",
        )
        self._flush_on_terminal(is_error=False)

    def on_chain_error(self, error: Exception | KeyboardInterrupt, **kwargs: Any) -> None:
        self._capture(
            phase="chain_failed",
            payload={"error_type": type(error).__name__, "error_message": str(error)},
            kwargs=kwargs,
        )
        self._flush_on_terminal(is_error=True)

    def on_tool_start(self, serialized: Any, input_str: str, **kwargs: Any) -> None:
        self._capture(
            phase="tool_started",
            payload={
                "serialized": serialized if self._capture_inputs else None,
                "tool_input": input_str if self._capture_inputs else None,
            },
            kwargs=kwargs,
        )

    def on_tool_end(self, output: Any, **kwargs: Any) -> None:
        self._capture(
            phase="tool_completed",
            payload={"tool_output": output if self._capture_outputs else None},
            kwargs=kwargs,
            event_type="tool_result",
        )

    def on_tool_error(self, error: Exception | KeyboardInterrupt, **kwargs: Any) -> None:
        self._capture(
            phase="tool_failed",
            payload={"error_type": type(error).__name__, "error_message": str(error)},
            kwargs=kwargs,
        )

    def on_llm_start(self, serialized: Any, prompts: list[str], **kwargs: Any) -> None:
        self._capture(
            phase="llm_started",
            payload={
                "serialized": serialized if self._capture_inputs else None,
                "prompts": prompts if self._capture_inputs else None,
            },
            kwargs=kwargs,
        )

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        self._capture(
            phase="llm_completed",
            payload={"response": response if self._capture_outputs else None},
            kwargs=kwargs,
            event_type="tool_result",
        )

    def on_llm_error(self, error: Exception | KeyboardInterrupt, **kwargs: Any) -> None:
        self._capture(
            phase="llm_failed",
            payload={"error_type": type(error).__name__, "error_message": str(error)},
            kwargs=kwargs,
        )

    def on_agent_action(self, action: Any, **kwargs: Any) -> None:
        self._capture(
            phase="agent_action",
            payload={"action": action if self._capture_outputs else None},
            kwargs=kwargs,
            event_type="tool_result",
        )

    def on_agent_finish(self, finish: Any, **kwargs: Any) -> None:
        self._capture(
            phase="agent_finished",
            payload={"finish": finish if self._capture_outputs else None},
            kwargs=kwargs,
            event_type="tool_result",
        )


def create_langchain_callback_handler(
    client: Any,
    *,
    integration: str = "langchain",
    agent_id: str | None = None,
    session_id: str | None = None,
    flush_on_success: bool = False,
    flush_on_error: bool = True,
    capture_inputs: bool = True,
    capture_outputs: bool = True,
) -> SynapseLangChainCallbackHandler:
    return SynapseLangChainCallbackHandler(
        client=client,
        integration=integration,
        agent_id=agent_id,
        session_id=session_id,
        flush_on_success=flush_on_success,
        flush_on_error=flush_on_error,
        capture_inputs=capture_inputs,
        capture_outputs=capture_outputs,
    )


def build_langchain_config(handler: Any) -> dict[str, list[Any]]:
    return {"callbacks": [handler]}


def bind_langchain(
    client: Any,
    target: Any,
    *,
    handler: Any | None = None,
    integration: str = "langchain",
    fallback_monitor: bool = True,
    monitor_include_methods: Sequence[str] | None = None,
    agent_id: str | None = None,
    session_id: str | None = None,
    monitor_fn: Callable[..., Any] = monitor_langchain,
) -> Any:
    resolved_handler = handler or create_langchain_callback_handler(
        client,
        integration=integration,
        agent_id=agent_id,
        session_id=session_id,
    )

    bound, mode = _bind_langchain_like_target(target, resolved_handler)
    if mode is not None:
        _emit_debug(
            client,
            "native_framework_bound",
            {
                "framework": integration,
                "binding_mode": mode,
                "target_type": type(target).__name__,
            },
        )
        return bound

    if fallback_monitor:
        _emit_debug(
            client,
            "native_framework_fallback_monitor",
            {
                "framework": integration,
                "target_type": type(target).__name__,
            },
        )
        return monitor_fn(
            client,
            target,
            include_methods=monitor_include_methods,
            agent_id=agent_id,
            session_id=session_id,
        )

    raise RuntimeError(
        "Unable to bind native LangChain callbacks; no supported callback surface found on target."
    )


def bind_langgraph(
    client: Any,
    target: Any,
    *,
    handler: Any | None = None,
    fallback_monitor: bool = True,
    monitor_include_methods: Sequence[str] | None = None,
    agent_id: str | None = None,
    session_id: str | None = None,
) -> Any:
    return bind_langchain(
        client,
        target,
        handler=handler,
        integration="langgraph",
        fallback_monitor=fallback_monitor,
        monitor_include_methods=monitor_include_methods,
        agent_id=agent_id,
        session_id=session_id,
        monitor_fn=monitor_langgraph,
    )


def bind_crewai(
    client: Any,
    target: Any,
    *,
    event_names: Sequence[str] = DEFAULT_CREWAI_EVENTS,
    event_handler: Callable[[str, Any], None] | None = None,
    monitor_runtime: bool = True,
    monitor_include_methods: Sequence[str] | None = None,
    agent_id: str | None = None,
    session_id: str | None = None,
) -> Any:
    resolved_handler = event_handler or _build_default_crewai_event_handler(
        client,
        agent_id=agent_id,
        session_id=session_id,
    )

    registered = 0
    event_targets = [target]
    event_bus = getattr(target, "event_bus", None)
    if event_bus is not None:
        event_targets.append(event_bus)

    for name in event_names:
        bound = False
        for container in event_targets:
            if _register_event_listener(container, str(name), lambda payload, _name=str(name): resolved_handler(_name, payload)):
                bound = True
                break
        if bound:
            registered += 1

    if hasattr(target, "step_callback"):
        existing = getattr(target, "step_callback")
        step_callback = _build_crewai_step_callback(
            client,
            existing if callable(existing) else None,
            agent_id=agent_id,
            session_id=session_id,
        )
        try:
            setattr(target, "step_callback", step_callback)
            registered += 1
        except Exception:
            pass

    _emit_debug(
        client,
        "native_framework_bound",
        {
            "framework": "crewai",
            "binding_mode": "event_bus_or_callbacks",
            "target_type": type(target).__name__,
            "registered_hooks": int(registered),
        },
    )

    if monitor_runtime:
        return monitor_crewai(
            client,
            target,
            include_methods=monitor_include_methods,
            agent_id=agent_id,
            session_id=session_id,
        )
    return target


def _build_crewai_step_callback(
    client: Any,
    existing: Callable[..., Any] | None,
    *,
    agent_id: str | None,
    session_id: str | None,
) -> Callable[..., Any]:
    def _callback(*args: Any, **kwargs: Any) -> Any:
        client.capture(
            event_type="system_signal",
            payload=_safe_serialize(
                {
                    "integration": "crewai",
                    "phase": "step_callback",
                    "args": args,
                    "kwargs": kwargs,
                }
            ),
            agent_id=agent_id,
            session_id=session_id or str(uuid4()),
            tags=["integration:crewai", "native_callback"],
        )
        if existing is not None:
            return existing(*args, **kwargs)
        return None

    return _callback


def _build_default_crewai_event_handler(
    client: Any,
    *,
    agent_id: str | None,
    session_id: str | None,
) -> Callable[[str, Any], None]:
    def _handler(event_name: str, payload: Any) -> None:
        client.capture(
            event_type="system_signal",
            payload=_safe_serialize(
                {
                    "integration": "crewai",
                    "phase": "event_bus_signal",
                    "event_name": event_name,
                    "payload": payload,
                }
            ),
            agent_id=agent_id,
            session_id=session_id or str(uuid4()),
            tags=["integration:crewai", "native_callback"],
        )

    return _handler


def _register_event_listener(container: Any, event_name: str, handler: Callable[[Any], None]) -> bool:
    for method_name in ("on", "add_listener", "subscribe", "register_listener"):
        method = getattr(container, method_name, None)
        if not callable(method):
            continue
        for call in (
            lambda: method(event_name, handler),
            lambda: method(event_name=event_name, handler=handler),
            lambda: method(name=event_name, callback=handler),
            lambda: method(event_name, callback=handler),
        ):
            try:
                call()
                return True
            except TypeError:
                continue
            except Exception:
                return False
    return False


def _bind_langchain_like_target(target: Any, handler: Any) -> tuple[Any, str | None]:
    with_config = getattr(target, "with_config", None)
    if callable(with_config):
        try:
            bound = with_config(build_langchain_config(handler))
            if bound is not None:
                return bound, "with_config"
        except Exception:
            pass

    callback_manager = getattr(target, "callback_manager", None)
    if callback_manager is not None:
        add_handler = getattr(callback_manager, "add_handler", None)
        if callable(add_handler):
            for call in (
                lambda: add_handler(handler),
                lambda: add_handler(handler, True),
                lambda: add_handler(handler, inherit=True),
            ):
                try:
                    call()
                    return target, "callback_manager.add_handler"
                except TypeError:
                    continue
                except Exception:
                    break
        add_handlers = getattr(callback_manager, "add_handlers", None)
        if callable(add_handlers):
            for call in (
                lambda: add_handlers([handler]),
                lambda: add_handlers([handler], True),
                lambda: add_handlers([handler], inherit=True),
            ):
                try:
                    call()
                    return target, "callback_manager.add_handlers"
                except TypeError:
                    continue
                except Exception:
                    break

    callbacks = getattr(target, "callbacks", None)
    if isinstance(callbacks, list):
        if not any(item is handler for item in callbacks):
            callbacks.append(handler)
        return target, "callbacks_list"
    if isinstance(callbacks, tuple):
        try:
            setattr(target, "callbacks", list(callbacks) + [handler])
            return target, "callbacks_tuple"
        except Exception:
            pass
    if callbacks is None:
        try:
            setattr(target, "callbacks", [handler])
            return target, "callbacks_new"
        except Exception:
            pass

    config = getattr(target, "config", None)
    if isinstance(config, dict):
        config_callbacks = config.get("callbacks")
        if isinstance(config_callbacks, list):
            if not any(item is handler for item in config_callbacks):
                config_callbacks.append(handler)
            return target, "config_callbacks_list"
        config["callbacks"] = [handler]
        return target, "config_callbacks_new"

    return target, None


def _emit_debug(client: Any, event: str, details: dict[str, Any]) -> None:
    emit = getattr(client, "_emit_debug", None)
    if callable(emit):
        try:
            emit(event, details)
            return
        except Exception:
            pass


def _safe_serialize(value: Any, *, _depth: int = 0, _max_depth: int = 4, _max_items: int = 30) -> Any:
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
        serialized = [_safe_serialize(item, _depth=_depth + 1) for item in items[:_max_items]]
        if len(items) > _max_items:
            serialized.append(f"...({len(items) - _max_items} more items)")
        return serialized
    if hasattr(value, "model_dump") and callable(value.model_dump):
        try:
            return _safe_serialize(value.model_dump(mode="json"), _depth=_depth + 1)
        except TypeError:
            return _safe_serialize(value.model_dump(), _depth=_depth + 1)
        except Exception:
            return repr(value)
    if hasattr(value, "dict") and callable(value.dict):
        try:
            return _safe_serialize(value.dict(), _depth=_depth + 1)
        except Exception:
            return repr(value)
    return repr(value)
