from __future__ import annotations

import unittest

from services.mcp.app.runtime import SynapseKnowledgeRuntime


class _FakeStore:
    def __init__(self) -> None:
        self.calls = 0

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
        self.calls += 1
        return {
            "project_id": kwargs["project_id"],
            "role": kwargs.get("role"),
            "freshness_days": kwargs.get("freshness_days"),
            "sections": {
                "critical_playbooks": [{"statement_id": "st-1"}],
                "escalation_rules": [],
                "forbidden_actions": [],
                "fresh_changes": [],
            },
        }


class McpRuntimeOnboardingPackTests(unittest.TestCase):
    def test_get_onboarding_pack_is_cached(self) -> None:
        store = _FakeStore()
        runtime = SynapseKnowledgeRuntime(store, cache_ttl_seconds=30, max_cache_entries=256)

        first = runtime.get_onboarding_pack(project_id="omega_demo", role="support", max_items_per_section=3, freshness_days=7)
        second = runtime.get_onboarding_pack(project_id="omega_demo", role="support", max_items_per_section=3, freshness_days=7)

        self.assertEqual(first["project_id"], "omega_demo")
        self.assertEqual(first["sections"]["critical_playbooks"][0]["statement_id"], "st-1")
        self.assertFalse(bool(first.get("cached")))
        self.assertTrue(bool(second.get("cached")))
        self.assertEqual(store.calls, 1)


if __name__ == "__main__":
    unittest.main()
