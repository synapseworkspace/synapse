from __future__ import annotations

from datetime import UTC, datetime
import re
import unittest

try:
    from services.api.app.main import (
        _apply_wiki_schema_contract,
        _build_decisions_log_compiler_page,
        _evaluate_decisions_log_bootstrap_contract,
        _evaluate_publish_enrichment_need,
        _evaluate_decision_focused_quality_gate,
        _evaluate_wiki_schema_contract,
        _merge_markdown_with_enrichment,
    )
except Exception:  # pragma: no cover
    _apply_wiki_schema_contract = None
    _build_decisions_log_compiler_page = None
    _evaluate_decisions_log_bootstrap_contract = None
    _evaluate_publish_enrichment_need = None
    _evaluate_decision_focused_quality_gate = None
    _evaluate_wiki_schema_contract = None
    _merge_markdown_with_enrichment = None


@unittest.skipIf(
    _apply_wiki_schema_contract is None
    or _build_decisions_log_compiler_page is None
    or _evaluate_decisions_log_bootstrap_contract is None
    or _evaluate_publish_enrichment_need is None
    or _evaluate_wiki_schema_contract is None
    or _evaluate_decision_focused_quality_gate is None
    or _merge_markdown_with_enrichment is None,
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

    def test_publish_enrichment_need_detects_thin_placeholder_page(self) -> None:
        payload = _evaluate_publish_enrichment_need(
            "# Agent Capability Profile\n\n## Orgchart\n- runtime discovery pending\n",
            page_type="agent_profile",
            slug="operations/agent-capability-profile",
        )
        self.assertTrue(bool(payload.get("needs_enrichment")))
        self.assertLess(int(payload.get("word_count") or 0), int(payload.get("min_word_count") or 0))

    def test_merge_markdown_with_enrichment_fills_missing_sections(self) -> None:
        merged, meta = _merge_markdown_with_enrichment(
            markdown="# Agent Capability Profile\n\n## Orgchart\n- runtime discovery pending\n",
            candidate_markdown=(
                "# Agent Capability Profile\n\n"
                "## Orgchart\n- Dispatch Bot (`dispatch_bot`) | Dispatch | Coordinator | active | [Open](/wiki/agents/dispatch_bot)\n\n"
                "## Capability Matrix\n- Dispatch Bot routes orders and escalates blockers.\n\n"
                "## Capability Signals\n- Tool invocations and runtime actions.\n\n"
                "## Handoffs\n- Dispatch -> Billing for approval-sensitive incidents.\n"
            ),
            page_type="agent_profile",
            title="Agent Capability Profile",
            slug="operations/agent-capability-profile",
            status="published",
            generated_at=datetime(2026, 5, 2, 12, 0, tzinfo=UTC),
        )
        self.assertTrue(bool(meta.get("used_candidate")))
        self.assertIn("Capability Matrix", merged)
        self.assertIn("Dispatch Bot routes orders", merged)
        self.assertTrue(bool(_evaluate_wiki_schema_contract(
            markdown=merged,
            page_type="agent_profile",
            slug="operations/agent-capability-profile",
        ).get("passed")))

    def test_decisions_log_compiler_produces_canonical_entries(self) -> None:
        class _Cursor:
            def __init__(self) -> None:
                self.mode = "none"

            def execute(self, sql: str, params=None) -> None:
                text = str(sql)
                if "FROM evidence_bundles b" in text:
                    self.mode = "bundles"
                elif "FROM claims" in text:
                    self.mode = "claims"
                else:
                    self.mode = "none"

            def fetchall(self):
                if self.mode == "bundles":
                    return [
                        (
                            "bundle-1",
                            "decision:dispatch",
                            "decision",
                            "decision_log",
                            "dispatch",
                            "ready",
                            3,
                            2,
                            2,
                            3,
                            0.91,
                            datetime(2026, 5, 2, 12, 0, tzinfo=UTC),
                            {"source_system": "dispatch_db"},
                            [{"claim_text": "Escalate yard access failures after 15 minutes.", "category": "decision", "metadata": {}}],
                        )
                    ]
                if self.mode == "claims":
                    return []
                return []

        pages = _build_decisions_log_compiler_page(
            _Cursor(),
            project_id="omega_demo",
            space_key="operations",
            max_entries=10,
        )
        markdown = str(pages[0].get("markdown") or "")
        contract = _evaluate_decisions_log_bootstrap_contract(markdown, min_entries=1)
        self.assertTrue(bool(contract.get("passed")))
        self.assertIn("Escalate yard access failures", markdown)
        self.assertIn("Source: dispatch_db", markdown)


if __name__ == "__main__":
    unittest.main()
