from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class RegisteredTool:
    name: str
    handler: Callable[..., Any]
    description: str | None = None


class OpenClawRuntimeTemplate:
    """Minimal runtime template compatible with Synapse OpenClawConnector."""

    def __init__(self) -> None:
        self._hooks: dict[str, list[Callable[[dict[str, Any]], Any]]] = {}
        self._tools: dict[str, RegisteredTool] = {}
        self._event_log: list[dict[str, Any]] = []

    def on(self, event_name: str, handler: Callable[[dict[str, Any]], Any]) -> None:
        self._hooks.setdefault(event_name, []).append(handler)

    def register_hook(self, event_name: str, handler: Callable[[dict[str, Any]], Any]) -> None:
        self.on(event_name, handler)

    def register_tool(self, name: str, handler: Callable[..., Any], description: str | None = None) -> None:
        self._tools[name] = RegisteredTool(name=name, handler=handler, description=description)

    def emit(self, event_name: str, payload: dict[str, Any]) -> None:
        self._event_log.append({"event_name": event_name, "payload": payload})
        for hook in self._hooks.get(event_name, []):
            hook(payload)

    def call_tool(self, name: str, **kwargs: Any) -> Any:
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"tool {name!r} is not registered")
        return tool.handler(**kwargs)

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": tool.name, "description": tool.description}
            for tool in sorted(self._tools.values(), key=lambda item: item.name)
        ]

    @property
    def event_log(self) -> list[dict[str, Any]]:
        return list(self._event_log)
