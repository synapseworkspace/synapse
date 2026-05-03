from __future__ import annotations

import unittest

try:
    from services.api.app.main import (
        _build_company_knowledge_candidate_markdown,
        _merge_company_knowledge_candidate_into_markdown,
        _render_company_knowledge_candidate_section,
    )
except Exception:  # pragma: no cover - optional API deps in minimal envs
    _build_company_knowledge_candidate_markdown = None
    _merge_company_knowledge_candidate_into_markdown = None
    _render_company_knowledge_candidate_section = None


@unittest.skipIf(
    _merge_company_knowledge_candidate_into_markdown is None or _render_company_knowledge_candidate_section is None,
    "api helpers unavailable",
)
class CompanyKnowledgePromotionTests(unittest.TestCase):
    def test_render_candidate_section_wraps_block_with_markers(self) -> None:
        candidate = {
            "block_id": "logistics:source_of_truth_rule",
            "human_title": "Which systems to trust for live logistics state",
            "page_markdown": "# Which systems to trust for live logistics state\n\n## Summary\n- Prefer ERP for live route state.\n",
        }
        rendered = _render_company_knowledge_candidate_section(candidate)
        self.assertIn("<!-- synapse:company-knowledge-start logistics:source_of_truth_rule -->", rendered)
        self.assertIn("### Which systems to trust for live logistics state", rendered)
        self.assertIn("<!-- synapse:company-knowledge-meta group=source_of_truth", rendered)
        self.assertIn("Prefer ERP for live route state.", rendered)
        self.assertIn("<!-- synapse:company-knowledge-end logistics:source_of_truth_rule -->", rendered)

    def test_merge_appends_new_company_knowledge_section(self) -> None:
        existing = "# Trust Rules for Logistics Data\n\n## Existing Rule\n- Operators validate stale sheet output before use.\n"
        candidate = {
            "block_id": "logistics:source_of_truth_rule",
            "human_title": "Which systems to trust for live logistics state",
            "page_markdown": "# Which systems to trust for live logistics state\n\n## Summary\n- Prefer ERP for live route state.\n",
        }
        merged = _merge_company_knowledge_candidate_into_markdown(existing, candidate)
        self.assertIn("# Trust Rules for Logistics Data", merged)
        self.assertIn("## Existing Rule", merged)
        self.assertIn("<!-- synapse:company-knowledge-managed-start -->", merged)
        self.assertIn("## Source-of-truth rules", merged)
        self.assertIn("<!-- synapse:company-knowledge-start logistics:source_of_truth_rule -->", merged)
        self.assertIn("Prefer ERP for live route state.", merged)

    def test_merge_replaces_existing_managed_section_for_same_block(self) -> None:
        existing = """# Trust Rules for Logistics Data

<!-- synapse:company-knowledge-start logistics:source_of_truth_rule -->
### Which systems to trust for live logistics state

## Summary
- Old rule.
<!-- synapse:company-knowledge-end logistics:source_of_truth_rule -->
"""
        candidate = {
            "block_id": "logistics:source_of_truth_rule",
            "human_title": "Which systems to trust for live logistics state",
            "page_markdown": "# Which systems to trust for live logistics state\n\n## Summary\n- Prefer ERP for live route state.\n",
        }
        merged = _merge_company_knowledge_candidate_into_markdown(existing, candidate)
        self.assertNotIn("Old rule.", merged)
        self.assertEqual(merged.count("<!-- synapse:company-knowledge-start logistics:source_of_truth_rule -->"), 1)
        self.assertIn("Prefer ERP for live route state.", merged)
        self.assertEqual(merged.count("## Source-of-truth rules"), 1)

    def test_merge_groups_sections_in_stable_order(self) -> None:
        existing = "# Trust Rules for Logistics Data\n"
        contradiction = {
            "block_id": "logistics:contradiction_watch",
            "block_type": "contradiction_watch",
            "contradiction_topic": "source_of_truth_conflict",
            "human_title": "Source-of-truth conflicts that still need resolution",
            "page_markdown": "# Source-of-truth conflicts that still need resolution\n\n## Summary\n- Follow up on stale sheets.\n",
        }
        source_rule = {
            "block_id": "logistics:source_of_truth_rule",
            "block_type": "source_of_truth_rule",
            "target_page_type": "source_of_truth",
            "human_title": "Which systems to trust for live logistics state",
            "page_markdown": "# Which systems to trust for live logistics state\n\n## Summary\n- Prefer ERP for live route state.\n",
        }
        merged = _merge_company_knowledge_candidate_into_markdown(existing, contradiction)
        merged = _merge_company_knowledge_candidate_into_markdown(merged, source_rule)
        self.assertLess(merged.index("## Source-of-truth rules"), merged.index("## Open contradictions and follow-ups"))
        self.assertLess(
            merged.index("Which systems to trust for live logistics state"),
            merged.index("Source-of-truth conflicts that still need resolution"),
        )

    def test_candidate_markdown_includes_manual_review_resolution(self) -> None:
        markdown = _build_company_knowledge_candidate_markdown(
            {
                "human_title": "Which systems to trust for live logistics state",
                "human_summary": "Use ERP as the live source of truth for route state.",
                "knowledge_state": "reviewed",
                "confidence": "medium",
                "block_id": "logistics:source_of_truth_rule",
                "evidence_basis": "Repeated trust signals.",
                "resolution_rule": "Prefer ERP for live state.",
                "manual_review": {
                    "decision": "prefer_canonical",
                    "preferred_source_label": "ERP",
                    "resolution_note": "Keep sheets as secondary context only.",
                },
            }
        )
        self.assertIn("## Review Decision", markdown)
        self.assertIn("Decision: prefer_canonical", markdown)
        self.assertIn("Preferred source: ERP", markdown)
        self.assertIn("Review note: Keep sheets as secondary context only.", markdown)


if __name__ == "__main__":
    unittest.main()
