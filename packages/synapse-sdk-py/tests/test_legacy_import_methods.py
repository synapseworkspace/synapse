from __future__ import annotations

import unittest
from typing import Any

from synapse_sdk.client import Synapse
from synapse_sdk.types import (
    AgentReflection,
    AgentReflectionInsight,
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

    def test_get_adoption_signal_noise_audit_is_project_scoped(self) -> None:
        self.client.get_adoption_signal_noise_audit(days=9, max_items_per_bucket=4)
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/adoption/signal-noise/audit")
        self.assertEqual(call["method"], "GET")
        self.assertEqual(call["params"].get("project_id"), "omega_demo")
        self.assertEqual(call["params"].get("days"), 9)
        self.assertEqual(call["params"].get("max_items_per_bucket"), 4)

    def test_get_adoption_synthesis_prompts_is_project_scoped(self) -> None:
        self.client.get_adoption_synthesis_prompts(days=10, max_items=5)
        call = self.client.calls[-1]
        self.assertEqual(call["path"], "/v1/adoption/synthesis-prompts")
        self.assertEqual(call["method"], "GET")
        self.assertEqual(call["params"].get("project_id"), "omega_demo")
        self.assertEqual(call["params"].get("days"), 10)
        self.assertEqual(call["params"].get("max_items"), 5)

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
            dry_run=False,
            include_role_template=True,
            role_template_key="logistics_ops",
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
        self.assertFalse(payload.get("dry_run"))
        self.assertEqual(payload.get("confirm_project_id"), "omega_demo")
        self.assertEqual(payload.get("role_template_key"), "logistics_ops")
        self.assertEqual(payload.get("sync_processor_lookback_minutes"), 45)
        self.assertTrue(payload.get("fail_on_sync_processor_unavailable"))
        self.assertFalse(payload.get("auto_apply_safe_mode_on_critical"))

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
