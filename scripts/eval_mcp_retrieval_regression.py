#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import deque
from pathlib import Path
from typing import Any

from app.runtime import SynapseKnowledgeRuntime


class InMemoryGraphStore:
    def __init__(self) -> None:
        self.docs = [
            {
                "statement_id": "s1",
                "statement_text": "Card required.",
                "section_key": "access_rules",
                "page": {
                    "id": "p1",
                    "title": "BC Omega Access",
                    "slug": "bc-omega",
                    "entity_key": "bc_omega",
                    "page_type": "entity",
                },
                "category": "access",
                "related_entities": ["warehouse_9"],
            },
            {
                "statement_id": "s2",
                "statement_text": "Card required.",
                "section_key": "dispatch_rules",
                "page": {
                    "id": "p2",
                    "title": "Dispatch Checklist",
                    "slug": "dispatch-checklist",
                    "entity_key": "dispatch_center",
                    "page_type": "policy",
                },
                "category": "operations",
                "related_entities": ["bc_omega"],
            },
            {
                "statement_id": "s3",
                "statement_text": "Warehouse closes at 20:00.",
                "section_key": "operations",
                "page": {
                    "id": "p3",
                    "title": "Warehouse 9",
                    "slug": "warehouse-9",
                    "entity_key": "warehouse_9",
                    "page_type": "entity",
                },
                "category": "operations",
                "related_entities": [],
            },
            {
                "statement_id": "s4",
                "statement_text": "Card required for dispatch handoff.",
                "section_key": "handoff_rules",
                "page": {
                    "id": "p4",
                    "title": "Route Hub Guide",
                    "slug": "route-hub-guide",
                    "entity_key": "route_hub",
                    "page_type": "policy",
                },
                "category": "operations",
                "related_entities": ["dispatch_center"],
            },
            {
                "statement_id": "s5",
                "statement_text": "Card required for handoff planning.",
                "section_key": "handoff_rules",
                "page": {
                    "id": "p5",
                    "title": "Support Ops Notes",
                    "slug": "support-ops-notes",
                    "entity_key": "support_ops",
                    "page_type": "policy",
                },
                "category": "operations",
                "related_entities": [],
            },
        ]

    def get_project_revision(self, project_id: str) -> str:
        return "eval-rev-1"

    def search_knowledge(
        self,
        *,
        project_id: str,
        query: str,
        limit: int,
        entity_key: str | None,
        category: str | None,
        page_type: str | None,
        related_entity_key: str | None,
    ) -> list[dict[str, Any]]:
        q = query.strip().lower()
        graph_hops = _compute_graph_hops(self.docs, related_entity_key=related_entity_key, max_hops=3)
        results: list[tuple[float, int, dict[str, Any]]] = []
        for idx, item in enumerate(self.docs):
            page = item["page"]
            if entity_key and page["entity_key"].lower() != str(entity_key).lower():
                continue
            if category and str(item.get("category") or "").lower() != str(category).lower():
                continue
            if page_type and page["page_type"].lower() != str(page_type).lower():
                continue

            lexical = _lexical_score(q, item["statement_text"], page["title"], page["slug"], page["entity_key"])
            hops = graph_hops.get(str(page["entity_key"]).lower())
            graph_boost = _graph_boost(hops)
            score = lexical + graph_boost

            row = {
                "statement_id": item["statement_id"],
                "statement_text": item["statement_text"],
                "section_key": item["section_key"],
                "page": dict(page),
                "category": item["category"],
                "score": round(score, 4),
                "graph_boost": graph_boost,
                "graph_hops": hops,
            }
            results.append((score, idx, row))

        results.sort(key=lambda record: (-record[0], record[1]))
        return [row for _, _, row in results[: max(1, min(100, int(limit)))]]

    def get_entity_facts(
        self,
        *,
        project_id: str,
        entity_key: str,
        limit: int,
        category: str | None,
        include_non_current: bool,
    ) -> list[dict[str, Any]]:
        return []

    def get_recent_changes(
        self,
        *,
        project_id: str,
        limit: int,
        since_hours: int,
    ) -> list[dict[str, Any]]:
        return []

    def explain_conflicts(
        self,
        *,
        project_id: str,
        limit: int,
        resolution_status: str | None,
        entity_key: str | None,
    ) -> list[dict[str, Any]]:
        return []


def _lexical_score(query: str, *texts: str) -> float:
    tokens = {token for token in re.findall(r"[a-z0-9_]+", query.lower()) if token}
    if not tokens:
        return 0.0
    blob = " ".join(texts).lower()
    hits = sum(1 for token in tokens if token in blob)
    return hits / len(tokens)


