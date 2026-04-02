#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process queued Agent Simulator runs.")
    parser.add_argument(
        "--project-id",
        action="append",
        dest="project_ids",
        default=[],
        help="Optional project filter. Can be repeated.",
    )
    parser.add_argument("--limit", type=int, default=10, help="Maximum queued runs to process.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        from app.db import get_conn
        from app.simulator import AgentSimulatorEngine
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing runtime dependency. Install worker requirements (including psycopg) before processing simulator queue."
        ) from exc

    engine = AgentSimulatorEngine()
    with get_conn() as conn:
        result = engine.process_queued_runs(
            conn,
            project_ids=list(dict.fromkeys(args.project_ids)) or None,
            limit=args.limit,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
