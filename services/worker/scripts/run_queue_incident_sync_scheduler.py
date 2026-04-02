#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from typing import Any
from urllib import error as url_error
from urllib import parse as url_parse
from urllib import request as url_request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run scheduled queue incident sync using API preflight enforcement gate."
    )
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
        help="Discover projects from queue command-center compare API before sync.",
    )
    parser.add_argument(
        "--use-api-schedules",
        action="store_true",
        help="Execute persisted API schedules via /incidents/sync/schedules/run.",
    )
    parser.add_argument(
        "--discover-limit",
        type=int,
        default=200,
        help="Maximum projects to fetch during --all-projects discovery.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Maximum project ids per sync request.",
    )
    parser.add_argument(
        "--schedule-id",
        action="append",
        dest="schedule_ids",
        default=[],
        help="Optional schedule id filter for --use-api-schedules mode. Can be repeated.",
    )
    parser.add_argument(
        "--schedule-limit",
        type=int,
        default=50,
        help="Maximum schedules to execute per cycle in --use-api-schedules mode.",
    )
    parser.add_argument("--window-hours", type=int, default=24, help="Queue health window for sync logic.")
    parser.add_argument("--sync-limit", type=int, default=200, help="API-side cap for per-run target projects.")
    parser.add_argument("--dry-run", action="store_true", help="Run incident sync in dry-run mode.")
    parser.add_argument("--force-resolve", action="store_true", help="Force resolve stale open incidents when health is clear.")
    parser.add_argument(
        "--force-run",
        action="store_true",
        help="Ignore due windows and execute schedules immediately in --use-api-schedules mode.",
    )
    parser.add_argument(
        "--skip-due-check",
        action="store_true",
        help="Skip due-window check in --use-api-schedules mode.",
    )
    parser.add_argument(
        "--preflight-enforcement-mode",
        choices=["inherit", "off", "block", "pause"],
        default="inherit",
        help="Enforcement override; inherit uses per-project queue control.",
    )
    parser.add_argument(
        "--preflight-pause-hours",
        type=int,
        default=None,
        help="Optional pause window override when enforcement mode is pause.",
    )
    parser.add_argument(
        "--preflight-critical-fail-threshold",
        type=int,
        default=None,
        help="Optional critical fail threshold override for sync gate.",
    )
    parser.add_argument(
        "--preflight-include-run-before-live-sync-only",
        dest="preflight_include_run_before_live_sync_only",
        action="store_true",
        default=True,
        help="Evaluate only presets marked for pre-live-sync runs.",
    )
    parser.add_argument(
        "--no-preflight-include-run-before-live-sync-only",
        dest="preflight_include_run_before_live_sync_only",
        action="store_false",
        help="Evaluate all enabled preflight presets.",
    )
    parser.add_argument(
        "--preflight-record-audit",
        dest="preflight_record_audit",
        action="store_true",
        default=True,
        help="Persist preflight audit events during sync.",
    )
    parser.add_argument(
        "--no-preflight-record-audit",
        dest="preflight_record_audit",
        action="store_false",
        help="Disable preflight audit writes during sync run.",
    )
    parser.add_argument("--cycles", type=int, default=1, help="Number of scheduler cycles to execute.")
    parser.add_argument("--sleep-sec", type=float, default=60.0, help="Sleep between cycles when --cycles > 1.")
    parser.add_argument(
        "--requested-by",
        default="incident_sync_scheduler",
        help="Actor name persisted in queue incident audit events.",
    )
    parser.add_argument("--api-url", default="http://localhost:8080", help="Synapse API base URL.")
    parser.add_argument("--api-key", default=None, help="Optional API bearer token.")
    parser.add_argument(
        "--fail-on-sync-failures",
        action="store_true",
        help="Exit with code 1 when any cycle has failed sync actions.",
    )
    return parser.parse_args()


