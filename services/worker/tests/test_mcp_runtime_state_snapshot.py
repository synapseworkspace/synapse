from __future__ import annotations

import unittest

from services.mcp.app.runtime import SynapseKnowledgeRuntime


class _FakeStore:
    def __init__(self) -> None:
        self.state_calls = 0

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
            "sections": {
                "critical_playbooks": [],
                "escalation_rules": [],
                "forbidden_actions": [],
                "fresh_changes": [],
            },
        }

    def get_space_policy_adoption_summary(self, **kwargs):
        return {
            "project_id": kwargs["project_id"],
            "space_key": kwargs["space_key"],
            "summary": {"total_updates": 0},
            "available": True,
            "meta": {"limit": kwargs.get("limit", 200)},
        }

    def get_state_snapshot(self, **kwargs):
        self.state_calls += 1
        return {
            "project_id": kwargs["project_id"],
            "space_key": kwargs.get("space_key"),
            "available": True,
            "state_page": {
                "id": "state-1",
                "title": "Wiki State Snapshot",
                "slug": "state",
                "page_type": "state",
                "updated_at": "2026-04-17T00:00:00+00:00",
                "version": 3,
                "created_by": "synapse",
                "created_at": "2026-04-17T00:00:00+00:00",
            },
            "summary_markdown": "| Item | Owner | Deadline |\n|---|---|---|\n| Escalation queue overflow | ops_manager | 17.04.2026 |",
        }


class McpRuntimeStateSnapshotTests(unittest.TestCase):
    def test_get_state_snapshot_is_cached(self) -> None:
        store = _FakeStore()
        runtime = SynapseKnowledgeRuntime(store, cache_ttl_seconds=30, max_cache_entries=256)

        first = runtime.get_state_snapshot(project_id="omega_demo", space_key="operations")
        second = runtime.get_state_snapshot(project_id="omega_demo", space_key="operations")

        self.assertEqual(first["project_id"], "omega_demo")
        self.assertEqual(first["state_page"]["slug"], "state")
        self.assertFalse(bool(first.get("cached")))
        self.assertTrue(bool(second.get("cached")))
        self.assertEqual(store.state_calls, 1)

    def test_search_knowledge_includes_state_snapshot_in_context_snippets(self) -> None:
        store = _FakeStore()
        runtime = SynapseKnowledgeRuntime(store, cache_ttl_seconds=30, max_cache_entries=256)

        payload = runtime.search_knowledge(
            project_id="omega_demo",
            query="What should I check first before escalation?",
            limit=5,
            max_context_snippets=3,
        )

        snippets = list(payload.get("context_injection", {}).get("snippets") or [])
        self.assertGreaterEqual(len(snippets), 1)
        self.assertEqual(snippets[0].get("page_type"), "state")
        self.assertEqual(snippets[0].get("page_slug"), "state")
        explainability = payload.get("explainability", {})
        self.assertTrue(bool(explainability.get("state_snapshot", {}).get("included")))
        self.assertEqual(explainability.get("state_snapshot", {}).get("slug"), "state")


if __name__ == "__main__":
    unittest.main()
