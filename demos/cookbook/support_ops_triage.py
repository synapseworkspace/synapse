from __future__ import annotations

import json
from typing import Any

from synapse_sdk import ExtractedInsight, InsightContext, Synapse, SynapseConfig, SynthesisContext

from _memory_transport import MemoryTransport


class EscalationExtractor:
    name = "escalation_extractor"

    def extract(self, context: InsightContext) -> list[ExtractedInsight]:
        text = str(context.result or "")
        lowered = text.lower()
        if "refund" in lowered and "priority" in lowered:
            return [
                ExtractedInsight(
                    claim_text=text,
                    category="support_policy",
                    entity_key=context.entity_hint,
                    confidence=0.88,
                    metadata={"signal": "refund+priority"},
                )
            ]
        return []


class ConfidenceFloorSynthesizer:
    name = "confidence_floor_85"
    contract_version = "v1"

    def synthesize(self, context: SynthesisContext) -> list[ExtractedInsight]:
        out: list[ExtractedInsight] = []
        for item in context.extracted_insights:
            confidence = item.confidence if item.confidence is not None else 0.0
            out.append(
                ExtractedInsight(
                    claim_text=item.claim_text,
                    category=item.category,
                    entity_key=item.entity_key,
                    confidence=max(confidence, 0.85),
                    metadata=dict(item.metadata),
                    valid_from=item.valid_from,
                    valid_to=item.valid_to,
                )
            )
        return out


def run_demo() -> dict[str, Any]:
    transport = MemoryTransport()
    synapse = Synapse(
        SynapseConfig(api_url="http://localhost:8080", project_id="cookbook_support_ops"),
        transport=transport,
    )
    synapse.register_extractor(EscalationExtractor())
    synapse.register_synthesizer(ConfidenceFloorSynthesizer())

    def process_ticket(customer_id: str, ticket_text: str) -> str:
        if "delay" in ticket_text.lower() and "refund" in ticket_text.lower():
            return f"Priority refund workflow for {customer_id}: escalate to support lead."
        return f"Standard response for {customer_id}."

    wrapped = synapse.collect_insight(
        category="support_policy",
        integration="support_ops",
        extractor_names=["escalation_extractor"],
        synthesizer_names=["confidence_floor_85"],
        min_confidence=0.8,
    )(process_ticket)

    result = wrapped("customer_77", "Delivery delay again, request refund, priority case")
    synapse.flush()

    return {
        "result": result,
        "transport": transport.summary(),
        "claim_ids": [claim.id for claim in transport.claims],
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
