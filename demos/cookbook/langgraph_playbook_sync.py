from __future__ import annotations

import json
from typing import Any, Iterable

from synapse_sdk import MCPContextHelper, MemoryBackfillRecord, Synapse, SynapseConfig

from _memory_transport import MemoryTransport


class LangGraphStyleFlow:
    """Small LangGraph-like runtime fixture with invoke/stream surface."""

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        destination = str(payload.get("destination") or "unknown")
        customer = str(payload.get("customer_id") or "unknown")
        return {
            "result": (
                f"Dispatch note for {customer}: route to {destination} requires gate card after 10:00; "
                "notify driver before arrival."
            ),
            "entity_key": destination,
            "category": "access_policy",
            "confidence": 0.9,
        }

    def stream(self, payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
        destination = str(payload.get("destination") or "unknown")
        yield {"stage": "plan", "text": f"Collected route context for {destination}."}
        yield {"stage": "act", "text": f"Generated dispatch reminder for {destination} gate policy."}
        yield {"stage": "finalize", "text": f"Prepared final instruction package for {destination}."}


def _fake_mcp_tool_call(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "search_knowledge":
        query = str(args.get("query") or "")
        return {
            "results": [
                {
                    "statement_text": f"Approved policy: {query} -> gate card required after 10:00",
                    "page": {"slug": "operations/bc-omega", "entity_key": "bc_omega"},
                }
            ],
            "revision": "cookbook-langgraph-r1",
        }
    if tool_name == "get_entity_facts":
        return {
            "facts": [
                {
                    "statement_text": "BC Omega access policy: card required after 10:00",
                    "category": "access_policy",
                }
            ]
        }
    if tool_name == "get_recent_changes":
        return {
            "changes": [
                {
                    "action": "approve",
                    "created_at": "2026-04-03T10:00:00Z",
                    "page": {"slug": "operations/bc-omega"},
                }
            ]
        }
    return {}


def run_demo() -> dict[str, Any]:
    transport = MemoryTransport()
    synapse = Synapse(
        SynapseConfig(
            api_url="http://localhost:8080",
            project_id="cookbook_langgraph",
        ),
        transport=transport,
    )
    synapse.set_debug_mode(True, max_records=200)

    # Day-0 bootstrap before first graph execution.
    batch_id = synapse.backfill_memory(
        [
            MemoryBackfillRecord(
                source_id="legacy-l1",
                content="BC Omega switched to card-only gate access after 10:00",
                entity_key="bc_omega",
                category="access_policy",
            ),
            MemoryBackfillRecord(
                source_id="legacy-l2",
                content="Dispatch must remind drivers to prepare access cards before checkpoint",
                entity_key="bc_omega",
                category="dispatch_playbook",
            ),
        ],
        source_system="langgraph_history",
        chunk_size=1,
    )

    flow = LangGraphStyleFlow()
    monitored_flow = synapse.attach(
        flow,
        integration="langgraph",
        include_methods=["invoke", "stream"],
        agent_id="langgraph_dispatcher",
        session_id="langgraph-session-1",
    )

    invoke_result = monitored_flow.invoke({"destination": "bc_omega", "customer_id": "cust_42"})
    streamed_steps = list(monitored_flow.stream({"destination": "bc_omega"}))

    @synapse.collect_insight(
        category="dispatch_playbook",
        integration="langgraph",
        source_type="tool_output",
        min_confidence=0.6,
    )
    def synthesize_playbook(route_summary: str) -> str:
        return route_summary

    synthesized_text = synthesize_playbook(str(invoke_result.get("result") or ""))

    # Execute phase preview via MCP helper (offline stub caller).
    mcp = MCPContextHelper(
        project_id="cookbook_langgraph",
        call_tool=_fake_mcp_tool_call,
    )
    context_bundle = mcp.build_context(
        query="bc_omega gate policy",
        entity_key="bc_omega",
        include_recent_changes=True,
    )

    synapse.flush()

    return {
        "transport": transport.summary(),
        "batch_id": batch_id,
        "invoke_result": invoke_result,
        "stream_steps": len(streamed_steps),
        "synthesized_text": synthesized_text,
        "context_preview": {
            "search_results": len(context_bundle.get("search_results", [])),
            "entity_facts": len(context_bundle.get("entity_facts", [])),
            "recent_changes": len(context_bundle.get("recent_changes", [])),
        },
        "debug_events_tail": [
            item.get("event")
            for item in synapse.get_debug_records(limit=12)
            if isinstance(item, dict) and "event" in item
        ],
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
