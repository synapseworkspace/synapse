from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from services.worker.app.wiki_engine import ClaimInput, GatekeeperConfig, GatekeeperLLMAssessment, WikiSynthesisEngine


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

    def test_backfill_filter_skips_event_like_payload_even_if_category_is_operations(self) -> None:
        payload = {
            "source_id": "memory_export_batch_2026_04_04_1",
            "content": '{"warehouse":"W2","order_id":"ord_8932","delivery_status":"processing","updated_at":"2026-04-04T10:05:00Z","customer_id":"c_44"}',
            "metadata": {"source": "ops_stream"},
        }
        claim_payload = self.engine._claim_payload_from_backfill_event(
            event_id=uuid.uuid4(),
            project_id="omega_demo",
            agent_id="agent_1",
            session_id="session_1",
            payload=payload,
            observed_at=datetime.now(timezone.utc),
        )
        self.assertIsNone(claim_payload)

    def test_backfill_filter_keeps_access_policy_from_event_transport_when_explicit(self) -> None:
        payload = {
            "source_id": "ops_manual_policy_card_1",
            "category": "access",
            "content": "Access policy: warehouse gate requires physical key card from 10:00 to 18:00.",
            "metadata": {"source_system": "event_stream"},
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
        self.assertEqual(claim_payload["category"], "access")

    def test_backfill_suppression_exposes_event_like_reason(self) -> None:
        evaluation = self.engine._evaluate_backfill_suppression(
            source_id="memory_export_batch_42",
            content='{"order_id":"ord_1","status":"processing","updated_at":"2026-04-04T00:00:00Z","customer_id":"c_1"}',
            category="operations",
            payload={},
            metadata={"source": "ops_stream"},
        )
        self.assertTrue(bool(evaluation.get("skip")))
        self.assertEqual(str(evaluation.get("reason")), "event_like_low_signal")

    def test_backfill_suppression_trusted_hint_bypasses_skip(self) -> None:
        evaluation = self.engine._evaluate_backfill_suppression(
            source_id="order_snapshot_42",
            content='{"order_id":"ord_1","status":"processing"}',
            category="general",
            payload={"knowledge_signal": True},
            metadata={},
        )
        self.assertFalse(bool(evaluation.get("skip")))
        self.assertTrue(bool(evaluation.get("trusted_hint")))

    def test_backfill_suppression_knowledge_lane_ignores_source_transport_block(self) -> None:
        event_lane = self.engine._evaluate_backfill_suppression(
            source_id="legacy_memory_42",
            content="Warehouse entry note: call security desk before opening gate override.",
            category="operations",
            payload={"backfill": {"ingest_lane": "event"}},
            metadata={"source_system": "event_stream", "source_type": "external_event"},
        )
        knowledge_lane = self.engine._evaluate_backfill_suppression(
            source_id="legacy_memory_42",
            content="Warehouse entry note: call security desk before opening gate override.",
            category="operations",
            payload={"backfill": {"ingest_lane": "knowledge"}},
            metadata={"source_system": "event_stream", "source_type": "external_event"},
        )
        self.assertTrue(bool(event_lane.get("skip")))
        self.assertEqual(str(event_lane.get("reason")), "event_transport_low_signal")
        self.assertFalse(bool(knowledge_lane.get("skip")))
        self.assertEqual(str(knowledge_lane.get("ingest_lane")), "knowledge")

    def test_backfill_suppression_enforce_mode_can_override_keep(self) -> None:
        class _Classifier:
            def classify(self, *, claim, features, config):  # type: ignore[no-untyped-def]
                return GatekeeperLLMAssessment(
                    status="ok",
                    provider="openai",
                    model=config.llm_model,
                    suggested_tier="insight_candidate",
                    score=0.82,
                    confidence=0.96,
                    rationale="knowledge-like operational note",
                )

        engine = WikiSynthesisEngine(llm_classifier=_Classifier(), gatekeeper_llm_assist_enabled=True)
        evaluation = engine._evaluate_backfill_suppression(
            source_id="legacy_batch_42",
            content='{"order_id":"ord_1","status":"processing","updated_at":"2026-04-04T00:00:00Z"}',
            category="general",
            payload={},
            metadata={},
            routing_policy={
                "backfill_llm_classifier_mode": "enforce",
                "backfill_llm_classifier_min_confidence": 0.8,
                "backfill_llm_classifier_ambiguous_only": False,
            },
        )
        self.assertFalse(bool(evaluation.get("skip")))
        self.assertEqual(str(evaluation.get("reason")), "llm_override_keep_knowledge")
        self.assertTrue(bool(evaluation.get("llm_applied")))

    def test_backfill_suppression_assist_mode_does_not_override(self) -> None:
        class _Classifier:
            def classify(self, *, claim, features, config):  # type: ignore[no-untyped-def]
                return GatekeeperLLMAssessment(
                    status="ok",
                    provider="openai",
                    model=config.llm_model,
                    suggested_tier="insight_candidate",
                    score=0.82,
                    confidence=0.96,
                    rationale="knowledge-like operational note",
                )

        engine = WikiSynthesisEngine(llm_classifier=_Classifier(), gatekeeper_llm_assist_enabled=True)
        evaluation = engine._evaluate_backfill_suppression(
            source_id="legacy_batch_42",
            content='{"order_id":"ord_1","status":"processing","updated_at":"2026-04-04T00:00:00Z"}',
            category="general",
            payload={},
            metadata={},
            routing_policy={
                "backfill_llm_classifier_mode": "assist",
                "backfill_llm_classifier_min_confidence": 0.8,
                "backfill_llm_classifier_ambiguous_only": False,
            },
        )
        self.assertTrue(bool(evaluation.get("skip")))
        self.assertEqual(str(evaluation.get("reason")), "event_like_low_signal")
        self.assertFalse(bool(evaluation.get("llm_applied")))
        self.assertEqual(str(evaluation.get("llm_reason_code")), "assist_only")

    def test_backfill_suppression_enforce_mode_can_override_skip(self) -> None:
        class _Classifier:
            def classify(self, *, claim, features, config):  # type: ignore[no-untyped-def]
                return GatekeeperLLMAssessment(
                    status="ok",
                    provider="openai",
                    model=config.llm_model,
                    suggested_tier="operational_memory",
                    score=0.12,
                    confidence=0.94,
                    rationale="event-like update",
                )

        engine = WikiSynthesisEngine(llm_classifier=_Classifier(), gatekeeper_llm_assist_enabled=True)
        evaluation = engine._evaluate_backfill_suppression(
            source_id="ops_note_77",
            content="Access policy update for Warehouse #2: physical key card required after 10:00.",
            category="access",
            payload={},
            metadata={},
            routing_policy={
                "backfill_llm_classifier_mode": "enforce",
                "backfill_llm_classifier_min_confidence": 0.8,
                "backfill_llm_classifier_ambiguous_only": False,
            },
        )
        self.assertTrue(bool(evaluation.get("skip")))
        self.assertEqual(str(evaluation.get("reason")), "llm_override_skip_event")
        self.assertTrue(bool(evaluation.get("llm_applied")))

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
            metadata={},
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
            metadata={},
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
            metadata={},
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

    def test_gatekeeper_repeated_short_operational_signal_moves_out_of_l1(self) -> None:
        claim = ClaimInput(
            id=uuid.uuid4(),
            project_id="omega_demo",
            entity_key="driver_22",
            category="operations",
            claim_text="Sent docs",
            evidence=[
                {
                    "source_type": "tool_result",
                    "source_id": "evt_22",
                    "tool_name": "runtime_memory",
                    "source_system": "runtime_memory",
                }
            ],
            metadata={},
        )
        decision = self.engine._gatekeeper_decide_from_inputs(
            claim=claim,
            config=_base_gatekeeper_config(),
            repeated_count=1,
            historical_source_count=1,
            incoming_source_ids=["evt_22"],
            has_recent_open_conflict=False,
        )
        self.assertEqual(decision.tier, "insight_candidate")
        self.assertFalse(bool(decision.features.get("insufficient_support")))

    def test_backfill_infers_process_category_from_runbook_text(self) -> None:
        payload = {
            "source_id": "support_runbook_update_1",
            "content": "Support workflow: when chargeback is detected, then escalate to Tier-2 and verify refund SLA result: customer informed.",
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
        self.assertEqual(claim_payload["category"], "process")
        evidence = claim_payload.get("evidence")
        self.assertIsInstance(evidence, list)
        self.assertGreaterEqual(len(evidence), 1)
        first = evidence[0]
        self.assertIsInstance(first, dict)
        process_triplet = first.get("process_triplet")
        self.assertIsInstance(process_triplet, dict)
        self.assertTrue(str(process_triplet.get("action") or "").strip())

    def test_backfill_claim_evidence_uses_knowledge_lane_markers(self) -> None:
        payload = {
            "source_id": "ops_playbook_knowledge_1",
            "content": "Dispatch policy: escalate delayed critical shipment to on-call within 15 minutes.",
            "metadata": {"source_system": "legacy_kb"},
            "backfill": {"ingest_lane": "knowledge", "source_system": "legacy_kb"},
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
        first = claim_payload["evidence"][0]
        self.assertEqual(first.get("ingest_lane"), "knowledge")
        self.assertEqual(first.get("source_type"), "knowledge_ingest")
        self.assertEqual(first.get("tool_name"), "knowledge_backfill")

    def test_gatekeeper_knowledge_ingest_does_not_hard_block_by_source_type(self) -> None:
        claim = ClaimInput(
            id=uuid.uuid4(),
            project_id="omega_demo",
            entity_key="warehouse_gate_policy",
            category="access",
            claim_text="Warehouse gate policy requires physical key-card after 10:00.",
            evidence=[
                {
                    "source_type": "external_event",
                    "source_id": "legacy_policy_1",
                    "tool_name": "knowledge_backfill",
                    "source_system": "event_stream",
                    "ingest_lane": "knowledge",
                }
            ],
            metadata={},
        )
        decision = self.engine._gatekeeper_decide_from_inputs(
            claim=claim,
            config=_base_gatekeeper_config(),
            repeated_count=0,
            historical_source_count=0,
            incoming_source_ids=["legacy_policy_1"],
            has_recent_open_conflict=False,
        )
        self.assertFalse(bool(decision.features.get("blocked_by_source_type")))
        self.assertFalse(bool(decision.features.get("blocked_by_source_system")))

    def test_gatekeeper_marks_process_assertion_class(self) -> None:
        claim = ClaimInput(
            id=uuid.uuid4(),
            project_id="omega_demo",
            entity_key="support_chargeback_process",
            category="process",
            claim_text="When chargeback is detected, follow runbook steps and escalate to Tier-2 within 15 minutes.",
            evidence=[
                {
                    "source_type": "tool_result",
                    "source_id": "ops_runbook_1",
                    "tool_name": "runtime_memory",
                    "source_system": "ops_manual",
                }
            ],
            metadata={},
        )
        decision = self.engine._gatekeeper_decide_from_inputs(
            claim=claim,
            config=_base_gatekeeper_config(),
            repeated_count=0,
            historical_source_count=0,
            incoming_source_ids=["ops_runbook_1"],
            has_recent_open_conflict=False,
        )
        self.assertIn(decision.tier, {"insight_candidate", "golden_candidate"})
        self.assertEqual(str(decision.features.get("assertion_class")), "process")

    def test_process_section_resolution_prefers_steps(self) -> None:
        section_key, section_heading, created_new = self.engine._resolve_section(
            page_type="process",
            category="process",
            claim_text="Runbook steps: verify ticket context, then escalate to Tier-2.",
            existing_sections=[],
        )
        self.assertTrue(created_new)
        self.assertEqual(section_key, "steps")
        self.assertEqual(section_heading, "Steps")

    def test_operator_decision_context_extracts_ticket_and_outcome(self) -> None:
        claim = ClaimInput(
            id=uuid.uuid4(),
            project_id="omega_demo",
            entity_key="support_ops",
            category="process",
            claim_text="When payment fails, then escalate to Tier-2. Ticket SUP-442 resolved.",
            evidence=[
                {
                    "source_type": "tool_result",
                    "source_id": "ops_note_77",
                    "tool_name": "chat_runtime",
                    "source_system": "runtime_memory",
                }
            ],
            metadata={"outcome": "resolved"},
        )
        context = self.engine._extract_operator_decision_context(claim)
        self.assertIn("process_triplet", context)
        self.assertIn("ticket_ids", context)
        self.assertIn("SUP-442", context["ticket_ids"])
        self.assertEqual(context.get("outcome"), "resolved")

    def test_routing_policy_normalizes_auto_publish_risk_keywords(self) -> None:
        policy = self.engine._normalize_gatekeeper_routing_policy(
            {
                "auto_publish_risk_keywords_high": ["Legal", "PAYMENT", "", "payment"],
                "auto_publish_risk_keywords_medium": ["sla", "Finance", " "],
                "auto_publish_force_human_required_levels": ["HIGH", "medium", ""],
            }
        )
        self.assertEqual(policy["auto_publish_risk_keywords_high"][:2], ["legal", "payment"])
        self.assertEqual(policy["auto_publish_risk_keywords_medium"][:2], ["sla", "finance"])
        self.assertEqual(policy["auto_publish_force_human_required_levels"][:2], ["high", "medium"])


if __name__ == "__main__":
    unittest.main()
