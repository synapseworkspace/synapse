from __future__ import annotations

import unittest
from typing import Any

from synapse_sdk.client import Synapse
from synapse_sdk.types import SynapseConfig


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


if __name__ == "__main__":
    unittest.main()
