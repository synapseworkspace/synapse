from __future__ import annotations

import unittest

try:
    from services.api.app.main import _extract_ticket_outcome_signal
except Exception:  # pragma: no cover - optional API deps in minimal envs
    _extract_ticket_outcome_signal = None


@unittest.skipIf(_extract_ticket_outcome_signal is None, "api helpers unavailable")
class TicketOutcomeSignalTests(unittest.TestCase):
    def test_positive_ticket_outcome_adds_bonus(self) -> None:
        signal = _extract_ticket_outcome_signal(
            {
                "linked_ticket_ids": ["INC-1", "INC-2", "INC-1"],
                "resolution_outcome": "resolved",
            }
        )
        self.assertEqual(signal["ticket_count"], 2)
        self.assertTrue(bool(signal["positive_outcome"]))
        self.assertFalse(bool(signal["negative_outcome"]))
        self.assertAlmostEqual(float(signal["score_bonus"]), 0.13, places=4)

    def test_negative_outcome_penalizes_score(self) -> None:
        signal = _extract_ticket_outcome_signal(
            {
                "operator_decision": {"ticket_ids": ["OPS-5"], "outcome": "regressed"},
            }
        )
        self.assertEqual(signal["ticket_count"], 1)
        self.assertFalse(bool(signal["positive_outcome"]))
        self.assertTrue(bool(signal["negative_outcome"]))
        self.assertAlmostEqual(float(signal["score_bonus"]), 0.0, places=4)


if __name__ == "__main__":
    unittest.main()
