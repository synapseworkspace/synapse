from __future__ import annotations

import json
from typing import Any, Iterable

from synapse_sdk import MemoryBackfillRecord, Synapse, SynapseConfig

from _memory_transport import MemoryTransport


class LangChainStyleRunnable:
    """Small runnable fixture with LangChain-like invoke/call/stream/batch surface."""

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        customer_id = str(payload.get("customer_id") or "unknown")
        channel = str(payload.get("preferred_channel") or "slack")
        return {
            "message": f"Customer {customer_id} prefers {channel} for urgent updates.",
            "entity_key": customer_id,
            "category": "customer_preference",
            "confidence": 0.86,
        }

    def call(self, payload: dict[str, Any]) -> str:
        customer_id = str(payload.get("customer_id") or "unknown")
        return f"Escalation policy for {customer_id}: use Slack first, then email fallback."

    def stream(self, payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
        customer_id = str(payload.get("customer_id") or "unknown")
        yield {"stage": "plan", "text": f"Loaded preference profile for {customer_id}."}
        yield {"stage": "respond", "text": f"Prepared channel plan for {customer_id}."}

    def batch(self, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.invoke(payload) for payload in payloads]


def _extract_integration(synapse: Synapse) -> str:
    for record in synapse.get_debug_records(limit=80):
        if not isinstance(record, dict):
            continue
        if str(record.get("event") or "") != "attach_started":
            continue
        details = record.get("details")
        if isinstance(details, dict):
            integration = str(details.get("integration") or "")
            if integration:
                return integration
    return "unknown"


def run_demo() -> dict[str, Any]:
    transport = MemoryTransport()
    synapse = Synapse(
        SynapseConfig(
            api_url="http://localhost:8080",
            project_id="cookbook_langchain",
        ),
        transport=transport,
    )
    synapse.set_debug_mode(True, max_records=200)

    batch_id = synapse.backfill_memory(
        [
            MemoryBackfillRecord(
                source_id="legacy-lc-1",
                content="Customer 77 asked to receive urgent updates in Slack.",
                entity_key="customer_77",
                category="customer_preference",
            )
        ],
        source_system="langchain_history",
        chunk_size=1,
    )

    runnable = LangChainStyleRunnable()
    monitored = synapse.attach(
        runnable,
        agent_id="langchain_support_agent",
        session_id="langchain-session-1",
    )

    invoke_result = monitored.invoke({"customer_id": "customer_77", "preferred_channel": "slack"})
    call_result = monitored.call({"customer_id": "customer_77"})
    stream_events = list(monitored.stream({"customer_id": "customer_77"}))
    batch_results = monitored.batch(
        [
            {"customer_id": "customer_77", "preferred_channel": "slack"},
            {"customer_id": "customer_88", "preferred_channel": "email"},
        ]
    )

    @synapse.collect_insight(
        category="support_playbook",
        integration="langchain",
        source_type="tool_output",
        min_confidence=0.6,
    )
    def summarize_policy(text: str) -> str:
        return text

    synthesized_text = summarize_policy(call_result)

    synapse.flush()

    return {
        "transport": transport.summary(),
        "batch_id": batch_id,
        "resolved_integration": _extract_integration(synapse),
        "invoke_result": str(invoke_result.get("message") or ""),
        "call_result": call_result,
        "stream_steps": len(stream_events),
        "batch_result_count": len(batch_results),
        "synthesized_text": synthesized_text,
        "queued_claims": [getattr(item, "claim_text", "") for item in transport.claims],
        "debug_events_tail": [
            item.get("event")
            for item in synapse.get_debug_records(limit=12)
            if isinstance(item, dict) and "event" in item
        ],
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
