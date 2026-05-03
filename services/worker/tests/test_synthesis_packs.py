from __future__ import annotations

import unittest

from services.api.app.synthesis_packs import get_synthesis_pack


def _normalize(text: str) -> str:
    return " ".join(str(text or "").lower().replace("_", " ").split())


class SynthesisPackTests(unittest.TestCase):
    def test_generic_pack_leaves_process_playbook_neutral(self) -> None:
        pack = get_synthesis_pack("generic_ops")
        playbook = {
            "title": "Driver Economy Sheet Playbook",
            "purpose": "Document the process.",
            "trigger": "Scheduled workflow fires.",
            "action": "driver_economy_report_to_sheet",
            "steps": ["Run task.", "Record result."],
            "output": "Workflow done.",
        }
        refined = pack.refine_process_playbook(
            playbook=playbook,
            source_kind="scheduled_task",
            normalize_statement_text=_normalize,
        )
        self.assertEqual(refined["purpose"], "Document the process.")
        self.assertEqual(refined["steps"], ["Run task.", "Record result."])

    def test_logistics_pack_deepens_driver_economy_playbook(self) -> None:
        pack = get_synthesis_pack("logistics_ops")
        playbook = {
            "title": "Driver Economy Sheet Playbook",
            "purpose": "Document the process.",
            "trigger": "Scheduled workflow fires.",
            "action": "driver_economy_report_to_sheet",
            "steps": ["Run task.", "Record result."],
            "output": "Workflow done.",
            "inputs": ["postgres_sql:memory_items:polling"],
        }
        refined = pack.refine_process_playbook(
            playbook=playbook,
            source_kind="scheduled_task",
            normalize_statement_text=_normalize,
        )
        self.assertIn("driver economy", str(refined["purpose"]).lower())
        self.assertIn("report", str(refined["output"]).lower())
        self.assertGreaterEqual(len(refined["steps"]), 4)
        self.assertNotIn("workflow done", str(refined["output"]).lower())

    def test_logistics_pack_builds_company_context_extensions(self) -> None:
        pack = get_synthesis_pack("logistics_ops")
        payload = pack.build_company_context_extensions(
            matrix_rows=[
                {
                    "standing_orders": ["daily report", "incident monitor"],
                    "scheduled_tasks": ["driver economy sheet", "daily report"],
                }
            ],
            source_counts=[("postgres_sql", 2)],
            claims_rollup=[("documents_orders", 3), ("incident_monitor", 2)],
            normalize_statement_text=_normalize,
        )
        principles = payload.get("principles") or []
        workflow_signals = payload.get("workflow_signals") or []
        snapshot_notes = payload.get("snapshot_notes") or []
        self.assertTrue(any("dispatch" in item.lower() or "incident" in item.lower() for item in principles))
        self.assertTrue(any("daily report" in str(item.get("label") or "").lower() for item in workflow_signals))
        self.assertTrue(any("connected source streams" in item.lower() for item in snapshot_notes))

    def test_support_pack_deepens_ticket_playbook(self) -> None:
        pack = get_synthesis_pack("support_ops")
        playbook = {
            "title": "Ticket Escalation Playbook",
            "purpose": "Document the process.",
            "trigger": "Queue rule fires.",
            "action": "ticket_escalation_review",
            "steps": ["Run task.", "Record result."],
            "output": "Workflow done.",
        }
        refined = pack.refine_process_playbook(
            playbook=playbook,
            source_kind="scheduled_task",
            normalize_statement_text=_normalize,
        )
        self.assertIn("support", str(refined["purpose"]).lower())
        self.assertTrue(any("customer" in str(step).lower() or "queue" in str(step).lower() for step in refined["steps"]))

    def test_sales_pack_deepens_handoff_playbook(self) -> None:
        pack = get_synthesis_pack("sales_ops")
        playbook = {
            "title": "Deal Handoff Playbook",
            "purpose": "Document the process.",
            "trigger": "Handoff workflow fires.",
            "action": "deal_handoff_review",
            "steps": ["Run task.", "Record result."],
            "output": "Workflow done.",
        }
        refined = pack.refine_process_playbook(
            playbook=playbook,
            source_kind="scheduled_task",
            normalize_statement_text=_normalize,
        )
        self.assertIn("revenue", str(refined["purpose"]).lower())
        self.assertTrue(any("handoff" in str(step).lower() or "stage" in str(step).lower() for step in refined["steps"]))


if __name__ == "__main__":
    unittest.main()
