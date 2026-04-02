#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process queued Gatekeeper calibration operations.")
    parser.add_argument(
        "--project-id",
        action="append",
        dest="project_ids",
        default=[],
        help="Optional project filter. Can be repeated.",
    )
    parser.add_argument("--limit", type=int, default=10, help="Maximum queued operations to process.")
    parser.add_argument("--heartbeat-sec", type=float, default=3.0, help="Heartbeat interval while operation is running.")
    parser.add_argument(
        "--worker-id",
        default=f"gatekeeper_calibration_queue@{socket.gethostname()}",
        help="Worker identity persisted in operation run records.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        from app.calibration_queue import GatekeeperCalibrationOperationQueueEngine
        from app.db import get_conn
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing runtime dependency. Install worker requirements (including psycopg) before processing calibration queue."
        ) from exc

    engine = GatekeeperCalibrationOperationQueueEngine(worker_id=str(args.worker_id).strip() or "gatekeeper_calibration_queue")
    with get_conn() as conn:
        result = engine.process_queued_runs(
            conn,
            project_ids=list(dict.fromkeys(args.project_ids)) or None,
            limit=max(1, int(args.limit)),
            heartbeat_sec=max(0.5, float(args.heartbeat_sec)),
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
