from __future__ import annotations

import unittest
from typing import Any

from synapse_sdk.client import Synapse
from synapse_sdk.types import (
    AgentReflection,
    AgentReflectionInsight,
    AgentRuntimeSurfaceAgent,
    MemoryBackfillRecord,
    SynapseConfig,
    WikiDraftBulkReviewFilter,
)


class _DummyTransport:
    def send_events(self, events: list[dict[str, Any]], *, idempotency_key: str | None = None) -> None:
        return None

    def propose_fact(self, claim: dict[str, Any], *, idempotency_key: str | None = None) -> None:
        return None

    def ingest_memory_backfill(self, batch_payload: dict[str, Any], *, idempotency_key: str | None = None) -> None:
        return None


class _RecordingSynapse(Synapse):
    def __init__(self) -> None:
        super().__init__(SynapseConfig(api_url="http://localhost:8080", project_id="omega_demo"), transport=_DummyTransport())
        self.calls: list[dict[str, Any]] = []

    def _request_json(
        self,
        path: str,
        *,
        method: str,
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "path": path,
                "method": method,
                "payload": dict(payload or {}),
                "params": dict(params or {}),
                "idempotency_key": idempotency_key,
            }
        )
        return {"ok": True, "path": path}


class LegacyImportClientMethodsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = _RecordingSynapse()

    def test_upsert_legacy_import_source_sends_expected_payload(self) -> None:
        result = self.client.upsert_legacy_import_source(
            source_type="postgres_sql",
            source_ref="hw_memory",
            updated_by="ops_admin",
            sync_interval_minutes=5,
            config={"sql_dsn_env": "HW_MEMORY_DSN", "sql_profile": "ops_kb_items"},
        )
        self.assertTrue(result.get("ok"))
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/legacy-import/sources")
        self.assertEqual(call["method"], "PUT")
        payload = call["payload"]
        self.assertEqual(payload.get("project_id"), "omega_demo")
        self.assertEqual(payload.get("source_type"), "postgres_sql")
        self.assertEqual(payload.get("source_ref"), "hw_memory")
        self.assertEqual(payload.get("updated_by"), "ops_admin")
        self.assertEqual(payload.get("sync_interval_minutes"), 5)
        self.assertIsInstance(call.get("idempotency_key"), str)

    def test_queue_legacy_import_source_sync_encodes_source_id(self) -> None:
        self.client.queue_legacy_import_source_sync("source/with space", requested_by="ops_admin")
        call = self.client.calls[-1]
        self.assertEqual(call["method"], "POST")
        self.assertEqual(call["path"], "/v1/legacy-import/sources/source/with%20space/sync")
        self.assertEqual(call["payload"].get("project_id"), "omega_demo")
        self.assertEqual(call["payload"].get("requested_by"), "ops_admin")

    def test_list_legacy_import_sync_runs_includes_project_scope(self) -> None:
        self.client.list_legacy_import_sync_runs(source_id="abc", status="running", limit=20)
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/legacy-import/runs")
        self.assertEqual(call["method"], "GET")
        params = call["params"]
        self.assertEqual(params.get("project_id"), "omega_demo")
        self.assertEqual(params.get("source_id"), "abc")
        self.assertEqual(params.get("status"), "running")
        self.assertEqual(params.get("limit"), 20)

    def test_list_legacy_import_mapper_templates_scopes_profile(self) -> None:
        self.client.list_legacy_import_mapper_templates(source_type="postgres_sql", profile="ops_kb_items")
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/legacy-import/mapper-templates")
        self.assertEqual(call["method"], "GET")
        self.assertEqual(call["params"].get("source_type"), "postgres_sql")
        self.assertEqual(call["params"].get("profile"), "ops_kb_items")

    def test_list_legacy_import_sync_contracts_defaults_source_type(self) -> None:
        self.client.list_legacy_import_sync_contracts()
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/legacy-import/sync-contracts")
        self.assertEqual(call["method"], "GET")
        self.assertEqual(call["params"].get("source_type"), "postgres_sql")

    def test_sync_agent_runtime_surface_posts_control_plane_contract(self) -> None:
        self.client.sync_agent_runtime_surface(
            [
                AgentRuntimeSurfaceAgent(
                    agent_id="logistics-assistant",
                    runtime_overview={"runtime_mode": "service", "running_instances": 6},
                    scheduled_tasks=[
                        {
                            "task_code": "standing_order.logistics.driver_economy_sheet",
                            "builtin_task": "driver_economy_report_to_sheet",
                            "cron_expr": "0 12 * * *",
                        }
                    ],
                    capability_registry=["driver_economics", "logistics_world_model"],
                    action_surface=["outbound_messaging"],
                    tool_manifest=[{"tool": "driver_economy_report_to_sheet", "purpose": "Publish daily driver economics"}],
                    source_hints=["driver_economy_daily_latest"],
                    approvals=[{"mode": "none"}],
                )
            ],
            updated_by="ops_admin",
            refresh_space_keys=["logistics"],
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/agents/runtime-surface/sync")
        self.assertEqual(call["method"], "POST")
        payload = call["payload"]
        self.assertEqual(payload.get("project_id"), "omega_demo")
        self.assertEqual(payload.get("updated_by"), "ops_admin")
        self.assertTrue(payload.get("ensure_scaffold"))
        self.assertTrue(payload.get("refresh_bootstrap_pages"))
        self.assertEqual(payload.get("refresh_space_keys"), ["logistics"])
        self.assertTrue(payload.get("bootstrap_publish_core"))
        self.assertEqual(len(payload.get("agents") or []), 1)
        first = payload["agents"][0]
        self.assertEqual(first.get("agent_id"), "logistics-assistant")
        self.assertEqual(first.get("runtime_overview", {}).get("running_instances"), 6)
        self.assertEqual(first.get("capability_registry"), ["driver_economics", "logistics_world_model"])

    def test_bootstrap_recommendation_is_project_scoped(self) -> None:
        self.client.get_bootstrap_migration_recommendation()
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/wiki/drafts/bootstrap-approve/recommendation")
        self.assertEqual(call["method"], "GET")
        self.assertEqual(call["params"].get("project_id"), "omega_demo")

    def test_explain_curated_backfill_calls_preview_endpoint(self) -> None:
        self.client.explain_curated_backfill(
            [
                MemoryBackfillRecord(
                    source_id="rec-1",
                    content='{"order_id":"123","status":"created"}',
                    category="order_snapshot",
                    metadata={"source_system": "postgres_sql", "namespace": "orders"},
                )
            ],
            curated_enabled=True,
            curated_source_systems=["postgres_sql"],
            curated_namespaces=["orders"],
            noise_preset="balanced",
            sample_limit=9,
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/backfill/curated-explain")
        self.assertEqual(call["method"], "POST")
        self.assertEqual(call["params"].get("sample_limit"), 9)
        payload = call["payload"].get("batch") or {}
        self.assertEqual(payload.get("project_id"), "omega_demo")
        self.assertEqual(payload.get("ingest_lane"), "knowledge")
        self.assertEqual((payload.get("curated") or {}).get("noise_preset"), "balanced")

    def test_resolve_adoption_import_connector_uses_project_scope(self) -> None:
        self.client.resolve_adoption_import_connector(
            connector_id="postgres_sql:ops_kb_items:polling",
            field_overrides={"sql_dsn_env": "HW_MEMORY_DSN", "curated_import.noise_preset": "strict"},
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/adoption/import-connectors/resolve")
        self.assertEqual(call["method"], "POST")
        payload = call["payload"]
        self.assertEqual(payload.get("project_id"), "omega_demo")
        self.assertEqual(payload.get("connector_id"), "postgres_sql:ops_kb_items:polling")
        self.assertIsInstance(payload.get("field_overrides"), dict)

    def test_validate_adoption_import_connector_uses_project_scope(self) -> None:
        self.client.validate_adoption_import_connector(
            connector_id="postgres_sql:ops_kb_items:polling",
            source_ref="hw_memory_items",
            field_overrides={"sql_dsn_env": "HW_MEMORY_DSN"},
            live_connect=False,
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/adoption/import-connectors/validate")
        self.assertEqual(call["method"], "POST")
        payload = call["payload"]
        self.assertEqual(payload.get("project_id"), "omega_demo")
        self.assertEqual(payload.get("connector_id"), "postgres_sql:ops_kb_items:polling")
        self.assertEqual(payload.get("source_ref"), "hw_memory_items")
        self.assertFalse(payload.get("live_connect"))

    def test_bootstrap_adoption_import_connector_posts_expected_payload(self) -> None:
        self.client.bootstrap_adoption_import_connector(
            updated_by="ops_admin",
            connector_id="postgres_sql:ops_kb_items:polling",
            source_type="postgres_sql",
            field_overrides={"sql_dsn_env": "HW_MEMORY_DSN"},
            dry_run=False,
            sync_interval_minutes=15,
            queue_sync=True,
            sync_processor_lookback_minutes=45,
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/adoption/import-connectors/bootstrap")
        self.assertEqual(call["method"], "POST")
        payload = call["payload"]
        self.assertEqual(payload.get("project_id"), "omega_demo")
        self.assertEqual(payload.get("updated_by"), "ops_admin")
        self.assertEqual(payload.get("connector_id"), "postgres_sql:ops_kb_items:polling")
        self.assertFalse(payload.get("dry_run"))
        self.assertEqual(payload.get("confirm_project_id"), "omega_demo")
        self.assertEqual(payload.get("sync_interval_minutes"), 15)
        self.assertEqual(payload.get("sync_processor_lookback_minutes"), 45)

    def test_get_enterprise_readiness_uses_get_endpoint(self) -> None:
        self.client.get_enterprise_readiness(project_id="omega_demo")
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/enterprise/readiness")
        self.assertEqual(call["method"], "GET")
        self.assertEqual(call["params"].get("project_id"), "omega_demo")

    def test_get_adoption_kpi_is_project_scoped(self) -> None:
        self.client.get_adoption_kpi(days=21)
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/adoption/kpi")
        self.assertEqual(call["method"], "GET")
        self.assertEqual(call["params"].get("project_id"), "omega_demo")
        self.assertEqual(call["params"].get("days"), 21)

    def test_get_adoption_knowledge_gaps_is_project_scoped(self) -> None:
        self.client.get_adoption_knowledge_gaps(days=12, max_items_per_bucket=6)
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/adoption/knowledge-gaps")
        self.assertEqual(call["method"], "GET")
        self.assertEqual(call["params"].get("project_id"), "omega_demo")
        self.assertEqual(call["params"].get("days"), 12)
        self.assertEqual(call["params"].get("max_items_per_bucket"), 6)

    def test_sync_adoption_knowledge_gap_tasks_posts_expected_payload(self) -> None:
        self.client.sync_adoption_knowledge_gap_tasks(
            created_by="ops_admin",
            updated_by="ops_admin",
            assignee="wiki_editor",
            dry_run=False,
            days=10,
            limit_per_kind=4,
            include_candidate_bundles=True,
            include_page_enrichment_gaps=True,
            include_unresolved_questions=False,
            include_repeated_escalations=True,
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/adoption/knowledge-gaps/tasks/sync")
        self.assertEqual(call["method"], "POST")
        payload = call["payload"]
        self.assertEqual(payload.get("project_id"), "omega_demo")
        self.assertEqual(payload.get("created_by"), "ops_admin")
        self.assertEqual(payload.get("updated_by"), "ops_admin")
        self.assertEqual(payload.get("assignee"), "wiki_editor")
        self.assertFalse(payload.get("dry_run"))
        self.assertEqual(payload.get("confirm_project_id"), "omega_demo")
        self.assertEqual(payload.get("days"), 10)
        self.assertEqual(payload.get("limit_per_kind"), 4)
        self.assertFalse(payload.get("include_unresolved_questions"))

    def test_get_adoption_signal_noise_audit_is_project_scoped(self) -> None:
        self.client.get_adoption_signal_noise_audit(days=9, max_items_per_bucket=4)
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/adoption/signal-noise/audit")
        self.assertEqual(call["method"], "GET")
        self.assertEqual(call["params"].get("project_id"), "omega_demo")
        self.assertEqual(call["params"].get("days"), 9)
        self.assertEqual(call["params"].get("max_items_per_bucket"), 4)

    def test_list_adoption_evidence_ledger_is_project_scoped(self) -> None:
        self.client.list_adoption_evidence_ledger(
            source_shape="document",
            volatility_class="durable",
            pii_level="possible",
            evidence_role="supporting",
            knowledge_taxonomy_class="semantic",
            normalized_target_type="data_source_doc",
            bundle_status="ready",
            limit=17,
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/adoption/evidence-ledger")
        self.assertEqual(call["method"], "GET")
        self.assertEqual(call["params"].get("project_id"), "omega_demo")
        self.assertEqual(call["params"].get("source_shape"), "document")
        self.assertEqual(call["params"].get("volatility_class"), "durable")
        self.assertEqual(call["params"].get("bundle_status"), "ready")
        self.assertEqual(call["params"].get("limit"), 17)

    def test_get_adoption_evidence_ledger_stats_is_project_scoped(self) -> None:
        self.client.get_adoption_evidence_ledger_stats(days=45)
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/adoption/evidence-ledger/stats")
        self.assertEqual(call["method"], "GET")
        self.assertEqual(call["params"].get("project_id"), "omega_demo")
        self.assertEqual(call["params"].get("days"), 45)

    def test_get_adoption_stability_monitor_is_project_scoped(self) -> None:
        self.client.get_adoption_stability_monitor(days=11, max_items_per_bucket=5)
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/adoption/stability-monitor")
        self.assertEqual(call["method"], "GET")
        self.assertEqual(call["params"].get("project_id"), "omega_demo")
        self.assertEqual(call["params"].get("days"), 11)
        self.assertEqual(call["params"].get("max_items_per_bucket"), 5)

    def test_get_adoption_synthesis_prompts_is_project_scoped(self) -> None:
        self.client.get_adoption_synthesis_prompts(days=10, max_items=5)
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/adoption/synthesis-prompts")
        self.assertEqual(call["method"], "GET")
        self.assertEqual(call["params"].get("project_id"), "omega_demo")
        self.assertEqual(call["params"].get("days"), 10)
        self.assertEqual(call["params"].get("max_items"), 5)

    def test_run_adoption_bundle_promotion_posts_expected_payload(self) -> None:
        self.client.run_adoption_bundle_promotion(
            updated_by="ops_admin",
            dry_run=False,
            publish=True,
            bootstrap_publish_core=True,
            space_key="logistics",
            max_sources=15,
            max_agents=9,
            max_signals=42,
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/adoption/bundle-promotion/run")
        self.assertEqual(call["method"], "POST")
        payload = call["payload"]
        self.assertEqual(payload.get("project_id"), "omega_demo")
        self.assertEqual(payload.get("updated_by"), "ops_admin")
        self.assertFalse(payload.get("dry_run"))
        self.assertEqual(payload.get("confirm_project_id"), "omega_demo")
        self.assertEqual(payload.get("space_key"), "logistics")
        self.assertEqual(payload.get("max_sources"), 15)
        self.assertEqual(payload.get("max_agents"), 9)
        self.assertEqual(payload.get("max_signals"), 42)
        self.assertTrue(payload.get("include_decisions_log"))

    def test_submit_agent_reflection_posts_expected_payload(self) -> None:
        self.client.submit_agent_reflection(
            AgentReflection(
                agent_id="dispatch_bot",
                reflected_by="dispatch_bot",
                task_id="task-1",
                summary="Learned new gated-access escalation rule.",
                learned_rules=["If gated access fails for 15 minutes, escalate to on-call."],
                decisions_made=["Approved reroute after warehouse confirmation."],
                tools_used=["maps_router"],
                data_sources_used=["orders_api"],
                insights=[
                    AgentReflectionInsight(
                        claim_text="Dispatch bot can reroute deliveries but cannot change billing state.",
                        category="capability",
                        confidence=0.88,
                    )
                ],
            )
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/agents/reflections")
        self.assertEqual(call["method"], "POST")
        payload = call["payload"]
        self.assertEqual(payload.get("project_id"), "omega_demo")
        self.assertEqual(payload.get("agent_id"), "dispatch_bot")
        self.assertEqual(payload.get("reflected_by"), "dispatch_bot")
        self.assertEqual(payload.get("tools_used"), ["maps_router"])
        self.assertEqual(payload.get("data_sources_used"), ["orders_api"])
        self.assertEqual(len(payload.get("insights") or []), 1)

    def test_run_adoption_first_run_bootstrap_posts_expected_payload(self) -> None:
        self.client.run_adoption_first_run_bootstrap(
            created_by="ops_admin",
            profile="support_ops",
            business_profile_key="support_center",
            dry_run=True,
            publish=True,
            include_state_snapshot=False,
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/adoption/first-run/bootstrap")
        self.assertEqual(call["method"], "POST")
        payload = call["payload"]
        self.assertEqual(payload.get("project_id"), "omega_demo")
        self.assertEqual(payload.get("created_by"), "ops_admin")
        self.assertEqual(payload.get("profile"), "support_ops")
        self.assertEqual(payload.get("business_profile_key"), "support_center")
        self.assertTrue(payload.get("dry_run"))
        self.assertIsNone(payload.get("confirm_project_id"))
        self.assertTrue(payload.get("publish"))
        self.assertFalse(payload.get("include_state_snapshot"))

    def test_apply_adoption_wiki_space_template_posts_expected_payload(self) -> None:
        self.client.apply_adoption_wiki_space_template(
            updated_by="ops_admin",
            template_key="support_ops",
            space_key="support",
            publish=True,
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/adoption/wiki-space-templates/apply")
        self.assertEqual(call["method"], "POST")
        payload = call["payload"]
        self.assertEqual(payload.get("project_id"), "omega_demo")
        self.assertEqual(payload.get("template_key"), "support_ops")
        self.assertEqual(payload.get("space_key"), "support")

    def test_execute_adoption_sync_preset_posts_expected_payload(self) -> None:
        self.client.execute_adoption_sync_preset(
            updated_by="ops_admin",
            business_profile_key="logistics_operator",
            dry_run=False,
            include_role_template=True,
            role_template_key="logistics_ops",
            run_bundle_promotion=True,
            bundle_promotion_space_key="logistics",
            bundle_promotion_publish=True,
            bundle_promotion_bootstrap_publish_core=True,
            sync_processor_lookback_minutes=45,
            fail_on_sync_processor_unavailable=True,
            auto_apply_safe_mode_on_critical=False,
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/adoption/sync-presets/execute")
        self.assertEqual(call["method"], "POST")
        payload = call["payload"]
        self.assertEqual(payload.get("project_id"), "omega_demo")
        self.assertEqual(payload.get("updated_by"), "ops_admin")
        self.assertEqual(payload.get("business_profile_key"), "logistics_operator")
        self.assertFalse(payload.get("dry_run"))
        self.assertEqual(payload.get("confirm_project_id"), "omega_demo")
        self.assertEqual(payload.get("role_template_key"), "logistics_ops")
        self.assertTrue(payload.get("run_bundle_promotion"))
        self.assertEqual(payload.get("bundle_promotion_space_key"), "logistics")
        self.assertTrue(payload.get("bundle_promotion_publish"))
        self.assertTrue(payload.get("bundle_promotion_bootstrap_publish_core"))
        self.assertEqual(payload.get("sync_processor_lookback_minutes"), 45)
        self.assertTrue(payload.get("fail_on_sync_processor_unavailable"))
        self.assertFalse(payload.get("auto_apply_safe_mode_on_critical"))

    def test_list_adoption_business_profiles_uses_catalog_endpoint(self) -> None:
        self.client.list_adoption_business_profiles()
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/adoption/business-profiles")
        self.assertEqual(call["method"], "GET")

    def test_run_adoption_agent_wiki_bootstrap_posts_expected_payload(self) -> None:
        self.client.run_adoption_agent_wiki_bootstrap(
            updated_by="ops_admin",
            dry_run=False,
            space_key="operations",
            bootstrap_publish_core=True,
            include_data_sources_catalog=True,
            include_agent_capability_profile=True,
            include_tooling_map=True,
            include_process_playbooks=True,
            include_company_operating_context=True,
            include_operational_logic=True,
            include_state_snapshot=False,
            max_sources=12,
            max_agents=30,
            max_signals=15,
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/adoption/agent-wiki-bootstrap")
        self.assertEqual(call["method"], "POST")
        payload = call["payload"]
        self.assertEqual(payload.get("project_id"), "omega_demo")
        self.assertEqual(payload.get("updated_by"), "ops_admin")
        self.assertFalse(payload.get("dry_run"))
        self.assertEqual(payload.get("confirm_project_id"), "omega_demo")
        self.assertEqual(payload.get("space_key"), "operations")
        self.assertTrue(payload.get("bootstrap_publish_core"))
        self.assertTrue(payload.get("include_tooling_map"))
        self.assertTrue(payload.get("include_process_playbooks"))
        self.assertTrue(payload.get("include_company_operating_context"))
        self.assertFalse(payload.get("include_state_snapshot"))
        self.assertEqual(payload.get("max_sources"), 12)
        self.assertEqual(payload.get("max_agents"), 30)
        self.assertEqual(payload.get("max_signals"), 15)

    def test_get_wiki_state_snapshot_scopes_project_and_limits(self) -> None:
        self.client.get_wiki_state_snapshot(
            space_key="operations",
            max_workstreams=9,
            max_open_items=31,
            max_people_watch=11,
            max_metrics=7,
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/wiki/state")
        self.assertEqual(call["method"], "GET")
        params = call["params"]
        self.assertEqual(params.get("project_id"), "omega_demo")
        self.assertEqual(params.get("space_key"), "operations")
        self.assertEqual(params.get("max_workstreams"), 9)
        self.assertEqual(params.get("max_open_items"), 31)
        self.assertEqual(params.get("max_people_watch"), 11)
        self.assertEqual(params.get("max_metrics"), 7)

    def test_sync_wiki_state_snapshot_posts_expected_payload(self) -> None:
        self.client.sync_wiki_state_snapshot(
            updated_by="ops_admin",
            space_key="operations",
            status="published",
            max_workstreams=10,
            max_open_items=20,
            max_people_watch=8,
            max_metrics=6,
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/wiki/state/sync")
        self.assertEqual(call["method"], "POST")
        payload = call["payload"]
        self.assertEqual(payload.get("project_id"), "omega_demo")
        self.assertEqual(payload.get("updated_by"), "ops_admin")
        self.assertEqual(payload.get("space_key"), "operations")
        self.assertEqual(payload.get("status"), "published")
        self.assertEqual(payload.get("max_workstreams"), 10)
        self.assertEqual(payload.get("max_open_items"), 20)
        self.assertEqual(payload.get("max_people_watch"), 8)
        self.assertEqual(payload.get("max_metrics"), 6)

    def test_get_wiki_change_feed_scopes_project_and_filters(self) -> None:
        self.client.get_wiki_change_feed(
            space_key="operations",
            since="2026-05-03T10:00:00Z",
            since_hours=12,
            limit=15,
            include_reviewed=True,
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/wiki/change-feed")
        self.assertEqual(call["method"], "GET")
        params = call["params"]
        self.assertEqual(params.get("project_id"), "omega_demo")
        self.assertEqual(params.get("space_key"), "operations")
        self.assertEqual(params.get("since"), "2026-05-03T10:00:00Z")
        self.assertEqual(params.get("since_hours"), 12)
        self.assertEqual(params.get("limit"), 15)
        self.assertTrue(params.get("include_reviewed"))

    def test_hydrate_agent_shared_memory_posts_expected_payload(self) -> None:
        self.client.hydrate_agent_shared_memory(
            agent_id="logistics-assistant",
            role="dispatcher",
            space_key="logistics",
            since_hours=18,
            limit=9,
            include_reviewed=True,
            review_policy_mode="reviewed_plus_published",
            memory_tier_mode="reviewed_team",
            max_workstreams=11,
            max_open_items=19,
            max_people_watch=7,
            max_metrics=5,
            max_items_per_section=4,
            freshness_days=10,
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/agents/shared-memory/hydrate")
        self.assertEqual(call["method"], "POST")
        payload = call["payload"]
        self.assertEqual(payload.get("project_id"), "omega_demo")
        self.assertEqual(payload.get("agent_id"), "logistics-assistant")
        self.assertEqual(payload.get("role"), "dispatcher")
        self.assertEqual(payload.get("space_key"), "logistics")
        self.assertEqual(payload.get("since_hours"), 18)
        self.assertEqual(payload.get("limit"), 9)
        self.assertTrue(payload.get("include_reviewed"))
        self.assertEqual(payload.get("review_policy_mode"), "reviewed_plus_published")
        self.assertEqual(payload.get("memory_tier_mode"), "reviewed_team")
        self.assertEqual(payload.get("max_workstreams"), 11)
        self.assertEqual(payload.get("max_open_items"), 19)
        self.assertEqual(payload.get("max_people_watch"), 7)
        self.assertEqual(payload.get("max_metrics"), 5)
        self.assertEqual(payload.get("max_items_per_section"), 4)
        self.assertEqual(payload.get("freshness_days"), 10)

    def test_get_agent_shared_memory_invalidation_posts_expected_payload(self) -> None:
        self.client.get_agent_shared_memory_invalidation(
            agent_id="logistics-assistant",
            role="dispatcher",
            space_key="logistics",
            include_reviewed=True,
            review_policy_mode="auto",
            memory_tier_mode="published_org",
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/agents/shared-memory/invalidation")
        self.assertEqual(call["method"], "POST")
        payload = call["payload"]
        self.assertEqual(payload.get("project_id"), "omega_demo")
        self.assertEqual(payload.get("agent_id"), "logistics-assistant")
        self.assertEqual(payload.get("role"), "dispatcher")
        self.assertEqual(payload.get("space_key"), "logistics")
        self.assertTrue(payload.get("include_reviewed"))
        self.assertEqual(payload.get("review_policy_mode"), "auto")
        self.assertEqual(payload.get("memory_tier_mode"), "published_org")

    def test_get_agent_shared_memory_impact_posts_expected_payload(self) -> None:
        self.client.get_agent_shared_memory_impact(
            space_key="logistics",
            since="2026-05-03T08:00:00Z",
            since_hours=16,
            limit=12,
            include_reviewed=True,
            review_policy_mode="published_only",
            memory_tier_mode="draft_private",
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/agents/shared-memory/impact")
        self.assertEqual(call["method"], "POST")
        payload = call["payload"]
        self.assertEqual(payload.get("project_id"), "omega_demo")
        self.assertEqual(payload.get("space_key"), "logistics")
        self.assertEqual(payload.get("since"), "2026-05-03T08:00:00Z")
        self.assertEqual(payload.get("since_hours"), 16)
        self.assertEqual(payload.get("limit"), 12)
        self.assertTrue(payload.get("include_reviewed"))
        self.assertEqual(payload.get("review_policy_mode"), "published_only")
        self.assertEqual(payload.get("memory_tier_mode"), "draft_private")

    def test_preview_agent_shared_memory_publish_impact_posts_expected_payload(self) -> None:
        self.client.preview_agent_shared_memory_publish_impact(
            agent_id="logistics-assistant",
            role="dispatcher",
            space_key="logistics",
            page_slug="logistics/process-playbooks",
            page_title="Process Playbooks",
            page_type="process",
            entity_key="daily.report",
            change_summary="Updated escalation policy for daily report workflow.",
            include_reviewed=True,
            review_policy_mode="auto",
            memory_tier_mode="reviewed_team",
            limit=7,
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/agents/shared-memory/publish-impact-preview")
        self.assertEqual(call["method"], "POST")
        payload = call["payload"]
        self.assertEqual(payload.get("project_id"), "omega_demo")
        self.assertEqual(payload.get("agent_id"), "logistics-assistant")
        self.assertEqual(payload.get("role"), "dispatcher")
        self.assertEqual(payload.get("space_key"), "logistics")
        self.assertEqual(payload.get("page_slug"), "logistics/process-playbooks")
        self.assertEqual(payload.get("page_title"), "Process Playbooks")
        self.assertEqual(payload.get("page_type"), "process")
        self.assertEqual(payload.get("entity_key"), "daily.report")
        self.assertEqual(payload.get("change_summary"), "Updated escalation policy for daily report workflow.")
        self.assertTrue(payload.get("include_reviewed"))
        self.assertEqual(payload.get("review_policy_mode"), "auto")
        self.assertEqual(payload.get("memory_tier_mode"), "reviewed_team")
        self.assertEqual(payload.get("limit"), 7)

    def test_get_agent_shared_memory_health_scopes_project(self) -> None:
        self.client.get_agent_shared_memory_health(
            agent_id="logistics-assistant",
            role="dispatcher",
            space_key="logistics",
            include_reviewed=True,
            review_policy_mode="auto",
            memory_tier_mode="reviewed_team",
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/agents/shared-memory/health")
        self.assertEqual(call["method"], "GET")
        params = call["params"]
        self.assertEqual(params.get("project_id"), "omega_demo")
        self.assertEqual(params.get("agent_id"), "logistics-assistant")
        self.assertEqual(params.get("role"), "dispatcher")
        self.assertEqual(params.get("space_key"), "logistics")
        self.assertTrue(params.get("include_reviewed"))
        self.assertEqual(params.get("review_policy_mode"), "auto")
        self.assertEqual(params.get("memory_tier_mode"), "reviewed_team")

    def test_upsert_agent_shared_memory_entry_posts_expected_payload(self) -> None:
        self.client.upsert_agent_shared_memory_entry(
            updated_by="ops_admin",
            entry_id=12,
            title="Dispatch handoff note",
            summary="Escalate route-gap checks before first wave dispatch.",
            content="Gap checks should happen before 07:30 handoff.",
            visibility_tier="draft_private",
            status="active",
            space_key="logistics",
            owner_agent_id="logistics-assistant",
            role_scope="dispatcher",
            team_scope="ops",
            entity_key="dispatch.handoff",
            page_slug="logistics/process-playbooks",
            delta_kind="process_change",
            action_hint="refresh_playbook_context",
            importance="high",
            source_kind="agent_note",
            source_ref="shift-briefing",
            metadata={"channel": "night-shift"},
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/agents/shared-memory/entries")
        self.assertEqual(call["method"], "POST")
        payload = call["payload"]
        self.assertEqual(payload.get("project_id"), "omega_demo")
        self.assertEqual(payload.get("updated_by"), "ops_admin")
        self.assertEqual(payload.get("entry_id"), 12)
        self.assertEqual(payload.get("title"), "Dispatch handoff note")
        self.assertEqual(payload.get("summary"), "Escalate route-gap checks before first wave dispatch.")
        self.assertEqual(payload.get("content"), "Gap checks should happen before 07:30 handoff.")
        self.assertEqual(payload.get("visibility_tier"), "draft_private")
        self.assertEqual(payload.get("space_key"), "logistics")
        self.assertEqual(payload.get("owner_agent_id"), "logistics-assistant")
        self.assertEqual(payload.get("role_scope"), "dispatcher")
        self.assertEqual(payload.get("team_scope"), "ops")
        self.assertEqual(payload.get("entity_key"), "dispatch.handoff")
        self.assertEqual(payload.get("page_slug"), "logistics/process-playbooks")
        self.assertEqual(payload.get("delta_kind"), "process_change")
        self.assertEqual(payload.get("action_hint"), "refresh_playbook_context")
        self.assertEqual(payload.get("importance"), "high")
        self.assertEqual(payload.get("source_kind"), "agent_note")
        self.assertEqual(payload.get("source_ref"), "shift-briefing")
        self.assertEqual(payload.get("metadata"), {"channel": "night-shift"})

    def test_list_agent_shared_memory_entries_scopes_project(self) -> None:
        self.client.list_agent_shared_memory_entries(
            agent_id="logistics-assistant",
            role="dispatcher",
            space_key="logistics",
            visibility_tier="reviewed_team",
            include_archived=True,
            limit=17,
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/agents/shared-memory/entries")
        self.assertEqual(call["method"], "GET")
        params = call["params"]
        self.assertEqual(params.get("project_id"), "omega_demo")
        self.assertEqual(params.get("agent_id"), "logistics-assistant")
        self.assertEqual(params.get("role"), "dispatcher")
        self.assertEqual(params.get("space_key"), "logistics")
        self.assertEqual(params.get("visibility_tier"), "reviewed_team")
        self.assertTrue(params.get("include_archived"))
        self.assertEqual(params.get("limit"), 17)

    def test_enable_adoption_safe_mode_posts_expected_payload(self) -> None:
        self.client.enable_adoption_safe_mode(
            updated_by="ops_admin",
            dry_run=False,
            note="critical queue regression",
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/adoption/safe-mode/enable")
        self.assertEqual(call["method"], "POST")
        payload = call["payload"]
        self.assertEqual(payload.get("project_id"), "omega_demo")
        self.assertEqual(payload.get("updated_by"), "ops_admin")
        self.assertFalse(payload.get("dry_run"))
        self.assertEqual(payload.get("confirm_project_id"), "omega_demo")
        self.assertEqual(payload.get("note"), "critical queue regression")

    def test_recommend_adoption_safe_mode_posts_expected_payload(self) -> None:
        self.client.recommend_adoption_safe_mode(
            recommended_by="ops_admin",
            days=21,
            dry_run=False,
            note="claims floor breached",
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/adoption/safe-mode/recommend")
        self.assertEqual(call["method"], "POST")
        payload = call["payload"]
        self.assertEqual(payload.get("project_id"), "omega_demo")
        self.assertEqual(payload.get("recommended_by"), "ops_admin")
        self.assertEqual(payload.get("days"), 21)
        self.assertFalse(payload.get("dry_run"))
        self.assertEqual(payload.get("confirm_project_id"), "omega_demo")
        self.assertEqual(payload.get("note"), "claims floor breached")

    def test_bulk_review_wiki_drafts_posts_expected_payload(self) -> None:
        self.client.bulk_review_wiki_drafts(
            reviewed_by="ops_reviewer",
            action="reject",
            dry_run=False,
            limit=77,
            filter={
                "category": "policy",
                "category_mode": "prefix",
                "source_system": "postgres_sql",
                "assertion_class": "process",
                "min_confidence": 0.8,
            },
            reason="legacy noise",
            dismiss_conflicts=True,
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/wiki/drafts/bulk-review")
        self.assertEqual(call["method"], "POST")
        payload = call["payload"]
        self.assertEqual(payload.get("project_id"), "omega_demo")
        self.assertEqual(payload.get("reviewed_by"), "ops_reviewer")
        self.assertEqual(payload.get("action"), "reject")
        self.assertFalse(payload.get("dry_run"))
        self.assertEqual(payload.get("limit"), 77)
        self.assertEqual((payload.get("filter") or {}).get("category"), "policy")
        self.assertEqual(payload.get("reason"), "legacy noise")

    def test_bulk_review_wiki_drafts_accepts_typed_filter(self) -> None:
        self.client.bulk_review_wiki_drafts(
            reviewed_by="ops_reviewer",
            action="approve",
            dry_run=True,
            filter=WikiDraftBulkReviewFilter(
                category="policy",
                category_mode="prefix",
                source_system="postgres_sql",
                page_type="process",
                assertion_class="policy",
                min_confidence=0.82,
                min_risk_level="medium",
            ),
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/wiki/drafts/bulk-review")
        payload = call["payload"]
        filter_payload = payload.get("filter") if isinstance(payload.get("filter"), dict) else {}
        self.assertEqual(filter_payload.get("category"), "policy")
        self.assertEqual(filter_payload.get("category_mode"), "prefix")
        self.assertEqual(filter_payload.get("source_system"), "postgres_sql")
        self.assertEqual(filter_payload.get("page_type"), "process")
        self.assertEqual(filter_payload.get("assertion_class"), "policy")
        self.assertEqual(filter_payload.get("min_confidence"), 0.82)
        self.assertEqual(filter_payload.get("min_risk_level"), "medium")

    def test_list_wiki_drafts_scopes_project_and_filters(self) -> None:
        self.client.list_wiki_drafts(status="pending_review", limit=77)
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/wiki/drafts")
        self.assertEqual(call["method"], "GET")
        params = call["params"]
        self.assertEqual(params.get("project_id"), "omega_demo")
        self.assertEqual(params.get("status"), "pending_review")
        self.assertEqual(params.get("limit"), 77)

    def test_get_adoption_pipeline_visibility_is_project_scoped(self) -> None:
        self.client.get_adoption_pipeline_visibility(
            days=21,
            source_systems=["postgres_sql", "memory_api"],
            namespaces=["ops", "kb"],
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/adoption/pipeline/visibility")
        self.assertEqual(call["method"], "GET")
        params = call["params"]
        self.assertEqual(params.get("project_id"), "omega_demo")
        self.assertEqual(params.get("days"), 21)
        self.assertEqual(params.get("source_systems"), "postgres_sql,memory_api")
        self.assertEqual(params.get("namespaces"), "ops,kb")

    def test_get_adoption_wiki_quality_report_is_project_scoped(self) -> None:
        self.client.get_adoption_wiki_quality_report(
            days=30,
            placeholder_ratio_max=0.08,
            daily_summary_draft_ratio_max=0.15,
            min_core_published=7,
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/adoption/wiki-quality/report")
        self.assertEqual(call["method"], "GET")
        params = call["params"]
        self.assertEqual(params.get("project_id"), "omega_demo")
        self.assertEqual(params.get("days"), 30)
        self.assertEqual(params.get("placeholder_ratio_max"), 0.08)
        self.assertEqual(params.get("daily_summary_draft_ratio_max"), 0.15)
        self.assertEqual(params.get("min_core_published"), 7)

    def test_get_adoption_wiki_richness_benchmark_is_project_scoped(self) -> None:
        self.client.get_adoption_wiki_richness_benchmark(
            days=18,
            placeholder_ratio_max=0.07,
            daily_summary_draft_ratio_max=0.12,
            min_core_published=8,
            min_contract_pass_ratio=0.75,
            min_average_page_score=0.66,
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/adoption/wiki-richness/benchmark")
        self.assertEqual(call["method"], "GET")
        params = call["params"]
        self.assertEqual(params.get("project_id"), "omega_demo")
        self.assertEqual(params.get("days"), 18)
        self.assertEqual(params.get("placeholder_ratio_max"), 0.07)
        self.assertEqual(params.get("daily_summary_draft_ratio_max"), 0.12)
        self.assertEqual(params.get("min_core_published"), 8)
        self.assertEqual(params.get("min_contract_pass_ratio"), 0.75)
        self.assertEqual(params.get("min_average_page_score"), 0.66)

    def test_get_adoption_rejection_diagnostics_is_project_scoped(self) -> None:
        self.client.get_adoption_rejection_diagnostics(days=11, sample_limit=7)
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/adoption/rejections/diagnostics")
        self.assertEqual(call["method"], "GET")
        params = call["params"]
        self.assertEqual(params.get("project_id"), "omega_demo")
        self.assertEqual(params.get("days"), 11)
        self.assertEqual(params.get("sample_limit"), 7)

    def test_run_adoption_project_reset_posts_expected_payload(self) -> None:
        self.client.run_adoption_project_reset(
            requested_by="ops_admin",
            scopes=["drafts", "wiki", "claims"],
            reason="clean rerun",
            cascade_cleanup_orphan_draft_pages=True,
            dry_run=False,
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/adoption/project-reset")
        self.assertEqual(call["method"], "POST")
        payload = call["payload"]
        self.assertEqual(payload.get("project_id"), "omega_demo")
        self.assertEqual(payload.get("requested_by"), "ops_admin")
        self.assertEqual(payload.get("scopes"), ["drafts", "wiki", "claims"])
        self.assertEqual(payload.get("reason"), "clean rerun")
        self.assertTrue(payload.get("cascade_cleanup_orphan_draft_pages"))
        self.assertFalse(payload.get("dry_run"))
        self.assertEqual(payload.get("confirm_project_id"), "omega_demo")

    def test_get_adoption_sync_cursor_health_is_project_scoped(self) -> None:
        self.client.get_adoption_sync_cursor_health(stale_after_hours=72)
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/adoption/sync/cursor-health")
        self.assertEqual(call["method"], "GET")
        params = call["params"]
        self.assertEqual(params.get("project_id"), "omega_demo")
        self.assertEqual(params.get("stale_after_hours"), 72)

    def test_get_wiki_lifecycle_stats_supports_page_type_aware_mode(self) -> None:
        self.client.get_wiki_lifecycle_stats(
            stale_days=9,
            critical_days=18,
            stale_limit=15,
            space_key="operations",
            page_type_aware=False,
        )
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/wiki/lifecycle/stats")
        self.assertEqual(call["method"], "GET")
        params = call["params"]
        self.assertEqual(params.get("project_id"), "omega_demo")
        self.assertEqual(params.get("space_key"), "operations")
        self.assertEqual(params.get("stale_days"), 9)
        self.assertEqual(params.get("critical_days"), 18)
        self.assertEqual(params.get("stale_limit"), 15)
        self.assertFalse(params.get("page_type_aware"))


if __name__ == "__main__":
    unittest.main()
