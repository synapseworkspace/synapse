from __future__ import annotations

import unittest

try:
    from services.api.app.main import (
        _build_adoption_safe_mode_target_config,
        _enforce_high_signal_auto_publish_gate,
        _normalize_gatekeeper_routing_policy,
    )
except Exception:  # pragma: no cover - optional api deps in minimal test env
    _build_adoption_safe_mode_target_config = None
    _enforce_high_signal_auto_publish_gate = None
    _normalize_gatekeeper_routing_policy = None


@unittest.skipIf(
    _build_adoption_safe_mode_target_config is None
    or _enforce_high_signal_auto_publish_gate is None
    or _normalize_gatekeeper_routing_policy is None,
    "api adoption helpers unavailable",
)
class AdoptionSafeModeAndAutopublishTests(unittest.TestCase):
    def test_high_signal_gate_blocks_low_signal_fact(self) -> None:
        gate = _enforce_high_signal_auto_publish_gate(
            assertion_class="fact",
            category="order_snapshot/runtime_event",
            page_type="operations",
            routing_policy=_normalize_gatekeeper_routing_policy(None),
        )
        self.assertFalse(bool(gate["allowed"]))
        self.assertEqual(str(gate["reason"]), "blocked_by_high_signal_gate")

    def test_high_signal_gate_allows_policy(self) -> None:
        gate = _enforce_high_signal_auto_publish_gate(
            assertion_class="policy",
            category="warehouse_access_policy",
            page_type="access",
            routing_policy=_normalize_gatekeeper_routing_policy(None),
        )
        self.assertTrue(bool(gate["allowed"]))
        self.assertEqual(str(gate["reason"]), "matched_high_signal_profile")

    def test_safe_mode_target_config_stays_risk_tiered_not_globally_manual(self) -> None:
        payload = _build_adoption_safe_mode_target_config(
            current_config={
                "publish_mode_default": "auto_publish",
                "publish_mode_by_category": {"policy": "conditional"},
                "auto_publish_min_score": 0.81,
                "auto_publish_min_sources": 1,
                "auto_publish_require_golden": False,
                "auto_publish_allow_conflicts": True,
                "routing_policy": {"event_stream_min_token_hits": 2},
            }
        )
        target_config = payload.get("target_config") if isinstance(payload.get("target_config"), dict) else {}
        routing = target_config.get("routing_policy") if isinstance(target_config.get("routing_policy"), dict) else {}
        self.assertEqual(str(target_config.get("publish_mode_default")), "conditional")
        publish_by_category = (
            target_config.get("publish_mode_by_category")
            if isinstance(target_config.get("publish_mode_by_category"), dict)
            else {}
        )
        self.assertEqual(str(publish_by_category.get("policy")), "human_required")
        self.assertEqual(str(publish_by_category.get("security")), "human_required")
        self.assertEqual(str(publish_by_category.get("process")), "conditional")
        self.assertEqual(str(publish_by_category.get("incident")), "conditional")
        self.assertGreaterEqual(float(target_config.get("auto_publish_min_score") or 0.0), 0.95)
        self.assertGreaterEqual(int(target_config.get("auto_publish_min_sources") or 0), 3)
        self.assertTrue(bool(target_config.get("auto_publish_require_golden")))
        self.assertFalse(bool(target_config.get("auto_publish_allow_conflicts")))
        self.assertGreaterEqual(int(routing.get("event_stream_min_token_hits") or 0), 3)
        publish_by_assertion = (
            routing.get("publish_mode_by_assertion_class")
            if isinstance(routing.get("publish_mode_by_assertion_class"), dict)
            else {}
        )
        self.assertEqual(str(publish_by_assertion.get("policy")), "human_required")
        self.assertEqual(str(publish_by_assertion.get("event")), "human_required")
        self.assertEqual(str(publish_by_assertion.get("process")), "conditional")
        self.assertEqual(str(publish_by_assertion.get("incident")), "conditional")


if __name__ == "__main__":
    unittest.main()
