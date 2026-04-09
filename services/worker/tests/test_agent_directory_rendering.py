from __future__ import annotations

from datetime import date
import unittest

try:
    from services.api.app.main import (
        _build_agent_provenance_activity,
        _compute_agent_capability_confidence,
        _derive_runtime_agent_responsibilities,
        _derive_runtime_agent_role,
        _normalize_agent_directory_items,
        _normalize_agent_publish_policy,
        _render_agent_capability_matrix_markdown,
        _render_agent_daily_reports_page,
        _render_agent_daily_worklog_entry,
        _render_agent_handoff_markdown,
        _render_agent_overview_markdown,
        _render_agent_scorecards_markdown,
    )
except Exception:  # pragma: no cover
    _build_agent_provenance_activity = None
    _compute_agent_capability_confidence = None
    _derive_runtime_agent_responsibilities = None
    _derive_runtime_agent_role = None
    _normalize_agent_directory_items = None
    _normalize_agent_publish_policy = None
    _render_agent_capability_matrix_markdown = None
    _render_agent_daily_reports_page = None
    _render_agent_daily_worklog_entry = None
    _render_agent_handoff_markdown = None
    _render_agent_overview_markdown = None
    _render_agent_scorecards_markdown = None


@unittest.skipIf(
    _normalize_agent_directory_items is None
    or _build_agent_provenance_activity is None
    or _compute_agent_capability_confidence is None
    or _derive_runtime_agent_responsibilities is None
    or _derive_runtime_agent_role is None
    or _render_agent_capability_matrix_markdown is None
    or _normalize_agent_publish_policy is None
    or _render_agent_overview_markdown is None
    or _render_agent_daily_worklog_entry is None
    or _render_agent_daily_reports_page is None
    or _render_agent_handoff_markdown is None
    or _render_agent_scorecards_markdown is None,
    "api agent directory helpers unavailable",
)
class AgentDirectoryRenderingTests(unittest.TestCase):
    def test_normalize_agent_items_dedupes_and_trims(self) -> None:
        values = [" Escalate billing issues ", "escalate billing issues", "", "Handle VIP"]
        normalized = _normalize_agent_directory_items(values, limit=10)
        self.assertEqual(normalized, ["Escalate billing issues", "Handle VIP"])

    def test_overview_contains_core_sections(self) -> None:
        markdown = _render_agent_overview_markdown(
            profile={
                "agent_id": "support_bot",
                "display_name": "Support Bot",
                "status": "active",
                "last_seen_at": "2026-04-04T00:00:00Z",
                "profile_slug": "agents/support_bot",
                "responsibilities": ["Resolve tier-1 tickets"],
                "tools": ["Zendesk", "CRM"],
                "data_sources": ["Policy Wiki"],
                "limits": ["No refunds above $500"],
            },
            include_daily_report_stub=True,
        )
        self.assertIn("# Support Bot Overview", markdown)
        self.assertIn("## Responsibilities", markdown)
        self.assertIn("## Daily Report Stub", markdown)

    def test_daily_worklog_rendering(self) -> None:
        entry = _render_agent_daily_worklog_entry(
            profile={"agent_id": "support_bot"},
            worklog_date=date(2026, 4, 4),
            summary={
                "events_total": 12,
                "sessions_total": 3,
                "tasks_touched": 4,
                "tasks_done": 2,
                "events_by_type": {"tool_result": 8, "fact_proposed": 4},
            },
        )
        page = _render_agent_daily_reports_page(display_name="Support Bot", entries=[entry])
        self.assertIn("## 2026-04-04", page)
        self.assertIn("Events captured: 12", page)

    def test_capability_matrix_rendering(self) -> None:
        confidence = _compute_agent_capability_confidence(
            {"tasks_touched": 10, "tasks_done": 8, "events_total": 20}
        )
        self.assertGreaterEqual(confidence, 0.6)
        markdown = _render_agent_capability_matrix_markdown(
            matrix=[
                {
                    "agent_id": "support_bot",
                    "display_name": "Support Bot",
                    "team": "Support",
                    "role": "Tier1",
                    "confidence": confidence,
                    "last_success_at": "2026-04-04T00:00:00+00:00",
                    "responsibilities": ["Resolve tier-1 tickets", "Escalate billing cases"],
                }
            ]
        )
        self.assertIn("# Agent Capability Matrix", markdown)
        self.assertIn("Support Bot", markdown)

    def test_handoff_map_rendering(self) -> None:
        markdown = _render_agent_handoff_markdown(
            edges=[
                {
                    "from_agent": "triage_bot",
                    "from_display_name": "Triage Bot",
                    "to_agent": "billing_bot",
                    "to_display_name": "Billing Bot",
                    "input_contract": "ticket + customer profile",
                    "output_contract": "billing resolution plan",
                    "sla": "15m",
                }
            ]
        )
        self.assertIn("# Agent Handoff Map", markdown)
        self.assertIn("Triage Bot", markdown)
        self.assertIn("billing resolution plan", markdown)

    def test_scorecards_rendering(self) -> None:
        markdown = _render_agent_scorecards_markdown(
            scorecards=[
                {
                    "agent_id": "support_bot",
                    "display_name": "Support Bot",
                    "team": "Support",
                    "role": "Tier1",
                    "quality_score": 0.82,
                    "reliability_score": 0.87,
                    "escalation_rate": 0.1,
                    "active_tasks": 12,
                    "blocked_tasks": 2,
                    "evidence_page": "agents/support_bot/daily-reports",
                }
            ],
            lookback_days=14,
        )
        self.assertIn("# Agent Scorecards", markdown)
        self.assertIn("Support Bot", markdown)
        self.assertIn("0.82", markdown)

    def test_agent_provenance_rollback_flags(self) -> None:
        activity = _build_agent_provenance_activity(
            activity_id="act-1",
            page_id="page-1",
            slug="agents/support_bot/overview",
            title="Support Bot Overview",
            page_type="operations",
            page_status="published",
            current_version=5,
            version=5,
            source="agent",
            created_by="support_bot",
            change_summary="updated runbook",
            created_at=None,
        )
        self.assertTrue(bool(activity["rollback"]["possible"]))
        self.assertEqual(activity["rollback"]["target_version"], 4)
        stale = _build_agent_provenance_activity(
            activity_id="act-2",
            page_id="page-1",
            slug="agents/support_bot/overview",
            title="Support Bot Overview",
            page_type="operations",
            page_status="published",
            current_version=6,
            version=5,
            source="agent",
            created_by="support_bot",
            change_summary="older update",
            created_at=None,
        )
        self.assertFalse(bool(stale["rollback"]["possible"]))

    def test_publish_policy_normalization(self) -> None:
        policy = _normalize_agent_publish_policy(
            {
                "default_mode": "HUMAN_REQUIRED",
                "by_page_type": {
                    "Policy": "human_required",
                    "Operations Incident": "conditional",
                    "": "auto_publish",
                    "misc": "invalid",
                },
            }
        )
        self.assertEqual(policy["default_mode"], "human_required")
        self.assertEqual(policy["by_page_type"].get("policy"), "human_required")
        self.assertEqual(policy["by_page_type"].get("operations_incident"), "conditional")

    def test_runtime_role_and_responsibilities_are_human_readable(self) -> None:
        role = _derive_runtime_agent_role(
            event_types=["dispatch_task_started", "route_selected"],
            tools=["maps_router", "fleet_registry"],
        )
        responsibilities = _derive_runtime_agent_responsibilities(
            event_types=["dispatch_task_started", "route_selected"],
            tools=["maps_router", "fleet_registry"],
            data_sources=["orders_api", "warehouse_access_rules"],
        )
        self.assertEqual(role, "Dispatch Agent")
        self.assertTrue(any("Handles runtime events" in item for item in responsibilities))
        self.assertTrue(any("Uses tools" in item for item in responsibilities))


if __name__ == "__main__":
    unittest.main()
