from __future__ import annotations

from datetime import UTC, date, datetime
import unittest

try:
    import services.api.app.main as _api_main
    from services.api.app.main import (
        AgentReflectionSubmitRequest,
        _bootstrap_page_importance,
        _build_agent_reflection_claim_payloads,
        _build_data_sources_catalog_pages,
        _build_agent_capability_bootstrap_page,
        _build_process_playbooks_bootstrap_page,
        _build_agent_wiki_bootstrap_quality_report,
        _build_project_wiki_richness_benchmark_from_rows,
        _build_human_guided_synthesis_prompts,
        _page_type_freshness_thresholds,
        _prepend_bootstrap_publish_notice,
        _build_runtime_agent_capability_matrix,
        _collect_agent_source_usage,
        _build_project_wiki_quality_report_from_rows,
        _build_agent_provenance_activity,
        _compute_agent_capability_confidence,
        _derive_runtime_agent_responsibilities,
        _derive_runtime_agent_role,
        _evaluate_agent_capability_bootstrap_contract,
        _is_daily_summary_like_draft_row,
        _normalize_agent_directory_items,
        _normalize_agent_publish_policy,
        _render_agent_capability_matrix_markdown,
        _render_agent_daily_reports_page,
        _render_agent_daily_worklog_entry,
        _render_agent_handoff_markdown,
        _render_agent_overview_markdown,
        _render_agent_scorecards_markdown,
        _runtime_agent_filter_sql,
        _runtime_agent_id_sql_expr,
    )
except Exception:  # pragma: no cover
    _api_main = None
    AgentReflectionSubmitRequest = None
    _bootstrap_page_importance = None
    _build_agent_reflection_claim_payloads = None
    _build_data_sources_catalog_pages = None
    _build_agent_capability_bootstrap_page = None
    _build_process_playbooks_bootstrap_page = None
    _build_agent_wiki_bootstrap_quality_report = None
    _build_project_wiki_richness_benchmark_from_rows = None
    _build_human_guided_synthesis_prompts = None
    _page_type_freshness_thresholds = None
    _prepend_bootstrap_publish_notice = None
    _build_runtime_agent_capability_matrix = None
    _collect_agent_source_usage = None
    _build_project_wiki_quality_report_from_rows = None
    _build_agent_provenance_activity = None
    _compute_agent_capability_confidence = None
    _derive_runtime_agent_responsibilities = None
    _derive_runtime_agent_role = None
    _evaluate_agent_capability_bootstrap_contract = None
    _is_daily_summary_like_draft_row = None
    _normalize_agent_directory_items = None
    _normalize_agent_publish_policy = None
    _render_agent_capability_matrix_markdown = None
    _render_agent_daily_reports_page = None
    _render_agent_daily_worklog_entry = None
    _render_agent_handoff_markdown = None
    _render_agent_overview_markdown = None
    _render_agent_scorecards_markdown = None
    _runtime_agent_filter_sql = None
    _runtime_agent_id_sql_expr = None


@unittest.skipIf(
    _normalize_agent_directory_items is None
    or _bootstrap_page_importance is None
    or _build_data_sources_catalog_pages is None
    or _build_agent_capability_bootstrap_page is None
    or _build_process_playbooks_bootstrap_page is None
    or _build_agent_wiki_bootstrap_quality_report is None
    or _build_project_wiki_richness_benchmark_from_rows is None
    or _build_human_guided_synthesis_prompts is None
    or _page_type_freshness_thresholds is None
    or _build_agent_reflection_claim_payloads is None
    or _prepend_bootstrap_publish_notice is None
    or _build_project_wiki_quality_report_from_rows is None
    or AgentReflectionSubmitRequest is None
    or _build_agent_provenance_activity is None
    or _compute_agent_capability_confidence is None
    or _derive_runtime_agent_responsibilities is None
    or _derive_runtime_agent_role is None
    or _evaluate_agent_capability_bootstrap_contract is None
    or _is_daily_summary_like_draft_row is None
    or _render_agent_capability_matrix_markdown is None
    or _normalize_agent_publish_policy is None
    or _render_agent_overview_markdown is None
    or _render_agent_daily_worklog_entry is None
    or _render_agent_daily_reports_page is None
    or _render_agent_handoff_markdown is None
    or _render_agent_scorecards_markdown is None
    or _build_runtime_agent_capability_matrix is None
    or _collect_agent_source_usage is None
    or _runtime_agent_filter_sql is None
    or _runtime_agent_id_sql_expr is None,
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
        self.assertIn("- Purpose:", markdown)
        self.assertIn("- Inputs:", markdown)
        self.assertIn("- Steps:", markdown)
        self.assertIn("- Exceptions:", markdown)
        self.assertIn("- Outputs:", markdown)
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


if __name__ == "__main__":
    unittest.main()
