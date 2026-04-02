#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run legacy import scheduled sync orchestration.")
    parser.add_argument(
        "--project-id",
        action="append",
        dest="project_ids",
        default=[],
        help="Optional project id filter. Can be repeated.",
    )
    parser.add_argument(
        "--all-projects",
        action="store_true",
        help="Resolve projects from configured legacy import sources.",
    )
    parser.add_argument(
        "--skip-enqueue",
        action="store_true",
        help="Skip due-source enqueue stage.",
    )
    parser.add_argument(
        "--skip-process",
        action="store_true",
        help="Skip queued-run processing stage.",
    )
    parser.add_argument("--enqueue-limit", type=int, default=20, help="Maximum due sources to enqueue.")
    parser.add_argument("--process-limit", type=int, default=20, help="Maximum queued runs to process.")
    parser.add_argument("--api-url", default="http://localhost:8080", help="Synapse API URL for backfill upload.")
    parser.add_argument("--api-key", default=None, help="Optional Synapse API key.")
    parser.add_argument("--requested-by", default="legacy_sync_scheduler", help="Actor name for scheduler-created runs.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        from app.db import get_conn
        from app.legacy_sync import LegacySyncEngine
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing runtime dependency. Install worker requirements (including psycopg) before running legacy sync scheduler."
        ) from exc

    engine = LegacySyncEngine(
        api_url=args.api_url,
        api_key=args.api_key,
        default_requested_by=args.requested_by,
    )
    summary: dict[str, Any] = {
        "status": "ok",
        "project_ids": [],
        "enqueued": {},
        "processed": {},
    }
    with get_conn() as conn:
        project_ids = list(dict.fromkeys(args.project_ids))
        if args.all_projects:
            discovered = engine.discover_projects(conn)
            for project_id in discovered:
                if project_id not in project_ids:
                    project_ids.append(project_id)
        summary["project_ids"] = project_ids
        project_filter = project_ids or None

        if not args.skip_enqueue:
            summary["enqueued"] = engine.enqueue_due_sources(
                conn,
                project_ids=project_filter,
                limit=max(1, args.enqueue_limit),
                requested_by=args.requested_by,
            )
        else:
            summary["enqueued"] = {"status": "skipped"}

        if not args.skip_process:
            summary["processed"] = engine.process_queued_runs(
                conn,
                project_ids=project_filter,
                limit=max(1, args.process_limit),
            )
        else:
            summary["processed"] = {"status": "skipped"}

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
