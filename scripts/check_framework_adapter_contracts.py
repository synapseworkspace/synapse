#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import asdict
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


class DummyLangGraph:
    def invoke(self, payload: Any) -> dict[str, Any]:
        return {"framework": "langgraph", "payload": payload}

    async def ainvoke(self, payload: Any) -> dict[str, Any]:
        return {"framework": "langgraph", "payload": payload, "mode": "async"}

    def stream(self, payload: Any):
        yield {"framework": "langgraph", "chunk": 1, "payload": payload}
        yield {"framework": "langgraph", "chunk": 2, "payload": payload}


class DummyLangChain:
    def invoke(self, payload: Any) -> dict[str, Any]:
        return {"framework": "langchain", "payload": payload}

    def call(self, payload: Any) -> dict[str, Any]:
        return {"framework": "langchain", "payload": payload, "via": "call"}


class DummyCrewAI:
    def kickoff(self) -> dict[str, Any]:
        return {"framework": "crewai", "status": "ok"}


def _debug_integrations(client: Synapse) -> set[str]:
    out: set[str] = set()
    for record in client.get_debug_records(limit=1000):
        if record.get("event") != "attach_started":
            continue
        details = record.get("details")
        if isinstance(details, dict):
            integration = str(details.get("integration") or "").strip()
            if integration:
                out.add(integration)
    return out


def _event_tags(transport: MemoryTransport) -> set[str]:
    tags: set[str] = set()
    for event in transport.events:
        raw_tags = getattr(event, "tags", None)
        if isinstance(raw_tags, list):
            for tag in raw_tags:
                if isinstance(tag, str):
                    tags.add(tag)
    return tags


def main() -> int:
    transport = MemoryTransport()
    client = Synapse(SynapseConfig(api_url="http://localhost:8080", project_id="framework_smoke"), transport=transport)
    client.set_debug_mode(True, max_records=2000)

    langgraph = client.attach(DummyLangGraph())
    langgraph.invoke({"input": "gate policy"})
    list(langgraph.stream({"input": "gate policy"}))
    # Keep this check sync-only to avoid coupling the contract test to runtime-specific
    # event-loop/context token behavior of async wrappers.

    langchain = client.attach(DummyLangChain())
    langchain.invoke({"question": "what changed"})
    langchain.call({"question": "what changed"})

    crew = client.attach(DummyCrewAI())
    crew.kickoff()

    client.flush()

    integrations = _debug_integrations(client)
    expected_integrations = {"langgraph", "langchain", "crewai"}
    missing = sorted(expected_integrations.difference(integrations))
    if missing:
        raise SystemExit(
            json.dumps(
                {
                    "status": "failed",
                    "reason": "missing_attach_integration_detection",
                    "missing_integrations": missing,
                    "detected_integrations": sorted(integrations),
                },
                ensure_ascii=False,
            )
        )

    tags = _event_tags(transport)
    expected_tags = {f"integration:{name}" for name in expected_integrations}
    missing_tags = sorted(expected_tags.difference(tags))
    if missing_tags:
        raise SystemExit(
            json.dumps(
                {
                    "status": "failed",
                    "reason": "missing_integration_tags",
                    "missing_tags": missing_tags,
                    "seen_tags": sorted(tags),
                },
                ensure_ascii=False,
            )
        )

    print(
        json.dumps(
            {
                "status": "ok",
                "integrations": sorted(expected_integrations),
                "events_sent": len(transport.events),
                "claims_sent": len(transport.claims),
                "debug_records": len(client.get_debug_records(limit=2000)),
                "sample_event": asdict(transport.events[0]) if transport.events else None,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
