from __future__ import annotations

from datetime import UTC, date, datetime
import unittest

try:
    import services.api.app.main as _api_main
    from services.api.app.synthesis_packs import get_synthesis_pack
    from services.api.app.main import (
        AgentReflectionSubmitRequest,
        AgentRuntimeSurfaceAgentIn,
        _bootstrap_page_importance,
        _build_agent_reflection_claim_payloads,
        _build_agent_profile_from_runtime_surface,
        _build_agent_directory_profile_fallback_matrix,
        _build_data_sources_catalog_pages,
        _build_agent_capability_bootstrap_page,
        _build_tooling_map_bootstrap_page,
        _build_process_playbooks_bootstrap_page,
        _build_agent_wiki_bootstrap_quality_report,
        _build_project_wiki_richness_benchmark_from_rows,
        _build_human_guided_synthesis_prompts,
        _build_adoption_signal_noise_audit,
        _build_adoption_signal_noise_stability_monitor,
        AdoptionSyncPresetExecuteRequest,
        _bundle_promotion_scope_for_page_type,
        _draft_bundle_priority,
        _draft_passes_default_bundle_guard_for_approve,
        _summarize_draft_queue,
        _build_first_run_starter_pages,
        _page_type_freshness_thresholds,
        _prepend_bootstrap_publish_notice,
        _build_runtime_agent_capability_matrix,
        _collect_agent_source_usage,
        _build_project_wiki_quality_report_from_rows,
        _build_agent_provenance_activity,
        _compute_agent_capability_confidence,
        _derive_runtime_agent_responsibilities,
        _derive_runtime_agent_role,
        _adoption_business_profiles_catalog,
        _resolve_adoption_business_profile,
        _infer_runtime_surface_core_space_keys,
        _draft_matches_bulk_filter,
        _evaluate_agent_capability_bootstrap_contract,
        _is_daily_summary_like_draft_row,
        _normalize_agent_directory_items,
        _normalize_agent_publish_policy,
        _render_agent_capability_matrix_markdown,
        _render_agent_daily_reports_page,
        _render_agent_daily_worklog_entry,
        _render_agent_handoff_markdown,
        _render_agent_overview_markdown,
        _render_agent_runbooks_markdown,
        _render_agent_scheduled_task_runbook_markdown,
        _render_agent_scorecards_markdown,
        _runtime_agent_filter_sql,
        _runtime_agent_id_sql_expr,
    )
except Exception:  # pragma: no cover
    _api_main = None
    get_synthesis_pack = None
    AgentReflectionSubmitRequest = None
    AgentRuntimeSurfaceAgentIn = None
    _bootstrap_page_importance = None
    _build_agent_reflection_claim_payloads = None
    _build_agent_profile_from_runtime_surface = None
    _build_agent_directory_profile_fallback_matrix = None
    _build_data_sources_catalog_pages = None
    _build_agent_capability_bootstrap_page = None
    _build_tooling_map_bootstrap_page = None
    _build_process_playbooks_bootstrap_page = None
    _build_agent_wiki_bootstrap_quality_report = None
    _build_project_wiki_richness_benchmark_from_rows = None
    _build_human_guided_synthesis_prompts = None
    _build_adoption_signal_noise_audit = None
    _build_adoption_signal_noise_stability_monitor = None
    AdoptionSyncPresetExecuteRequest = None
    _bundle_promotion_scope_for_page_type = None
    _draft_bundle_priority = None
    _draft_passes_default_bundle_guard_for_approve = None
    _summarize_draft_queue = None
    _build_first_run_starter_pages = None
    _page_type_freshness_thresholds = None
    _prepend_bootstrap_publish_notice = None
    _build_runtime_agent_capability_matrix = None
    _collect_agent_source_usage = None
    _build_project_wiki_quality_report_from_rows = None
    _build_agent_provenance_activity = None
    _compute_agent_capability_confidence = None
    _derive_runtime_agent_responsibilities = None
    _derive_runtime_agent_role = None
    _adoption_business_profiles_catalog = None
    _resolve_adoption_business_profile = None
    _infer_runtime_surface_core_space_keys = None
    _draft_matches_bulk_filter = None
    _evaluate_agent_capability_bootstrap_contract = None
    _is_daily_summary_like_draft_row = None
    _normalize_agent_directory_items = None
    _normalize_agent_publish_policy = None
    _render_agent_capability_matrix_markdown = None
    _render_agent_daily_reports_page = None
    _render_agent_daily_worklog_entry = None
    _render_agent_handoff_markdown = None
    _render_agent_overview_markdown = None
    _render_agent_runbooks_markdown = None
    _render_agent_scheduled_task_runbook_markdown = None
    _render_agent_scorecards_markdown = None
    _runtime_agent_filter_sql = None
    _runtime_agent_id_sql_expr = None


