#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run shared-memory maintenance processors.")
    parser.add_argument("--project-id", action="append", dest="project_ids", default=[], help="Optional project id filter. Can be repeated.")
    parser.add_argument("--all-projects", action="store_true", help="Discover projects from shared-memory tables.")
    parser.add_argument("--skip-pending", action="store_true", help="Skip queued fanout delivery processing.")
    parser.add_argument("--skip-retries", action="store_true", help="Skip due retry processing.")
    parser.add_argument("--skip-lifecycle", action="store_true", help="Skip shared-memory entry lifecycle processing.")
    parser.add_argument("--pending-limit", type=int, default=50, help="Maximum pending fanout deliveries processed per project.")
    parser.add_argument("--retry-limit", type=int, default=50, help="Maximum due retries processed per project.")
    parser.add_argument("--lifecycle-limit", type=int, default=100, help="Maximum due lifecycle entries processed per project.")
    parser.add_argument("--api-url", default="http://localhost:8080", help="Synapse API URL.")
    parser.add_argument("--api-key", default=None, help="Optional Synapse API key.")
    parser.add_argument("--updated-by", default="shared_memory_maintenance", help="Actor name for maintenance operations.")
    parser.add_argument("--space-key", default=None, help="Optional space key scope.")
    parser.add_argument("--dry-run", action="store_true", help="Preview maintenance work without mutating state.")
    return parser.parse_args()


def _request_json(api_url: str, path: str, *, api_key: str | None, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{api_url.rstrip('/')}{path}"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=30.0) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body.strip() else {}
    except HTTPError as exc:  # pragma: no cover - operational path
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"shared-memory maintenance api error {exc.code}: {detail[:500]}") from exc
    except URLError as exc:  # pragma: no cover - operational path
        raise SystemExit(f"shared-memory maintenance api unreachable: {exc}") from exc


def _discover_projects() -> list[str]:
    try:
        from app.db import get_conn
    except ModuleNotFoundError as exc:  # pragma: no cover - runtime packaging guard
        raise SystemExit(
            "Missing runtime dependency. Install worker requirements (including psycopg) before running shared-memory maintenance."
        ) from exc
    project_ids: list[str] = []
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT project_id
                FROM (
                  SELECT DISTINCT project_id FROM shared_memory_entries
                  UNION
                  SELECT DISTINCT project_id FROM shared_memory_fanout_hooks
                  UNION
                  SELECT DISTINCT project_id FROM shared_memory_fanout_deliveries
                ) projects
                WHERE project_id IS NOT NULL AND project_id <> ''
                ORDER BY project_id ASC
                """
            )
            rows = cur.fetchall() or []
    for row in rows:
        project_id = str(row[0] or "").strip()
        if project_id and project_id not in project_ids:
            project_ids.append(project_id)
    return project_ids


def _process_project(api_url: str, api_key: str | None, project_id: str, args: argparse.Namespace) -> dict[str, Any]:
    result: dict[str, Any] = {"project_id": project_id}
    common_payload = {
        "project_id": project_id,
        "updated_by": str(args.updated_by or "shared_memory_maintenance").strip() or "shared_memory_maintenance",
        "dry_run": bool(args.dry_run),
        "space_key": str(args.space_key).strip() if args.space_key is not None and str(args.space_key).strip() else None,
    }
    if not args.skip_pending:
        payload = {**common_payload, "limit": max(1, int(args.pending_limit))}
        result["pending"] = _request_json(api_url, "/v1/agents/shared-memory/fanout-deliveries/process-pending", api_key=api_key, method="POST", payload=payload)
    else:
        result["pending"] = {"status": "skipped"}
    if not args.skip_retries:
        payload = {**common_payload, "limit": max(1, int(args.retry_limit))}
        result["retries"] = _request_json(api_url, "/v1/agents/shared-memory/fanout-deliveries/process-due-retries", api_key=api_key, method="POST", payload=payload)
    else:
        result["retries"] = {"status": "skipped"}
    if not args.skip_lifecycle:
        payload = {**common_payload, "limit": max(1, int(args.lifecycle_limit))}
        result["lifecycle"] = _request_json(api_url, "/v1/agents/shared-memory/entries/process-lifecycle", api_key=api_key, method="POST", payload=payload)
    else:
        result["lifecycle"] = {"status": "skipped"}
    health_query = urlencode({"project_id": project_id, **({"space_key": args.space_key} if args.space_key else {})})
    result["health"] = _request_json(api_url, f"/v1/agents/shared-memory/health?{health_query}", api_key=api_key, method="GET")
    return result


def main() -> None:
    args = parse_args()
    project_ids = list(dict.fromkeys(str(item).strip() for item in args.project_ids if str(item).strip()))
    if args.all_projects:
        for project_id in _discover_projects():
            if project_id not in project_ids:
                project_ids.append(project_id)
    summary: dict[str, Any] = {
        "status": "ok",
        "dry_run": bool(args.dry_run),
        "project_ids": project_ids,
        "results": [],
    }
    for project_id in project_ids:
        summary["results"].append(_process_project(str(args.api_url or "http://localhost:8080").strip() or "http://localhost:8080", args.api_key, project_id, args))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