def _graph_boost(hops: int | None) -> float:
    if hops is None:
        return 0.0
    if hops <= 1:
        return 0.2
    if hops == 2:
        return 0.12
    if hops == 3:
        return 0.06
    return 0.03


def _compute_graph_hops(
    docs: list[dict[str, Any]],
    *,
    related_entity_key: str | None,
    max_hops: int,
) -> dict[str, int]:
    seed = str(related_entity_key or "").strip().lower()
    if not seed:
        return {}

    edges: dict[str, set[str]] = {}
    for item in docs:
        page = item.get("page") if isinstance(item, dict) else {}
        source = str((page or {}).get("entity_key") or "").strip().lower()
        if not source:
            continue
        for rel in item.get("related_entities") or []:
            target = str(rel or "").strip().lower()
            if not target:
                continue
            edges.setdefault(source, set()).add(target)
            edges.setdefault(target, set()).add(source)

    hops: dict[str, int] = {}
    queue: deque[tuple[str, int]] = deque([(seed, 0)])
    visited: set[str] = {seed}
    while queue:
        node, depth = queue.popleft()
        if depth >= max_hops:
            continue
        for neighbor in sorted(edges.get(node, set())):
            if neighbor in visited:
                continue
            next_depth = depth + 1
            visited.add(neighbor)
            hops[neighbor] = next_depth
            queue.append((neighbor, next_depth))
    return hops


def _run_case(runtime: SynapseKnowledgeRuntime, case: dict[str, Any]) -> dict[str, Any]:
    case_id = str(case.get("id") or "unknown")
    payload = runtime.search_knowledge(
        project_id="eval_project",
        query=str(case.get("query") or ""),
        limit=int(case.get("limit") or 3),
        entity_key=case.get("entity_key"),
        category=case.get("category"),
        page_type=case.get("page_type"),
        related_entity_key=case.get("related_entity_key"),
    )
    results = payload.get("results") or []
    top = results[0] if isinstance(results, list) and results else {}
    top_entity = None
    if isinstance(top, dict):
        page = top.get("page")
        if isinstance(page, dict):
            top_entity = page.get("entity_key")
    expected = case.get("expected_top_entity")
    ok = str(top_entity) == str(expected)
    return {
        "id": case_id,
        "ok": ok,
        "expected_top_entity": expected,
        "predicted_top_entity": top_entity,
        "top_score": top.get("score") if isinstance(top, dict) else None,
        "graph_boost": top.get("graph_boost") if isinstance(top, dict) else None,
        "graph_hops": top.get("graph_hops") if isinstance(top, dict) else None,
        "result_count": len(results) if isinstance(results, list) else 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic MCP retrieval regression dataset.")
    parser.add_argument("--dataset", default="eval/mcp_retrieval_cases.json", help="Path to retrieval dataset")
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print compact summary without per-case result payloads.",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(json.dumps({"status": "error", "error": "dataset_not_found", "dataset": str(dataset_path)}))
        sys.exit(2)

    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    cases = payload.get("cases") or []
    if not cases:
        print(json.dumps({"status": "error", "error": "dataset_empty", "dataset": str(dataset_path)}))
        sys.exit(2)

    runtime = SynapseKnowledgeRuntime(store=InMemoryGraphStore(), cache_ttl_seconds=1, max_cache_entries=100)
    results = [_run_case(runtime, case) for case in cases]
    passed = sum(1 for item in results if item["ok"])
    failed = len(results) - passed
    top1_accuracy = round(passed / max(len(results), 1), 4)

    minimum_metrics = (payload.get("meta") or {}).get("minimum_metrics") or {}
    threshold = float(minimum_metrics.get("top1_accuracy", 1.0))
    metric_errors: list[str] = []
    if top1_accuracy < threshold:
        metric_errors.append(
            f"metric top1_accuracy below threshold: actual={top1_accuracy:.4f} threshold={threshold:.4f}"
        )

    summary = {
        "status": "ok" if failed == 0 and not metric_errors else "failed",
        "dataset": str(dataset_path),
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "metric_errors": metric_errors,
        "metrics": {"top1_accuracy": top1_accuracy},
    }
    if args.summary_only:
        summary["failed_case_ids"] = [str(item.get("id")) for item in results if not item.get("ok")]
    else:
        summary["cases"] = results
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if failed > 0 or metric_errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
