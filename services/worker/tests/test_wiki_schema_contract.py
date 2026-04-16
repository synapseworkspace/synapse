from __future__ import annotations

from datetime import UTC, datetime
import re
import unittest

try:
    from services.api.app.main import (
        _apply_wiki_schema_contract,
        _evaluate_decision_focused_quality_gate,
        _evaluate_wiki_schema_contract,
    )
except Exception:  # pragma: no cover
    _apply_wiki_schema_contract = None
    _evaluate_decision_focused_quality_gate = None
    _evaluate_wiki_schema_contract = None


@unittest.skipIf(
    _apply_wiki_schema_contract is None
    or _evaluate_wiki_schema_contract is None
    or _evaluate_decision_focused_quality_gate is None,
    "wiki schema helpers unavailable",
)
class WikiSchemaContractTests(unittest.TestCase):
    def test_apply_contract_enforces_frontmatter_backlinks_and_decisions_source(self) -> None:
        markdown = _apply_wiki_schema_contract(
            markdown="# Dispatch Escalation\n\n## Discussion\n- maybe we should escalate later.\n",
            title="Dispatch Escalation",
            page_type="process",
            slug="operations/dispatch-escalation",
            status="published",
            generated_at=datetime(2026, 4, 17, 9, 0, tzinfo=UTC),
        )
        self.assertTrue(markdown.startswith("---\n"))
        self.assertIn("summary:", markdown)
        self.assertIn("status:", markdown)
        self.assertIn("last_updated:", markdown)
        self.assertIn("## Backlinks", markdown)
        self.assertIn("/wiki/operations/state", markdown)
        self.assertIn("## Decisions Log", markdown)
        self.assertRegex(markdown, r"Source:\s+internal://")
        self.assertRegex(markdown, r"-\s+2026-04-17\s+-")

        schema = _evaluate_wiki_schema_contract(
            markdown=markdown,
            page_type="process",
            slug="operations/dispatch-escalation",
        )
        self.assertTrue(bool(schema.get("passed")))

    def test_apply_contract_adds_typed_metric_skeleton(self) -> None:
        markdown = _apply_wiki_schema_contract(
            markdown="# Delivery SLA KPI\n",
            title="Delivery SLA KPI",
            page_type="metric",
            slug="operations/delivery-sla-kpi",
            status="published",
            generated_at=datetime(2026, 4, 17, 9, 0, tzinfo=UTC),
        )
        for heading in ("## Definition", "## Current Value", "## Thresholds", "## Source"):
            self.assertIn(heading, markdown)

    def test_decision_quality_gate_blocks_discussion_only_content(self) -> None:
        payload = _evaluate_decision_focused_quality_gate(
            "# Process Notes\n\n## Discussion\n- maybe later, open question?\n",
            page_type="process",
        )
        self.assertTrue(bool(payload.get("applies")))
        self.assertFalse(bool(payload.get("passed")))
        self.assertEqual(str(payload.get("reason") or ""), "discussion_without_decision")
        self.assertGreaterEqual(int(payload.get("discussion_hits") or 0), 1)


if __name__ == "__main__":
    unittest.main()
