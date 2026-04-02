from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

import anyio

from synapse_sdk import MCPContextHelper, OpenClawConnector, Synapse, SynapseConfig


class MemoryTransport:
    def __init__(self) -> None:
        self.events: list[Any] = []
        self.claims: list[Any] = []
        self.backfills: list[dict[str, Any]] = []

    def send_events(self, events: list[Any], *, idempotency_key: str | None = None) -> None:
        self.events.extend(events)

    def propose_fact(self, claim: Any, *, idempotency_key: str | None = None) -> None:
        self.claims.append((claim, idempotency_key))

    def ingest_memory_backfill(self, batch_payload: dict[str, Any], *, idempotency_key: str | None = None) -> None:
        self.backfills.append(batch_payload)


class Runtime:
    def __init__(self) -> None:
        self.handlers: dict[str, Any] = {}
        self.tools: dict[str, Any] = {}

    def on(self, event_name: str, handler: Any) -> None:
        self.handlers[event_name] = handler

    def register_tool(self, name: str, handler: Any, description: str | None = None) -> None:
        self.tools[name] = {"handler": handler, "description": description}

    def emit(self, event_name: str, payload: dict[str, Any]) -> None:
        handler = self.handlers.get(event_name)
        if handler is None:
            raise RuntimeError(f"hook {event_name!r} is not registered")
        handler(payload)


def _try_import_mcp() -> tuple[Any, Any, Any, Any]:
    try:
        from mcp.client.session import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client
        from mcp.server.fastmcp import FastMCP
    except Exception as exc:
        raise RuntimeError("mcp package is required. Install with `pip install mcp`.") from exc
    return ClientSession, StdioServerParameters, stdio_client, FastMCP


def _build_demo_server(fastmcp_cls: Any) -> Any:
    server = fastmcp_cls("synapse-mcp-e2e")

    @server.tool(name="search_knowledge")
    def search_knowledge(
        project_id: str,
        query: str,
        limit: int = 10,
        entity_key: str | None = None,
        category: str | None = None,
        page_type: str | None = None,
    ) -> dict[str, Any]:
        base = [
            {
                "statement_text": "BC Omega gate requires physical card after 10:00",
                "page": {"slug": "bc-omega", "entity_key": "bc_omega", "page_type": "entity"},
                "section_key": "access_rules",
                "score": 0.96,
                "category": "access",
            },
            {
                "statement_text": "Dispatch must warn drivers about checkpoint validation",
                "page": {"slug": "dispatch-playbook", "entity_key": "dispatch", "page_type": "policy"},
                "section_key": "dispatch_rules",
                "score": 0.84,
                "category": "operations",
            },
        ]
        filtered = []
        for item in base:
            if entity_key and item["page"]["entity_key"] != entity_key:
                continue
            if category and item.get("category") != category:
                continue
            if page_type and item["page"]["page_type"] != page_type:
                continue
            filtered.append(item)
        return {
            "project_id": project_id,
            "query": query,
            "results": filtered[: max(1, min(100, int(limit)))],
            "revision": "demo-rev-1",
            "cached": False,
        }

    @server.tool(name="get_entity_facts")
    def get_entity_facts(
        project_id: str,
        entity_key: str,
        limit: int = 50,
        category: str | None = None,
        include_non_current: bool = False,
    ) -> dict[str, Any]:
        facts = [
            {"statement_text": "Card-only after 10:00", "section_key": "access_rules"},
            {"statement_text": "Manual gate opening is disabled", "section_key": "access_rules"},
        ]
        if category and category != "access":
            facts = []
        return {
            "project_id": project_id,
            "entity_key": entity_key,
            "facts": facts[: max(1, min(500, int(limit)))],
            "include_non_current": include_non_current,
            "revision": "demo-rev-1",
            "cached": False,
        }

    @server.tool(name="get_recent_changes")
    def get_recent_changes(project_id: str, limit: int = 20, since_hours: int = 168) -> dict[str, Any]:
        changes = [
            {
                "change_type": "moderation",
                "action": "approve",
                "created_at": "2026-03-31T10:00:00Z",
                "page": {"slug": "bc-omega"},
            }
        ]
        return {
            "project_id": project_id,
            "since_hours": since_hours,
            "changes": changes[: max(1, min(200, int(limit)))],
            "cached": False,
            "revision": "demo-rev-1",
        }

    @server.tool(name="explain_conflicts")
    def explain_conflicts(
        project_id: str,
        limit: int = 20,
        resolution_status: str | None = "open",
        entity_key: str | None = None,
    ) -> dict[str, Any]:
        return {
            "project_id": project_id,
            "resolution_status": resolution_status,
            "conflicts": [],
            "cached": False,
            "revision": "demo-rev-1",
        }

    return server


