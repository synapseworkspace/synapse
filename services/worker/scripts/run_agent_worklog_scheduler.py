#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    from app.db import get_conn as _get_conn
except ModuleNotFoundError:  # pragma: no cover - fallback for unit tests importing by package path
    try:
        from services.worker.app.db import get_conn as _get_conn
    except ModuleNotFoundError:  # pragma: no cover - no DB driver available in lightweight test env
        _get_conn = None


_DEFAULT_PROJECT_SETTINGS = {
    "timezone": "UTC",
    "schedule_hour_local": 8,
    "schedule_minute_local": 0,
    "min_activity_score": 1,
    "include_idle_days": False,
    "realtime_enabled": True,
    "realtime_lookback_minutes": 15,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run scheduled agent daily worklog sync for one or many projects."
    )
    parser.add_argument(
        "--project-id",
        action="append",
        dest="project_ids",
        default=[],
        help="Project id to sync. Can be repeated.",
    )
    parser.add_argument(
        "--all-projects",
        action="store_true",
        help="Discover projects from agent directory table before syncing.",
    )
    parser.add_argument(
        "--discover-limit",
        type=int,
        default=500,
        help="Maximum projects discovered when --all-projects is enabled.",
    )
    parser.add_argument(
        "--api-url",
        default=os.getenv("SYNAPSE_API_URL", "http://localhost:8080"),
        help="Synapse API base URL.",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("SYNAPSE_API_KEY"),
        help="Optional bearer token for API requests.",
    )
    parser.add_argument(
        "--generated-by",
        default=os.getenv("SYNAPSE_AGENT_WORKLOG_GENERATED_BY", "agent_worklog_scheduler"),
        help="Actor label stored in worklog generation metadata.",
    )
    parser.add_argument(
        "--worklog-date",
        default=None,
        help="Optional target date in YYYY-MM-DD. Default: resolved from project timezone.",
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=1,
        help="How many days to regenerate (1-30).",
    )
    parser.add_argument(
        "--max-agents",
        type=int,
        default=500,
        help="Maximum agent profiles processed per project (1-2000).",
    )
    parser.add_argument(
        "--include-retired",
        action="store_true",
        help="Include retired agents in generation.",
    )
    parser.add_argument(
        "--max-logs-per-agent-page",
        type=int,
        default=14,
        help="How many recent entries to keep on each daily-reports wiki page (1-60).",
    )
    parser.add_argument(
        "--trigger-mode",
        choices=["daily_batch", "session_close", "task_close", "realtime"],
        default="daily_batch",
        help="Sync mode: daily batch window or realtime signal mode.",
    )
    parser.add_argument(
        "--trigger-lookback-minutes",
        type=int,
        default=15,
        help="Realtime signal lookback window for session/task close triggers.",
    )
    parser.add_argument(
        "--respect-project-schedule",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="For daily batch mode, respect project local schedule from routing policy.",
    )
    parser.add_argument(
        "--fail-on-errors",
        action="store_true",
        help="Exit non-zero if any project sync fails.",
    )
    return parser.parse_args()


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for raw in values:
        item = str(raw or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def _normalize_timezone_name(value: Any, *, default: str = "UTC") -> str:
    timezone_name = str(value or "").strip()
    if not timezone_name:
        return default
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return default
    return timezone_name


def _normalize_project_setting_int(value: Any, *, default: int, low: int, high: int) -> int:
    try:
        resolved = int(value)
    except Exception:
        resolved = default
    return max(low, min(high, resolved))


def _discover_agent_project_settings(*, limit: int) -> list[dict[str, Any]]:
    if _get_conn is None:
        return []
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.agent_directory_profiles')::text")
                table_name_row = cur.fetchone()
                table_name = str(table_name_row[0] or "") if table_name_row else ""
                if not table_name.endswith("agent_directory_profiles"):
                    return []
                cur.execute(
                    """
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'gatekeeper_project_configs'
                      AND column_name = 'routing_policy'
                    LIMIT 1
                    """
                )
                has_routing_policy = cur.fetchone() is not None
                if has_routing_policy:
                    cur.execute(
                        """
                        SELECT p.project_id, c.routing_policy
                        FROM (
                          SELECT project_id
                          FROM agent_directory_profiles
                          GROUP BY project_id
                          ORDER BY project_id ASC
                          LIMIT %s
                        ) p
                        LEFT JOIN gatekeeper_project_configs c
                          ON c.project_id = p.project_id
                        """,
                        (max(1, min(2000, int(limit))),),
                    )
                else:
                    cur.execute(
                        """
                        SELECT project_id, NULL::jsonb
                        FROM (
                          SELECT project_id
                          FROM agent_directory_profiles
                          GROUP BY project_id
                          ORDER BY project_id ASC
                          LIMIT %s
                        ) p
                        """,
                        (max(1, min(2000, int(limit))),),
                    )
                rows = cur.fetchall() or []
        settings: list[dict[str, Any]] = []
        for row in rows:
            project_id = str(row[0] or "").strip()
            if not project_id:
                continue
            routing_policy = row[1] if isinstance(row[1], dict) else {}
            setting = dict(_DEFAULT_PROJECT_SETTINGS)
            setting["project_id"] = project_id
            setting["timezone"] = _normalize_timezone_name(routing_policy.get("agent_worklog_timezone"), default="UTC")
            setting["schedule_hour_local"] = _normalize_project_setting_int(
                routing_policy.get("agent_worklog_schedule_hour_local"),
                default=int(setting["schedule_hour_local"]),
                low=0,
                high=23,
            )
            setting["schedule_minute_local"] = _normalize_project_setting_int(
                routing_policy.get("agent_worklog_schedule_minute_local"),
                default=int(setting["schedule_minute_local"]),
                low=0,
                high=59,
            )
            setting["min_activity_score"] = _normalize_project_setting_int(
                routing_policy.get("agent_worklog_min_activity_score"),
                default=int(setting["min_activity_score"]),
                low=0,
                high=1000,
            )
            setting["include_idle_days"] = bool(
                routing_policy.get("agent_worklog_include_idle_days", setting["include_idle_days"])
            )
            setting["realtime_enabled"] = bool(
                routing_policy.get("agent_worklog_realtime_enabled", setting["realtime_enabled"])
            )
            setting["realtime_lookback_minutes"] = _normalize_project_setting_int(
                routing_policy.get("agent_worklog_realtime_lookback_minutes"),
                default=int(setting["realtime_lookback_minutes"]),
                low=1,
                high=240,
            )
            settings.append(setting)
        return settings
    except Exception:
        return []


def _discover_agent_projects(*, limit: int) -> list[str]:
    settings = _discover_agent_project_settings(limit=limit)
    return [str(item.get("project_id") or "") for item in settings if str(item.get("project_id") or "").strip()]


def _build_request_headers(api_key: str | None) -> dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    explicit_api_key = str(api_key or "").strip()
    if explicit_api_key:
        headers["Authorization"] = f"Bearer {explicit_api_key}"
        return headers

    session_token = str(os.getenv("SYNAPSE_SESSION_TOKEN", "") or "").strip()
    if session_token:
        headers["X-Synapse-Session"] = session_token
    bearer = str(os.getenv("SYNAPSE_OIDC_BEARER_TOKEN", "") or "").strip()
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    worker_user = str(os.getenv("SYNAPSE_WORKER_USER", "") or "").strip()
    if worker_user:
        headers["X-Synapse-User"] = worker_user
    worker_roles = str(os.getenv("SYNAPSE_WORKER_ROLES", "") or "").strip()
    if worker_roles:
        headers["X-Synapse-Roles"] = worker_roles
    return headers


def _post_json(*, url: str, payload: dict[str, Any], api_key: str | None) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=_build_request_headers(api_key),
        method="POST",
    )
    try:
        with urlopen(request, timeout=45.0) as response:
            body = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"http_error:{exc.code}:{detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"connection_error:{exc}") from exc
    if not body.strip():
        return {}
    data = json.loads(body)
    if not isinstance(data, dict):
        raise RuntimeError("unexpected_response_shape")
    return data


