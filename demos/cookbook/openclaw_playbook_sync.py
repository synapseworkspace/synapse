from __future__ import annotations

import json
from typing import Any

from synapse_sdk import MemoryBackfillRecord, Synapse, SynapseConfig

from _memory_transport import MemoryTransport


class Runtime:
    def __init__(self) -> None:
        self.handlers: dict[str, Any] = {}
        self.tools: dict[str, Any] = {}

    def on(self, event_name: str, handler: Any) -> None:
        self.handlers[event_name] = handler

    def register_tool(self, name: str, handler: Any, description: str | None = None) -> None:
        self.tools[name] = {"handler": handler, "description": description}

    def emit(self, event_name: str, payload: dict[str, Any]) -> None:
        handler = self.handlers.get(event_name)
        if handler is None:
            raise RuntimeError(f"hook {event_name!r} is not registered")
        handler(payload)


def run_demo() -> dict[str, Any]:
    transport = MemoryTransport()
    synapse = Synapse(
        SynapseConfig(
            api_url="http://localhost:8080",
            project_id="cookbook_openclaw",
        ),
        transport=transport,
    )
    runtime = Runtime()

    synapse.attach(
        runtime,
        integration="openclaw",
        openclaw_search_knowledge=lambda query, limit, filters: [
            {
                "entity_key": "bc_omega",
                "title": "BC Omega Access",
                "fact": "Gate access is card-only after 10:00",
                "query": query,
                "limit": limit,
                "filters": filters,
            }
        ],
    )

    runtime.emit("tool:result", {"sessionKey": "s-1", "result": "Driver confirms card-only access at BC Omega"})
    runtime.emit("agent:completed", {"sessionKey": "s-1", "summary": "Reminder about access cards added to dispatch flow"})

    search_result = runtime.tools["synapse_search_wiki"]["handler"]("omega gate policy", limit=3)
    proposal_result = runtime.tools["synapse_propose_to_wiki"]["handler"](
        entity_key="bc_omega",
        category="access_policy",
        claim_text="Dispatch must remind drivers about access cards for BC Omega after 10:00.",
        source_id="openclaw_session_s-1",
        confidence=0.93,
    )

    batch_id = synapse.backfill_memory(
        [
            MemoryBackfillRecord(source_id="legacy-1", content="BC Omega switched to card-only after 10:00"),
            MemoryBackfillRecord(source_id="legacy-2", content="Drivers without cards are blocked at checkpoint"),
        ],
        source_system="openclaw_history",
        chunk_size=1,
    )

    synapse.flush()

    return {
        "transport": transport.summary(),
        "tool_names": sorted(runtime.tools.keys()),
        "search_result_count": len(search_result),
        "proposal_status": proposal_result["status"],
        "batch_id": batch_id,
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
