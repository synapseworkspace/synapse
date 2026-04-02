from __future__ import annotations

import json
from typing import Any

from synapse_sdk import MemoryBackfillRecord, Synapse, SynapseConfig

from _memory_transport import MemoryTransport


class CrewAIStyleRuntime:
    """Small CrewAI-like runtime fixture with kickoff/run surface."""

    def kickoff(self, payload: dict[str, Any]) -> dict[str, Any]:
        route = str(payload.get("route") or "unknown")
        return {
            "summary": (
                f"Crew found repeated delay at {route}; policy update required: "
                "add 20-minute buffer for evening shifts."
            ),
            "entity_key": route,
            "category": "dispatch_playbook",
            "confidence": 0.9,
        }

    def run(self, task: str) -> str:
        return f"Crew run completed: {task}"


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
            project_id="cookbook_crewai",
        ),
        transport=transport,
    )
    synapse.set_debug_mode(True, max_records=200)

    batch_id = synapse.backfill_memory(
        [
            MemoryBackfillRecord(
                source_id="legacy-ca-1",
                content="Evening route at warehouse_2 often takes +20 minutes due to gate queue.",
                entity_key="warehouse_2",
                category="dispatch_playbook",
            )
        ],
        source_system="crewai_history",
        chunk_size=1,
    )

    crew = CrewAIStyleRuntime()
    monitored = synapse.attach(
        crew,
        agent_id="crewai_dispatch_team",
        session_id="crewai-session-1",
    )

    kickoff_result = monitored.kickoff({"route": "warehouse_2"})
    run_result = monitored.run("Update evening dispatch checklist")

    @synapse.collect_insight(
        category="dispatch_playbook",
        integration="crewai",
        source_type="tool_output",
        min_confidence=0.6,
    )
    def synthesize_rule(summary: str) -> str:
        return summary

    synthesized_text = synthesize_rule(str(kickoff_result.get("summary") or ""))

    synapse.flush()

    return {
        "transport": transport.summary(),
        "batch_id": batch_id,
        "resolved_integration": _extract_integration(synapse),
        "kickoff_summary": str(kickoff_result.get("summary") or ""),
        "run_result": run_result,
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
