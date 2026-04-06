from __future__ import annotations

import unittest

try:
    from services.api.app.main import _classify_process_simulation_risk, _extract_assertion_class
except Exception:  # pragma: no cover - optional dependency path in minimal test envs
    _classify_process_simulation_risk = None
    _extract_assertion_class = None


@unittest.skipIf(
    _classify_process_simulation_risk is None or _extract_assertion_class is None,
    "api simulation helpers unavailable (missing optional api deps)",
)
class ProcessSimulationRiskTests(unittest.TestCase):
    def test_extract_assertion_class_process(self) -> None:
        self.assertEqual(
            _extract_assertion_class({}, category="process", page_type="process"),
            "process",
        )

    def test_high_risk_process_change_blocks_auto_publish(self) -> None:
        risk = _classify_process_simulation_risk(
            proposed_markdown="Update payment chargeback runbook and legal compliance requirements.",
            changed_terms=["payment", "chargeback", "legal", "compliance"],
            removed_terms=["old-step"],
            impacted_pages_total=12,
            pending_process_drafts=9,
            open_process_conflicts=2,
            routing_policy={
                "auto_publish_risk_keywords_high": ["payment", "chargeback", "legal", "compliance"],
                "auto_publish_risk_keywords_medium": ["sla"],
            },
        )
        self.assertEqual(risk["level"], "high")
        self.assertTrue(bool(risk["should_block_publish"]))
        self.assertEqual(risk["suggested_publish_mode"], "human_required")


if __name__ == "__main__":
    unittest.main()
