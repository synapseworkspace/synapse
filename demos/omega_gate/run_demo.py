from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from typing import Any

import psycopg

from synapse_sdk.client import SynapseClient
from synapse_sdk.integrations.openclaw import OpenClawConnector
from synapse_sdk.types import SynapseConfig


@dataclass
class DemoRuntime:
    handlers: dict[str, Any]
    tools: dict[str, Any]

    def __init__(self) -> None:
        self.handlers = {}
        self.tools = {}

    def on(self, event_name: str, handler: Any) -> None:
        self.handlers[event_name] = handler

    def register_tool(self, name: str, handler: Any, description: str | None = None) -> None:
        self.tools[name] = {
            "handler": handler,
            "description": description,
        }

    def emit(self, event_name: str, payload: dict[str, Any]) -> None:
        handler = self.handlers.get(event_name)
        if not handler:
            raise RuntimeError(f"No handler registered for event {event_name!r}")
        handler(payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Synapse Omega Gate vertical demo")
    parser.add_argument("--api-url", default=os.getenv("SYNAPSE_API_URL", "http://localhost:8080"))
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", "postgresql://synapse:synapse@localhost:55432/synapse"))
    parser.add_argument("--project-id", default="omega_demo")
    parser.add_argument("--skip-db-check", action="store_true")
    return parser.parse_args()


def make_search_callback() -> Any:
    def _search(query: str, limit: int, filters: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "entity_key": "bc_omega",
                "title": "BC Omega Access Rules",
                "fact": "Gate access requires magnetic access cards.",
                "query": query,
                "limit": limit,
                "filters": filters,
                "source": "synapse_wiki",
            }
        ]

    return _search


def run_demo(api_url: str, project_id: str) -> dict[str, Any]:
    client = SynapseClient(
        SynapseConfig(
            api_url=api_url,
            project_id=project_id,
        )
    )

    runtime = DemoRuntime()
    connector = OpenClawConnector(
        client=client,
        search_knowledge=make_search_callback(),
        default_agent_id="openclaw_dispatcher",
    )
    connector.attach(
        runtime,
        hook_events=["tool:result", "message:received", "agent:completed"],
    )

    now = datetime.now(UTC).isoformat()

    # Simulate three independent reports from OpenClaw events.
    runtime.emit(
        "tool:result",
        {
            "sessionKey": "session-12",
            "timestamp": now,
            "tool": "driver_chat",
            "result": "Driver #12 says BC Omega gate switched to card-only access.",
        },
    )
    runtime.emit(
        "message:received",
        {
            "sessionKey": "session-45",
            "timestamp": now,
            "channel": "dispatch",
            "text": "Driver #45 confirms no manual gate opening anymore.",
        },
    )
    runtime.emit(
        "agent:completed",
        {
            "sessionKey": "session-88",
            "timestamp": now,
            "summary": "Route blocked until card validated at BC Omega checkpoint.",
        },
    )

    search_result = runtime.tools["synapse_search_wiki"]["handler"](
        "What is the latest access policy for BC Omega?",
        limit=3,
    )

    proposal_result = runtime.tools["synapse_propose_to_wiki"]["handler"](
        entity_key="bc_omega",
        category="access_policy",
        claim_text="BC Omega gate is card-only. Dispatch must remind drivers to bring access cards.",
        source_id="omega_demo_evidence_bundle_1",
        source_type="external_event",
        confidence=0.92,
        metadata={"domain": "logistics", "priority": "high"},
    )

    client.flush()

    return {
        "search_result": search_result,
        "proposal_result": proposal_result,
    }


def query_db(database_url: str, project_id: str, claim_id: str) -> dict[str, Any]:
    with psycopg.connect(database_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM events
                WHERE project_id = %s
                """,
                (project_id,),
            )
            event_count = cur.fetchone()[0]

            cur.execute(
                """
                SELECT claim_id, status, created_at
                FROM claim_proposals
                WHERE claim_id = %s
                """,
                (claim_id,),
            )
            proposal_row = cur.fetchone()

    return {
        "event_count": event_count,
        "proposal_row": {
            "claim_id": str(proposal_row[0]) if proposal_row else None,
            "status": proposal_row[1] if proposal_row else None,
            "created_at": proposal_row[2].isoformat() if proposal_row else None,
        },
    }


def main() -> None:
    args = parse_args()
    demo_result = run_demo(args.api_url, args.project_id)

    print("=== Omega Demo Result ===")
    print(json.dumps(demo_result, ensure_ascii=False, indent=2))

    claim_id = demo_result["proposal_result"]["claim_id"]

    if not args.skip_db_check:
        db_result = query_db(args.database_url, args.project_id, claim_id)
        print("=== DB Verification ===")
        print(json.dumps(db_result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
