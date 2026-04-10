from __future__ import annotations

import unittest

try:
    from services.api.app.main import (
        _build_adoption_pipeline_pressure_warnings,
        _build_adoption_safe_mode_target_config,
        _normalize_gatekeeper_routing_policy,
    )
except Exception:  # pragma: no cover - optional api deps in minimal test env
    _build_adoption_pipeline_pressure_warnings = None
    _build_adoption_safe_mode_target_config = None
    _normalize_gatekeeper_routing_policy = None


@unittest.skipIf(
    _build_adoption_pipeline_pressure_warnings is None
    or _build_adoption_safe_mode_target_config is None
    or _normalize_gatekeeper_routing_policy is None,
    "api adoption pressure helpers unavailable",
)
class AdoptionPipelinePressureControlTests(unittest.TestCase):
    def test_pressure_warnings_include_queue_page_and_entity_limits(self) -> None:
        warnings = _build_adoption_pipeline_pressure_warnings(
            {
                "draft_queue": {"open_total": 9000},
                "draft_flood_guard": {
                    "thresholds": {
                        "safe_mode_open_drafts_threshold": 5000,
                        "safe_mode_open_drafts_per_page_threshold": 200,
                        "max_open_per_entity": 400,
                    },
                    "max_open_per_page": 450,
                    "max_open_per_entity": 700,
                },
            }
        )
        codes = {str(item.get("code") or "") for item in warnings if isinstance(item, dict)}
        self.assertIn("draft_queue_pressure", codes)
        self.assertIn("draft_flood_page_limit", codes)
        self.assertIn("draft_flood_entity_limit", codes)

    def test_pressure_warnings_empty_when_within_thresholds(self) -> None:
        warnings = _build_adoption_pipeline_pressure_warnings(
            {
                "draft_queue": {"open_total": 100},
                "draft_flood_guard": {
                    "thresholds": {
                        "safe_mode_open_drafts_threshold": 5000,
                        "safe_mode_open_drafts_per_page_threshold": 200,
                        "max_open_per_entity": 400,
                    },
                    "max_open_per_page": 20,
                    "max_open_per_entity": 30,
                },
            }
        )
        self.assertEqual(warnings, [])

    def test_pressure_warnings_include_events_claims_floor_alert(self) -> None:
        warnings = _build_adoption_pipeline_pressure_warnings(
            {
                "draft_queue": {"open_total": 10},
                "draft_flood_guard": {
                    "thresholds": {
                        "safe_mode_open_drafts_threshold": 5000,
                        "safe_mode_open_drafts_per_page_threshold": 200,
                        "max_open_per_entity": 400,
                    },
                    "max_open_per_page": 12,
                    "max_open_per_entity": 20,
                },
                "claims_floor_guard": {
                    "triggered": True,
                    "events_total": 1672,
                    "claims_total": 0,
                    "min_events": 120,
                    "alert_after_minutes": 20,
                },
            }
        )
        codes = {str(item.get("code") or "") for item in warnings if isinstance(item, dict)}
        self.assertIn("events_claims_zero_floor", codes)

    def test_safe_mode_target_config_enforces_flood_guard_controls(self) -> None:
        payload = _build_adoption_safe_mode_target_config(
            current_config={
                "routing_policy": _normalize_gatekeeper_routing_policy(
                    {
                        "emit_reinforcement_drafts": True,
                        "draft_flood_max_open_per_page": 2000,
                        "draft_flood_max_open_per_entity": 10000,
                        "queue_pressure_safe_mode_open_drafts_threshold": 90000,
                        "queue_pressure_safe_mode_open_drafts_per_page_threshold": 2000,
                    }
                )
            }
        )
        target = payload.get("target_routing_policy") if isinstance(payload.get("target_routing_policy"), dict) else {}
        self.assertFalse(bool(target.get("emit_reinforcement_drafts")))
        self.assertLessEqual(int(target.get("draft_flood_max_open_per_page") or 0), 200)
        self.assertLessEqual(int(target.get("draft_flood_max_open_per_entity") or 0), 400)
        self.assertLessEqual(int(target.get("queue_pressure_safe_mode_open_drafts_threshold") or 0), 5000)
        self.assertLessEqual(int(target.get("queue_pressure_safe_mode_open_drafts_per_page_threshold") or 0), 200)


if __name__ == "__main__":
    unittest.main()
