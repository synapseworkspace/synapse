#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any


def _skip(message: str) -> int:
    print(json.dumps({"status": "skipped", "reason": message}))
    return 0


try:
    import psycopg
except Exception:
    raise SystemExit(_skip("psycopg_not_installed"))


@dataclass
class PolicyViolation:
    project_id: str
    code: str
    detail: str


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Queue governance policy assertions.")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", "postgresql://synapse:synapse@localhost:55432/synapse"))
    parser.add_argument("--window-hours", type=int, default=24)
    parser.add_argument("--project-limit", type=int, default=100)
    parser.add_argument("--max-critical-without-alert-target", type=int, default=0)
    parser.add_argument("--max-congestion-without-owner", type=int, default=0)
    parser.add_argument("--max-unreviewed-pauses", type=int, default=0)
    return parser.parse_args()


def _health_for_row(depth_total: int, queue_depth_warn: int, stale_workers: int) -> str:
    if stale_workers > 0:
        return "critical"
    if depth_total >= max(1, queue_depth_warn) * 2:
        return "critical"
    if depth_total > max(1, queue_depth_warn):
        return "watch"
    return "healthy"


def _run(args: argparse.Namespace) -> int:
    if os.getenv("SYNAPSE_SKIP_QUEUE_GOVERNANCE_POLICY", "0") == "1":
        return _skip("disabled_by_env")

    try:
        conn = psycopg.connect(args.database_url)
    except Exception as exc:
        return _skip(f"db_unavailable:{exc}")

    window_hours = max(1, min(168, int(args.window_hours)))
    since = datetime.now(UTC) - timedelta(hours=window_hours)
    violations: list[PolicyViolation] = []
    projects: list[str] = []
    summaries: list[dict[str, Any]] = []

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH ranked_runs AS (
                      SELECT project_id, MAX(created_at) AS last_seen_at
                      FROM gatekeeper_calibration_operation_runs
                      WHERE mode = 'async'
                      GROUP BY project_id
                    ),
                    ranked_controls AS (
                      SELECT project_id, MAX(updated_at) AS last_seen_at
                      FROM gatekeeper_calibration_queue_controls
                      GROUP BY project_id
                    ),
                    ranked_ownership AS (
                      SELECT project_id, MAX(updated_at) AS last_seen_at
                      FROM gatekeeper_calibration_queue_ownership
                      GROUP BY project_id
                    ),
                    merged AS (
                      SELECT project_id, last_seen_at FROM ranked_runs
                      UNION ALL
                      SELECT project_id, last_seen_at FROM ranked_controls
                      UNION ALL
                      SELECT project_id, last_seen_at FROM ranked_ownership
                    )
                    SELECT project_id
                    FROM (
                      SELECT project_id, MAX(last_seen_at) AS rank_ts
                      FROM merged
                      GROUP BY project_id
                    ) ranked
                    ORDER BY rank_ts DESC NULLS LAST, project_id ASC
                    LIMIT %s
                    """,
                    (max(1, min(200, int(args.project_limit))),),
                )
                projects = [str(row[0]) for row in cur.fetchall() if row and row[0]]

                for project_id in projects:
                    cur.execute(
                        """
                        SELECT
                          paused_until,
                          COALESCE(worker_lag_sla_minutes, 20),
                          COALESCE(queue_depth_warn, 12)
                        FROM gatekeeper_calibration_queue_controls
                        WHERE project_id = %s
                        LIMIT 1
                        """,
                        (project_id,),
                    )
                    control_row = cur.fetchone()
                    paused_until = control_row[0] if control_row else None
                    lag_sla = int(control_row[1] or 20) if control_row else 20
                    queue_warn = int(control_row[2] or 12) if control_row else 12
                    pause_active = bool(paused_until and paused_until > datetime.now(UTC))

                    cur.execute(
                        """
                        SELECT
                          COUNT(*) FILTER (WHERE status = 'queued')::int,
                          COUNT(*) FILTER (WHERE status = 'running')::int,
                          COUNT(*) FILTER (WHERE status = 'cancel_requested')::int,
                          COUNT(*) FILTER (
                            WHERE status IN ('running', 'cancel_requested')
                              AND COALESCE(heartbeat_at, updated_at, created_at) < NOW() - (%s * INTERVAL '1 minute')
                          )::int
                        FROM gatekeeper_calibration_operation_runs
                        WHERE project_id = %s
                          AND mode = 'async'
                        """,
                        (lag_sla, project_id),
                    )
                    run_row = cur.fetchone() or (0, 0, 0, 0)
                    queue_depth = int(run_row[0] or 0) + int(run_row[1] or 0) + int(run_row[2] or 0)
                    stale_workers = int(run_row[3] or 0)
                    health = _health_for_row(queue_depth, queue_warn, stale_workers)

                    cur.execute(
                        """
                        SELECT owner_name, owner_contact
                        FROM gatekeeper_calibration_queue_ownership
                        WHERE project_id = %s
                        LIMIT 1
                        """,
                        (project_id,),
                    )
                    owner_row = cur.fetchone()
                    has_owner = bool(owner_row and ((owner_row[0] and str(owner_row[0]).strip()) or (owner_row[1] and str(owner_row[1]).strip())))

                    cur.execute(
                        """
                        SELECT COUNT(*)::int
                        FROM gatekeeper_alert_targets
                        WHERE project_id = %s
                          AND enabled = TRUE
                        """,
                        (project_id,),
                    )
                    alert_targets = int((cur.fetchone() or (0,))[0] or 0)

                    latest_pause_event_id: int | None = None
                    if pause_active:
                        cur.execute(
                            """
                            SELECT id
                            FROM gatekeeper_calibration_queue_control_events
                            WHERE project_id = %s
                              AND action IN ('pause', 'bulk_pause')
                            ORDER BY created_at DESC, id DESC
                            LIMIT 1
                            """,
                            (project_id,),
                        )
                        pause_row = cur.fetchone()
                        latest_pause_event_id = int(pause_row[0]) if pause_row else None

                    latest_pause_status: str | None = None
                    if latest_pause_event_id is not None:
                        cur.execute(
                            """
                            SELECT status
                            FROM gatekeeper_calibration_queue_audit_annotations
                            WHERE event_id = %s
                            ORDER BY created_at DESC, id DESC
                            LIMIT 1
                            """,
                            (latest_pause_event_id,),
                        )
                        status_row = cur.fetchone()
                        latest_pause_status = str(status_row[0]) if status_row and status_row[0] else None

                    summaries.append(
                        {
                            "project_id": project_id,
                            "health": health,
                            "queue_depth": queue_depth,
                            "queue_depth_warn": queue_warn,
                            "stale_workers": stale_workers,
                            "pause_active": pause_active,
                            "has_owner": has_owner,
                            "alert_targets": alert_targets,
                            "latest_pause_status": latest_pause_status,
                        }
                    )

                    if health == "critical" and alert_targets <= 0:
                        violations.append(
                            PolicyViolation(
                                project_id=project_id,
                                code="critical_without_alert_target",
                                detail="Critical queue health requires at least one enabled alert target.",
                            )
                        )
                    if queue_depth > queue_warn and not has_owner:
                        violations.append(
                            PolicyViolation(
                                project_id=project_id,
                                code="congestion_without_owner",
                                detail="Queue exceeds warning threshold but project has no ownership routing.",
                            )
                        )
                    if pause_active and latest_pause_status != "resolved":
                        violations.append(
                            PolicyViolation(
                                project_id=project_id,
                                code="unreviewed_pause_window",
                                detail="Pause window is active without a resolved audit annotation.",
                            )
                        )
    except Exception as exc:
        return _skip(f"policy_check_unavailable:{exc}")
    finally:
        conn.close()

    counters = {
        "critical_without_alert_target": sum(1 for v in violations if v.code == "critical_without_alert_target"),
        "congestion_without_owner": sum(1 for v in violations if v.code == "congestion_without_owner"),
        "unreviewed_pause_window": sum(1 for v in violations if v.code == "unreviewed_pause_window"),
    }
    limits = {
        "critical_without_alert_target": max(0, int(args.max_critical_without_alert_target)),
        "congestion_without_owner": max(0, int(args.max_congestion_without_owner)),
        "unreviewed_pause_window": max(0, int(args.max_unreviewed_pauses)),
    }
    violations_exceeded = {
        key: counters[key]
        for key in counters
        if counters[key] > limits[key]
    }

    payload = {
        "status": "ok" if not violations_exceeded else "failed",
        "window_hours": window_hours,
        "projects_evaluated": len(projects),
        "counters": counters,
        "limits": limits,
        "violations_exceeded": violations_exceeded,
        "violations": [
            {"project_id": v.project_id, "code": v.code, "detail": v.detail}
            for v in violations[:200]
        ],
        "summaries": summaries[:200],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 1 if violations_exceeded else 0


def main() -> int:
    args = _parse_args()
    return _run(args)


if __name__ == "__main__":
    raise SystemExit(main())
