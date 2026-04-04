from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from services.worker.app.wiki_engine import ClaimInput, GatekeeperConfig, WikiSynthesisEngine


def _base_gatekeeper_config() -> GatekeeperConfig:
    return GatekeeperConfig(
        min_sources_for_golden=3,
        conflict_free_days=7,
        min_score_for_golden=0.72,
        operational_short_text_len=32,
        operational_short_token_len=5,
    )


class WikiEngineRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = WikiSynthesisEngine()

    def test_backfill_filter_skips_order_snapshot_payload(self) -> None:
        event_id = uuid.uuid4()
        payload = {
            "source_id": "order_snapshot_2026_04_04_001",
            "content": '{"order_id":"12345","status":"shipped","updated_at":"2026-04-04T00:00:00Z","invoice_id":"inv_1"}',
            "metadata": {"source": "order_stream"},
        }
        claim_payload = self.engine._claim_payload_from_backfill_event(
            event_id=event_id,
            project_id="omega_demo",
            agent_id="agent_1",
            session_id="session_1",
            payload=payload,
            observed_at=datetime.now(timezone.utc),
        )
        self.assertIsNone(claim_payload)

    def test_backfill_filter_keeps_policy_note(self) -> None:
        payload = {
            "source_id": "ops_note_gate_policy",
            "content": "Warehouse #2 gate is closed until Monday. Access only with physical key card.",
            "metadata": {"source": "ops_manual"},
        }
        claim_payload = self.engine._claim_payload_from_backfill_event(
            event_id=uuid.uuid4(),
            project_id="omega_demo",
            agent_id="agent_1",
            session_id="session_1",
            payload=payload,
            observed_at=datetime.now(timezone.utc),
        )
        self.assertIsNotNone(claim_payload)
        assert claim_payload is not None
        self.assertEqual(claim_payload["project_id"], "omega_demo")
        self.assertIn(claim_payload["category"], {"access", "operations"})

    def test_gatekeeper_demotes_order_snapshot_claim(self) -> None:
        claim = ClaimInput(
            id=uuid.uuid4(),
            project_id="omega_demo",
            entity_key="order_snapshot_12345",
            category="general",
            claim_text='{"order_id":"12345","status":"shipped","updated_at":"2026-04-04T00:00:00Z"}',
            evidence=[
                {
                    "source_type": "external_event",
                    "source_id": "order_snapshot_12345",
                    "tool_name": "memory_backfill",
                    "source_system": "order_stream",
                }
            ],
        )
        decision = self.engine._gatekeeper_decide_from_inputs(
            claim=claim,
            config=_base_gatekeeper_config(),
            repeated_count=0,
            historical_source_count=0,
            incoming_source_ids=["order_snapshot_12345"],
            has_recent_open_conflict=False,
        )
        self.assertEqual(decision.tier, "operational_memory")
        self.assertTrue(bool(decision.features.get("routing_hard_block")))
        self.assertEqual(str(decision.features.get("assertion_class")), "event")
        self.assertTrue(
            bool(decision.features.get("blocked_by_source_id"))
            or bool(decision.features.get("has_event_stream_shape"))
        )

    def test_gatekeeper_keeps_customer_preference_for_review(self) -> None:
        claim = ClaimInput(
            id=uuid.uuid4(),
            project_id="omega_demo",
            entity_key="customer_42",
            category="customer",
            claim_text="Customer prefers Slack over email for urgent updates.",
            evidence=[
                {
                    "source_type": "tool_result",
                    "source_id": "dialog_42",
                    "tool_name": "chat_runtime",
                    "source_system": "runtime_memory",
                }
            ],
        )
        decision = self.engine._gatekeeper_decide_from_inputs(
            claim=claim,
            config=_base_gatekeeper_config(),
            repeated_count=0,
            historical_source_count=0,
            incoming_source_ids=["dialog_42"],
            has_recent_open_conflict=False,
        )
        self.assertEqual(decision.tier, "insight_candidate")
        self.assertTrue(bool(decision.features.get("has_durable_signal")))
        self.assertEqual(str(decision.features.get("assertion_class")), "preference")

    def test_gatekeeper_marks_policy_assertion_class(self) -> None:
        claim = ClaimInput(
            id=uuid.uuid4(),
            project_id="omega_demo",
            entity_key="warehouse_2",
            category="access",
            claim_text="Warehouse #2 entry policy: only physical key-card after 10:00.",
            evidence=[
                {
                    "source_type": "tool_result",
                    "source_id": "ops_note_1",
                    "tool_name": "runtime_memory",
                    "source_system": "ops_manual",
                }
            ],
        )
        decision = self.engine._gatekeeper_decide_from_inputs(
            claim=claim,
            config=_base_gatekeeper_config(),
            repeated_count=0,
            historical_source_count=0,
            incoming_source_ids=["ops_note_1"],
            has_recent_open_conflict=False,
        )
        self.assertIn(decision.tier, {"insight_candidate", "golden_candidate"})
        self.assertEqual(str(decision.features.get("assertion_class")), "policy")


if __name__ == "__main__":
    unittest.main()
