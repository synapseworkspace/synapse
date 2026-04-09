from __future__ import annotations

import unittest

try:
    from services.api.app.main import (
        DraftBulkReviewFilter,
        _draft_matches_bulk_filter,
        _normalize_draft_statuses,
    )
except Exception:  # pragma: no cover - optional API dependency path in test env
    DraftBulkReviewFilter = None
    _draft_matches_bulk_filter = None
    _normalize_draft_statuses = None


@unittest.skipIf(
    DraftBulkReviewFilter is None or _draft_matches_bulk_filter is None or _normalize_draft_statuses is None,
    "bulk review helpers unavailable",
)
class WikiBulkReviewFilterTests(unittest.TestCase):
    def test_normalize_statuses_applies_default(self) -> None:
        statuses = _normalize_draft_statuses(["pending_review", "PENDING_REVIEW", "bad"], default=["pending_review"])
        self.assertEqual(statuses, ["pending_review"])

    def test_filter_matches_category_source_and_risk_threshold(self) -> None:
        draft = {
            "confidence": 0.92,
            "has_open_conflict": False,
            "page": {"status": "published", "page_type": "operations"},
            "claim": {"category": "business_rule"},
            "gatekeeper": {"assertion_class": "policy", "tier": "golden_candidate"},
            "evidence": {"source_systems": ["ops_kb_sync"], "connectors": ["postgres_sql"]},
            "risk": {"level": "medium"},
        }
        filter_cfg = DraftBulkReviewFilter(
            category="business_",
            category_mode="prefix",
            source_system="ops_kb",
            source_system_mode="prefix",
            connector="postgres",
            connector_mode="prefix",
            page_type="operations",
            assertion_class="policy",
            tier="golden",
            tier_mode="prefix",
            min_confidence=0.8,
            min_risk_level="medium",
            include_open_conflicts=False,
            include_published_pages=True,
        )
        self.assertTrue(_draft_matches_bulk_filter(draft, filter_cfg))

    def test_filter_excludes_open_conflict_by_default(self) -> None:
        draft = {
            "confidence": 0.9,
            "has_open_conflict": True,
            "page": {"status": "reviewed", "page_type": "operations"},
            "claim": {"category": "process"},
            "gatekeeper": {"assertion_class": "process", "tier": "insight_candidate"},
            "evidence": {"source_systems": ["ops_kb_sync"], "connectors": ["postgres_sql"]},
            "risk": {"level": "low"},
        }
        filter_cfg = DraftBulkReviewFilter()
        self.assertFalse(_draft_matches_bulk_filter(draft, filter_cfg))


if __name__ == "__main__":
    unittest.main()