@unittest.skipIf(
    _normalize_agent_directory_items is None
    or _bootstrap_page_importance is None
    or _build_data_sources_catalog_pages is None
    or _build_agent_capability_bootstrap_page is None
    or _build_tooling_map_bootstrap_page is None
    or _build_process_playbooks_bootstrap_page is None
    or _build_agent_wiki_bootstrap_quality_report is None
    or _build_project_wiki_richness_benchmark_from_rows is None
    or _build_human_guided_synthesis_prompts is None
    or _build_adoption_signal_noise_audit is None
    or _build_adoption_signal_noise_stability_monitor is None
    or AdoptionSyncPresetExecuteRequest is None
    or _bundle_promotion_scope_for_page_type is None
    or _draft_bundle_priority is None
    or _draft_passes_default_bundle_guard_for_approve is None
    or _summarize_draft_queue is None
    or _build_first_run_starter_pages is None
    or _page_type_freshness_thresholds is None
    or _build_agent_reflection_claim_payloads is None
    or _build_agent_profile_from_runtime_surface is None
    or _build_agent_directory_profile_fallback_matrix is None
    or _prepend_bootstrap_publish_notice is None
    or _build_project_wiki_quality_report_from_rows is None
    or AgentReflectionSubmitRequest is None
    or AgentRuntimeSurfaceAgentIn is None
    or _build_agent_provenance_activity is None
    or _compute_agent_capability_confidence is None
    or _derive_runtime_agent_responsibilities is None
    or _derive_runtime_agent_role is None
    or _adoption_business_profiles_catalog is None
    or _resolve_adoption_business_profile is None
    or _infer_runtime_surface_core_space_keys is None
    or _draft_matches_bulk_filter is None
    or _evaluate_agent_capability_bootstrap_contract is None
    or _is_daily_summary_like_draft_row is None
    or _render_agent_capability_matrix_markdown is None
    or _normalize_agent_publish_policy is None
    or _render_agent_overview_markdown is None
    or _render_agent_runbooks_markdown is None
    or _render_agent_daily_worklog_entry is None
    or _render_agent_daily_reports_page is None
    or _render_agent_handoff_markdown is None
    or _render_agent_scorecards_markdown is None
    or _render_agent_scheduled_task_runbook_markdown is None
    or get_synthesis_pack is None
    or _build_runtime_agent_capability_matrix is None
    or _collect_agent_source_usage is None
    or _runtime_agent_filter_sql is None
    or _runtime_agent_id_sql_expr is None,
    "api agent directory helpers unavailable",
)
class AgentDirectoryRenderingTests(unittest.TestCase):
    def test_sync_preset_defaults_to_standard_starter_profile(self) -> None:
        request = AdoptionSyncPresetExecuteRequest(project_id="omega_demo")
        self.assertEqual(request.starter_profile, "standard")

    def test_business_profiles_catalog_exposes_logistics_operator(self) -> None:
        profiles = _adoption_business_profiles_catalog()
        logistics = next(item for item in profiles if str(item.get("key") or "") == "logistics_operator")
        self.assertEqual(logistics["starter_profile"], "logistics_ops")
        self.assertEqual(logistics["role_template_key"], "logistics_ops")
        self.assertEqual(logistics["bundle_promotion_space_key"], "logistics")

    def test_resolve_business_profile_returns_ai_employee_org(self) -> None:
        profile = _resolve_adoption_business_profile("ai_employee_org")
        assert profile is not None
        self.assertEqual(profile["starter_profile"], "ai_employee_org")
        self.assertEqual(profile["default_space_key"], "operations")

    def test_runtime_surface_profile_builder_extracts_control_plane_contracts(self) -> None:
        surface = AgentRuntimeSurfaceAgentIn(
            agent_id="logistics-assistant",
            runtime_overview={
                "org_code": "hw",
                "agent_code": "logistics-assistant",
                "enabled": True,
                "runtime_mode": "service",
                "running_instances": 6,
                "latest_heartbeat_at": "2026-05-03T03:37:59+03:00",
            },
            scheduled_tasks=[
                {
                    "task_code": "standing_order.logistics.incident.monitor",
                    "schedule_kind": "interval",
                    "interval_seconds": 600,
                    "builtin_task": "logistics_incident_monitor",
                    "standing_order_program": "logistics-default-ops-v1",
                    "standing_order_authority": ["logist", "director"],
                    "standing_order_approval_mode": "none",
                    "standing_order_escalation": {"mode": "notify"},
                    "source_hints": ["logistics_world_model_latest"],
                }
            ],
            action_surface=["outbound_messaging", "browser_automation"],
            tool_manifest=[
                {
                    "name": "controlled_exec",
                    "purpose": "Run controlled operational commands",
                    "scenarios": ["incident mitigation"],
                    "guardrails": ["human approval for destructive actions"],
                    "source_hints": ["logistics_world_model_latest"],
                    "capabilities": ["route_reschedule_request"],
                }
            ],
            source_hints=[
                {
                    "source": "driver_shift_daily_latest",
                    "capabilities": ["documents_orders"],
                    "processes": ["shift readiness control"],
                    "tools": ["documents_orders_for_driver_day"],
                },
                "driver_economy_daily_latest",
            ],
            capability_registry=[
                {
                    "name": "documents_orders",
                    "actions": ["prepare_shift_documents"],
                    "source_hints": ["driver_shift_daily_latest"],
                    "tools": ["documents_orders_for_driver_day"],
                    "processes": ["shift readiness control"],
                },
                "logistics_world_model",
            ],
            model_routing={"primary": "gpt-5.5", "fallback": "gpt-5.4"},
        )
        profile = _build_agent_profile_from_runtime_surface(surface, actor="ops_admin")
        self.assertEqual(profile["status"], "active")
        self.assertIn("documents_orders", profile["responsibilities"])
        self.assertIn("controlled_exec", profile["tools"])
        self.assertIn("driver_shift_daily_latest", profile["data_sources"])
        metadata = profile["metadata"]
        self.assertIn("standing_order.logistics.incident.monitor", " ".join(metadata["scheduled_tasks"]))
        self.assertIn("controlled_exec", [item["name"] for item in metadata["tool_registry"]])
        self.assertEqual(metadata["source_binding_contracts"][0]["source"], "driver_shift_daily_latest")
        self.assertEqual(metadata["capability_contracts"][0]["name"], "documents_orders")
        self.assertEqual(metadata["runtime_overview"]["running_instances"], 6)

    def test_runtime_surface_space_inference_prefers_domain_token(self) -> None:
        surface = AgentRuntimeSurfaceAgentIn(
            agent_id="logistics-assistant",
            team="operations",
            scheduled_tasks=[
                {
                    "task_code": "standing_order.logistics.incident.monitor",
                    "builtin_task": "logistics_incident_monitor",
                },
                {
                    "task_code": "standing_order.logistics.driver_economy_sheet",
                    "builtin_task": "driver_economy_report_to_sheet",
                },
            ],
            capability_registry=[
                {
                    "name": "documents_orders",
                    "processes": ["daily report", "incident monitor"],
                    "source_hints": ["postgres_sql:memory_items:polling"],
                },
                "logistics_world_model",
            ],
        )
        spaces = _infer_runtime_surface_core_space_keys(surfaces=[surface], profiles=[])
        self.assertEqual(spaces[0], "logistics")
        self.assertNotIn("standing-order-logistics-incident-monitor", spaces)
        self.assertNotIn("documents_orders", spaces)

    def test_generic_ops_pack_space_inference_still_avoids_task_tokens(self) -> None:
        surface = AgentRuntimeSurfaceAgentIn(
            agent_id="logistics-assistant",
            scheduled_tasks=[
                {
                    "task_code": "standing_order.logistics.incident.monitor",
                    "builtin_task": "logistics_incident_monitor",
                }
            ],
        )
        spaces = get_synthesis_pack("generic_ops").infer_core_space_keys(
            surfaces=[surface],
            profiles=[],
            normalize_space_key=lambda value: _api_main._normalize_space_key(value, default=""),
        )
        self.assertEqual(spaces[0], "logistics")
        self.assertNotIn("incident", spaces)
        self.assertNotIn("monitor", spaces)

    def test_bundle_promotion_scope_prefers_process_family_for_process_pages(self) -> None:
        scope = _bundle_promotion_scope_for_page_type("process")
        self.assertFalse(scope["include_data_sources_catalog"])
        self.assertFalse(scope["include_agent_capability_profile"])
        self.assertTrue(scope["include_tooling_map"])
        self.assertTrue(scope["include_process_playbooks"])
        self.assertTrue(scope["include_decisions_log"])
        self.assertTrue(scope["include_company_operating_context"])
        self.assertTrue(scope["include_operational_logic_map"])

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

    def test_agent_capability_contract_passes_for_bootstrap_page(self) -> None:
        assert _api_main is not None
        original_agent_directory_exists = _api_main._agent_directory_table_exists_from_cursor
        original_runtime_matrix = _api_main._build_runtime_agent_capability_matrix
        original_get_orgchart = _api_main.get_agent_orgchart
        try:
            _api_main._agent_directory_table_exists_from_cursor = lambda cur: False
            _api_main._build_runtime_agent_capability_matrix = lambda cur, project_id, max_agents: [
                {
                    "agent_id": "dispatch_bot",
                    "display_name": "Dispatch Bot",
                    "team": "Runtime Agents",
                    "role": "Dispatch Agent",
                    "status": "active",
                    "responsibilities": ["Plans dispatch routes", "Monitors SLA risks"],
                    "typical_actions": [
                        "Plans routing decisions and applies dispatch fallback actions.",
                        "Evaluates policy/process changes and opens governance review when needed.",
                    ],
                    "escalation_rules": [
                        "Escalates when SLA risk persists after mitigation attempt.",
                    ],
                    "scenario_examples": [
                        "When route/access constraints change, updates plan and escalates if SLA at risk.",
                    ],
                    "tools": ["maps_router", "fleet_registry"],
                    "data_sources": ["orders_api", "warehouse_access_rules"],
                    "limits": ["Operates under role-specific runbooks and approval guardrails."],
                    "scheduled_tasks": ["refresh dispatch queue (0 * * * *)"],
                    "standing_orders": ["Escalate route blockers within 15m"],
                    "source_bindings": ["orders_api -> dispatch planner"],
                    "integrations": ["Slack", "Postgres"],
                    "model_routing": ["primary: gpt-4.1", "fallback: gpt-4o-mini"],
                    "confidence": 0.88,
                    "last_success_at": "2026-04-10T00:00:00+00:00",
                    "evidence": [],
                }
            ]
            _api_main.get_agent_orgchart = lambda **kwargs: {
                "nodes": [
                    {
                        "agent_id": "dispatch_bot",
                        "display_name": "Dispatch Bot",
                        "team": "Runtime Agents",
                        "role": "Dispatch Agent",
                        "status": "active",
                        "profile_slug": "agents/dispatch_bot",
                    }
                ],
                "edges": [],
                "teams": [{"team": "Runtime Agents", "agents_total": 1}],
            }

            pages = _build_agent_capability_bootstrap_page(
                object(),
                project_id="omega_demo",
                space_key="operations",
                max_agents=10,
            )
            self.assertTrue(bool(pages))
            markdown = str(pages[0].get("markdown") or "")
            contract = _evaluate_agent_capability_bootstrap_contract(markdown, min_sections=4, min_facts=6)
            self.assertTrue(bool(contract.get("passed")))
            self.assertEqual(list(contract.get("missing_sections") or []), [])
            self.assertGreaterEqual(int(contract.get("facts_count") or 0), 6)
            self.assertIn("Scheduled tasks: refresh dispatch queue", markdown)
            self.assertIn("Standing orders / processes: Escalate route blockers within 15m", markdown)
            self.assertIn("Source bindings: orders_api -> dispatch planner", markdown)
            self.assertIn("Model routing / failover: primary: gpt-4.1", markdown)
        finally:
            _api_main._agent_directory_table_exists_from_cursor = original_agent_directory_exists
            _api_main._build_runtime_agent_capability_matrix = original_runtime_matrix
            _api_main.get_agent_orgchart = original_get_orgchart

    def test_bootstrap_quality_report_highlights_core_publish_gaps(self) -> None:
        plan_pages = [
            {
                "title": "Agent Capability Profile",
                "slug": "operations/agent-capability-profile",
                "page_type": "agent_profile",
                "markdown": "# Agent Capability Profile\n\n## Orgchart\n- A\n\n## Capability Matrix\n- B\n",
            },
            {
                "title": "Data Sources Catalog",
                "slug": "operations/data-sources-catalog",
                "page_type": "data_map",
                "markdown": "# Data Sources Catalog\n\n## Connected Sources\n- source\n",
            },
            {
                "title": "Company Operating Context",
                "slug": "operations/company-operating-context",
                "page_type": "operations",
                "markdown": "# Company Operating Context\n\n## Snapshot\n- ctx\n",
            },
        ]
        page_result = {
            "created": [
                {"slug": "operations/agent-capability-profile", "status": "published"},
                {"slug": "operations/data-sources-catalog", "status": "reviewed", "quality_gate": {"quality_score": 0.42}},
            ]
        }
        report = _build_agent_wiki_bootstrap_quality_report(plan_pages=plan_pages, page_result=page_result)
        self.assertEqual(report["mode"], "applied")
        self.assertGreaterEqual(int(report["core_pages"]["planned"]), 2)
        self.assertGreaterEqual(int(report["core_pages"]["published"]), 1)
        self.assertGreaterEqual(int(report["core_pages"]["reviewed"]), 1)
        self.assertIn("page_importance", report)
        self.assertIn("priority_backlog", report["core_pages"])
        self.assertEqual(report["core_pages"]["priority_backlog"][0]["slug"], "operations/data-sources-catalog")

    def test_agent_capability_bootstrap_page_uses_bundle_signals(self) -> None:
        assert _api_main is not None

        class _BundleAwareCursor:
            def __init__(self) -> None:
                self.mode = "none"

            def execute(self, sql: str, params=None) -> None:
                text = str(sql)
                if "FROM evidence_bundles b" in text:
                    self.mode = "bundles"
                else:
                    self.mode = "none"

            def fetchall(self):
                if self.mode == "bundles":
                    return [
                        (
                            "bundle-1",
                            "capability:dispatch_bot",
                            "capability",
                            "agent_profile",
                            "dispatch_bot",
                            "ready",
                            3,
                            1,
                            2,
                            2,
                            0.88,
                            datetime(2026, 5, 2, 12, 0, tzinfo=UTC),
                            {"claim_entity_key": "dispatch_bot"},
                            [
                                {
                                    "claim_text": "Dispatch bot can reroute deliveries but needs approval for address override.",
                                    "category": "operations",
                                    "metadata": {},
                                }
                            ],
                        )
                    ]
                return []

        original_agent_directory_exists = _api_main._agent_directory_table_exists_from_cursor
        original_runtime_matrix = _api_main._build_runtime_agent_capability_matrix
        original_get_orgchart = _api_main.get_agent_orgchart
        original_table_exists = _api_main._wiki_feature_table_exists
        try:
            _api_main._agent_directory_table_exists_from_cursor = lambda cur: False
            _api_main._build_runtime_agent_capability_matrix = lambda cur, project_id, max_agents: [
                {
                    "agent_id": "dispatch_bot",
                    "display_name": "Dispatch Bot",
                    "team": "Dispatch",
                    "role": "Coordinator",
                    "status": "active",
                    "confidence": 0.82,
                    "typical_actions": ["reroute delivery"],
                    "escalation_rules": ["address override requires approval"],
                    "tools": ["maps_router"],
                    "data_sources": ["orders_api"],
                    "limits": ["cannot change billing"],
                    "scenario_examples": ["route blocker"],
                    "observed_strengths": ["Use address override only after dispatcher approval."],
                    "observed_actions": ["reroute delivery and notify dispatch"],
                    "observed_questions": ["When should address override bypass normal queue?"],
                    "observed_uncertainties": ["Courier handoff policy differs after 18:00."],
                    "observed_decisions": ["Approved same-day reroute for gated access incidents."],
                    "latest_reflection_summary": "Dispatch bot summarized the reroute workflow and captured approval boundary.",
                    "latest_reflection_outcome": "resolved with approval",
                    "reflection_count": 2,
                }
            ]
            _api_main.get_agent_orgchart = lambda **kwargs: {
                "nodes": [
                    {
                        "agent_id": "dispatch_bot",
                        "display_name": "Dispatch Bot",
                        "team": "Dispatch",
                        "role": "Coordinator",
                        "status": "active",
                        "profile_slug": "agents/dispatch_bot",
                    }
                ],
                "edges": [],
                "teams": [{"team": "Dispatch", "agents_total": 1}],
            }
            _api_main._wiki_feature_table_exists = lambda cur, table: table in {
                "public.evidence_bundles",
                "public.evidence_bundle_claim_links",
                "public.claims",
            }
            pages = _build_agent_capability_bootstrap_page(
                _BundleAwareCursor(),
                project_id="omega_demo",
                space_key="operations",
                max_agents=10,
            )
        finally:
            _api_main._agent_directory_table_exists_from_cursor = original_agent_directory_exists
            _api_main._build_runtime_agent_capability_matrix = original_runtime_matrix
            _api_main.get_agent_orgchart = original_get_orgchart
            _api_main._wiki_feature_table_exists = original_table_exists

        markdown = str(pages[0].get("markdown") or "")
        self.assertIn("## Bundle Signals", markdown)
        self.assertIn("capability:dispatch_bot", markdown)
        self.assertIn("Bundle evidence: ready 1 / candidate 0", markdown)
        self.assertIn("Dispatch bot can reroute deliveries", markdown)
        self.assertIn("Durable rules learned: Use address override only after dispatcher approval.", markdown)
        self.assertIn("Latest debrief: Dispatch bot summarized the reroute workflow", markdown)
        self.assertIn("Missing documentation questions: When should address override bypass normal queue?", markdown)

    def test_bootstrap_page_importance_prioritizes_core_onboarding_pages(self) -> None:
        agent_page = _bootstrap_page_importance(
            slug="operations/agent-capability-profile",
            page_type="agent_profile",
        )
        digest_page = _bootstrap_page_importance(
            slug="operations/daily-operations-digest",
            page_type="operations",
        )
        self.assertGreater(int(agent_page["priority"]), int(digest_page["priority"]))
        self.assertEqual(agent_page["label"], "critical")

    def test_bootstrap_publish_notice_makes_forced_core_publish_explicit(self) -> None:
        markdown = "# Agent Capability Profile\n\n## Orgchart\n- dispatch_bot\n"
        notice = _prepend_bootstrap_publish_notice(
            markdown,
            title="Agent Capability Profile",
            importance=_bootstrap_page_importance(
                slug="operations/agent-capability-profile",
                page_type="agent_profile",
            ),
            quality_assessment={
                "quality_score": 0.44,
                "missing_required_markers": ["## Capability Matrix"],
                "placeholder_hits": ["runtime discovery pending"],
            },
        )
        self.assertIn("Bootstrap note:", notice)
        self.assertIn("high-priority onboarding knowledge", notice)
        self.assertIn("Missing signals to enrich next: ## Capability Matrix.", notice)
        self.assertIn("Placeholder-like content still present: runtime discovery pending.", notice)

    def test_daily_summary_draft_detector_uses_gatekeeper_and_text_signals(self) -> None:
        by_feature = _is_daily_summary_like_draft_row(
            page_slug="operations/dispatch-log",
            page_title="Dispatch Log",
            page_entity_key="dispatch",
            markdown_patch="minor update",
            semantic_diff={},
            gatekeeper_features={"has_daily_summary_noise": True},
        )
        self.assertTrue(by_feature)

        by_text = _is_daily_summary_like_draft_row(
            page_slug="operations/daily-log",
            page_title="Daily Operations Summary",
            page_entity_key="ops_daily",
            markdown_patch="Daily summary for 2026-04-10: processed 42 orders.",
            semantic_diff={},
            gatekeeper_features={},
        )
        self.assertTrue(by_text)

        negative = _is_daily_summary_like_draft_row(
            page_slug="operations/process-playbooks",
            page_title="Process Playbooks",
            page_entity_key="processes",
            markdown_patch="Escalate billing incidents to L2 within 15 minutes.",
            semantic_diff={},
            gatekeeper_features={"ingestion_classification": "evergreen_knowledge"},
        )
        self.assertFalse(negative)

    def test_project_wiki_quality_report_from_rows_applies_acceptance_thresholds(self) -> None:
        published_pages = [
            {
                "slug": "operations/agent-capability-profile",
                "title": "Agent Capability Profile",
                "markdown": "# Agent Capability Profile\n\n## Role\nThis agent handles routing policy and execution control with incident guardrails.",
            },
            {
                "slug": "operations/data-sources-catalog",
                "title": "Data Sources Catalog",
                "markdown": "# Data Sources Catalog\n\n## Sources\nOrders API, CRM, dispatch DB with ownership and freshness metadata.",
            },
            {
                "slug": "operations/tooling-map",
                "title": "Tooling Map",
                "markdown": "# Tooling Map\n\n## Guardrails\nTool permissions, escalation triggers, and approval boundaries.",
            },
            {
                "slug": "operations/process-playbooks",
                "title": "Process Playbooks",
                "markdown": "# Process Playbooks\n\n## Escalation\nWhen SLA risk persists for 15m, page on-call and notify dispatch lead.",
            },
            {
                "slug": "operations/company-operating-context",
                "title": "Company Operating Context",
                "markdown": "# Company Operating Context\n\n## Domain Snapshot\nB2B logistics with strict yard-access and compliance windows.",
            },
            {
                "slug": "operations/operational-logic-map",
                "title": "Operational Logic Map",
                "markdown": "# Operational Logic Map\n\n## Signal -> Action\nAccess issue signal maps to escalation and fallback delivery flow.",
            },
        ]
        open_drafts = [
            {
                "draft_id": "d1",
                "page_slug": "operations/daily-log",
                "page_title": "Daily Summary",
                "is_daily_summary_like": True,
            },
            {
                "draft_id": "d2",
                "page_slug": "operations/process-playbooks",
                "page_title": "Process Playbooks",
                "is_daily_summary_like": False,
            },
        ]
        report = _build_project_wiki_quality_report_from_rows(
            project_id="omega_demo",
            published_pages=published_pages,
            open_drafts=open_drafts,
            window_days=14,
            placeholder_ratio_max=0.10,
            daily_summary_draft_ratio_max=0.20,
            min_core_published=6,
        )
        checks = report.get("quality", {}).get("checks") if isinstance(report.get("quality"), dict) else {}
        self.assertFalse(bool(report.get("quality", {}).get("pass")))
        self.assertTrue(bool(checks.get("core_required_pages_present")))
        self.assertTrue(bool(checks.get("core_publish_coverage")))
        self.assertFalse(bool(checks.get("daily_summary_open_draft_ratio")))

    def test_project_wiki_richness_benchmark_detects_thin_bootstrap_pages(self) -> None:
        published_pages = [
            {
                "slug": "operations/agent-capability-profile",
                "title": "Agent Capability Profile",
                "page_type": "agent_profile",
                "markdown": "# Agent Capability Profile\n\n## Orgchart\n- runtime discovery pending\n",
            },
            {
                "slug": "operations/data-sources-catalog",
                "title": "Data Sources Catalog",
                "page_type": "data_map",
                "markdown": "# Data Sources Catalog\n\n## Governance\n- n/a\n",
            },
            {
                "slug": "operations/tooling-map",
                "title": "Tooling Map",
                "page_type": "operations",
                "markdown": "# Tooling Map\n\n## Registry\n- n/a\n",
            },
            {
                "slug": "operations/process-playbooks",
                "title": "Process Playbooks",
                "page_type": "runbook",
                "markdown": "# Process Playbooks\n\n## Playbook Index\n- pending\n",
            },
            {
                "slug": "operations/company-operating-context",
                "title": "Company Operating Context",
                "page_type": "operations",
                "markdown": "# Company Operating Context\n\n## Snapshot\n- pending\n",
            },
            {
                "slug": "operations/operational-logic-map",
                "title": "Operational Logic Map",
                "page_type": "operations",
                "markdown": "# Operational Logic Map\n\n## Signal -> Action\n- pending\n",
            },
        ]
        benchmark = _build_project_wiki_richness_benchmark_from_rows(
            project_id="omega_demo",
            published_pages=published_pages,
            open_drafts=[],
            window_days=14,
            placeholder_ratio_max=0.10,
            daily_summary_draft_ratio_max=0.20,
            min_core_published=6,
            min_contract_pass_ratio=0.80,
            min_average_page_score=0.72,
        )
        self.assertFalse(bool(benchmark.get("pass")))
        self.assertFalse(bool((benchmark.get("checks") or {}).get("page_contract_pass_ratio")))
        self.assertLess(float((benchmark.get("scores") or {}).get("average_page_score") or 0.0), 0.72)

    def test_project_wiki_richness_benchmark_passes_for_grounded_core_pages(self) -> None:
        published_pages = [
            {
                "slug": "operations/agent-capability-profile",
                "title": "Agent Capability Profile",
                "page_type": "agent_profile",
                "markdown": (
                    "# Agent Capability Profile\n\n## Orgchart\n- Dispatch Bot (`dispatch_bot`) | Dispatch | Coordinator | active | [Open](/wiki/agents/dispatch_bot)\n\n"
                    "## Capability Matrix\n- Dispatch Bot routes deliveries and escalates access blockers.\n\n"
                    "## Capability Signals\n- Runtime actions and tool use are captured.\n\n"
                    "## Handoffs\n- Dispatch -> Billing for approval-sensitive reroutes.\n\n"
                    "### Dispatch Bot (`dispatch_bot`)\n"
                    "- Team / Role: Dispatch / Coordinator\n"
                    "- Typical actions: reroute delivery; resolve access blockers\n"
                    "- Escalation rules: escalate after 15 minutes\n"
                    "- Toolset: maps_router, ticketing\n"
                    "- Data sources: orders_api, warehouse_access_rules\n"
                    "- Constraints: cannot change billing\n"
                    "- Scenario examples: route blocker near gated site\n"
                ),
            },
            {
                "slug": "operations/data-sources-catalog",
                "title": "Data Sources Catalog",
                "page_type": "data_map",
                "markdown": (
                    "# Data Sources Catalog\n\n"
                    "| Source | Type | Location | Owner | Freshness | Key Fields | Used By Agents | Capability / Process Impact |\n"
                    "|---|---|---|---|---|---|---|---|\n"
                    "| [orders_api](/wiki/operations/source-orders-api) | postgres_sql | `orders` | ops_manager | 5m | order_id, customer_id | dispatch_bot | Dispatch escalation |\n\n"
                    "## Durable Source Signals\n- orders_api drives dispatch escalation and reroute decisions.\n\n"
                    "## Governance\n- Validate ownership and freshness before promotion.\n"
                ),
            },
            {
                "slug": "operations/tooling-map",
                "title": "Tooling Map",
                "page_type": "operations",
                "markdown": "# Tooling Map\n\n## Registry\n| Tool | Used By Agents | Purpose / Scenario | Guardrails |\n|---|---|---|---|\n| `maps_router` | dispatch_bot | reroute delivery | approval for billing-affecting changes |\n\n## Governance\n- Policy-backed execution only.\n",
            },
            {
                "slug": "operations/process-playbooks",
                "title": "Process Playbooks",
                "page_type": "runbook",
                "markdown": (
                    "# Process Playbooks\n\n## Playbook Index\n| Playbook | Area | Trigger | Escalation |\n|---|---|---|---|\n| Dispatch Escalation | `operations` | gated access failure | notify on-call |\n\n"
                    "## Canonical Runbooks\n\n### 1. Dispatch Escalation\n"
                    "- Purpose: keep deliveries moving when access rules fail\n"
                    "- Trigger: gated access failure persists for 15 minutes\n"
                    "- Inputs: orders_api; warehouse_access_rules\n"
                    "- Steps:\n  - confirm access rule\n  - attempt approved reroute\n"
                    "- Exceptions:\n  - if billing impact exists, request approval\n"
                    "- Outputs: reroute plan and incident note\n"
                    "- Escalation: notify on-call in #ops-escalation\n"
                    "- Tools used: maps_router, ticketing\n"
                    "- Source evidence: claims + bundle evidence\n\n"
                    "## How To Use\n1. Validate inputs.\n2. Follow sequence.\n3. Escalate on low confidence.\n"
                ),
            },
            {
                "slug": "operations/company-operating-context",
                "title": "Company Operating Context",
                "page_type": "operations",
                "markdown": (
                    "# Company Operating Context\n\n## Snapshot\n- B2B logistics with gated access workflows.\n"
                    "## Team Topology\n- Dispatch, Billing, Warehouse Ops.\n"
                    "## Data Backbone\n- orders_api, warehouse_access_rules, ticketing.\n"
                    "## Core Operating Principles\n- Escalate low-confidence changes.\n- Prefer policy-backed execution.\n- Protect billing-sensitive actions.\n"
                ),
            },
            {
                "slug": "operations/operational-logic-map",
                "title": "Operational Logic Map",
                "page_type": "operations",
                "markdown": "# Operational Logic Map\n\n## Signal -> Action\n- Access issue signal maps to reroute attempt and on-call escalation.\n## Escalation Rules\n- Notify dispatch lead after 15 minutes.\n",
            },
        ]
        benchmark = _build_project_wiki_richness_benchmark_from_rows(
            project_id="omega_demo",
            published_pages=published_pages,
            open_drafts=[],
            window_days=14,
            placeholder_ratio_max=0.10,
            daily_summary_draft_ratio_max=0.20,
            min_core_published=6,
            min_contract_pass_ratio=0.60,
            min_average_page_score=0.50,
        )
        self.assertTrue(bool(benchmark.get("pass")))
        self.assertTrue(bool((benchmark.get("checks") or {}).get("page_contract_pass_ratio")))

    def test_agent_reflection_claim_builder_emits_rules_decisions_and_capability_summary(self) -> None:
        payload = AgentReflectionSubmitRequest(
            project_id="omega_demo",
            agent_id="dispatch_bot",
            reflected_by="dispatch_bot",
            task_id="task-1",
            summary="Handled gated access blocker and learned new escalation rule.",
            learned_rules=["If gated access fails for 15 minutes, escalate to on-call dispatch owner."],
            decisions_made=["Approved reroute via alternate loading bay after warehouse confirmation."],
            tools_used=["maps_router"],
            data_sources_used=["orders_api"],
            follow_up_actions=["Document alternate loading bay fallback."],
            insights=[
                {
                    "claim_text": "Dispatch bot can reroute deliveries but cannot override billing.",
                    "category": "capability",
                    "confidence": 0.88,
                    "temporary": False,
                    "evidence": [],
                    "metadata": {},
                }
            ],
        )
        claims = _build_agent_reflection_claim_payloads(
            payload,
            observed_at=datetime(2026, 5, 2, 12, 0, tzinfo=UTC),
        )
        categories = [str(item.get("category") or "") for item in claims]
        self.assertIn("process", categories)
        self.assertIn("decision", categories)
        self.assertTrue(any(str((item.get("metadata") or {}).get("reflection_kind") or "") == "capability_summary" for item in claims))

    def test_page_type_freshness_thresholds_prefer_semantic_defaults(self) -> None:
        policy = _page_type_freshness_thresholds(
            page_type="policy",
            fallback_stale_days=10,
            fallback_critical_days=20,
            page_type_aware=True,
        )
        data_map = _page_type_freshness_thresholds(
            page_type="data_map",
            fallback_stale_days=10,
            fallback_critical_days=20,
            page_type_aware=True,
        )
        global_mode = _page_type_freshness_thresholds(
            page_type="policy",
            fallback_stale_days=10,
            fallback_critical_days=20,
            page_type_aware=False,
        )
        self.assertEqual(policy["stale_days"], 3)
        self.assertEqual(data_map["stale_days"], 14)
        self.assertEqual(global_mode["stale_days"], 10)

    def test_human_guided_synthesis_prompts_use_knowledge_gaps(self) -> None:
        assert _api_main is not None
        original_gap_report = _api_main._build_adoption_knowledge_gap_report
        try:
            _api_main._build_adoption_knowledge_gap_report = lambda **kwargs: {
                "candidate_knowledge_bundles": [
                    {
                        "bundle_key": "process:dispatch_bot",
                        "bundle_type": "process",
                        "suggested_page_type": "process",
                        "entity_key": "dispatch_bot",
                        "bundle_status": "candidate",
                        "support_count": 3,
                        "quality_score": 0.81,
                    }
                ],
                "unresolved_agent_questions": [{"question": "When should dispatch escalate gated access failures?", "count": 3}],
                "page_enrichment_gaps": [
                    {
                        "leaf": "process-playbooks",
                        "slug": "operations/process-playbooks",
                        "score": 0.42,
                        "missing_sections": ["## Canonical Runbooks", "## How To Use"],
                    }
                ],
            }
            prompts = _build_human_guided_synthesis_prompts(
                project_id="omega_demo",
                days=14,
                max_items=5,
            )
        finally:
            _api_main._build_adoption_knowledge_gap_report = original_gap_report

        items = prompts.get("prompts") if isinstance(prompts.get("prompts"), list) else []
        self.assertGreaterEqual(len(items), 3)
        self.assertTrue(any(str(item.get("prompt_type") or "") == "bundle_follow_up" for item in items if isinstance(item, dict)))
        self.assertTrue(any(str(item.get("prompt_type") or "") == "repeated_question" for item in items if isinstance(item, dict)))
        self.assertTrue(any(str(item.get("prompt_type") or "") == "page_enrichment" for item in items if isinstance(item, dict)))
        bundle_prompt = next(
            item for item in items if isinstance(item, dict) and str(item.get("prompt_type") or "") == "bundle_follow_up"
        )
        self.assertTrue(bool(bundle_prompt.get("why_now")))
        self.assertTrue(bool(bundle_prompt.get("expected_sections")))
        summary = prompts.get("summary") if isinstance(prompts.get("summary"), dict) else {}
        by_type = summary.get("by_type") if isinstance(summary.get("by_type"), dict) else {}
        self.assertEqual(int(by_type.get("bundle_follow_up") or 0), 1)

    def test_quality_report_v2_surfaces_reviewed_backlog_and_missing_signals(self) -> None:
        report = _build_project_wiki_quality_report_from_rows(
            project_id="omega_demo",
            published_pages=[
                {
                    "slug": "operations/agent-capability-profile",
                    "title": "Agent Capability Profile",
                    "page_type": "agent_profile",
                    "markdown": "# Agent Capability Profile\n\n## Orgchart\n- Dispatch Bot\n\n## Capability Matrix\n- Routes deliveries.\n\n## Capability Signals\n- Uses maps_router.\n\n## Handoffs\n- Billing handoff.",
                }
            ],
            open_drafts=[],
            reviewed_pages=[
                {
                    "slug": "operations/process-playbooks",
                    "title": "Process Playbooks",
                    "page_type": "runbook",
                    "markdown": "# Process Playbooks\n\n## Playbook Index\n- pending\n",
                    "metadata": {
                        "bootstrap_quality_gate": {
                            "quality_score": 0.31,
                            "publish_warning": "missing_process_structure",
                            "missing_required_markers": ["steps", "exceptions", "escalation"],
                            "placeholder_hits": ["pending"],
                        }
                    },
                }
            ],
            window_days=14,
            placeholder_ratio_max=0.10,
            daily_summary_draft_ratio_max=0.20,
            min_core_published=1,
        )
        self.assertEqual(int(report.get("core_pages", {}).get("reviewed_total") or 0), 1)
        self.assertTrue(bool(report.get("reviewed_core_backlog")))
        self.assertTrue(any(str(item.get("signal") or "") == "steps" for item in (report.get("signals_missing") or [])))
        self.assertTrue(any(str(item.get("page_type") or "") == "runbook" for item in (report.get("weak_page_families") or [])))

    def test_first_run_ai_employee_org_profile_includes_agent_org_pages(self) -> None:
        pages = _build_first_run_starter_pages("ai_employee_org", space_key="operations", include_decisions_log=True)
        slugs = {str(item.get("slug") or "") for item in pages}
        self.assertIn("operations/tool-catalog", slugs)
        self.assertIn("operations/scheduled-tasks", slugs)
        self.assertIn("operations/human-in-the-loop-rules", slugs)
        self.assertIn("operations/integrations-map", slugs)
        self.assertIn("operations/escalation-rules", slugs)

    def test_generic_ops_pack_builds_ai_employee_org_starter_pages(self) -> None:
        pages = get_synthesis_pack("generic_ops").build_first_run_starter_pages(
            "ai_employee_org",
            space_key="operations",
            include_decisions_log=True,
            normalize_space_key=lambda value: _api_main._normalize_space_key(value, default=""),
            space_slug=_api_main._space_slug,
            build_decisions_log_seed_page=_api_main._build_decisions_log_seed_page,
        )
        slugs = {str(item.get("slug") or "") for item in pages}
        self.assertIn("operations/tool-catalog", slugs)
        self.assertIn("operations/scheduled-tasks", slugs)

    def test_generic_ops_pack_exposes_logistics_template_defaults(self) -> None:
        templates = get_synthesis_pack("generic_ops").wiki_space_template_catalog()
        logistics = next(item for item in templates if str(item.get("template_key")) == "logistics_ops")
        self.assertEqual(logistics["default_space_key"], "logistics")

    def test_signal_noise_audit_aggregates_quality_and_bundle_health(self) -> None:
        assert _api_main is not None
        original_pipeline = _api_main.get_adoption_pipeline_visibility
        original_quality = _api_main._build_project_wiki_quality_report
        original_benchmark = _api_main._build_project_wiki_richness_benchmark
        original_gap_report = _api_main._build_adoption_knowledge_gap_report
        original_rejections = _api_main.get_adoption_rejection_diagnostics
        original_get_conn = _api_main.get_conn
        original_table_exists = _api_main._wiki_feature_table_exists
        original_public_exists = _api_main._public_table_exists
        try:
            _api_main.get_adoption_pipeline_visibility = lambda **kwargs: {
                "pipeline": {"accepted": 100, "events": 50, "claims": 12, "drafts": 4, "pages": 3},
                "signal_noise_ratio": {"signal_claims_per_event": 0.24},
                "extraction": {"drop_reasons": [{"reason": "event_like_low_signal", "count": 40}]},
                "warnings": [],
                "bottleneck": {"from_stage": "events", "to_stage": "claims"},
                "rejected_event_like": 60,
                "stages": [],
                "conversions": {},
            }
            _api_main._build_project_wiki_quality_report = lambda **kwargs: {
                "quality": {"pass": False, "checks": {"core_publish_coverage": False}},
                "content_quality": {"placeholder_ratio_core": 0.12},
                "weak_page_families": [{"page_type": "runbook", "count": 2}],
                "signals_missing": [{"signal": "steps", "count": 2}],
                "reviewed_core_backlog": [{"slug": "operations/process-playbooks"}],
            }
            _api_main._build_project_wiki_richness_benchmark = lambda **kwargs: {
                "pass": False,
                "checks": {"average_page_score": False},
                "scores": {"average_page_score": 0.41},
            }
            _api_main._build_adoption_knowledge_gap_report = lambda **kwargs: {
                "candidate_knowledge_bundles": [{"bundle_key": "process:dispatch"}],
                "page_enrichment_gaps": [{"slug": "operations/process-playbooks"}],
                "unresolved_agent_questions": [{"question": "When to escalate?"}],
            }
            _api_main.get_adoption_rejection_diagnostics = lambda **kwargs: {
                "top_blocked_patterns": {
                    "source_types": [{"key": "external_event", "count": 20}],
                    "source_systems": [{"key": "wand_sheet", "count": 10}],
                    "tool_names": [{"key": "memory_backfill", "count": 8}],
                },
                "top_preclaim_drop_reasons": [{"key": "event_like_low_signal", "count": 40}],
            }

            class _Cursor:
                def __init__(self) -> None:
                    self.mode = "none"
                def execute(self, sql: str, params=None) -> None:
                    text = str(sql)
                    if "FROM evidence_bundles" in text:
                        self.mode = "bundles"
                    elif "FROM wiki_pages" in text:
                        self.mode = "pages"
                    else:
                        self.mode = "none"
                def fetchall(self):
                    if self.mode == "bundles":
                        return [
                            ("ready", "procedural", "process_playbook", 3),
                            ("candidate", "semantic", "agent_profile", 2),
                        ]
                    if self.mode == "pages":
                        return [
                            ("runbook", "published", 2),
                            ("agent_profile", "reviewed", 1),
                        ]
                    return []
                def __enter__(self):
                    return self
                def __exit__(self, exc_type, exc, tb):
                    return False

            class _Conn:
                def cursor(self):
                    return _Cursor()
                def __enter__(self):
                    return self
                def __exit__(self, exc_type, exc, tb):
                    return False

            _api_main.get_conn = lambda: _Conn()
            _api_main._wiki_feature_table_exists = lambda cur, table: True
            _api_main._public_table_exists = lambda conn, table: True

            audit = _build_adoption_signal_noise_audit(project_id="omega_demo", days=14, max_items_per_bucket=4)
        finally:
            _api_main.get_adoption_pipeline_visibility = original_pipeline
            _api_main._build_project_wiki_quality_report = original_quality
            _api_main._build_project_wiki_richness_benchmark = original_benchmark
            _api_main._build_adoption_knowledge_gap_report = original_gap_report
            _api_main.get_adoption_rejection_diagnostics = original_rejections
            _api_main.get_conn = original_get_conn
            _api_main._wiki_feature_table_exists = original_table_exists
            _api_main._public_table_exists = original_public_exists

        self.assertIn("summary", audit)
        self.assertEqual(int(audit.get("bundles", {}).get("total") or 0), 5)
        self.assertTrue(bool(audit.get("quality", {}).get("report", {}).get("weak_page_families")))
        self.assertTrue(bool(audit.get("top_noisy_source_families", {}).get("source_types")))

    def test_stability_monitor_merges_pipeline_and_safe_mode_audit(self) -> None:
        assert _api_main is not None
        original_pipeline = _api_main.get_adoption_pipeline_visibility
        original_audit = _api_main._build_adoption_signal_noise_audit
        original_safe_mode_events = _api_main._list_adoption_safe_mode_audit_events
        try:
            _api_main.get_adoption_pipeline_visibility = lambda **kwargs: {
                "warnings": [
                    {
                        "code": "events_claims_zero_floor",
                        "severity": "critical",
                        "message": "Events are flowing but claims remain zero.",
                    }
                ],
                "bottleneck": {"from_stage": "events", "to_stage": "claims"},
                "claims_floor_guard": {"triggered": True, "events_total": 220, "claims_total": 0},
                "draft_flood_guard": {"max_open_per_page": 0, "max_open_per_entity": 0, "thresholds": {}},
            }
            _api_main._build_adoption_signal_noise_audit = lambda **kwargs: {
                "summary": {
                    "evidence_rejected_pct": 0.93,
                    "bundle_promotion_ratio": 0.05,
                    "placeholder_ratio_core": 0.18,
                },
                "bundles": {
                    "by_status": [
                        {"status": "candidate", "count": 9},
                        {"status": "ready", "count": 1},
                    ]
                },
                "quality": {
                    "report": {"pass": False, "checks": {"core_publish_coverage": False}},
                    "richness_benchmark": {"pass": False, "scores": {"average_page_score": 0.44}},
                },
                "top_noisy_source_families": {"source_types": [{"key": "external_event", "count": 30}]},
            }
            _api_main._list_adoption_safe_mode_audit_events = lambda **kwargs: [
                {
                    "id": 41,
                    "action": "adoption_safe_mode_recommended",
                    "actor": "ops_admin",
                    "reason": "queue pressure",
                    "payload": {},
                    "created_at": "2026-05-03T10:00:00+00:00",
                }
            ]
            monitor = _build_adoption_signal_noise_stability_monitor(
                project_id="omega_demo",
                days=14,
                max_items_per_bucket=4,
            )
        finally:
            _api_main.get_adoption_pipeline_visibility = original_pipeline
            _api_main._build_adoption_signal_noise_audit = original_audit
            _api_main._list_adoption_safe_mode_audit_events = original_safe_mode_events

        self.assertEqual(str(monitor.get("status") or ""), "critical")
        self.assertTrue(bool((monitor.get("safe_mode") or {}).get("latest_recommendation")))
        self.assertTrue(any(str(item.get("code") or "") == "bundle_promotion_backlog" for item in (monitor.get("alerts") or [])))
        self.assertEqual(str((monitor.get("safe_mode") or {}).get("state") or ""), "recommended")

    def test_runtime_agent_sql_expr_and_filter_include_payload_fallbacks(self) -> None:
        expr = _runtime_agent_id_sql_expr(table_alias="e")
        self.assertIn("e.payload->>'agent_id'", expr)
        self.assertIn("e.payload#>>'{metadata,agent_id}'", expr)
        self.assertIn("e.payload#>>'{agent,id}'", expr)

        runtime_filter = _runtime_agent_filter_sql(column="runtime_agent_id")
        self.assertIn("runtime_agent_id !~ '@'", runtime_filter)
        self.assertIn("NOT IN", runtime_filter)

    def test_runtime_capability_matrix_uses_payload_agent_fallback_in_queries(self) -> None:
        assert _api_main is not None

        class _RuntimeCursor:
            def __init__(self) -> None:
                self.mode = "none"
                self.sql: list[str] = []

            def execute(self, sql: str, params=None) -> None:
                text = str(sql)
                self.sql.append(text)
                if "GROUP BY runtime_agent_id" in text:
                    self.mode = "agents"
                elif "GROUP BY e.event_type" in text:
                    self.mode = "events"
                elif "GROUP BY tool_name" in text:
                    self.mode = "tools"
                elif "GROUP BY source_name" in text:
                    self.mode = "sources"
                else:
                    self.mode = "none"

            def fetchall(self):
                if self.mode == "agents":
                    return [("dispatch_bot", 12, 3, datetime(2026, 4, 10, 12, 0, tzinfo=UTC))]
                if self.mode == "events":
                    return [("dispatch_task_started", 8)]
                if self.mode == "tools":
                    return [("maps_router", 5)]
                if self.mode == "sources":
                    return [("orders_api", 4)]
                return []

        cursor = _RuntimeCursor()
        original_table_exists = _api_main._wiki_feature_table_exists
        try:
            _api_main._wiki_feature_table_exists = lambda cur, table: False
            matrix = _build_runtime_agent_capability_matrix(
                cursor,
                project_id="omega_demo",
                max_agents=10,
            )
        finally:
            _api_main._wiki_feature_table_exists = original_table_exists

        self.assertEqual(len(matrix), 1)
        self.assertEqual(matrix[0]["agent_id"], "dispatch_bot")
        combined_sql = "\n".join(cursor.sql)
        self.assertIn("payload->>'agent_id'", combined_sql)
        self.assertIn("payload#>>'{metadata,agent_id}'", combined_sql)
        self.assertNotIn("COALESCE(trim(agent_id), '') <> ''", combined_sql)

    def test_collect_agent_source_usage_uses_runtime_agent_inference(self) -> None:
        assert _api_main is not None

        class _SourceUsageCursor:
            def __init__(self) -> None:
                self.mode = "none"
                self.sql: list[str] = []

            def execute(self, sql: str, params=None) -> None:
                text = str(sql)
                self.sql.append(text)
                if "FROM agent_directory_profiles" in text:
                    self.mode = "profiles"
                elif "FROM runtime_events" in text and "source_name" in text:
                    self.mode = "events"
                else:
                    self.mode = "none"

            def fetchall(self):
                if self.mode == "profiles":
                    return []
                if self.mode == "events":
                    return [("dispatch_bot", "orders_api", "dispatch", "maps_router")]
                return []

        cursor = _SourceUsageCursor()
        original_table_exists = _api_main._wiki_feature_table_exists
        try:
            _api_main._wiki_feature_table_exists = lambda cur, table: table == "public.events"
            usage = _collect_agent_source_usage(cursor, project_id="omega_demo")
        finally:
            _api_main._wiki_feature_table_exists = original_table_exists

        self.assertIn("orders_api", usage)
        self.assertIn("dispatch_bot", usage["orders_api"]["agents"])
        combined_sql = "\n".join(cursor.sql)
        self.assertIn("runtime_agent_id", combined_sql)
        self.assertIn("payload->>'agent_id'", combined_sql)
        self.assertIn("payload#>>'{metadata,agent_id}'", combined_sql)

    def test_collect_agent_source_usage_keeps_capability_and_process_hints(self) -> None:
        assert _api_main is not None

        class _ProfileUsageCursor:
            def __init__(self) -> None:
                self.mode = "none"

            def execute(self, sql: str, params=None) -> None:
                text = str(sql)
                if "FROM agent_directory_profiles" in text:
                    self.mode = "profiles"
                else:
                    self.mode = "none"

            def fetchall(self):
                if self.mode == "profiles":
                    return [
                        (
                            "dispatch_bot",
                            ["orders_api"],
                            ["Plans dispatch routes"],
                            ["maps_router"],
                            {
                                "scenarios": ["dispatch route planning"],
                                "processes": ["Dispatch escalation"],
                                "allowed_actions": ["reroute_delivery"],
                            },
                        )
                    ]
                return []

        cursor = _ProfileUsageCursor()
        original_table_exists = _api_main._wiki_feature_table_exists
        try:
            _api_main._wiki_feature_table_exists = lambda cur, table: table == "public.agent_directory_profiles"
            usage = _collect_agent_source_usage(cursor, project_id="omega_demo")
        finally:
            _api_main._wiki_feature_table_exists = original_table_exists

        bucket = usage["orders_api"]
        self.assertIn("dispatch_bot", bucket["agents"])
        self.assertIn("Plans dispatch routes", bucket["capabilities"])
        self.assertIn("reroute_delivery", bucket["actions"])
        self.assertIn("Dispatch escalation", bucket["processes"])
        self.assertIn("maps_router", bucket["tools"])

    def test_collect_agent_source_usage_reads_source_bindings_from_metadata(self) -> None:
        assert _api_main is not None

        class _BindingUsageCursor:
            def __init__(self) -> None:
                self.mode = "none"

            def execute(self, sql: str, params=None) -> None:
                text = str(sql)
                if "FROM agent_directory_profiles" in text:
                    self.mode = "profiles"
                else:
                    self.mode = "none"

            def fetchall(self):
                if self.mode == "profiles":
                    return [
                        (
                            "ops_bot",
                            [],
                            ["Coordinates logistics workflow"],
                            ["dispatch_console"],
                            {
                                "scenarios": ["warehouse sync"],
                                "source_bindings": [{"source": "warehouse_sheet"}],
                                "standing_orders": ["Warehouse intake reconciliation"],
                                "allowed_actions": ["reconcile_inventory"],
                            },
                        )
                    ]
                return []

        cursor = _BindingUsageCursor()
        original_table_exists = _api_main._wiki_feature_table_exists
        try:
            _api_main._wiki_feature_table_exists = lambda cur, table: table == "public.agent_directory_profiles"
            usage = _collect_agent_source_usage(cursor, project_id="omega_demo")
        finally:
            _api_main._wiki_feature_table_exists = original_table_exists

        bucket = usage["warehouse_sheet"]
        self.assertIn("ops_bot", bucket["agents"])
        self.assertIn("Coordinates logistics workflow", bucket["capabilities"])
        self.assertIn("Warehouse intake reconciliation", bucket["processes"])
        self.assertIn("reconcile_inventory", bucket["actions"])

    def test_generic_ops_pack_can_infer_source_usage_from_runtime_matrix(self) -> None:
        assert _api_main is not None
        inferred = get_synthesis_pack("generic_ops").infer_source_usage_from_matrix(
            matrix_rows=[
                {
                    "agent_id": "logistics-assistant",
                    "status": "active",
                    "running_instances": 6,
                    "responsibilities": ["documents_orders"],
                    "standing_orders": ["daily report"],
                    "scheduled_tasks": ["standing_order.logistics.daily_report"],
                    "allowed_actions": ["outbound_messaging"],
                    "tools": ["kb_search"],
                    "scenario_examples": ["driver docs readiness"],
                    "source_binding_contracts": [
                        {
                            "source": "postgres_sql:memory_items:polling",
                            "capabilities": ["documents_orders"],
                            "processes": ["daily report"],
                        }
                    ],
                }
            ],
            source_ref="postgres_sql:memory_items:polling",
            source_type="postgres_sql",
            config={"sql_profile": "memory_items"},
            normalize_statement_text=_api_main._normalize_statement_text,
        )
        self.assertIn("logistics-assistant", inferred["agents"])
        self.assertIn("documents_orders", inferred["capabilities"])
        self.assertIn("daily report", inferred["processes"])

    def test_render_agent_runbooks_uses_scheduled_task_contracts(self) -> None:
        profile = {
            "agent_id": "logistics-assistant",
            "display_name": "Logistics Assistant",
            "profile_slug": "agents/logistics-assistant",
            "tools": ["kb_search"],
            "data_sources": ["driver_economy_daily_latest"],
            "limits": ["No direct execution outside approved standing orders."],
            "metadata": {
                "scheduled_task_contracts": [
                    {
                        "task_code": "standing_order.logistics.driver_economy_sheet",
                        "builtin_task": "driver_economy_report_to_sheet",
                        "cron_expr": "0 12 * * *",
                        "standing_order_authority": ["logist"],
                    }
                ],
                "source_bindings": ["driver_economy_daily_latest"],
                "approval_rules": ["Escalate if report affects payroll review."],
            },
        }
        markdown = _render_agent_runbooks_markdown(profile=profile)
        self.assertIn("driver_economy_report_to_sheet", markdown)
        self.assertIn("0 12 * * *", markdown)
        self.assertIn("Escalate if report affects payroll review.", markdown)
        self.assertIn("Source: driver_economy_daily_latest", markdown)
        self.assertIn("/wiki/agents/logistics-assistant/runbooks/standing-order-logistics-driver-economy-sheet", markdown)

    def test_scheduled_task_runbook_markdown_uses_concrete_driver_economy_language(self) -> None:
        markdown = _render_agent_scheduled_task_runbook_markdown(
            profile={
                "agent_id": "logistics-assistant",
                "display_name": "Logistics Assistant",
            },
            task_contract={
                "task_code": "standing_order.logistics.driver_economy_sheet",
                "builtin_task": "driver_economy_report_to_sheet",
                "cron_expr": "0 12 * * *",
                "timezone": "Europe/Moscow",
                "standing_order_program": "logistics-default-ops-v1",
                "standing_order_approval_mode": "none",
                "source_hints": ["driver_economy_daily_latest", "driver_shift_daily_latest"],
            },
        )
        self.assertIn("driver economy reporting workflow", markdown.lower())
        self.assertIn("Collect the latest driver economy metrics", markdown)
        self.assertIn("Updated driver economy report/sheet ready for operations or finance review.", markdown)
        self.assertNotIn("runtime task context + bound sources", markdown)

    def test_generic_ops_pack_stays_neutral_for_driver_economy_task(self) -> None:
        assert _api_main is not None
        semantics = get_synthesis_pack("generic_ops").derive_task_semantics(
            {
                "task_code": "standing_order.logistics.driver_economy_sheet",
                "builtin_task": "driver_economy_report_to_sheet",
                "schedule_kind": "cron",
                "cron_expr": "0 12 * * *",
                "source_hints": ["driver_economy_daily_latest"],
            },
            normalize_items=lambda value: _normalize_agent_directory_items(value, limit=6),
            extract_runtime_items=_api_main._runtime_surface_extract_items,
            normalize_statement_text=_api_main._normalize_statement_text,
        )
        self.assertIn("Execute a recurring operational workflow", semantics["purpose"])
        self.assertNotIn("driver economy reporting workflow", semantics["purpose"])

    def test_data_sources_catalog_pages_include_capability_and_process_impact(self) -> None:
        assert _api_main is not None

        class _CatalogCursor:
            def __init__(self) -> None:
                self.mode = "none"

            def execute(self, sql: str, params=None) -> None:
                text = str(sql)
                if "FROM legacy_import_sources" in text:
                    self.mode = "sources"
                else:
                    self.mode = "none"

            def fetchall(self):
                if self.mode == "sources":
                    return [
                        (
                            "postgres_sql",
                            "orders_api",
                            {
                                "sql_dsn_env": "ORDERS_DSN",
                                "sql_table": "orders",
                                "sql_mapping": {
                                    "source_id_field": "id",
                                    "entity_key_field": "customer_id",
                                    "content_field": "summary",
                                },
                            },
                            "ops_manager",
                            datetime(2026, 4, 10, 10, 0, tzinfo=UTC),
                            datetime(2026, 4, 10, 10, 0, tzinfo=UTC),
                        )
                    ]
                return []

        cursor = _CatalogCursor()
        original_table_exists = _api_main._legacy_import_sources_table_exists_from_cursor
        original_collect_usage = _api_main._collect_agent_source_usage
        try:
            _api_main._legacy_import_sources_table_exists_from_cursor = lambda cur: True
            _api_main._collect_agent_source_usage = lambda cur, project_id: {
                "orders_api": {
                    "agents": {"dispatch_bot"},
                    "scenarios": {"dispatch via maps_router"},
                    "capabilities": {"Plans dispatch routes"},
                    "actions": {"reroute_delivery"},
                    "processes": {"Dispatch escalation"},
                    "tools": {"maps_router"},
                }
            }
            pages = _build_data_sources_catalog_pages(
                cursor,
                project_id="omega_demo",
                space_key="operations",
                max_sources=10,
            )
        finally:
            _api_main._legacy_import_sources_table_exists_from_cursor = original_table_exists
            _api_main._collect_agent_source_usage = original_collect_usage

        self.assertGreaterEqual(len(pages), 2)
        catalog_markdown = str(pages[0].get("markdown") or "")
        detail_markdown = str(pages[1].get("markdown") or "")
        self.assertIn("Capability / Process Impact", catalog_markdown)
        self.assertIn("Dispatch escalation", catalog_markdown)
        self.assertIn("Capabilities: Plans dispatch routes", detail_markdown)
        self.assertIn("Actions: reroute_delivery", detail_markdown)
        self.assertIn("Process impact: Dispatch escalation", detail_markdown)

    def test_data_sources_catalog_pages_use_bundle_signals(self) -> None:
        assert _api_main is not None

        class _BundleCatalogCursor:
            def __init__(self) -> None:
                self.mode = "none"

            def execute(self, sql: str, params=None) -> None:
                text = str(sql)
                if "FROM legacy_import_sources" in text:
                    self.mode = "sources"
                elif "FROM evidence_bundles b" in text:
                    self.mode = "bundles"
                else:
                    self.mode = "none"

            def fetchall(self):
                if self.mode == "sources":
                    return [
                        (
                            "postgres_sql",
                            "orders_api",
                            {
                                "sql_dsn_env": "ORDERS_DSN",
                                "sql_table": "orders",
                            },
                            "ops_manager",
                            datetime(2026, 5, 2, 12, 0, tzinfo=UTC),
                            datetime(2026, 5, 2, 12, 0, tzinfo=UTC),
                        )
                    ]
                if self.mode == "bundles":
                    return [
                        (
                            "bundle-source-1",
                            "data_source:orders_api",
                            "data_source",
                            "data_map",
                            "orders_api",
                            "ready",
                            4,
                            2,
                            2,
                            3,
                            0.91,
                            datetime(2026, 5, 2, 12, 0, tzinfo=UTC),
                            {
                                "source_system": "orders_api",
                                "processes": ["Dispatch escalation"],
                                "capabilities": ["Plan dispatch routes"],
                            },
                            [
                                {
                                    "claim_text": "Orders API drives dispatch escalation when access windows change.",
                                    "category": "process",
                                    "metadata": {},
                                }
                            ],
                        )
                    ]
                return []

        cursor = _BundleCatalogCursor()
        original_table_exists = _api_main._legacy_import_sources_table_exists_from_cursor
        original_collect_usage = _api_main._collect_agent_source_usage
        original_wiki_table_exists = _api_main._wiki_feature_table_exists
        try:
            _api_main._legacy_import_sources_table_exists_from_cursor = lambda cur: True
            _api_main._collect_agent_source_usage = lambda cur, project_id: {}
            _api_main._wiki_feature_table_exists = lambda cur, table: table in {
                "public.evidence_bundles",
                "public.evidence_bundle_claim_links",
                "public.claims",
            }
            pages = _build_data_sources_catalog_pages(
                cursor,
                project_id="omega_demo",
                space_key="operations",
                max_sources=10,
            )
        finally:
            _api_main._legacy_import_sources_table_exists_from_cursor = original_table_exists
            _api_main._collect_agent_source_usage = original_collect_usage
            _api_main._wiki_feature_table_exists = original_wiki_table_exists

        self.assertGreaterEqual(len(pages), 2)
        catalog_markdown = str(pages[0].get("markdown") or "")
        detail_markdown = str(pages[1].get("markdown") or "")
        self.assertIn("## Durable Source Signals", catalog_markdown)
        self.assertIn("data_source:orders_api", catalog_markdown)
        self.assertIn("Dispatch escalation", detail_markdown)
        self.assertIn("Bundle coverage: ready 1 / candidate 0", detail_markdown)
        self.assertIn("Orders API drives dispatch escalation", detail_markdown)
        self.assertIn("## Reliability & Risk", detail_markdown)
        self.assertIn("Stale risk:", detail_markdown)
        self.assertIn("Downstream decisions:", detail_markdown)

    def test_data_sources_catalog_pages_infer_runtime_usage_for_knowledge_plane_sources(self) -> None:
        assert _api_main is not None

        class _InferredUsageCursor:
            def __init__(self) -> None:
                self.mode = "none"

            def execute(self, sql: str, params=None) -> None:
                text = str(sql)
                if "FROM legacy_import_sources" in text:
                    self.mode = "sources"
                else:
                    self.mode = "none"

            def fetchall(self):
                if self.mode == "sources":
                    return [
                        (
                            "postgres_sql",
                            "profile:memory_items",
                            {
                                "sql_profile": "memory_items",
                                "sql_profile_table": "public.memory_items",
                            },
                            "legacy_sync_scheduler",
                            datetime(2026, 5, 3, 10, 0, tzinfo=UTC),
                            datetime(2026, 5, 3, 10, 0, tzinfo=UTC),
                        )
                    ]
                return []

        cursor = _InferredUsageCursor()
        original_table_exists = _api_main._legacy_import_sources_table_exists_from_cursor
        original_collect_usage = _api_main._collect_agent_source_usage
        original_agent_directory_exists = _api_main._agent_directory_table_exists_from_cursor
        original_build_matrix = _api_main._build_agent_capability_matrix
        try:
            _api_main._legacy_import_sources_table_exists_from_cursor = lambda cur: True
            _api_main._collect_agent_source_usage = lambda cur, project_id: {}
            _api_main._agent_directory_table_exists_from_cursor = lambda cur: True
            _api_main._build_agent_capability_matrix = lambda cur, project_id, max_agents: [
                {
                    "agent_id": "logistics-assistant",
                    "status": "active",
                    "running_instances": 6,
                    "responsibilities": ["driver_economics"],
                    "standing_orders": ["Daily driver economy sheet"],
                    "scheduled_tasks": ["standing_order.logistics.driver_economy_sheet"],
                    "scenario_examples": ["driver economy daily review"],
                    "allowed_actions": ["publish_driver_economy_report"],
                    "tools": ["driver_economy_report_to_sheet"],
                    "data_sources": [],
                    "source_bindings": [],
                    "tool_contracts": [],
                }
            ]
            pages = _build_data_sources_catalog_pages(
                cursor,
                project_id="omega_demo",
                space_key="logistics",
                max_sources=10,
            )
        finally:
            _api_main._legacy_import_sources_table_exists_from_cursor = original_table_exists
            _api_main._collect_agent_source_usage = original_collect_usage
            _api_main._agent_directory_table_exists_from_cursor = original_agent_directory_exists
            _api_main._build_agent_capability_matrix = original_build_matrix

        catalog_markdown = str(pages[0].get("markdown") or "")
        detail_markdown = str(pages[1].get("markdown") or "")
        self.assertIn("logistics-assistant", catalog_markdown)
        self.assertIn("driver_economics", detail_markdown)
        self.assertIn("Daily driver economy sheet", detail_markdown)
        self.assertIn("inferred from runtime/control-plane contracts", detail_markdown)
        self.assertIn("Explicit mappings:", detail_markdown)

    def test_data_sources_catalog_normalizes_runtime_contract_impact_labels(self) -> None:
        assert _api_main is not None

        class _CatalogCursor:
            def __init__(self) -> None:
                self.mode = "none"

            def execute(self, sql: str, params=None) -> None:
                if "FROM legacy_import_sources" in str(sql):
                    self.mode = "sources"
                else:
                    self.mode = "none"

            def fetchall(self):
                if self.mode == "sources":
                    return [
                        (
                            "postgres_sql",
                            "postgres_sql:memory_items:polling",
                            {"sql_profile": "memory_items", "sql_profile_table": "public.memory_items"},
                            "ops_admin",
                            datetime(2026, 5, 3, 11, 0, tzinfo=UTC),
                            datetime(2026, 5, 3, 11, 0, tzinfo=UTC),
                        )
                    ]
                return []

        cursor = _CatalogCursor()
        original_table_exists = _api_main._legacy_import_sources_table_exists_from_cursor
        original_collect_usage = _api_main._collect_agent_source_usage
        original_agent_directory_exists = _api_main._agent_directory_table_exists_from_cursor
        original_build_matrix = _api_main._build_agent_capability_matrix
        try:
            _api_main._legacy_import_sources_table_exists_from_cursor = lambda cur: True
            _api_main._collect_agent_source_usage = lambda cur, project_id: {}
            _api_main._agent_directory_table_exists_from_cursor = lambda cur: True
            _api_main._build_agent_capability_matrix = lambda cur, project_id, max_agents: [
                {
                    "agent_id": "logistics-assistant",
                    "status": "active",
                    "running_instances": 6,
                    "responsibilities": ["driver_cargo_state"],
                    "standing_orders": ["standing_order.logistics.daily_report"],
                    "scheduled_tasks": ["standing_order.logistics.daily_report"],
                    "scenario_examples": ["daily operating digest"],
                    "allowed_actions": ["publish_daily_report"],
                    "tools": ["daily_report_writer"],
                    "data_sources": [],
                    "source_bindings": [],
                    "tool_contracts": [],
                    "source_binding_contracts": [
                        {
                            "source": "postgres_sql:memory_items:polling",
                            "capabilities": ["driver_cargo_state"],
                            "processes": ["standing_order.logistics.daily_report"],
                            "tools": ["daily_report_writer"],
                        }
                    ],
                }
            ]
            pages = _build_data_sources_catalog_pages(
                cursor,
                project_id="omega_demo",
                space_key="logistics",
                max_sources=10,
            )
        finally:
            _api_main._legacy_import_sources_table_exists_from_cursor = original_table_exists
            _api_main._collect_agent_source_usage = original_collect_usage
            _api_main._agent_directory_table_exists_from_cursor = original_agent_directory_exists
            _api_main._build_agent_capability_matrix = original_build_matrix

        catalog_markdown = str(pages[0].get("markdown") or "")
        detail_markdown = str(pages[1].get("markdown") or "")
        self.assertIn("daily report", catalog_markdown)
        self.assertNotIn("standing_order.logistics.daily_report", catalog_markdown)
        self.assertIn("daily report", detail_markdown)
        self.assertIn("driver cargo state", detail_markdown)

    def test_agent_capability_bootstrap_page_renders_grounded_operating_scope(self) -> None:
        assert _api_main is not None

        original_agent_directory_exists = _api_main._agent_directory_table_exists_from_cursor
        original_build_matrix = _api_main._build_agent_capability_matrix
        original_orgchart = _api_main.get_agent_orgchart
        original_load_bundles = _api_main._load_evidence_bundles_for_bootstrap
        try:
            _api_main._agent_directory_table_exists_from_cursor = lambda cur: True
            _api_main._build_agent_capability_matrix = lambda cur, project_id, max_agents: [
                {
                    "agent_id": "dispatch_bot",
                    "display_name": "Dispatch Bot",
                    "team": "Logistics",
                    "role": "Dispatcher",
                    "status": "active",
                    "typical_actions": ["reroute delivery", "confirm access windows"],
                    "escalation_rules": ["Escalate route blockers to on-call ops"],
                    "tools": ["maps_router"],
                    "registry_tools": ["dispatch_console"],
                    "data_sources": ["orders_api"],
                    "source_bindings": ["warehouse_sheet"],
                    "limits": ["No reroute without valid access window"],
                    "allowed_actions": ["reroute_delivery"],
                    "approval_rules": ["Manual approval for VIP reroutes"],
                    "static_config_keys": ["scheduler", "approvals"],
                    "scheduled_tasks": ["Refresh route constraints (0 * * * *)"],
                    "standing_orders": ["Dispatch escalation policy"],
                    "integrations": ["Slack", "TMS"],
                    "model_routing": ["primary: gpt-5.5", "fallback: gpt-5.4"],
                    "prompt_signal": "Prioritize SLA-safe dispatch decisions.",
                    "scenario_examples": ["yard access changes", "driver late on route"],
                    "observed_strengths": ["Escalate yard access exceptions quickly"],
                    "observed_decisions": ["Moved blocked route to fallback lane"],
                    "observed_questions": ["Need doc for VIP reroute policy"],
                    "observed_uncertainties": ["Unknown card-access override hours"],
                    "observed_actions": ["publish fallback route update"],
                    "latest_reflection_summary": "Updated yard access handling after repeated blockers.",
                    "latest_reflection_outcome": "resolved",
                    "reflection_count": 3,
                    "confidence": 0.91,
                }
            ]
            _api_main.get_agent_orgchart = lambda **kwargs: {
                "nodes": [
                    {
                        "agent_id": "dispatch_bot",
                        "display_name": "Dispatch Bot",
                        "team": "Logistics",
                        "role": "Dispatcher",
                        "status": "active",
                        "profile_slug": "agents/dispatch_bot",
                    }
                ],
                "edges": [],
                "teams": [{"team": "Logistics", "agents_total": 1}],
            }
            _api_main._load_evidence_bundles_for_bootstrap = lambda *args, **kwargs: [
                {
                    "bundle_key": "capability:dispatch_bot",
                    "bundle_status": "ready",
                    "support_count": 4,
                    "suggested_page_type": "agent_profile",
                    "entity_key": "dispatch_bot",
                    "sample_claims": [{"claim_text": "Dispatch bot escalates yard-access exceptions before SLA breach."}],
                }
            ]
            pages = _build_agent_capability_bootstrap_page(
                object(),
                project_id="omega_demo",
                space_key="operations",
                max_agents=10,
            )
        finally:
            _api_main._agent_directory_table_exists_from_cursor = original_agent_directory_exists
            _api_main._build_agent_capability_matrix = original_build_matrix
            _api_main.get_agent_orgchart = original_orgchart
            _api_main._load_evidence_bundles_for_bootstrap = original_load_bundles

        markdown = str(pages[0].get("markdown") or "")
        self.assertIn("Declared operating scope: Dispatch escalation policy; yard access changes; driver late on route; publish fallback route update", markdown)
        self.assertIn("Guardrails / approvals: Manual approval for VIP reroutes; No reroute without valid access window; Escalate route blockers to on-call ops", markdown)
        self.assertIn("Toolset: maps_router, dispatch_console", markdown)
        self.assertIn("Data sources: orders_api, warehouse_sheet", markdown)
        self.assertIn("Bundle-backed insights: Dispatch bot escalates yard-access exceptions before SLA breach.", markdown)

    def test_tooling_map_bootstrap_page_uses_capability_process_and_source_context(self) -> None:
        assert _api_main is not None

        original_agent_directory_exists = _api_main._agent_directory_table_exists_from_cursor
        original_build_matrix = _api_main._build_agent_capability_matrix
        try:
            _api_main._agent_directory_table_exists_from_cursor = lambda cur: True
            _api_main._build_agent_capability_matrix = lambda cur, project_id, max_agents: [
                {
                    "agent_id": "dispatch_bot",
                    "tools": ["maps_router"],
                    "registry_tools": ["dispatch_console"],
                    "scenario_examples": ["yard access changes"],
                    "responsibilities": ["Plans dispatch routes"],
                    "standing_orders": ["Dispatch escalation policy"],
                    "observed_actions": ["publish fallback route update"],
                    "data_sources": ["orders_api"],
                    "source_bindings": ["warehouse_sheet"],
                    "limits": ["No reroute without valid access window"],
                    "approval_rules": ["Manual approval for VIP reroutes"],
                    "escalation_rules": ["Escalate route blockers to on-call ops"],
                    "tool_contracts": [
                        {
                            "tool": "dispatch_console",
                            "purpose": "Approve route changes and publish dispatch overrides",
                            "scenarios": ["vip reroute approval"],
                            "guardrails": ["Human approval for VIP dispatch changes"],
                            "sources": ["dispatch_overrides_sheet"],
                            "capabilities": ["Approve dispatch overrides"],
                        }
                    ],
                }
            ]
            pages = _build_tooling_map_bootstrap_page(
                object(),
                project_id="omega_demo",
                space_key="operations",
                max_agents=10,
            )
        finally:
            _api_main._agent_directory_table_exists_from_cursor = original_agent_directory_exists
            _api_main._build_agent_capability_matrix = original_build_matrix

        markdown = str(pages[0].get("markdown") or "")
        self.assertIn("Capability / Scenario", markdown)
        self.assertIn("Process / Sources", markdown)
        self.assertIn("Plans dispatch routes", markdown)
        self.assertIn("Dispatch escalation policy", markdown)
        self.assertIn("orders_api", markdown)
        self.assertIn("Manual approval for VIP reroutes", markdown)
        self.assertIn("Approve route changes and publish dispatch overrides", markdown)
        self.assertIn("dispatch_overrides_sheet", markdown)

    def test_draft_bulk_filter_can_require_ready_bundle_support(self) -> None:
        assert _draft_matches_bulk_filter is not None
        assert _api_main is not None

        draft = {
            "confidence": 0.92,
            "has_open_conflict": False,
            "page": {"status": "reviewed", "page_type": "process"},
            "claim": {"category": "process"},
            "gatekeeper": {
                "tier": "golden_candidate",
                "assertion_class": "process_rule",
                "compiler_v2": {
                    "suggested_page_type": "process",
                    "knowledge_dimensions": ["process", "procedural"],
                },
            },
            "bundle": {
                "bundle_key": "process:dispatch_escalation",
                "bundle_status": "ready",
                "support_count": 4,
            },
            "evidence": {"source_systems": ["ops_kb_sync"], "connectors": ["postgres_sql"], "source_types": ["knowledge"]},
            "risk": {"level": "medium"},
        }
        filter_config = _api_main.DraftBulkReviewFilter(
            suggested_page_type="process",
            bundle_status="ready",
            knowledge_dimension="process",
            min_bundle_support=3,
            require_bundle_ready=True,
        )
        self.assertTrue(_draft_matches_bulk_filter(draft, filter_config))
        failing_filter = _api_main.DraftBulkReviewFilter(
            bundle_status="candidate",
            require_bundle_ready=True,
        )
        self.assertFalse(_draft_matches_bulk_filter(draft, failing_filter))

    def test_draft_bundle_priority_prefers_ready_supported_bundles(self) -> None:
        assert _draft_bundle_priority is not None

        strong = _draft_bundle_priority(
            {
                "confidence": 0.88,
                "has_open_conflict": False,
                "gatekeeper": {
                    "compiler_v2": {
                        "knowledge_like_score": 0.84,
                        "bundle_support": 4,
                        "promotion_ready_from_bundle": True,
                    }
                },
                "bundle": {"bundle_status": "ready", "support_count": 4, "quality_score": 0.9},
                "risk": {"level": "medium"},
            }
        )
        weak = _draft_bundle_priority(
            {
                "confidence": 0.74,
                "has_open_conflict": False,
                "gatekeeper": {
                    "compiler_v2": {
                        "knowledge_like_score": 0.4,
                        "bundle_support": 0,
                        "promotion_ready_from_bundle": False,
                    }
                },
                "bundle": {"bundle_status": "observed", "support_count": 0, "quality_score": 0.2},
                "risk": {"level": "medium"},
            }
        )
        self.assertGreater(float(strong["score"]), float(weak["score"]))
        self.assertEqual(strong["recommendation"], "approve_first")

    def test_default_bundle_guard_requires_ready_or_promotion_ready_bundle(self) -> None:
        assert _draft_passes_default_bundle_guard_for_approve is not None

        ready_draft = {
            "gatekeeper": {"compiler_v2": {"bundle_support": 2, "promotion_ready_from_bundle": False}},
            "bundle": {"bundle_status": "ready", "support_count": 2},
        }
        candidate_draft = {
            "gatekeeper": {"compiler_v2": {"bundle_support": 1, "promotion_ready_from_bundle": False}},
            "bundle": {"bundle_status": "candidate", "support_count": 1},
        }
        promoted_candidate = {
            "gatekeeper": {"compiler_v2": {"bundle_support": 2, "promotion_ready_from_bundle": True}},
            "bundle": {"bundle_status": "candidate", "support_count": 2},
        }
        self.assertTrue(_draft_passes_default_bundle_guard_for_approve(ready_draft))
        self.assertFalse(_draft_passes_default_bundle_guard_for_approve(candidate_draft))
        self.assertTrue(_draft_passes_default_bundle_guard_for_approve(promoted_candidate))

    def test_summarize_draft_queue_groups_recommendations_and_statuses(self) -> None:
        assert _summarize_draft_queue is not None

        summary = _summarize_draft_queue(
            [
                {
                    "id": "d1",
                    "page": {"slug": "operations/process-1", "page_type": "process"},
                    "claim": {"category": "process"},
                    "bundle_priority": {"recommendation": "approve_first", "score": 4.2, "reason": "bundle=ready"},
                    "bundle": {"bundle_status": "ready", "support_count": 3},
                    "gatekeeper": {"compiler_v2": {"suggested_page_type": "process"}},
                },
                {
                    "id": "d2",
                    "page": {"slug": "operations/source-1", "page_type": "data_map"},
                    "claim": {"category": "data_source"},
                    "bundle_priority": {"recommendation": "review_with_context", "score": 2.1, "reason": "bundle=candidate"},
                    "bundle": {"bundle_status": "candidate", "support_count": 1},
                    "gatekeeper": {"compiler_v2": {"suggested_page_type": "data_map"}},
                },
            ]
        )
        self.assertEqual(summary["drafts_total"], 2)
        self.assertEqual(summary["recommendations"]["approve_first"], 1)
        self.assertEqual(summary["bundle_statuses"]["ready"], 1)
        self.assertEqual(summary["suggested_page_types"]["process"], 1)
        self.assertEqual(summary["ready_bundle_support_total"], 3)

    def test_process_playbooks_bootstrap_page_renders_runbook_sections(self) -> None:
        assert _api_main is not None

        class _ProcessCursor:
            def __init__(self) -> None:
                self.mode = "none"

            def execute(self, sql: str, params=None) -> None:
                if "FROM claims" in str(sql):
                    self.mode = "claims"
                else:
                    self.mode = "none"

            def fetchall(self):
                if self.mode == "claims":
                    return [
                        (
                            "When yard access changes, reroute delivery and verify SLA after dispatch update.",
                            "process",
                            {
                                "process_triplet": {
                                    "trigger": "yard access changes",
                                    "action": "reroute delivery and notify dispatch",
                                    "outcome": "sla verified after dispatch update",
                                    "confidence": 0.91,
                                },
                                "source_system": "ops_kb_sync",
                                "linked_ticket_ids": ["OPS-42"],
                                "resolution_outcome": "resolved",
                                "tool_name": "maps_router",
                            },
                            [
                                {
                                    "source_id": "ops_kb_items:42",
                                    "source_system": "ops_kb_sync",
                                    "tool_name": "maps_router",
                                }
                            ],
                        )
                    ]
                return []

        cursor = _ProcessCursor()
        original_table_exists = _api_main._wiki_feature_table_exists
        try:
            _api_main._wiki_feature_table_exists = lambda cur, table: table == "public.claims"
            pages = _build_process_playbooks_bootstrap_page(
                cursor,
                project_id="omega_demo",
                space_key="operations",
                max_signals=10,
            )
        finally:
            _api_main._wiki_feature_table_exists = original_table_exists

        markdown = str(pages[0].get("markdown") or "")
        self.assertIn("## Canonical Runbooks", markdown)
        self.assertIn("- Owners:", markdown)
        self.assertIn("- Purpose:", markdown)
        self.assertIn("- Inputs:", markdown)
        self.assertIn("- Steps:", markdown)
        self.assertIn("- Exceptions:", markdown)
        self.assertIn("- Outputs:", markdown)
        self.assertIn("- Verification:", markdown)
        self.assertIn("- Human-in-the-loop:", markdown)
        self.assertIn("- Tools used: maps_router", markdown)
        self.assertIn("- Source evidence: ops_kb_sync", markdown)

    def test_process_playbooks_bootstrap_page_uses_evidence_bundles(self) -> None:
        assert _api_main is not None

        class _BundleProcessCursor:
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
                            "bundle-22",
                            "process:yard_access",
                            "process",
                            "process",
                            "yard_access",
                            "ready",
                            4,
                            2,
                            2,
                            3,
                            0.91,
                            datetime(2026, 5, 2, 12, 0, tzinfo=UTC),
                            {"source_systems": ["ops_kb_sync"], "claim_entity_key": "yard_access"},
                            [
                                {
                                    "claim_text": "When yard access changes, reroute delivery and verify SLA after dispatch update.",
                                    "category": "process",
                                    "metadata": {
                                        "process_triplet": {
                                            "trigger": "yard access changes",
                                            "action": "reroute delivery and notify dispatch",
                                            "outcome": "sla verified after dispatch update",
                                            "confidence": 0.91,
                                        },
                                        "tool_name": "maps_router",
                                    },
                                }
                            ],
                        )
                    ]
                if self.mode == "claims":
                    return []
                return []

        original_table_exists = _api_main._wiki_feature_table_exists
        try:
            _api_main._wiki_feature_table_exists = lambda cur, table: table in {
                "public.evidence_bundles",
                "public.evidence_bundle_claim_links",
                "public.claims",
            }
            pages = _build_process_playbooks_bootstrap_page(
                _BundleProcessCursor(),
                project_id="omega_demo",
                space_key="operations",
                max_signals=10,
            )
        finally:
            _api_main._wiki_feature_table_exists = original_table_exists

        markdown = str(pages[0].get("markdown") or "")
        self.assertIn("Yard Access Playbook", markdown)
        self.assertIn("bundle_support=4", markdown)
        self.assertIn("bundle_status=ready", markdown)
        self.assertIn("- Tools used: maps_router", markdown)

    def test_process_playbooks_bootstrap_page_uses_agent_profile_processes(self) -> None:
        assert _api_main is not None

        original_agent_directory_exists = _api_main._agent_directory_table_exists_from_cursor
        original_build_matrix = _api_main._build_agent_capability_matrix
        original_runtime_matrix = _api_main._build_runtime_agent_capability_matrix
        original_load_reflections = _api_main._load_recent_agent_reflection_signals
        original_load_bundles = _api_main._load_evidence_bundles_for_bootstrap
        original_table_exists = _api_main._wiki_feature_table_exists
        try:
            _api_main._agent_directory_table_exists_from_cursor = lambda cur: True
            _api_main._build_agent_capability_matrix = lambda cur, project_id, max_agents: [
                {
                    "agent_id": "dispatch_bot",
                    "confidence": 0.88,
                    "standing_orders": ["Dispatch escalation policy"],
                    "scheduled_tasks": ["Refresh route constraints (0 * * * *)"],
                    "observed_actions": ["publish fallback route update"],
                    "approval_rules": ["Manual approval for VIP reroutes"],
                    "escalation_rules": ["Escalate route blockers to on-call ops"],
                    "scenario_examples": ["yard access changes"],
                    "tools": ["maps_router"],
                    "data_sources": ["orders_api"],
                    "source_bindings": ["warehouse_sheet"],
                }
            ]
            _api_main._build_runtime_agent_capability_matrix = lambda cur, project_id, max_agents: []
            _api_main._load_recent_agent_reflection_signals = lambda *args, **kwargs: {}
            _api_main._load_evidence_bundles_for_bootstrap = lambda *args, **kwargs: []
            _api_main._wiki_feature_table_exists = lambda cur, table: False
            pages = _build_process_playbooks_bootstrap_page(
                object(),
                project_id="omega_demo",
                space_key="operations",
                max_signals=10,
            )
        finally:
            _api_main._agent_directory_table_exists_from_cursor = original_agent_directory_exists
            _api_main._build_agent_capability_matrix = original_build_matrix
            _api_main._build_runtime_agent_capability_matrix = original_runtime_matrix
            _api_main._load_recent_agent_reflection_signals = original_load_reflections
            _api_main._load_evidence_bundles_for_bootstrap = original_load_bundles
            _api_main._wiki_feature_table_exists = original_table_exists

        markdown = str(pages[0].get("markdown") or "")
        self.assertIn("Dispatch escalation policy", markdown)
        self.assertIn("Manual approval for VIP reroutes", markdown)
        self.assertIn("warehouse_sheet", markdown)
        self.assertIn("maps_router", markdown)


if __name__ == "__main__":
    unittest.main()
