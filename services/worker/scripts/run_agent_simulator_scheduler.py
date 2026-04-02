#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Queue due Agent Simulator runs from schedule presets/template configs."
    )
    parser.add_argument(
        "--schedules-file",
        default=None,
        help="Path to JSON file with schedule definitions (object with `schedules` or list).",
    )
    parser.add_argument(
        "--schedules-json",
        default=None,
        help="Inline JSON payload with schedule definitions.",
    )
    parser.add_argument(
        "--project-id",
        action="append",
        dest="project_ids",
        default=[],
        help="Optional project filter. Can be repeated.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve schedules/templates and print actions without DB writes.",
    )
    return parser.parse_args()


def _load_schedule_payload(args: argparse.Namespace) -> Any:
    if args.schedules_file:
        return json.loads(Path(args.schedules_file).read_text(encoding="utf-8"))
    if args.schedules_json:
        return json.loads(args.schedules_json)
    env_payload = os.getenv("SYNAPSE_SIMULATOR_SCHEDULES_JSON")
    if env_payload:
        return json.loads(env_payload)
    raise SystemExit(
        "Provide --schedules-file, --schedules-json, or SYNAPSE_SIMULATOR_SCHEDULES_JSON."
    )


def main() -> None:
    args = parse_args()
    payload = _load_schedule_payload(args)
    try:
        from app.simulator_scheduler import SimulatorSchedulerEngine, normalize_schedules
    except ModuleNotFoundError as exc:
        raise SystemExit("Missing worker dependencies; run with PYTHONPATH=services/worker.") from exc

    schedules = normalize_schedules(payload)
    engine = SimulatorSchedulerEngine()
    project_filter = list(dict.fromkeys(args.project_ids)) or None

    if args.dry_run:
        result = engine.preview(schedules)
        if project_filter:
            filtered = [item for item in result.get("queued", []) if item.get("project_id") in set(project_filter)]
            result["queued"] = filtered
            result["queued_count"] = len(filtered)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    try:
        from app.db import get_conn
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing runtime dependency. Install worker requirements (including psycopg) before running scheduler."
        ) from exc

    with get_conn() as conn:
        result = engine.queue_due_runs(conn, schedules=schedules, project_ids=project_filter)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
