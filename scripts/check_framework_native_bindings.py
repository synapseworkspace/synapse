#!/usr/bin/env python3
from __future__ import annotations

import json
from typing import Any

from synapse_sdk import Synapse, SynapseConfig


class MemoryTransport:
    def __init__(self) -> None:
        self.events: list[Any] = []
        self.claims: list[Any] = []
        self.backfills: list[Any] = []

    def send_events(self, events: list[Any], *, idempotency_key: str | None = None) -> None:
        self.events.extend(events)

    def propose_fact(self, claim: Any, *, idempotency_key: str | None = None) -> None:
        self.claims.append(claim)

    def ingest_memory_backfill(self, batch_payload: dict[str, Any], *, idempotency_key: str | None = None) -> None:
        self.backfills.append(batch_payload)


class LangChainBoundRunnable:
    def __init__(self, callbacks: list[Any]) -> None:
        self.callbacks = callbacks

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        for callback in self.callbacks:
            on_start = getattr(callback, "on_chain_start", None)
            if callable(on_start):
                on_start({"name": "dummy_chain"}, payload, run_id="lc-run-1", parent_run_id="lc-parent-1")

        result = {"result": f"processed:{payload.get('input', 'unknown')}"}

        for callback in self.callbacks:
            on_end = getattr(callback, "on_chain_end", None)
            if callable(on_end):
                on_end(result, run_id="lc-run-1", parent_run_id="lc-parent-1")

        return result


class LangChainRunnableFixture:
    def with_config(self, config: dict[str, Any]) -> LangChainBoundRunnable:
        callbacks = list(config.get("callbacks") or [])
        return LangChainBoundRunnable(callbacks)


class CrewRuntimeFixture:
    def __init__(self) -> None:
        self.listeners: dict[str, Any] = {}
        self.step_callback: Any = None

    def on(self, event_name: str, handler: Any) -> None:
        self.listeners[event_name] = handler

    def kickoff(self) -> dict[str, Any]:
        started = self.listeners.get("crew_started")
        if callable(started):
            started({"crew": "dispatch", "status": "started"})

        if callable(self.step_callback):
            self.step_callback({"phase": "plan", "step": "collect_constraints"})

        completed = self.listeners.get("crew_completed")
        if callable(completed):
            completed({"crew": "dispatch", "status": "completed"})

        return {"status": "ok"}


class NotBindableFixture:
    __slots__ = ()


def _integration_tags(transport: MemoryTransport) -> set[str]:
    tags: set[str] = set()
    for event in transport.events:
        raw = getattr(event, "tags", None)
        if not isinstance(raw, list):
            continue
        for item in raw:
            if isinstance(item, str):
                tags.add(item)
    return tags


def _phase_values(transport: MemoryTransport) -> set[str]:
    phases: set[str] = set()
    for event in transport.events:
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            continue
        phase = payload.get("phase")
        if isinstance(phase, str):
            phases.add(phase)
    return phases


def main() -> int:
    transport = MemoryTransport()
    client = Synapse(SynapseConfig(api_url="http://localhost:8080", project_id="framework_native_smoke"), transport=transport)
    client.set_debug_mode(True, max_records=2000)

    # LangChain native callback binding via with_config.
    langchain_target = LangChainRunnableFixture()
    langchain_bound = client.bind_langchain(langchain_target, fallback_monitor=False, session_id="native-lc")
    lc_result = langchain_bound.invoke({"input": "hello"})
    assert lc_result.get("result") == "processed:hello", lc_result

    # LangGraph path reuses callback native binding with langgraph integration tag.
    langgraph_target = LangChainRunnableFixture()
    langgraph_bound = client.bind_langgraph(langgraph_target, fallback_monitor=False, session_id="native-lg")
    lg_result = langgraph_bound.invoke({"input": "graph"})
    assert lg_result.get("result") == "processed:graph", lg_result

    # CrewAI native hooks + monitor wrapper.
    crew_runtime = CrewRuntimeFixture()
    monitored_crew = client.bind_crewai(crew_runtime, session_id="native-crewai")
    crew_result = monitored_crew.kickoff()
    assert crew_result.get("status") == "ok", crew_result

    # LangChain fallback to monitor when no native bind surface exists.
    fallback_runner = client.bind_langchain(
        NotBindableFixture(),
        fallback_monitor=True,
        monitor_include_methods=["invoke"],
        session_id="native-fallback",
    )
    assert fallback_runner is not None

    client.flush()

    tags = _integration_tags(transport)
    phases = _phase_values(transport)

    for expected_tag in ("integration:langchain", "integration:langgraph", "integration:crewai"):
        assert expected_tag in tags, {"missing_tag": expected_tag, "tags": sorted(tags)}

    required_phases = {
        "chain_started",
        "chain_completed",
        "event_bus_signal",
        "step_callback",
    }
    missing_phases = sorted(required_phases.difference(phases))
    assert not missing_phases, {"missing_phases": missing_phases, "phases": sorted(phases)}

    debug_events = [
        item.get("event")
        for item in client.get_debug_records(limit=2000)
        if isinstance(item, dict) and isinstance(item.get("event"), str)
    ]
    assert "native_framework_bound" in debug_events, debug_events
    assert "native_framework_fallback_monitor" in debug_events, debug_events

    print(
        json.dumps(
            {
                "status": "ok",
                "events_sent": len(transport.events),
                "integration_tags": sorted(tags),
                "sample_phases": sorted(list(phases))[:12],
                "debug_events_total": len(debug_events),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
