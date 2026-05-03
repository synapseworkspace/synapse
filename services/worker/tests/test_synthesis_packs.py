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

    def test_logistics_pack_does_not_leak_driver_economy_into_daily_report(self) -> None:
        pack = get_synthesis_pack("logistics_ops")
        playbook = {
            "title": "Daily Report Playbook",
            "purpose": "Document the process.",
            "trigger": "Daily reporting workflow fires.",
            "action": "logistics_daily_report",
            "steps": ["Run task.", "Record result."],
            "output": "Workflow done.",
            "artifacts": ["driver_economy_daily_latest"],
            "evidence": ["driver_economy_daily_latest"],
        }
        refined = pack.refine_process_playbook(
            playbook=playbook,
            source_kind="scheduled_task",
            normalize_statement_text=_normalize,
        )
        self.assertTrue(
            "digest" in str(refined["purpose"]).lower()
            or "report" in str(refined["purpose"]).lower()
        )
        self.assertNotIn("driver economy workflow", str(refined["purpose"]).lower())

    def test_logistics_pack_does_not_leak_driver_economy_into_comment_learning(self) -> None:
        pack = get_synthesis_pack("logistics_ops")
        playbook = {
            "title": "Comment Signal Learning Playbook",
            "purpose": "Document the process.",
            "trigger": "Learning workflow fires.",
            "action": "comment_signal_learning",
            "steps": ["Run task.", "Record result."],
            "output": "Workflow done.",
            "artifacts": ["driver_economy_daily_latest"],
            "evidence": ["driver_economy_daily_latest"],
        }
        refined = pack.refine_process_playbook(
            playbook=playbook,
            source_kind="scheduled_task",
            normalize_statement_text=_normalize,
        )
        self.assertIn("comments", str(refined["purpose"]).lower())
        self.assertNotIn("driver economy workflow", str(refined["purpose"]).lower())

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

    def test_compliance_pack_deepens_control_playbook(self) -> None:
        pack = get_synthesis_pack("compliance_ops")
        playbook = {
            "title": "Control Evidence Review Playbook",
            "purpose": "Document the process.",
            "trigger": "Audit workflow fires.",
            "action": "control_evidence_review",
            "steps": ["Run task.", "Record result."],
            "output": "Workflow done.",
        }
        refined = pack.refine_process_playbook(
            playbook=playbook,
            source_kind="scheduled_task",
            normalize_statement_text=_normalize,
        )
        self.assertIn("compliance", str(refined["purpose"]).lower())
        self.assertTrue(any("evidence" in str(step).lower() or "approval" in str(step).lower() for step in refined["steps"]))

    def test_support_pack_tooling_extensions_are_domain_specific(self) -> None:
        pack = get_synthesis_pack("support_ops")
        payload = pack.build_tooling_map_extensions(matrix_rows=[])
        bullets = payload.get("governance_bullets") or []
        self.assertTrue(any("queue" in str(item).lower() or "customer" in str(item).lower() for item in bullets))
        self.assertIn("support", str(payload.get("empty_hint") or "").lower())

    def test_sales_pack_capability_extensions_are_domain_specific(self) -> None:
        pack = get_synthesis_pack("sales_ops")
        payload = pack.build_capability_profile_extensions(matrix_rows=[])
        bullets = payload.get("signal_bullets") or []
        self.assertTrue(any("qualification" in str(item).lower() or "handoff" in str(item).lower() for item in bullets))
        self.assertIn("stage", str(payload.get("sparse_hint") or "").lower())


if __name__ == "__main__":
    unittest.main()