def _run_server_stdio() -> int:
    _, _, _, fastmcp_cls = _try_import_mcp()
    server = _build_demo_server(fastmcp_cls)
    try:
        server.run(transport="stdio")
    except TypeError:
        server.run()
    return 0


def _extract_tool_names(payload: Any) -> list[str]:
    tools = getattr(payload, "tools", None)
    if tools is None and isinstance(payload, dict):
        tools = payload.get("tools")
    if not isinstance(tools, list):
        return []
    names: list[str] = []
    for tool in tools:
        if isinstance(tool, dict):
            value = tool.get("name")
        else:
            value = getattr(tool, "name", None)
        if value:
            names.append(str(value))
    return names


async def _run_client_e2e() -> dict[str, Any]:
    ClientSession, StdioServerParameters, stdio_client, _ = _try_import_mcp()
    script_path = Path(__file__).resolve()
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(script_path), "--server"],
        cwd=str(script_path.parent.parent),
        env=dict(os.environ),
    )
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            listed = await session.list_tools()
            listed_tool_names = sorted(_extract_tool_names(listed))

            def _run_openclaw_flow() -> dict[str, Any]:
                def _call_tool(name: str, arguments: dict[str, Any]) -> Any:
                    return anyio.from_thread.run(session.call_tool, name, arguments)

                helper = MCPContextHelper(project_id="openclaw_mcp_e2e", call_tool=_call_tool)
                search_callback = helper.make_openclaw_search_callback(default_filters={"entity_key": "bc_omega"})
                context_md = helper.build_context_markdown(
                    query="BC Omega access policy",
                    entity_key="bc_omega",
                    include_recent_changes=True,
                )

                transport = MemoryTransport()
                synapse = Synapse(
                    SynapseConfig(api_url="http://localhost:8080", project_id="openclaw_mcp_e2e"),
                    transport=transport,
                )
                runtime = Runtime()
                connector = OpenClawConnector(synapse, search_knowledge=search_callback)
                connector.attach(runtime, hook_events=["tool:result"])

                runtime.emit(
                    "tool:result",
                    {
                        "sessionKey": "s-1",
                        "result": "Driver confirms card-only rule at BC Omega checkpoint.",
                    },
                )

                tool_result = runtime.tools["synapse_search_wiki"]["handler"](
                    "What should driver know for BC Omega?",
                    limit=3,
                    filters={"category": "access"},
                )
                proposal = runtime.tools["synapse_propose_to_wiki"]["handler"](
                    entity_key="bc_omega",
                    category="access_policy",
                    claim_text="Dispatch reminder: BC Omega requires physical access card after 10:00.",
                    source_id="openclaw_mcp_e2e:s-1",
                    confidence=0.91,
                )
                synapse.flush()

                return {
                    "context_markdown": context_md,
                    "search_result_count": len(tool_result) if isinstance(tool_result, list) else 0,
                    "proposal_status": proposal.get("status"),
                    "runtime_tool_names": sorted(runtime.tools.keys()),
                    "captured_events": len(transport.events),
                    "captured_claims": len(transport.claims),
                }

            flow = await anyio.to_thread.run_sync(_run_openclaw_flow)
            return {
                "listed_tools": listed_tool_names,
                **flow,
            }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="E2E OpenClaw -> MCP runtime -> Synapse context injection demo")
    parser.add_argument("--server", action="store_true", help="Run stdio MCP server mode")
    parser.add_argument("--check", action="store_true", help="Run assertions and return non-zero on failure")
    return parser.parse_args()


def _run_checks(payload: dict[str, Any]) -> None:
    tools = set(payload.get("listed_tools", []))
    assert "search_knowledge" in tools, payload
    assert "get_entity_facts" in tools, payload
    assert "get_recent_changes" in tools, payload
    assert payload.get("search_result_count", 0) >= 1, payload
    assert payload.get("proposal_status") == "queued", payload
    assert payload.get("captured_events", 0) >= 1, payload
    assert payload.get("captured_claims", 0) >= 1, payload
    context_md = str(payload.get("context_markdown", ""))
    assert "Relevant Knowledge" in context_md, payload
    assert "Entity Facts" in context_md, payload


def main() -> int:
    args = parse_args()
    if args.server:
        return _run_server_stdio()

    result = anyio.run(_run_client_e2e)
    if args.check:
        _run_checks(result)
        print("openclaw mcp e2e ok")
        return 0

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