def _dedupe(tokens: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in tokens:
        item = str(raw or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _chunked(items: list[str], chunk_size: int) -> list[list[str]]:
    size = max(1, int(chunk_size))
    return [items[idx : idx + size] for idx in range(0, len(items), size)]


def _request_json(
    *,
    api_url: str,
    path: str,
    method: str,
    payload: dict[str, Any] | None,
    api_key: str | None,
) -> dict[str, Any]:
    base = str(api_url or "http://localhost:8080").rstrip("/")
    url = f"{base}{path}"
    body: bytes | None = None
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "synapse-worker-incident-sync-scheduler/1.0",
    }
    token = (api_key or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    req = url_request.Request(url, data=body, headers=headers, method=method.upper())
    try:
        with url_request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
    except url_error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        detail: Any = raw
        if raw:
            try:
                detail = json.loads(raw)
            except Exception:
                detail = raw[:2000]
        raise RuntimeError(f"api_http_error:{exc.code}:{detail}") from exc
    except url_error.URLError as exc:
        raise RuntimeError(f"api_unreachable:{exc.reason}") from exc


def _discover_projects(*, api_url: str, api_key: str | None, discover_limit: int) -> list[str]:
    query = url_parse.urlencode({"limit": max(1, min(200, int(discover_limit))), "window_hours": 24})
    payload = _request_json(
        api_url=api_url,
        path=f"/v1/gatekeeper/calibration/operations/throughput/compare?{query}",
        method="GET",
        payload=None,
        api_key=api_key,
    )
    rows = payload.get("projects") if isinstance(payload.get("projects"), list) else []
    return _dedupe([str(item.get("project_id") or "") for item in rows if isinstance(item, dict)])


def _sync_once(
    *,
    api_url: str,
    api_key: str | None,
    requested_by: str,
    project_ids: list[str] | None,
    window_hours: int,
    sync_limit: int,
    dry_run: bool,
    force_resolve: bool,
    preflight_enforcement_mode: str,
    preflight_pause_hours: int | None,
    preflight_critical_fail_threshold: int | None,
    preflight_include_run_before_live_sync_only: bool,
    preflight_record_audit: bool,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "project_id": None,
        "project_ids": project_ids if project_ids else None,
        "actor": requested_by,
        "window_hours": max(1, min(168, int(window_hours))),
        "dry_run": bool(dry_run),
        "force_resolve": bool(force_resolve),
        "preflight_enforcement_mode": str(preflight_enforcement_mode or "inherit").strip().lower() or "inherit",
        "preflight_pause_hours": None if preflight_pause_hours is None else max(1, min(168, int(preflight_pause_hours))),
        "preflight_critical_fail_threshold": None
        if preflight_critical_fail_threshold is None
        else max(1, min(100, int(preflight_critical_fail_threshold))),
        "preflight_include_run_before_live_sync_only": bool(preflight_include_run_before_live_sync_only),
        "preflight_record_audit": bool(preflight_record_audit),
        "limit": max(1, min(200, int(sync_limit))),
    }
    return _request_json(
        api_url=api_url,
        path="/v1/gatekeeper/calibration/operations/incidents/sync",
        method="POST",
        payload=body,
        api_key=api_key,
    )


def _run_schedules_once(
    *,
    api_url: str,
    api_key: str | None,
    actor: str,
    project_ids: list[str] | None,
    schedule_ids: list[str] | None,
    force_run: bool,
    skip_due_check: bool,
    limit: int,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "project_id": None,
        "project_ids": project_ids if project_ids else None,
        "schedule_ids": schedule_ids if schedule_ids else None,
        "actor": actor,
        "force_run": bool(force_run),
        "skip_due_check": bool(skip_due_check),
        "limit": max(1, min(200, int(limit))),
    }
    return _request_json(
        api_url=api_url,
        path="/v1/gatekeeper/calibration/operations/incidents/sync/schedules/run",
        method="POST",
        payload=body,
        api_key=api_key,
    )


def main() -> None:
    args = parse_args()
    requested_by = str(args.requested_by or "incident_sync_scheduler").strip() or "incident_sync_scheduler"
    explicit_projects = _dedupe(args.project_ids or [])
    explicit_schedule_ids = _dedupe(args.schedule_ids or [])
    cycles = max(1, int(args.cycles))
    batch_size = max(1, min(200, int(args.batch_size)))
    sync_limit = max(1, min(200, int(args.sync_limit)))
    schedule_limit = max(1, min(200, int(args.schedule_limit)))

    history: list[dict[str, Any]] = []
    aggregate = {"opened": 0, "resolved": 0, "failed": 0, "noop": 0, "blocked": 0, "paused": 0, "projects_total": 0}

    for cycle_no in range(1, cycles + 1):
        discovered_projects: list[str] = []
        if bool(args.all_projects):
            discovered_projects = _discover_projects(
                api_url=args.api_url,
                api_key=args.api_key,
                discover_limit=max(1, min(200, int(args.discover_limit))),
            )
        cycle_projects = _dedupe([*explicit_projects, *discovered_projects])
        cycle_started_at = datetime.now(UTC).isoformat()
        cycle_runs: list[dict[str, Any]] = []
        cycle_summary = {"opened": 0, "resolved": 0, "failed": 0, "noop": 0, "blocked": 0, "paused": 0, "projects_total": 0}

        if bool(args.use_api_schedules):
            payload = _run_schedules_once(
                api_url=args.api_url,
                api_key=args.api_key,
                actor=requested_by,
                project_ids=cycle_projects or None,
                schedule_ids=explicit_schedule_ids or None,
                force_run=bool(args.force_run),
                skip_due_check=bool(args.skip_due_check),
                limit=schedule_limit,
            )
            run_summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
            cycle_summary = {
                "opened": int(run_summary.get("opened") or 0),
                "resolved": int(run_summary.get("resolved") or 0),
                "failed": int(run_summary.get("sync_failed") or 0) + int(run_summary.get("failed") or 0),
                "noop": int(run_summary.get("noop") or 0),
                "blocked": int(run_summary.get("blocked") or 0),
                "paused": int(run_summary.get("paused") or 0),
                "projects_total": int(run_summary.get("schedules_total") or 0),
            }
            cycle_runs.append(
                {
                    "mode": "api_schedules",
                    "requested_projects": cycle_projects,
                    "requested_schedule_ids": explicit_schedule_ids,
                    "summary": run_summary,
                    "generated_at": payload.get("generated_at"),
                    "status": payload.get("status"),
                }
            )
        else:
            batches = _chunked(cycle_projects, batch_size) if cycle_projects else [[]]
            for batch in batches:
                payload = _sync_once(
                    api_url=args.api_url,
                    api_key=args.api_key,
                    requested_by=requested_by,
                    project_ids=batch or None,
                    window_hours=args.window_hours,
                    sync_limit=max(sync_limit, len(batch)) if batch else sync_limit,
                    dry_run=bool(args.dry_run),
                    force_resolve=bool(args.force_resolve),
                    preflight_enforcement_mode=args.preflight_enforcement_mode,
                    preflight_pause_hours=args.preflight_pause_hours,
                    preflight_critical_fail_threshold=args.preflight_critical_fail_threshold,
                    preflight_include_run_before_live_sync_only=bool(args.preflight_include_run_before_live_sync_only),
                    preflight_record_audit=bool(args.preflight_record_audit),
                )
                run_summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
                batch_summary = {
                    "opened": int(run_summary.get("opened") or 0),
                    "resolved": int(run_summary.get("resolved") or 0),
                    "failed": int(run_summary.get("failed") or 0),
                    "noop": int(run_summary.get("noop") or 0),
                    "blocked": int(run_summary.get("blocked") or 0),
                    "paused": int(run_summary.get("paused") or 0),
                    "projects_total": int(run_summary.get("projects_total") or 0),
                }
                for key in cycle_summary:
                    cycle_summary[key] += int(batch_summary[key])
                cycle_runs.append(
                    {
                        "mode": "direct_sync",
                        "batch_projects": batch,
                        "summary": batch_summary,
                        "generated_at": payload.get("generated_at"),
                        "status": payload.get("status"),
                    }
                )

        for key in aggregate:
            aggregate[key] += int(cycle_summary[key])

        history.append(
            {
                "cycle": cycle_no,
                "started_at": cycle_started_at,
                "finished_at": datetime.now(UTC).isoformat(),
                "requested_projects": cycle_projects,
                "batches": len(cycle_runs),
                "summary": cycle_summary,
                "runs": cycle_runs,
            }
        )

        if cycle_no < cycles:
            time.sleep(max(0.0, float(args.sleep_sec)))

    result = {
        "status": "ok",
        "api_url": str(args.api_url).rstrip("/"),
        "use_api_schedules": bool(args.use_api_schedules),
        "requested_by": requested_by,
        "dry_run": bool(args.dry_run),
        "force_resolve": bool(args.force_resolve),
        "force_run": bool(args.force_run),
        "skip_due_check": bool(args.skip_due_check),
        "preflight_enforcement_mode": args.preflight_enforcement_mode,
        "cycles": cycles,
        "aggregate": aggregate,
        "history": history,
        "generated_at": datetime.now(UTC).isoformat(),
    }

    if bool(args.fail_on_sync_failures) and aggregate["failed"] > 0:
        result["status"] = "failed"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