def _is_project_due_for_daily_sync(*, now_utc: datetime, timezone_name: str, schedule_hour: int, schedule_minute: int) -> bool:
    local_now = now_utc.astimezone(ZoneInfo(_normalize_timezone_name(timezone_name, default="UTC")))
    schedule_point = local_now.replace(hour=int(schedule_hour), minute=int(schedule_minute), second=0, microsecond=0)
    return bool(local_now >= schedule_point)


def _query_project_trigger_signal(
    *,
    project_id: str,
    mode: str,
    lookback_minutes: int,
    now_utc: datetime,
) -> dict[str, int]:
    if _get_conn is None:
        return {"session_close": 0, "task_close": 0}
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                window_start = now_utc - timedelta(minutes=max(1, min(240, int(lookback_minutes))))
                session_close = 0
                task_close = 0
                if mode in {"session_close", "realtime"}:
                    cur.execute(
                        """
                        SELECT COUNT(*)::int
                        FROM events
                        WHERE project_id = %s
                          AND observed_at >= %s
                          AND (
                            lower(event_type) LIKE '%%session%%close%%'
                            OR lower(event_type) LIKE '%%session%%end%%'
                            OR lower(event_type) LIKE '%%session_closed%%'
                          )
                        """,
                        (project_id, window_start),
                    )
                    row = cur.fetchone()
                    session_close = int(row[0] or 0) if row else 0
                if mode in {"task_close", "realtime"}:
                    cur.execute(
                        """
                        SELECT COUNT(*)::int
                        FROM synapse_tasks
                        WHERE project_id = %s
                          AND updated_at >= %s
                          AND status IN ('done', 'blocked')
                        """,
                        (project_id, window_start),
                    )
                    row = cur.fetchone()
                    task_close = int(row[0] or 0) if row else 0
        return {"session_close": session_close, "task_close": task_close}
    except Exception:
        return {"session_close": 0, "task_close": 0}


