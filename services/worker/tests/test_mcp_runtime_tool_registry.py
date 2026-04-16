from __future__ import annotations

import sys
import types
import unittest

from services.mcp.app.server import create_mcp_server


class _FakeRuntime:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.state_calls: list[dict[str, object]] = []

    def get_space_policy_adoption_summary(self, **kwargs):
        self.calls.append(dict(kwargs))
        return {
            "project_id": kwargs["project_id"],
            "space_key": kwargs["space_key"],
            "summary": {"total_updates": 3},
            "available": True,
            "meta": {"limit": kwargs["limit"]},
        }

    def get_state_snapshot(self, **kwargs):
        self.state_calls.append(dict(kwargs))
        return {
            "project_id": kwargs["project_id"],
            "space_key": kwargs.get("space_key"),
            "available": True,
            "state_page": {"slug": "state", "title": "Wiki State Snapshot"},
            "summary_markdown": "| Item | Owner | Deadline |",
        }


class _FakeFastMCP:
    def __init__(self, name: str) -> None:
        self.name = name
        self.tools: dict[str, dict[str, object]] = {}

    def tool(self, *, name: str, description: str):
        def decorator(fn):
            self.tools[name] = {"fn": fn, "description": description}
            return fn

        return decorator

    def run(self, *args, **kwargs):  # pragma: no cover - smoke stub
        return None


class McpToolRegistryTests(unittest.TestCase):
    def test_space_policy_adoption_summary_tool_registered_and_calls_runtime(self) -> None:
        fake_mcp_module = types.ModuleType("mcp")
        fake_mcp_server_module = types.ModuleType("mcp.server")
        fake_fastmcp_module = types.ModuleType("mcp.server.fastmcp")
        fake_fastmcp_module.FastMCP = _FakeFastMCP

        patched_modules = {
            "mcp": fake_mcp_module,
            "mcp.server": fake_mcp_server_module,
            "mcp.server.fastmcp": fake_fastmcp_module,
        }

        runtime = _FakeRuntime()
        original_modules = {key: sys.modules.get(key) for key in patched_modules}
        try:
            sys.modules.update(patched_modules)
            server = create_mcp_server(runtime=runtime)
        finally:
            for key, previous in original_modules.items():
                if previous is None:
                    sys.modules.pop(key, None)
                else:
                    sys.modules[key] = previous

        self.assertIsInstance(server, _FakeFastMCP)
        self.assertIn("get_space_policy_adoption_summary", server.tools)

        tool_fn = server.tools["get_space_policy_adoption_summary"]["fn"]
        result = tool_fn(project_id="omega_demo", space_key="operations_access", limit=123)

        self.assertEqual(result["project_id"], "omega_demo")
        self.assertEqual(result["space_key"], "operations_access")
        self.assertEqual(result["meta"]["limit"], 123)
        self.assertEqual(len(runtime.calls), 1)
        self.assertEqual(runtime.calls[0]["project_id"], "omega_demo")
        self.assertEqual(runtime.calls[0]["space_key"], "operations_access")
        self.assertEqual(runtime.calls[0]["limit"], 123)

    def test_get_state_snapshot_tool_registered_and_calls_runtime(self) -> None:
        fake_mcp_module = types.ModuleType("mcp")
        fake_mcp_server_module = types.ModuleType("mcp.server")
        fake_fastmcp_module = types.ModuleType("mcp.server.fastmcp")
        fake_fastmcp_module.FastMCP = _FakeFastMCP

        patched_modules = {
            "mcp": fake_mcp_module,
            "mcp.server": fake_mcp_server_module,
            "mcp.server.fastmcp": fake_fastmcp_module,
        }

        runtime = _FakeRuntime()
        original_modules = {key: sys.modules.get(key) for key in patched_modules}
        try:
            sys.modules.update(patched_modules)
            server = create_mcp_server(runtime=runtime)
        finally:
            for key, previous in original_modules.items():
                if previous is None:
                    sys.modules.pop(key, None)
                else:
                    sys.modules[key] = previous

        self.assertIsInstance(server, _FakeFastMCP)
        self.assertIn("get_state_snapshot", server.tools)

        tool_fn = server.tools["get_state_snapshot"]["fn"]
        result = tool_fn(project_id="omega_demo", space_key="operations")

        self.assertEqual(result["project_id"], "omega_demo")
        self.assertEqual(result["space_key"], "operations")
        self.assertTrue(bool(result["available"]))
        self.assertEqual(len(runtime.state_calls), 1)
        self.assertEqual(runtime.state_calls[0]["project_id"], "omega_demo")
        self.assertEqual(runtime.state_calls[0]["space_key"], "operations")


if __name__ == "__main__":
    unittest.main()
