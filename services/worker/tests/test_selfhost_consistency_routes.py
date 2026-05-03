from __future__ import annotations

import unittest

try:
    from services.api.app.main import get_selfhost_consistency_gate
except Exception:  # pragma: no cover - optional API deps in minimal envs
    get_selfhost_consistency_gate = None


@unittest.skipIf(get_selfhost_consistency_gate is None, "api helpers unavailable")
class SelfhostConsistencyRouteTests(unittest.TestCase):
    def _route_check(
        self,
        *,
        route_path: str,
        route_search: str = "",
        ui_features: str = "synthesis_observability_panel",
    ) -> dict[str, object]:
        payload = get_selfhost_consistency_gate(
            web_build="0.1.0",
            ui_profile="core",
            route_path=route_path,
            route_search=route_search,
            ui_features=ui_features,
        )
        checks = payload.get("checks") or []
        for check in checks:
            if check.get("key") == "route_is_wiki":
                return check
        self.fail("route_is_wiki check missing")

    def test_direct_wiki_slug_route_is_valid(self) -> None:
        check = self._route_check(route_path="/synapse/wiki/agents/index")
        self.assertEqual(check["status"], "ok")
        self.assertEqual(check["message"], "Route is wiki-first.")

    def test_query_based_wiki_route_under_wiki_prefix_is_valid(self) -> None:
        check = self._route_check(
            route_path="/synapse/wiki",
            route_search="?project=hw_ai_agents&wiki_page=agents%2Findex&wiki_space=agents&wiki_status=published",
        )
        self.assertEqual(check["status"], "ok")
        self.assertEqual(check["message"], "Route is wiki-first.")
        self.assertTrue(bool((check.get("meta") or {}).get("has_wiki_query_context")))

    def test_query_based_workspace_entry_without_wiki_prefix_is_valid(self) -> None:
        check = self._route_check(
            route_path="/synapse/",
            route_search="?project=hw_ai_agents&wiki_page=agents%2Findex&wiki_space=agents",
        )
        self.assertEqual(check["status"], "ok")
        self.assertEqual(
            check["message"],
            "You are viewing a query-based wiki workspace entrypoint.",
        )

    def test_operations_route_is_valid(self) -> None:
        check = self._route_check(route_path="/synapse/operations")
        self.assertEqual(check["status"], "ok")
        self.assertEqual(
            check["message"],
            "You are viewing an operations route outside the default wiki entrypoint.",
        )

    def test_unrelated_route_without_workspace_context_warns(self) -> None:
        check = self._route_check(route_path="/synapse/healthcheck", ui_features="")
        self.assertEqual(check["status"], "warning")
        self.assertEqual(
            check["message"],
            "Route is outside the expected wiki/operations workspace entrypoints.",
        )


if __name__ == "__main__":
    unittest.main()