def _sync_project(
    *,
    api_url: str,
    api_key: str | None,
    project_id: str,
    generated_by: str,
    timezone: str,
    include_idle_days: bool,
    min_activity_score: int,
    trigger_mode: str,
    trigger_reason: str,
    worklog_date: str | None,
    days_back: int,
    max_agents: int,
    include_retired: bool,
    max_logs_per_agent_page: int,
) -> dict[str, Any]:
    endpoint = f"{str(api_url).rstrip('/')}/v1/agents/worklogs/sync"
    payload = {
        "project_id": project_id,
        "generated_by": generated_by,
        "timezone": timezone,
        "include_idle_days": bool(include_idle_days),
        "min_activity_score": max(0, min(1000, int(min_activity_score))),
        "trigger_mode": trigger_mode,
        "trigger_reason": trigger_reason[:512] if trigger_reason else None,
        "worklog_date": str(worklog_date).strip() if str(worklog_date or "").strip() else None,
        "days_back": max(1, min(30, int(days_back))),
        "max_agents": max(1, min(2000, int(max_agents))),
        "include_retired": bool(include_retired),
        "max_logs_per_agent_page": max(1, min(60, int(max_logs_per_agent_page))),
    }
    started_at = datetime.now(UTC).isoformat()
    response = _post_json(url=endpoint, payload=payload, api_key=api_key)
    finished_at = datetime.now(UTC).isoformat()
    return {
        "project_id": project_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "request": {
            "timezone": timezone,
            "include_idle_days": bool(include_idle_days),
            "min_activity_score": int(min_activity_score),
            "trigger_mode": trigger_mode,
        },
        "response": response,
    }


