#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any, Callable

from synapse_sdk import OpenClawConnector, Synapse, SynapseConfig, Task


class MemoryTransport:
    def __init__(self) -> None:
        self.events: list[Any] = []
        self.claims: list[Any] = []
        self.tasks: dict[str, dict[str, Any]] = {}
        self.task_events: dict[str, list[dict[str, Any]]] = {}

    def send_events(self, events: list[Any], *, idempotency_key: str | None = None) -> None:
        self.events.extend(events)

    def propose_fact(self, claim: Any, *, idempotency_key: str | None = None) -> None:
        self.claims.append((claim, idempotency_key))

    def ingest_memory_backfill(self, batch_payload: dict[str, Any], *, idempotency_key: str | None = None) -> None:
        return None

    def request_json(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        payload = payload or {}
        params = params or {}
        project_id = str(params.get("project_id") or payload.get("project_id") or "openclaw_contract")

        if path == "/v1/tasks" and method == "GET":
            return {"tasks": list(self.tasks.values())}

        if path == "/v1/tasks" and method == "POST":
            task_id = str(payload.get("task_id") or "task-1")
            task = {
                "id": task_id,
                "project_id": project_id,
                "title": str(payload.get("title") or "Untitled"),
                "status": str(payload.get("status") or "todo"),
                "priority": str(payload.get("priority") or "normal"),
                "assignee": payload.get("assignee"),
                "entity_key": payload.get("entity_key"),
                "created_by": payload.get("created_by"),
                "updated_by": payload.get("updated_by"),
                "metadata": payload.get("metadata") or {},
            }
            self.tasks[task_id] = task
            self.task_events.setdefault(task_id, []).append({"event_type": "created", "payload": {"task": task}})
            return {"status": "created", "task": task}

        if path.startswith("/v1/tasks/") and method == "GET":
            task_id = path.split("/")[3]
            return {
                "task": self.tasks.get(task_id),
                "events": self.task_events.get(task_id, []),
                "links": [],
            }

        if path.startswith("/v1/tasks/") and path.endswith("/status") and method == "POST":
            task_id = path.split("/")[3]
            task = self.tasks.get(task_id)
            if task is None:
                return {"status": "error", "reason": "task_not_found"}
            task["status"] = str(payload.get("status") or task["status"])
            task["updated_by"] = payload.get("updated_by")
            self.task_events.setdefault(task_id, []).append({"event_type": "status_changed", "payload": dict(payload)})
            return {"status": "ok", "changed": True, "task": task}

        return {}


class RuntimeBase:
    def __init__(self) -> None:
        self.handlers: dict[str, Callable[[dict[str, Any]], Any]] = {}
        self.tools: dict[str, Callable[..., Any]] = {}
        self.tool_meta: dict[str, dict[str, Any]] = {}

    def emit(self, event_name: str, payload: dict[str, Any]) -> None:
        handler = self.handlers.get(event_name)
        if handler is None:
            raise RuntimeError(f"hook {event_name!r} is not registered")
        handler(payload)

    def call_tool(self, name: str, *args: Any, **kwargs: Any) -> Any:
        if name not in self.tools:
            raise RuntimeError(f"tool {name!r} is not registered")
        return self.tools[name](*args, **kwargs)


class RuntimeOnPositional(RuntimeBase):
    def on(self, event_name: str, handler: Callable[[dict[str, Any]], Any]) -> None:
        self.handlers[event_name] = handler

    def register_tool(self, name: str, handler: Callable[..., Any], description: str | None = None) -> None:
        self.tools[name] = handler
        self.tool_meta[name] = {"description": description}


class RuntimeHookKeyword(RuntimeBase):
    def register_hook(self, event_name: str, handler: Callable[[dict[str, Any]], Any]) -> None:
        self.handlers[event_name] = handler

    def register_tool(self, *, name: str, handler: Callable[..., Any], description: str | None = None) -> None:
        self.tools[name] = handler
        self.tool_meta[name] = {"description": description}


@dataclass
class RuntimeCase:
    name: str
    runtime_factory: Callable[[], RuntimeBase]


def _run_case(case: RuntimeCase) -> dict[str, Any]:
    transport = MemoryTransport()
    client = Synapse(
        SynapseConfig(api_url="http://localhost:8080", project_id="openclaw_contract"),
        transport=transport,
    )

    # Seed one task to validate task tools through connector.
    client.upsert_task(
        Task(title="Verify Omega gate access", entity_key="bc_omega", priority="high"),
        created_by="ops_manager",
        task_id="task-omega-1",
    )

    search_calls: list[dict[str, Any]] = []

    def _search(query: str, limit: int, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        search_calls.append({"query": query, "limit": limit, "filters": filters or {}})
        return [
            {
                "statement_text": "BC Omega gate requires physical card after 10:00",
                "page": {"slug": "bc-omega", "entity_key": "bc_omega"},
            }
        ]

    runtime = case.runtime_factory()
    connector = OpenClawConnector(
        client,
        search_knowledge=_search,
        default_agent_id="openclaw_dispatcher",
        provenance_secret="openclaw-contract-secret",
        provenance_key_id="contract-key-1",
    )
    connector.attach(runtime, hook_events=("tool:result", "message:received"))

    runtime.emit("tool:result", {"sessionKey": "session-a", "result": "driver confirms card policy"})

    search_result = runtime.call_tool(
        "synapse_search_wiki",
        "Omega gate policy",
        limit=3,
        filters={"entity_key": "bc_omega", "category": "access"},
    )
    proposal = runtime.call_tool(
        "synapse_propose_to_wiki",
        entity_key="bc_omega",
        category="access_policy",
        claim_text="Dispatch reminder: BC Omega card-only after 10:00.",
        source_id="openclaw_contract:session-a",
        confidence=0.92,
    )
    tasks_before = runtime.call_tool("synapse_get_open_tasks", entity_key="bc_omega", limit=10)
    status_result = runtime.call_tool(
        "synapse_update_task_status",
        "task-omega-1",
        status="in_progress",
        note="policy confirmed by driver",
    )

    client.flush()
    task_state = client.get_task("task-omega-1")
    first_claim = transport.claims[0][0] if transport.claims else None
    first_evidence = None
    evidence_provenance = None
    metadata_provenance = None
    if first_claim is not None:
        evidence = getattr(first_claim, "evidence", None)
        if isinstance(evidence, list) and evidence:
            first_evidence = evidence[0]
            evidence_provenance = getattr(first_evidence, "provenance", None)
        claim_metadata = getattr(first_claim, "metadata", None)
        if isinstance(claim_metadata, dict):
            metadata_provenance = claim_metadata.get("synapse_provenance")

    return {
        "case": case.name,
        "runtime_tools": sorted(runtime.tools.keys()),
        "search_calls": len(search_calls),
        "search_result_count": len(search_result) if isinstance(search_result, list) else 0,
        "proposal_status": proposal.get("status") if isinstance(proposal, dict) else None,
        "tasks_before_count": len(tasks_before.get("tasks", [])) if isinstance(tasks_before, dict) else 0,
        "task_status_result": status_result.get("status") if isinstance(status_result, dict) else None,
        "task_status_after": ((task_state.get("task") or {}).get("status") if isinstance(task_state, dict) else None),
        "captured_events": len(transport.events),
        "captured_claims": len(transport.claims),
        "provenance_present": bool(isinstance(evidence_provenance, dict)),
        "provenance_mode": (evidence_provenance or {}).get("mode") if isinstance(evidence_provenance, dict) else None,
        "provenance_signature_alg": (
            (evidence_provenance or {}).get("signature_alg") if isinstance(evidence_provenance, dict) else None
        ),
        "provenance_signature_len": (
            len(str((evidence_provenance or {}).get("signature") or ""))
            if isinstance(evidence_provenance, dict)
            else 0
        ),
        "provenance_key_id": (evidence_provenance or {}).get("key_id") if isinstance(evidence_provenance, dict) else None,
        "metadata_provenance_match": bool(
            isinstance(evidence_provenance, dict)
            and isinstance(metadata_provenance, dict)
            and evidence_provenance.get("signature") == metadata_provenance.get("signature")
        ),
    }


def _run_checks(results: list[dict[str, Any]]) -> None:
    required_tools = {
        "synapse_search_wiki",
        "synapse_propose_to_wiki",
        "synapse_get_open_tasks",
        "synapse_update_task_status",
    }
    for item in results:
        tools = set(item.get("runtime_tools") or [])
        assert required_tools.issubset(tools), item
        assert int(item.get("search_calls") or 0) >= 1, item
        assert int(item.get("search_result_count") or 0) >= 1, item
        assert item.get("proposal_status") == "queued", item
        assert int(item.get("tasks_before_count") or 0) >= 1, item
        assert item.get("task_status_result") == "ok", item
        assert item.get("task_status_after") == "in_progress", item
        assert int(item.get("captured_events") or 0) >= 3, item
        assert int(item.get("captured_claims") or 0) >= 1, item
        assert bool(item.get("provenance_present")), item
        assert item.get("provenance_mode") == "signed", item
        assert item.get("provenance_signature_alg") == "hmac-sha256", item
        assert int(item.get("provenance_signature_len") or 0) == 64, item
        assert item.get("provenance_key_id") == "contract-key-1", item
        assert bool(item.get("metadata_provenance_match")), item


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpenClaw runtime contract matrix integration check.")
    parser.add_argument("--check", action="store_true", help="Run assertions and exit non-zero on failure.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cases = [
        RuntimeCase(name="runtime_on_positional", runtime_factory=RuntimeOnPositional),
        RuntimeCase(name="runtime_hook_keyword", runtime_factory=RuntimeHookKeyword),
    ]
    results = [_run_case(case) for case in cases]

    if args.check:
        _run_checks(results)
        print("openclaw runtime contract matrix ok")
        return 0

    print(json.dumps({"results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
