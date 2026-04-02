from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from synapse_sdk import MemoryBackfillRecord, OpenClawConnector, Synapse, SynapseConfig

from runtime_template import OpenClawRuntimeTemplate


class MemoryTransport:
    """Offline transport for onboarding demo (no API/DB required)."""

    def __init__(self) -> None:
        self.events: list[Any] = []
        self.claims: list[Any] = []
        self.backfills: list[dict[str, Any]] = []

    def send_events(self, events: list[Any], *, idempotency_key: str | None = None) -> None:
        self.events.extend(events)

    def propose_fact(self, claim: Any, *, idempotency_key: str | None = None) -> None:
        self.claims.append(claim)

    def ingest_memory_backfill(self, batch_payload: dict[str, Any], *, idempotency_key: str | None = None) -> None:
        self.backfills.append(batch_payload)

    def summary(self) -> dict[str, int]:
        return {
            "events": len(self.events),
            "claims": len(self.claims),
            "backfill_batches": len(self.backfills),
        }


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value:
            continue
        rows.append(json.loads(value))
    return rows


def _build_search_index(records: list[MemoryBackfillRecord]) -> list[dict[str, Any]]:
    index: list[dict[str, Any]] = []
    for record in records:
        index.append(
            {
                "entity_key": record.entity_key or "general",
                "category": record.category or "operations",
                "title": f"{record.entity_key or 'general'}::{record.category or 'operations'}",
                "fact": record.content,
                "source_id": record.source_id,
                "tags": list(record.tags),
            }
        )
    return index


def _search_index(
    index: list[dict[str, Any]],
    *,
    query: str,
    limit: int,
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    terms = [part for part in query.lower().split() if part]
    entity_filter = str(filters.get("entity_key", "")).strip().lower()
    category_filter = str(filters.get("category", "")).strip().lower()
    scored: list[tuple[int, dict[str, Any]]] = []

    for row in index:
        haystack = f"{row['title']} {row['fact']} {' '.join(row['tags'])}".lower()
        if entity_filter and entity_filter != str(row.get("entity_key", "")).lower():
            continue
        if category_filter and category_filter != str(row.get("category", "")).lower():
            continue
        score = 0
        for term in terms:
            if term in haystack:
                score += 1
        if score > 0 or not terms:
            scored.append((score, row))

    scored.sort(key=lambda item: (item[0], len(item[1]["fact"])), reverse=True)
    return [item[1] for item in scored[: max(1, limit)]]


def _seed_tasks() -> dict[str, dict[str, Any]]:
    return {
        "task-omega-card-reminder": {
            "id": "task-omega-card-reminder",
            "title": "Add gate-card reminder to BC Omega dispatch flow",
            "status": "todo",
            "assignee": "agent_dispatch",
            "entity_key": "bc_omega",
            "priority": "high",
            "history": [],
        },
        "task-wh1-quarantine": {
            "id": "task-wh1-quarantine",
            "title": "Notify clients about Warehouse #1 quarantine window",
            "status": "in_progress",
            "assignee": "agent_support",
            "entity_key": "warehouse_1",
            "priority": "critical",
            "history": [],
        },
    }


def run_demo(dataset_path: Path | None = None) -> dict[str, Any]:
    base_dir = Path(__file__).resolve().parent
    source_path = dataset_path or base_dir / "dataset" / "openclaw_seed_memory.jsonl"
    rows = _load_jsonl(source_path)

    memory_records: list[MemoryBackfillRecord] = []
    runtime_events: list[tuple[str, dict[str, Any]]] = []
    for row in rows:
        kind = str(row.get("kind", "")).strip().lower()
        if kind == "memory":
            memory_records.append(
                MemoryBackfillRecord(
                    source_id=str(row["source_id"]),
                    content=str(row["content"]),
                    observed_at=row.get("observed_at"),
                    entity_key=row.get("entity_key"),
                    category=row.get("category"),
                    metadata=dict(row.get("metadata") or {}),
                    tags=list(row.get("tags") or []),
                )
            )
            continue
        if kind == "event":
            event_name = str(row.get("event_name", "tool:result"))
            payload = dict(row.get("payload") or {})
            runtime_events.append((event_name, payload))

    search_index = _build_search_index(memory_records)
    tasks = _seed_tasks()

    transport = MemoryTransport()
    synapse = Synapse(
        SynapseConfig(
            api_url="http://localhost:8080",
            project_id="openclaw_onboarding_demo",
        ),
        transport=transport,
    )
    runtime = OpenClawRuntimeTemplate()

    def list_tasks(*, limit: int = 20, assignee: str | None = None, entity_key: str | None = None, include_closed: bool = False) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for task in tasks.values():
            if assignee and assignee != task.get("assignee"):
                continue
            if entity_key and entity_key != task.get("entity_key"):
                continue
            if not include_closed and task.get("status") in {"done", "canceled"}:
                continue
            output.append({k: v for k, v in task.items() if k != "history"})
        return output[: max(1, limit)]

    def update_task_status(task_id: str, *, status: str, updated_by: str | None = None, note: str | None = None) -> dict[str, Any]:
        task = tasks.get(task_id)
        if task is None:
            return {"status": "not_found", "task_id": task_id}
        task["status"] = status
        task["history"].append({"updated_by": updated_by, "status": status, "note": note})
        return {"status": "ok", "task": {k: v for k, v in task.items() if k != "history"}}

    connector = OpenClawConnector(
        synapse,
        search_knowledge=lambda query, limit, filters: _search_index(
            search_index,
            query=query,
            limit=limit,
            filters=filters or {},
        ),
        list_tasks=list_tasks,
        update_task_status=update_task_status,
        default_agent_id="agent_dispatch",
        default_session_id="oc-session-1001",
    )
    connector.attach(runtime)

    for event_name, payload in runtime_events:
        runtime.emit(event_name, payload)

    search_result = runtime.call_tool(
        "synapse_search_wiki",
        query="omega card access after 10:00",
        limit=3,
        filters={"entity_key": "bc_omega"},
    )
    task_snapshot_before = runtime.call_tool("synapse_get_open_tasks", entity_key="bc_omega", limit=10)
    task_update = runtime.call_tool(
        "synapse_update_task_status",
        task_id="task-omega-card-reminder",
        status="in_progress",
        updated_by="agent_dispatch",
        note="Reminder was inserted into dispatch checklist.",
    )
    proposal = runtime.call_tool(
        "synapse_propose_to_wiki",
        entity_key="bc_omega",
        category="access_policy",
        claim_text="BC Omega gate is card-only after 10:00; dispatch must send access-card reminder before departure.",
        source_id="oc-session-1001",
        confidence=0.92,
        metadata={"origin": "openclaw_onboarding"},
    )
    task_snapshot_after = runtime.call_tool("synapse_get_open_tasks", entity_key="bc_omega", limit=10)

    batch_id = synapse.backfill_memory(
        memory_records,
        source_system="openclaw_seed_memory",
        chunk_size=2,
    )
    synapse.flush()

    return {
        "dataset_path": str(source_path),
        "dataset_rows": len(rows),
        "memory_records": len(memory_records),
        "runtime_events": len(runtime_events),
        "registered_tools": runtime.list_tools(),
        "search_result_count": len(search_result),
        "search_top_result": search_result[0] if search_result else None,
        "task_snapshot_before": task_snapshot_before,
        "task_update": task_update,
        "task_snapshot_after": task_snapshot_after,
        "proposal": proposal,
        "backfill_batch_id": batch_id,
        "transport": transport.summary(),
        "captured_runtime_events": len(runtime.event_log),
    }


if __name__ == "__main__":
    summary = run_demo()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