def main() -> int:
    args = parse_args()
    explicit_projects = _dedupe(list(args.project_ids or []))
    discovered_settings = _discover_agent_project_settings(limit=args.discover_limit) if bool(args.all_projects) else []
    settings_by_project: dict[str, dict[str, Any]] = {
        str(item.get("project_id")): item for item in discovered_settings if str(item.get("project_id") or "").strip()
    }
    for project_id in explicit_projects:
        if project_id in settings_by_project:
            continue
        settings_by_project[project_id] = {
            "project_id": project_id,
            **dict(_DEFAULT_PROJECT_SETTINGS),
        }
    project_ids = _dedupe(list(settings_by_project.keys()))
    discovered_projects = [str(item.get("project_id") or "") for item in discovered_settings]

    summary: dict[str, Any] = {
        "status": "ok",
        "generated_by": str(args.generated_by or "agent_worklog_scheduler").strip() or "agent_worklog_scheduler",
        "trigger_mode": str(args.trigger_mode),
        "projects_requested": explicit_projects,
        "projects_discovered": discovered_projects,
        "projects_total": len(project_ids),
        "synced": 0,
        "failed": 0,
        "skipped_schedule": 0,
        "skipped_trigger": 0,
        "results": [],
    }
    if not project_ids:
        print(json.dumps(summary, ensure_ascii=False))
        return 0

    now_utc = datetime.now(UTC)
    for project_id in project_ids:
        setting = settings_by_project.get(project_id) or {"project_id": project_id, **dict(_DEFAULT_PROJECT_SETTINGS)}
        timezone_name = _normalize_timezone_name(setting.get("timezone"), default="UTC")
        schedule_hour = _normalize_project_setting_int(setting.get("schedule_hour_local"), default=8, low=0, high=23)
        schedule_minute = _normalize_project_setting_int(setting.get("schedule_minute_local"), default=0, low=0, high=59)
        include_idle_days = bool(setting.get("include_idle_days"))
        min_activity_score = _normalize_project_setting_int(setting.get("min_activity_score"), default=1, low=0, high=1000)
        realtime_enabled = bool(setting.get("realtime_enabled", True))
        realtime_lookback = _normalize_project_setting_int(
            setting.get("realtime_lookback_minutes"),
            default=max(1, min(240, int(args.trigger_lookback_minutes))),
            low=1,
            high=240,
        )

        if args.trigger_mode == "daily_batch" and bool(args.respect_project_schedule):
            if not _is_project_due_for_daily_sync(
                now_utc=now_utc,
                timezone_name=timezone_name,
                schedule_hour=schedule_hour,
                schedule_minute=schedule_minute,
            ):
                summary["skipped_schedule"] = int(summary["skipped_schedule"]) + 1
                summary["results"].append(
                    {
                        "project_id": project_id,
                        "status": "skipped_schedule_window",
                        "timezone": timezone_name,
                        "schedule_hour_local": schedule_hour,
                        "schedule_minute_local": schedule_minute,
                    }
                )
                continue

        effective_trigger_mode = args.trigger_mode
        trigger_reason = ""
        if args.trigger_mode in {"session_close", "task_close", "realtime"}:
            if not realtime_enabled:
                summary["skipped_trigger"] = int(summary["skipped_trigger"]) + 1
                summary["results"].append(
                    {
                        "project_id": project_id,
                        "status": "skipped_realtime_disabled",
                        "timezone": timezone_name,
                    }
                )
                continue
            trigger_stats = _query_project_trigger_signal(
                project_id=project_id,
                mode=args.trigger_mode,
                lookback_minutes=realtime_lookback,
                now_utc=now_utc,
            )
            session_hits = int(trigger_stats.get("session_close") or 0)
            task_hits = int(trigger_stats.get("task_close") or 0)
            if args.trigger_mode == "session_close":
                if session_hits <= 0:
                    summary["skipped_trigger"] = int(summary["skipped_trigger"]) + 1
                    summary["results"].append(
                        {
                            "project_id": project_id,
                            "status": "skipped_no_session_close_signal",
                            "lookback_minutes": realtime_lookback,
                        }
                    )
                    continue
                effective_trigger_mode = "session_close"
                trigger_reason = f"session_close_hits={session_hits};lookback={realtime_lookback}m"
            elif args.trigger_mode == "task_close":
                if task_hits <= 0:
                    summary["skipped_trigger"] = int(summary["skipped_trigger"]) + 1
                    summary["results"].append(
                        {
                            "project_id": project_id,
                            "status": "skipped_no_task_close_signal",
                            "lookback_minutes": realtime_lookback,
                        }
                    )
                    continue
                effective_trigger_mode = "task_close"
                trigger_reason = f"task_close_hits={task_hits};lookback={realtime_lookback}m"
            else:
                if session_hits <= 0 and task_hits <= 0:
                    summary["skipped_trigger"] = int(summary["skipped_trigger"]) + 1
                    summary["results"].append(
                        {
                            "project_id": project_id,
                            "status": "skipped_no_realtime_signal",
                            "lookback_minutes": realtime_lookback,
                        }
                    )
                    continue
                effective_trigger_mode = "session_close" if session_hits >= task_hits else "task_close"
                trigger_reason = (
                    f"realtime_signal;"
                    f"session_close_hits={session_hits};"
                    f"task_close_hits={task_hits};"
                    f"lookback={realtime_lookback}m"
                )
        else:
            trigger_reason = "daily_batch_window"

        try:
            result = _sync_project(
                api_url=args.api_url,
                api_key=args.api_key,
                project_id=project_id,
                generated_by=summary["generated_by"],
                timezone=timezone_name,
                include_idle_days=include_idle_days,
                min_activity_score=min_activity_score,
                trigger_mode=effective_trigger_mode,
                trigger_reason=trigger_reason,
                worklog_date=args.worklog_date,
                days_back=args.days_back,
                max_agents=args.max_agents,
                include_retired=bool(args.include_retired),
                max_logs_per_agent_page=args.max_logs_per_agent_page,
            )
            summary["synced"] = int(summary["synced"]) + 1
            summary["results"].append(result)
        except Exception as exc:
            summary["failed"] = int(summary["failed"]) + 1
            summary["results"].append(
                {
                    "project_id": project_id,
                    "error": str(exc),
                    "timezone": timezone_name,
                }
            )
    if int(summary["failed"]) > 0:
        summary["status"] = "partial_failure"
    print(json.dumps(summary, ensure_ascii=False))
    if bool(args.fail_on_errors) and int(summary["failed"]) > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
