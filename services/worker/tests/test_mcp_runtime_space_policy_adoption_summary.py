from __future__ import annotations

from datetime import UTC, datetime
import unittest

from services.mcp.app.runtime import (
    PostgresKnowledgeStore,
    SynapseKnowledgeRuntime,
    _summarize_space_policy_audit_rows,
)


class _FakeStore:
    def __init__(self) -> None:
        self.calls = 0
        self.last_kwargs: dict[str, object] = {}

    def get_project_revision(self, project_id: str) -> str:
        return "snapshot:r1"

    def search_knowledge(self, **kwargs):
        return []

    def get_entity_facts(self, **kwargs):
        return []

    def get_recent_changes(self, **kwargs):
        return []

    def explain_conflicts(self, **kwargs):
        return []

    def get_open_tasks(self, **kwargs):
        return []

    def get_task_details(self, **kwargs):
        return None

    def get_onboarding_pack(self, **kwargs):
        return {
            "project_id": kwargs["project_id"],
            "role": kwargs.get("role"),
            "sections": {
                "critical_playbooks": [],
                "escalation_rules": [],
                "forbidden_actions": [],
                "fresh_changes": [],
            },
        }

    def get_space_policy_adoption_summary(self, **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs
        return {
            "project_id": kwargs["project_id"],
            "space_key": kwargs["space_key"],
            "summary": {
                "total_updates": 4,
                "unique_actors": 2,
                "top_actor": "ops_manager",
                "top_actor_updates": 3,
                "avg_update_interval_days": 1.25,
                "checklist_usage": {
                    "none": 1,
                    "ops_standard": 2,
                    "policy_strict": 1,
                },
                "checklist_transitions": 2,
                "first_updated_at": "2026-04-01T00:00:00+00:00",
                "last_updated_at": "2026-04-04T00:00:00+00:00",
            },
            "available": True,
            "meta": {"sampled_entries": 4, "limit": kwargs.get("limit")},
        }


class McpRuntimeSpacePolicyAdoptionSummaryTests(unittest.TestCase):
    def test_get_space_policy_adoption_summary_is_cached_and_normalized(self) -> None:
        store = _FakeStore()
        runtime = SynapseKnowledgeRuntime(store, cache_ttl_seconds=30, max_cache_entries=256)

        first = runtime.get_space_policy_adoption_summary(
            project_id="omega_demo",
            space_key="Operations / Access",
            limit=9999,
        )
        second = runtime.get_space_policy_adoption_summary(
            project_id="omega_demo",
            space_key="operations_access",
            limit=9999,
        )

        self.assertEqual(first["space_key"], "operations_access")
        self.assertEqual(first["summary"]["top_actor"], "ops_manager")
        self.assertFalse(bool(first.get("cached")))
        self.assertTrue(bool(second.get("cached")))
        self.assertEqual(store.calls, 1)
        self.assertEqual(store.last_kwargs.get("space_key"), "operations_access")
        self.assertEqual(store.last_kwargs.get("limit"), 2000)


class _ScriptedCursor:
    def __init__(self, *, table_name: str | None, rows: list[tuple[object, ...]]) -> None:
        self._table_name = table_name
        self._rows = rows
        self._mode = "none"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql: str, params: tuple[object, ...] | None = None) -> None:
        sql_text = str(sql)
        if "to_regclass('public.wiki_space_policy_audit')" in sql_text:
            self._mode = "table"
            return
        if "FROM wiki_space_policy_audit" in sql_text:
            self._mode = "rows"
            return
        self._mode = "none"

    def fetchone(self):
        if self._mode == "table":
            return (self._table_name,)
        return None

    def fetchall(self):
        if self._mode == "rows":
            return list(self._rows)
        return []


class _ScriptedConn:
    def __init__(self, *, table_name: str | None, rows: list[tuple[object, ...]]) -> None:
        self._table_name = table_name
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return _ScriptedCursor(table_name=self._table_name, rows=self._rows)


class PostgresSpacePolicyAdoptionSummaryTests(unittest.TestCase):
    def test_returns_unavailable_summary_when_audit_table_missing(self) -> None:
        store = PostgresKnowledgeStore(database_url="postgresql://unused")
        store._conn = lambda: _ScriptedConn(table_name=None, rows=[])  # type: ignore[method-assign]

        payload = store.get_space_policy_adoption_summary(
            project_id="omega_demo",
            space_key="Operations / Access",
            limit=100,
        )

        self.assertEqual(payload["space_key"], "operations_access")
        self.assertFalse(bool(payload["available"]))
        self.assertEqual(payload["summary"]["total_updates"], 0)
        self.assertEqual(payload["summary"]["checklist_usage"]["none"], 0)

    def test_handles_mixed_metadata_and_unknown_actor_in_summary(self) -> None:
        rows = [
            (
                "row-1",
                "ops_manager",
                {"metadata": {}},
                {"metadata": {"publish_checklist_preset": "ops_standard"}},
                ["publish_checklist_preset"],
                "set preset",
                datetime(2026, 4, 1, 10, 0, tzinfo=UTC),
            ),
            (
                "row-2",
                "ops_manager",
                {"metadata": {"publish_checklist_preset": "ops_standard"}},
                {"metadata": {"publish_checklist_preset": "custom_unknown"}},
                ["publish_checklist_preset"],
                "custom rollout",
                datetime(2026, 4, 2, 10, 0, tzinfo=UTC),
            ),
            (
                "row-3",
                "",
                {"metadata": {"publish_checklist_preset": "none"}},
                {"metadata": {"publish_checklist_preset": "policy_strict"}},
                ["publish_checklist_preset"],
                "incident hardening",
                datetime(2026, 4, 4, 10, 0, tzinfo=UTC),
            ),
        ]
        summary = _summarize_space_policy_audit_rows(rows)

        self.assertEqual(summary["total_updates"], 3)
        self.assertEqual(summary["unique_actors"], 2)  # ops_manager + unknown
        self.assertEqual(summary["top_actor"], "ops_manager")
        self.assertEqual(summary["top_actor_updates"], 2)
        self.assertEqual(summary["checklist_usage"]["ops_standard"], 1)
        self.assertEqual(summary["checklist_usage"]["none"], 1)
        self.assertEqual(summary["checklist_usage"]["policy_strict"], 1)
        self.assertEqual(summary["checklist_transitions"], 3)
        self.assertEqual(summary["first_updated_at"], "2026-04-01T10:00:00+00:00")
        self.assertEqual(summary["last_updated_at"], "2026-04-04T10:00:00+00:00")
        self.assertAlmostEqual(float(summary["avg_update_interval_days"]), 1.5, places=4)


if __name__ == "__main__":
    unittest.main()
