from __future__ import annotations

import unittest

from services.shared.retrieval import (
    RetrievalContextPolicyConfig,
    apply_intent_reranking,
    build_retrieval_explain_fields,
    infer_retrieval_intent,
)


class RetrievalIntentTests(unittest.TestCase):
    def test_infer_process_intent_from_query(self) -> None:
        profile = infer_retrieval_intent(
            query="How should support triage chargeback tickets and escalate to Tier-2?",
        )
        self.assertEqual(profile["intent"], "process")
        self.assertIn(profile["source"], {"inferred", "explicit"})

    def test_explicit_intent_overrides_auto_inference(self) -> None:
        profile = infer_retrieval_intent(
            query="How should support triage chargeback tickets and escalate to Tier-2?",
            explicit_intent="policy",
        )
        self.assertEqual(profile["intent"], "policy")
        self.assertEqual(profile["source"], "explicit")

    def test_process_intent_reranks_results_and_selects_snippets(self) -> None:
        results = [
            {
                "statement_id": "st-policy",
                "statement_text": "Gate access policy requires approval from security manager.",
                "section_key": "policy",
                "score": 0.95,
                "retrieval_confidence": 0.72,
                "context_policy": {"eligible": True},
                "page": {
                    "title": "Security Policy",
                    "slug": "policy/security-access",
                    "entity_key": "security_policy",
                    "page_type": "policy",
                },
                "category": "policy",
                "retrieval_reason": "lexical match",
            },
            {
                "statement_id": "st-process",
                "statement_text": "When chargeback is detected, verify ticket context and escalate to Tier-2 within 15 minutes.",
                "section_key": "steps",
                "score": 0.81,
                "retrieval_confidence": 0.86,
                "context_policy": {"eligible": True},
                "page": {
                    "title": "Chargeback Runbook",
                    "slug": "process/chargeback-runbook",
                    "entity_key": "support_chargeback",
                    "page_type": "process",
                },
                "category": "process",
                "retrieval_reason": "lexical match",
            },
        ]

        reranked, payload = apply_intent_reranking(
            query="Chargeback triage workflow: what steps should we run?",
            explicit_intent="process",
            results=results,
            max_context_snippets=2,
        )

        self.assertEqual(reranked[0]["statement_id"], "st-process")
        self.assertEqual(reranked[0]["intent_alignment"]["intent"], "process")
        self.assertGreater(float(reranked[0]["intent_alignment"]["score"]), 0.0)

        snippets = payload["context_snippets"]
        self.assertGreaterEqual(len(snippets), 1)
        self.assertEqual(snippets[0]["statement_id"], "st-process")
        self.assertEqual(payload["explainability"]["intent"], "process")

    def test_retrieval_explain_includes_provenance_links(self) -> None:
        result = {
            "statement_id": "st-1",
            "statement_text": "When chargeback is detected, escalate to Tier-2.",
            "section_key": "steps",
            "score": 1.02,
            "graph_boost": 0.11,
            "graph_hops": 1,
            "page": {
                "title": "Chargeback Runbook",
                "slug": "process/chargeback-runbook",
                "entity_key": "support_chargeback",
                "page_type": "process",
            },
            "category": "process",
            "claim_id": "claim-123",
            "claim_observed_at": "2026-04-04T08:30:00+00:00",
            "claim_metadata": {
                "linked_ticket_ids": ["SUP-442"],
                "resolution_outcome": "resolved",
            },
            "claim_evidence": [
                {"source_id": "dialog-88", "source_type": "tool_result"},
                {"source_id": "ticket-SUP-442", "source_type": "ticket"},
            ],
        }
        explained = build_retrieval_explain_fields(
            query="chargeback escalation steps",
            related_entity_key="support_chargeback",
            result=result,
            context_policy=RetrievalContextPolicyConfig(mode="advisory"),
        )
        self.assertIn("provenance", explained)
        provenance = explained["provenance"]
        self.assertEqual(provenance["claim_id"], "claim-123")
        self.assertIn("SUP-442", provenance["ticket_ids"])
        self.assertIn("dialog-88", provenance["source_ids"])
        self.assertEqual(provenance["outcome"], "resolved")


if __name__ == "__main__":
    unittest.main()
