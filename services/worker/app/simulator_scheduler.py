from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha1
import json
from typing import Any
from uuid import uuid4

try:
    from psycopg.types.json import Jsonb
except Exception:  # pragma: no cover - offline mode without psycopg runtime
    class Jsonb:  # type: ignore[override]
        def __init__(self, obj: Any):
            self.obj = obj

from .simulator_templates import build_policy_changes


PRESET_INTERVALS_HOURS: dict[str, int] = {
    "hourly": 1,
    "every_6_hours": 6,
    "daily": 24,
    "weekly": 24 * 7,
}


@dataclass(slots=True)
class SimulatorSchedule:
    project_id: str
    template_id: str
    template_params: dict[str, Any]
    preset: str
    schedule_id: str
    enabled: bool
    created_by: str
    lookback_days: int
    max_sessions: int
    events_per_session: int
    relevance_floor: float
    max_findings: int
    metadata: dict[str, Any]

    @property
    def interval(self) -> timedelta:
        hours = PRESET_INTERVALS_HOURS[self.preset]
        return timedelta(hours=hours)


def normalize_schedules(raw_payload: Any) -> list[SimulatorSchedule]:
    if isinstance(raw_payload, dict):
        if isinstance(raw_payload.get("schedules"), list):
            records = list(raw_payload["schedules"])
        else:
            records = [raw_payload]
    elif isinstance(raw_payload, list):
        records = list(raw_payload)
    else:
        raise ValueError("schedule payload must be an object or list of objects")

    schedules: list[SimulatorSchedule] = []
    for idx, item in enumerate(records):
        if not isinstance(item, dict):
            continue
        project_id = str(item.get("project_id") or "").strip()
        template_id = str(item.get("template_id") or "").strip().lower()
        preset = str(item.get("preset") or "daily").strip().lower()
        if not project_id:
            raise ValueError(f"schedule[{idx}] missing project_id")
        if not template_id:
            raise ValueError(f"schedule[{idx}] missing template_id")
        if preset not in PRESET_INTERVALS_HOURS:
            allowed = ", ".join(sorted(PRESET_INTERVALS_HOURS.keys()))
            raise ValueError(f"schedule[{idx}] has unsupported preset='{preset}' (allowed: {allowed})")

        template_params = item.get("template_params")
        if template_params is None:
            template_params = {}
        if not isinstance(template_params, dict):
            raise ValueError(f"schedule[{idx}] template_params must be an object")

        config_hash = sha1(
            json.dumps(template_params, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:10]
        schedule_id = str(item.get("schedule_id") or f"{project_id}:{template_id}:{preset}:{config_hash}").strip()
        enabled = bool(item.get("enabled", True))
        created_by = str(item.get("created_by") or "simulator_scheduler").strip() or "simulator_scheduler"

        metadata_raw = item.get("metadata")
        metadata = dict(metadata_raw) if isinstance(metadata_raw, dict) else {}

        schedules.append(
            SimulatorSchedule(
                project_id=project_id,
                template_id=template_id,
                template_params=dict(template_params),
                preset=preset,
                schedule_id=schedule_id,
                enabled=enabled,
                created_by=created_by,
                lookback_days=max(1, int(item.get("lookback_days", 14))),
                max_sessions=max(1, int(item.get("max_sessions", 200))),
                events_per_session=max(5, int(item.get("events_per_session", 80))),
                relevance_floor=max(0.0, min(1.0, float(item.get("relevance_floor", 0.22)))),
                max_findings=max(1, int(item.get("max_findings", 1200))),
                metadata=metadata,
            )
        )
    return schedules


class SimulatorSchedulerEngine:
    def preview(self, schedules: list[SimulatorSchedule], *, now: datetime | None = None) -> dict[str, Any]:
        now_utc = (now or datetime.now(UTC)).astimezone(UTC)
        queued: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for item in schedules:
            if not item.enabled:
                skipped.append(
                    {
                        "schedule_id": item.schedule_id,
                        "project_id": item.project_id,
                        "status": "skipped_disabled",
                    }
                )
                continue
            policy_changes = build_policy_changes(item.template_id, params=item.template_params)
            queued.append(
                {
                    "schedule_id": item.schedule_id,
                    "project_id": item.project_id,
                    "template_id": item.template_id,
                    "preset": item.preset,
                    "status": "would_queue",
                    "created_by": item.created_by,
                    "policy_count": len(policy_changes),
                    "queued_at": now_utc.isoformat(),
                }
            )
        return {
            "status": "preview",
            "evaluated": len(schedules),
            "queued_count": len(queued),
            "skipped_count": len(skipped),
            "queued": queued,
            "skipped": skipped,
        }

    def queue_due_runs(
        self,
        conn,
        *,
        schedules: list[SimulatorSchedule],
        project_ids: list[str] | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        allowed_projects = set(project_ids or [])
        now_utc = (now or datetime.now(UTC)).astimezone(UTC)
        queued: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []

        with conn.cursor() as cur:
            for item in schedules:
                if allowed_projects and item.project_id not in allowed_projects:
                    continue
                if not item.enabled:
                    skipped.append(
                        {
                            "schedule_id": item.schedule_id,
                            "project_id": item.project_id,
                            "template_id": item.template_id,
                            "status": "skipped_disabled",
                        }
                    )
                    continue

                policy_changes = build_policy_changes(item.template_id, params=item.template_params)

                cur.execute(
                    """
                    SELECT id::text, status, created_at
                    FROM agent_simulator_runs
                    WHERE project_id = %s
                      AND status IN ('queued', 'running')
                      AND config->'metadata'->'scheduler'->>'schedule_id' = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (item.project_id, item.schedule_id),
                )
                active = cur.fetchone()
                if active is not None:
                    skipped.append(
                        {
                            "schedule_id": item.schedule_id,
                            "project_id": item.project_id,
                            "template_id": item.template_id,
                            "status": "skipped_already_active",
                            "active_run_id": active[0],
                            "active_run_status": active[1],
                            "active_run_created_at": active[2].astimezone(UTC).isoformat(),
                        }
                    )
                    continue

                cur.execute(
                    """
                    SELECT created_at
                    FROM agent_simulator_runs
                    WHERE project_id = %s
                      AND status IN ('completed', 'failed', 'running', 'queued')
                      AND config->'metadata'->'scheduler'->>'schedule_id' = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (item.project_id, item.schedule_id),
                )
                last_row = cur.fetchone()
                if last_row is not None:
                    last_created_at = last_row[0].astimezone(UTC)
                    next_due = last_created_at + item.interval
                    if next_due > now_utc:
                        skipped.append(
                            {
                                "schedule_id": item.schedule_id,
                                "project_id": item.project_id,
                                "template_id": item.template_id,
                                "status": "skipped_not_due",
                                "last_run_at": last_created_at.isoformat(),
                                "next_due_at": next_due.isoformat(),
                                "preset": item.preset,
                            }
                        )
                        continue

                run_id = uuid4()
                config_payload = {
                    "lookback_days": int(item.lookback_days),
                    "max_sessions": int(item.max_sessions),
                    "events_per_session": int(item.events_per_session),
                    "relevance_floor": float(item.relevance_floor),
                    "max_findings": int(item.max_findings),
                    "policy_changes": policy_changes,
                    "metadata": {
                        **dict(item.metadata),
                        "scheduler": {
                            "schedule_id": item.schedule_id,
                            "template_id": item.template_id,
                            "preset": item.preset,
                            "queued_at": now_utc.isoformat(),
                        },
                        "requested_via": "simulator_scheduler",
                    },
                }
                cur.execute(
                    """
                    INSERT INTO agent_simulator_runs (
                      id,
                      project_id,
                      status,
                      mode,
                      created_by,
                      config,
                      result,
                      sessions_scanned,
                      findings_total,
                      started_at
                    )
                    VALUES (%s, %s, 'queued', 'policy_replay', %s, %s, '{}'::jsonb, 0, 0, NOW())
                    """,
                    (
                        run_id,
                        item.project_id,
                        item.created_by,
                        Jsonb(config_payload),
                    ),
                )
                queued.append(
                    {
                        "run_id": str(run_id),
                        "schedule_id": item.schedule_id,
                        "project_id": item.project_id,
                        "template_id": item.template_id,
                        "preset": item.preset,
                        "policy_count": len(policy_changes),
                    }
                )

        return {
            "status": "ok",
            "evaluated": len(schedules),
            "queued_count": len(queued),
            "skipped_count": len(skipped),
            "queued": queued,
            "skipped": skipped,
        }
