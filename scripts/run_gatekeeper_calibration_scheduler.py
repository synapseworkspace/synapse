#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
import json
import os
from pathlib import Path
import re
import smtplib
import subprocess
import sys
from typing import Any
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest


PRESET_INTERVAL_HOURS = {
    "nightly": 24,
    "weekly": 24 * 7,
}


def _has_psycopg() -> bool:
    try:
        import psycopg  # type: ignore  # noqa: F401
    except Exception:
        return False
    return True


def _parse_project_ids(raw: list[str]) -> list[str]:
    items: list[str] = []
    for value in raw:
        for token in str(value).split(","):
            normalized = token.strip()
            if normalized:
                items.append(normalized)
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", value.strip())
    return slug or "project"


def _extract_json(stdout: str) -> dict[str, Any]:
    text = (stdout or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in reversed(lines):
        if not (line.startswith("{") and line.endswith("}")):
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload
    return {"raw_output": text}


def _run_command(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any], str, str]:
    proc = subprocess.run(
        command,
        text=True,
        capture_output=True,
        env=env,
    )
    payload = _extract_json(proc.stdout)
    return proc.returncode, payload, proc.stdout, proc.stderr


def _maybe_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except Exception:
            return None
    return None


def _load_schedule_payload(args: argparse.Namespace) -> Any:
    if args.schedules_file:
        return json.loads(Path(args.schedules_file).read_text(encoding="utf-8"))
    if args.schedules_json:
        return json.loads(args.schedules_json)
    env_payload = os.getenv("SYNAPSE_GATEKEEPER_CALIBRATION_SCHEDULES_JSON")
    if env_payload:
        return json.loads(env_payload)
    return None


def _csv_grid_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            parsed = _maybe_float(item)
            if parsed is None:
                continue
            parts.append(str(parsed))
        return ",".join(parts) if parts else None
    text = str(value).strip()
    return text or None


def _normalize_schedules(payload: Any) -> list[dict[str, Any]]:
    raw_items = payload.get("schedules") if isinstance(payload, dict) else payload
    if not isinstance(raw_items, list):
        raise ValueError("schedule payload must be a list or an object with `schedules` list")
    schedules: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    for idx, raw in enumerate(raw_items):
        if not isinstance(raw, dict):
            raise ValueError(f"schedule[{idx}] must be an object")
        project_id = str(raw.get("project_id") or "").strip()
        if not project_id:
            raise ValueError(f"schedule[{idx}] missing `project_id`")
        preset = str(raw.get("preset") or "nightly").strip().lower()
        if preset not in PRESET_INTERVAL_HOURS:
            raise ValueError(f"schedule[{idx}] invalid preset `{preset}` (expected nightly|weekly)")
        enabled = bool(raw.get("enabled", True))
        interval_hours = raw.get("interval_hours")
        if interval_hours is not None:
            interval_hours = int(interval_hours)
            if interval_hours < 1:
                raise ValueError(f"schedule[{idx}] interval_hours must be >= 1")
        key = (project_id, str(raw.get("name") or preset))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        schedule = {
            "schedule_id": raw.get("id"),
            "name": str(raw.get("name") or f"{project_id}:{preset}"),
            "project_id": project_id,
            "preset": preset,
            "enabled": enabled,
            "interval_hours": interval_hours,
            "lookback_days": int(raw.get("lookback_days", 60)),
            "limit": int(raw.get("limit", raw.get("limit_rows", 20000))),
            "holdout_ratio": float(raw.get("holdout_ratio", 0.3)),
            "split_seed": str(raw.get("split_seed") or "synapse-gatekeeper-prod-holdout-v1"),
            "weights": _csv_grid_value(raw.get("weights")),
            "confidences": _csv_grid_value(raw.get("confidences")),
            "score_thresholds": _csv_grid_value(raw.get("score_thresholds")),
            "top_k": int(raw.get("top_k", 5)),
            "allow_guardrail_fail": bool(raw.get("allow_guardrail_fail", False)),
            "snapshot_note": raw.get("snapshot_note"),
            "updated_by": str(raw.get("updated_by") or "gatekeeper_calibration_scheduler"),
            "database_url": raw.get("database_url"),
            "api_url": raw.get("api_url"),
        }
        schedules.append(schedule)
    return schedules


def _discover_projects_from_db(database_url: str, lookback_days: int) -> list[str]:
    try:
        import psycopg
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Install psycopg[binary] to use --all-projects discovery.") from exc

    with psycopg.connect(database_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT project_id
                FROM gatekeeper_decisions
                WHERE updated_at >= NOW() - make_interval(days => %s)
                ORDER BY project_id ASC
                """,
                (max(1, int(lookback_days)),),
            )
            rows = cur.fetchall()
    return [str(row[0]) for row in rows if row and row[0]]


def _load_schedules_from_api(api_url: str, project_id: str | None) -> Any:
    root = str(api_url).rstrip("/")
    query = "?enabled=true&limit=500"
    if project_id:
        query += f"&project_id={urlparse.quote(project_id, safe='')}"
    url = f"{root}/v1/gatekeeper/calibration/schedules{query}"
    req = urlrequest.Request(url=url, method="GET")
    try:
        with urlrequest.urlopen(req, timeout=25) as resp:
            raw = resp.read().decode("utf-8")
    except urlerror.HTTPError as exc:
        details = exc.read().decode("utf-8") if exc.fp is not None else ""
        raise SystemExit(f"failed to load schedules from API: {exc.code} {details}") from exc
    except Exception as exc:  # pragma: no cover
        raise SystemExit(f"failed to load schedules from API: {exc}") from exc
    payload = json.loads(raw) if raw else {}
    if not isinstance(payload, dict):
        raise SystemExit("unexpected API response for calibration schedules")
    schedules = payload.get("schedules")
    if not isinstance(schedules, list):
        raise SystemExit("invalid calibration schedules payload from API")
    return {"schedules": schedules}


def _load_gatekeeper_alert_targets_from_api(api_url: str, project_id: str, limit: int = 200) -> list[dict[str, Any]]:
    root = str(api_url).rstrip("/")
    url = (
        f"{root}/v1/gatekeeper/alerts/targets"
        f"?project_id={urlparse.quote(project_id, safe='')}&limit={max(1, int(limit))}"
    )
    req = urlrequest.Request(url=url, method="GET")
    try:
        with urlrequest.urlopen(req, timeout=25) as resp:
            raw = resp.read().decode("utf-8")
    except urlerror.HTTPError as exc:
        details = exc.read().decode("utf-8") if exc.fp is not None else ""
        raise RuntimeError(f"failed to load gatekeeper alert targets: {exc.code} {details}") from exc
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"failed to load gatekeeper alert targets: {exc}") from exc
    payload = json.loads(raw) if raw else {}
    if not isinstance(payload, dict):
        return []
    targets = payload.get("targets")
    if not isinstance(targets, list):
        return []
    out: list[dict[str, Any]] = []
    for item in targets:
        if not isinstance(item, dict):
            continue
        if not bool(item.get("enabled", False)):
            continue
        out.append(item)
    return out


def _post_gatekeeper_alert_attempt(api_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    root = str(api_url).rstrip("/")
    body = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(
        url=f"{root}/v1/gatekeeper/alerts/attempts",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlrequest.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            parsed = json.loads(raw) if raw else {}
            return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {"status": "failed_to_log"}


def _post_calibration_run_history(api_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    root = str(api_url).rstrip("/")
    body = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(
        url=f"{root}/v1/gatekeeper/calibration/runs",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlrequest.urlopen(req, timeout=25) as resp:
            raw = resp.read().decode("utf-8")
            parsed = json.loads(raw) if raw else {}
            return parsed if isinstance(parsed, dict) else {}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


def _get_recent_calibration_snapshots(database_url: str, project_id: str, limit: int = 2) -> list[dict[str, Any]]:
    try:
        import psycopg
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Install psycopg[binary] to run gatekeeper calibration scheduler.") from exc

    with psycopg.connect(database_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  id::text,
                  created_at,
                  source,
                  guardrails_met,
                  calibration_report
                FROM gatekeeper_config_snapshots
                WHERE project_id = %s
                  AND source = 'calibration_cycle'
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (project_id, max(1, int(limit))),
            )
            rows = cur.fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "id": row[0],
                "created_at": row[1],
                "source": row[2],
                "guardrails_met": row[3],
                "calibration_report": row[4] if isinstance(row[4], dict) else {},
            }
        )
    return out


def _resolve_interval_hours(schedule: dict[str, Any]) -> int:
    custom = schedule.get("interval_hours")
    if custom is not None:
        return max(1, int(custom))
    preset = str(schedule.get("preset") or "nightly")
    return PRESET_INTERVAL_HOURS.get(preset, 24)


def _extract_holdout_metrics(snapshot: dict[str, Any] | None) -> dict[str, float | None]:
    if not isinstance(snapshot, dict):
        return {"accuracy": None, "macro_f1": None, "golden_precision": None}
    report = snapshot.get("calibration_report")
    if not isinstance(report, dict):
        return {"accuracy": None, "macro_f1": None, "golden_precision": None}
    best_candidate = report.get("best_candidate")
    if isinstance(best_candidate, dict) and isinstance(best_candidate.get("holdout_metrics"), dict):
        metrics = best_candidate.get("holdout_metrics")
    elif isinstance(report.get("holdout_metrics"), dict):
        metrics = report.get("holdout_metrics")
    else:
        metrics = {}
    if not isinstance(metrics, dict):
        metrics = {}
    by_tier = metrics.get("by_tier") if isinstance(metrics.get("by_tier"), dict) else {}
    golden_tier = by_tier.get("golden_candidate") if isinstance(by_tier.get("golden_candidate"), dict) else {}
    return {
        "accuracy": _maybe_float(metrics.get("accuracy")),
        "macro_f1": _maybe_float(metrics.get("macro_f1")),
        "golden_precision": _maybe_float(golden_tier.get("precision")),
    }


def _build_regression_alerts(
    *,
    project_id: str,
    previous_snapshot: dict[str, Any] | None,
    current_snapshot: dict[str, Any] | None,
    max_accuracy_drop: float,
    max_macro_f1_drop: float,
    max_golden_precision_drop: float,
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    if current_snapshot is None:
        return alerts

    previous_guardrails = previous_snapshot.get("guardrails_met") if isinstance(previous_snapshot, dict) else None
    current_guardrails = current_snapshot.get("guardrails_met")
    if previous_guardrails is True and current_guardrails is False:
        alerts.append(
            {
                "project_id": project_id,
                "code": "guardrails_regressed",
                "severity": "high",
                "message": "Guardrails regressed from met -> failed in latest calibration snapshot.",
                "context": {
                    "previous_snapshot_id": previous_snapshot.get("id") if isinstance(previous_snapshot, dict) else None,
                    "current_snapshot_id": current_snapshot.get("id"),
                },
            }
        )

    previous_metrics = _extract_holdout_metrics(previous_snapshot)
    current_metrics = _extract_holdout_metrics(current_snapshot)
    comparisons = [
        ("accuracy", max_accuracy_drop),
        ("macro_f1", max_macro_f1_drop),
        ("golden_precision", max_golden_precision_drop),
    ]
    for metric_name, max_drop in comparisons:
        prev = previous_metrics.get(metric_name)
        curr = current_metrics.get(metric_name)
        if prev is None or curr is None:
            continue
        delta = float(curr) - float(prev)
        if delta < -abs(max_drop):
            alerts.append(
                {
                    "project_id": project_id,
                    "code": f"{metric_name}_drop_exceeded",
                    "severity": "medium",
                    "message": f"{metric_name} dropped by {delta:.4f} (threshold -{abs(max_drop):.4f}).",
                    "context": {
                        "previous_value": float(prev),
                        "current_value": float(curr),
                        "delta": round(delta, 4),
                        "max_drop": float(max_drop),
                        "previous_snapshot_id": previous_snapshot.get("id") if isinstance(previous_snapshot, dict) else None,
                        "current_snapshot_id": current_snapshot.get("id"),
                    },
                }
            )
    return alerts


def _send_slack_alert(webhook_url: str, message: str) -> dict[str, Any]:
    body = json.dumps({"text": message}).encode("utf-8")
    req = urlrequest.Request(
        url=webhook_url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlrequest.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            return {"status": "sent", "http_status": int(getattr(resp, "status", 200)), "response": raw}
    except urlerror.HTTPError as exc:
        details = exc.read().decode("utf-8") if exc.fp is not None else ""
        return {"status": "failed", "http_status": int(exc.code), "error": details or str(exc)}
    except Exception as exc:  # pragma: no cover
        return {"status": "failed", "error": str(exc)}


def _send_email_alert(
    *,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str | None,
    smtp_password: str | None,
    smtp_use_tls: bool,
    sender: str,
    recipients: list[str],
    subject: str,
    message: str,
) -> dict[str, Any]:
    if not recipients:
        return {"status": "skipped", "reason": "no_recipients"}
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.set_content(message)
    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as smtp:
            if smtp_use_tls:
                smtp.starttls()
            if smtp_user:
                smtp.login(smtp_user, smtp_password or "")
            smtp.send_message(msg)
        return {"status": "sent", "recipients": recipients}
    except Exception as exc:  # pragma: no cover
        return {"status": "failed", "error": str(exc), "recipients": recipients}


def _format_alert_message(run_id: str, alerts: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    lines = [
        f"Synapse Gatekeeper Calibration Alert ({run_id})",
        f"status={summary.get('status')} total_schedules={summary.get('total_schedules')} executed={summary.get('executed_count')} alerts={len(alerts)}",
        "",
    ]
    for alert in alerts:
        lines.append(
            f"- [{str(alert.get('severity') or 'info').upper()}] {alert.get('project_id')}: {alert.get('code')} :: {alert.get('message')}"
        )
    return "\n".join(lines)


def _parse_csv_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for token in raw.split(","):
        value = token.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _severity_rank(value: str | None) -> int:
    key = str(value or "").strip().lower()
    mapping = {"debug": 0, "info": 1, "low": 1, "medium": 2, "warning": 2, "high": 3, "critical": 4}
    return mapping.get(key, 1)


def _filter_alerts_for_target(alerts: list[dict[str, Any]], config: dict[str, Any] | None) -> list[dict[str, Any]]:
    cfg = config if isinstance(config, dict) else {}
    min_rank = _severity_rank(cfg.get("min_severity"))
    code_whitelist_raw = cfg.get("alert_codes")
    code_whitelist = (
        {str(item).strip() for item in code_whitelist_raw if str(item).strip()}
        if isinstance(code_whitelist_raw, list)
        else set()
    )
    out: list[dict[str, Any]] = []
    for alert in alerts:
        if _severity_rank(alert.get("severity")) < min_rank:
            continue
        code = str(alert.get("code") or "").strip()
        if code_whitelist and code not in code_whitelist:
            continue
        out.append(alert)
    return out


def _format_project_alert_message(run_id: str, project_id: str, alerts: list[dict[str, Any]]) -> str:
    lines = [
        f"Synapse Gatekeeper Calibration Alert ({run_id})",
        f"project={project_id} alerts={len(alerts)}",
        "",
    ]
    for alert in alerts:
        lines.append(
            f"- [{str(alert.get('severity') or 'info').upper()}] {alert.get('code')} :: {alert.get('message')}"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run scheduled Gatekeeper calibration cycles (nightly/weekly) and alert on guardrail regressions."
    )
    parser.add_argument("--schedules-file", default=None, help="Path to schedule JSON file.")
    parser.add_argument("--schedules-json", default=None, help="Inline schedule JSON payload.")
    parser.add_argument(
        "--use-api-schedules",
        action="store_true",
        help="Load schedules from API endpoint (`/v1/gatekeeper/calibration/schedules`).",
    )
    parser.add_argument("--all-projects", action="store_true", help="Auto-discover projects from gatekeeper_decisions.")
    parser.add_argument(
        "--default-preset",
        default="nightly",
        choices=["nightly", "weekly"],
        help="Preset used for --all-projects auto-generated schedules.",
    )
    parser.add_argument(
        "--project-id",
        action="append",
        dest="project_ids",
        default=[],
        help="Optional project filter. Can be repeated or comma-separated.",
    )
    parser.add_argument("--force-run", action="store_true", help="Ignore due checks and run matching schedules immediately.")
    parser.add_argument("--dry-run", action="store_true", help="Do not execute cycles; print what would run.")
    parser.add_argument(
        "--skip-due-check",
        action="store_true",
        help="Skip DB due-check lookup and treat every enabled schedule as due (useful for offline dry-run preview).",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", "postgresql://synapse:synapse@localhost:55432/synapse"),
        help="Postgres connection URL for discovery and snapshot checks.",
    )
    parser.add_argument("--api-url", default="http://localhost:8080", help="Default Synapse API base URL.")
    parser.add_argument("--lookback-days", type=int, default=60, help="Default holdout lookback for auto schedules.")
    parser.add_argument("--limit", type=int, default=20000, help="Default holdout row limit for auto schedules.")
    parser.add_argument("--holdout-ratio", type=float, default=0.3, help="Default holdout ratio for auto schedules.")
    parser.add_argument("--split-seed", default="synapse-gatekeeper-prod-holdout-v1", help="Default split seed.")
    parser.add_argument("--top-k", type=int, default=5, help="Default top-k for calibrator.")
    parser.add_argument(
        "--python-bin",
        default=None,
        help="Python interpreter for invoking child scripts (defaults to current interpreter).",
    )
    parser.add_argument(
        "--scheduler-artifacts-dir",
        default="artifacts/gatekeeper_calibration_scheduler",
        help="Directory for scheduler run reports and alerts.",
    )
    parser.add_argument(
        "--cycle-artifacts-dir",
        default="artifacts/gatekeeper_calibration",
        help="Directory passed to run_gatekeeper_calibration_cycle.py for per-project cycle artifacts.",
    )
    parser.add_argument("--max-accuracy-drop", type=float, default=0.03, help="Alert when accuracy drop exceeds this value.")
    parser.add_argument("--max-macro-f1-drop", type=float, default=0.05, help="Alert when macro_f1 drop exceeds this value.")
    parser.add_argument(
        "--max-golden-precision-drop",
        type=float,
        default=0.08,
        help="Alert when golden precision drop exceeds this value.",
    )
    parser.add_argument("--alert-webhook-url", default=os.getenv("SYNAPSE_ALERT_SLACK_WEBHOOK"), help="Optional Slack webhook URL.")
    parser.add_argument(
        "--alert-email-to",
        action="append",
        default=[],
        help="Alert recipient email(s), can be repeated or comma-separated. Env fallback: SYNAPSE_ALERT_EMAIL_TO",
    )
    parser.add_argument(
        "--alert-email-from",
        default=os.getenv("SYNAPSE_ALERT_EMAIL_FROM", "synapse-alerts@localhost"),
        help="From address for SMTP alerts.",
    )
    parser.add_argument("--smtp-host", default=os.getenv("SYNAPSE_SMTP_HOST"), help="SMTP host for email alerts.")
    parser.add_argument("--smtp-port", type=int, default=int(os.getenv("SYNAPSE_SMTP_PORT", "587")), help="SMTP port.")
    parser.add_argument("--smtp-user", default=os.getenv("SYNAPSE_SMTP_USER"), help="SMTP user (optional).")
    parser.add_argument("--smtp-password", default=os.getenv("SYNAPSE_SMTP_PASSWORD"), help="SMTP password (optional).")
    parser.add_argument(
        "--smtp-no-tls",
        action="store_true",
        help="Disable STARTTLS for SMTP alerts.",
    )
    parser.add_argument(
        "--use-db-alert-targets",
        action="store_true",
        help="Route alerts through DB-managed targets (`/v1/gatekeeper/alerts/targets`) per project.",
    )
    parser.add_argument(
        "--db-alert-target-limit",
        type=int,
        default=200,
        help="Maximum DB-managed alert targets loaded per project.",
    )
    parser.add_argument(
        "--persist-run-history",
        action="store_true",
        default=True,
        help="Persist scheduler run history to API (`/v1/gatekeeper/calibration/runs`).",
    )
    parser.add_argument(
        "--no-persist-run-history",
        action="store_false",
        dest="persist_run_history",
        help="Disable scheduler run history persistence to API.",
    )
    parser.add_argument("--fail-on-alert", action="store_true", help="Exit non-zero if any alert is raised.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    scripts_dir = root / "scripts"
    runner_python = str(args.python_bin or sys.executable)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    started_at = datetime.now(UTC)
    scheduler_artifacts_dir = (root / args.scheduler_artifacts_dir / run_id).resolve()
    scheduler_artifacts_dir.mkdir(parents=True, exist_ok=True)

    payload = _load_schedule_payload(args)
    schedules: list[dict[str, Any]]
    if payload is not None:
        schedules = _normalize_schedules(payload)
    elif args.use_api_schedules:
        project_ids_for_api = _parse_project_ids(list(args.project_ids or []))
        api_project = project_ids_for_api[0] if len(project_ids_for_api) == 1 else None
        schedules = _normalize_schedules(_load_schedules_from_api(args.api_url, api_project))
    elif args.all_projects:
        discovered = _discover_projects_from_db(args.database_url, int(args.lookback_days))
        schedules = [
            {
                "schedule_id": None,
                "name": f"{project_id}:{args.default_preset}",
                "project_id": project_id,
                "preset": str(args.default_preset),
                "enabled": True,
                "interval_hours": None,
                "lookback_days": int(args.lookback_days),
                "limit": int(args.limit),
                "holdout_ratio": float(args.holdout_ratio),
                "split_seed": str(args.split_seed),
                "weights": None,
                "confidences": None,
                "score_thresholds": None,
                "top_k": int(args.top_k),
                "allow_guardrail_fail": False,
                "snapshot_note": None,
                "updated_by": "gatekeeper_calibration_scheduler",
                "database_url": args.database_url,
                "api_url": args.api_url,
            }
            for project_id in discovered
        ]
    else:
        raise SystemExit(
            "Provide --schedules-file/--schedules-json/SYNAPSE_GATEKEEPER_CALIBRATION_SCHEDULES_JSON, use --use-api-schedules, or use --all-projects."
        )

    project_filter = set(_parse_project_ids(list(args.project_ids or [])))
    if project_filter:
        schedules = [item for item in schedules if str(item.get("project_id")) in project_filter]

    if not args.skip_due_check and not _has_psycopg():
        raise SystemExit("Install psycopg[binary] or run with --skip-due-check for preview mode.")

    schedule_results: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []
    executed_count = 0

    for schedule in schedules:
        project_id = str(schedule.get("project_id"))
        schedule_name = str(schedule.get("name") or f"{project_id}:{schedule.get('preset')}")
        enabled = bool(schedule.get("enabled", True))
        interval_hours = _resolve_interval_hours(schedule)
        db_url = str(schedule.get("database_url") or args.database_url)
        api_url = str(schedule.get("api_url") or args.api_url)
        previous_snapshot: dict[str, Any] | None = None
        previous_created_at: datetime | None = None
        due_at = None
        is_due = True
        if not args.skip_due_check:
            previous_snapshots = _get_recent_calibration_snapshots(db_url, project_id, limit=1)
            previous_snapshot = previous_snapshots[0] if previous_snapshots else None
            previous_created_at = previous_snapshot.get("created_at") if isinstance(previous_snapshot, dict) else None
            now = datetime.now(UTC)
            if isinstance(previous_created_at, datetime):
                due_at = previous_created_at + timedelta(hours=interval_hours)
                is_due = now >= due_at

        entry: dict[str, Any] = {
            "schedule_id": schedule.get("schedule_id"),
            "schedule_name": schedule_name,
            "project_id": project_id,
            "preset": schedule.get("preset"),
            "interval_hours": interval_hours,
            "enabled": enabled,
            "force_run": bool(args.force_run),
            "skip_due_check": bool(args.skip_due_check),
            "due": bool(is_due),
            "due_at": due_at.isoformat() if isinstance(due_at, datetime) else None,
            "last_snapshot_at": previous_created_at.isoformat() if isinstance(previous_created_at, datetime) else None,
        }

        if not enabled:
            entry["status"] = "skipped_disabled"
            schedule_results.append(entry)
            continue
        if not args.force_run and not is_due:
            entry["status"] = "skipped_not_due"
            schedule_results.append(entry)
            continue
        if args.dry_run:
            entry["status"] = "would_run"
            schedule_results.append(entry)
            continue

        project_artifacts_dir = scheduler_artifacts_dir / _safe_slug(project_id)
        project_artifacts_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            runner_python,
            str(scripts_dir / "run_gatekeeper_calibration_cycle.py"),
            "--project-id",
            project_id,
            "--database-url",
            db_url,
            "--api-url",
            api_url,
            "--lookback-days",
            str(int(schedule.get("lookback_days", args.lookback_days))),
            "--limit",
            str(int(schedule.get("limit", args.limit))),
            "--holdout-ratio",
            str(float(schedule.get("holdout_ratio", args.holdout_ratio))),
            "--split-seed",
            str(schedule.get("split_seed") or args.split_seed),
            "--top-k",
            str(int(schedule.get("top_k", args.top_k))),
            "--updated-by",
            str(schedule.get("updated_by") or "gatekeeper_calibration_scheduler"),
            "--artifacts-dir",
            str(args.cycle_artifacts_dir),
        ]
        if schedule.get("weights"):
            cmd.extend(["--weights", str(schedule.get("weights"))])
        if schedule.get("confidences"):
            cmd.extend(["--confidences", str(schedule.get("confidences"))])
        if schedule.get("score_thresholds"):
            cmd.extend(["--score-thresholds", str(schedule.get("score_thresholds"))])
        if schedule.get("allow_guardrail_fail"):
            cmd.append("--allow-guardrail-fail")
        if schedule.get("snapshot_note"):
            cmd.extend(["--snapshot-note", str(schedule.get("snapshot_note"))])

        rc, cycle_payload, stdout, stderr = _run_command(cmd)
        executed_count += 1
        entry["status"] = "executed"
        entry["returncode"] = rc
        entry["cycle_summary"] = cycle_payload
        if stderr.strip():
            entry["stderr"] = stderr.strip()
        (project_artifacts_dir / "cycle_stdout.txt").write_text(stdout or "", encoding="utf-8")
        (project_artifacts_dir / "cycle_stderr.txt").write_text(stderr or "", encoding="utf-8")
        (project_artifacts_dir / "cycle_summary.json").write_text(
            json.dumps(cycle_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        cycle_projects = cycle_payload.get("projects") if isinstance(cycle_payload, dict) else None
        cycle_project = cycle_projects[0] if isinstance(cycle_projects, list) and cycle_projects else {}
        project_status = str(cycle_project.get("status") or "unknown")
        entry["project_cycle_status"] = project_status
        if rc != 0 or project_status not in {"ok", "dry_run"}:
            alerts.append(
                {
                    "project_id": project_id,
                    "code": "cycle_run_failed",
                    "severity": "high",
                    "message": f"Calibration cycle failed for project status={project_status} rc={rc}.",
                    "context": {
                        "schedule_name": schedule_name,
                        "returncode": rc,
                    },
                }
            )

        current_snapshot: dict[str, Any] | None = None
        if not args.skip_due_check:
            recent_after = _get_recent_calibration_snapshots(db_url, project_id, limit=1)
            current_snapshot = recent_after[0] if recent_after else None
        previous_for_compare = previous_snapshot
        if (
            isinstance(current_snapshot, dict)
            and isinstance(previous_snapshot, dict)
            and str(current_snapshot.get("id")) == str(previous_snapshot.get("id"))
        ):
            previous_for_compare = None
        regression_alerts = _build_regression_alerts(
            project_id=project_id,
            previous_snapshot=previous_for_compare,
            current_snapshot=current_snapshot,
            max_accuracy_drop=float(args.max_accuracy_drop),
            max_macro_f1_drop=float(args.max_macro_f1_drop),
            max_golden_precision_drop=float(args.max_golden_precision_drop),
        )
        if regression_alerts:
            alerts.extend(regression_alerts)
        entry["regression_alerts"] = regression_alerts
        schedule_results.append(entry)

    status = "ok"
    if args.dry_run:
        status = "preview"
    elif alerts:
        status = "alert"
    elif any(item.get("returncode") not in (None, 0) for item in schedule_results):
        status = "partial_failure"

    summary = {
        "status": status,
        "run_id": run_id,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "total_schedules": len(schedules),
        "executed_count": executed_count,
        "alerts_count": len(alerts),
        "alerts": alerts,
        "results": schedule_results,
        "artifacts_dir": str(scheduler_artifacts_dir),
    }

    summary_path = scheduler_artifacts_dir / "scheduler_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    alerts_path = scheduler_artifacts_dir / "alerts.jsonl"
    with alerts_path.open("w", encoding="utf-8") as fh:
        for alert in alerts:
            fh.write(json.dumps(alert, ensure_ascii=False) + "\n")

    delivery: dict[str, Any] = {}
    if alerts and not args.dry_run:
        project_alerts: dict[str, list[dict[str, Any]]] = {}
        for alert in alerts:
            project_id = str(alert.get("project_id") or "").strip()
            if not project_id:
                continue
            project_alerts.setdefault(project_id, []).append(alert)

        if args.use_db_alert_targets:
            db_delivery: list[dict[str, Any]] = []
            for project_id, project_items in project_alerts.items():
                try:
                    targets = _load_gatekeeper_alert_targets_from_api(
                        args.api_url,
                        project_id,
                        limit=max(1, int(args.db_alert_target_limit)),
                    )
                except Exception as exc:
                    db_delivery.append(
                        {
                            "project_id": project_id,
                            "status": "failed_to_load_targets",
                            "error": str(exc),
                        }
                    )
                    continue
                for target in targets:
                    channel = str(target.get("channel") or "")
                    target_value = str(target.get("target") or "")
                    config = target.get("config") if isinstance(target.get("config"), dict) else {}
                    filtered_alerts = _filter_alerts_for_target(project_items, config)
                    attempt_payload: dict[str, Any] = {
                        "run_id": run_id,
                        "project_id": project_id,
                        "channel": channel,
                        "target": target_value,
                        "alert_codes": [str(item.get("code") or "") for item in filtered_alerts],
                    }
                    if not filtered_alerts:
                        attempt_payload["status"] = "skipped"
                        attempt_payload["error_message"] = "no_matching_alerts_for_target_filters"
                        attempt_payload["response_payload"] = {"filters": config}
                        log_result = _post_gatekeeper_alert_attempt(args.api_url, attempt_payload)
                        db_delivery.append(
                            {
                                "project_id": project_id,
                                "channel": channel,
                                "target": target_value,
                                "status": "skipped",
                                "reason": "no_matching_alerts_for_target_filters",
                                "log_result": log_result,
                            }
                        )
                        continue

                    message = _format_project_alert_message(run_id, project_id, filtered_alerts)
                    send_result: dict[str, Any]
                    if channel == "slack_webhook":
                        send_result = _send_slack_alert(target_value, message)
                    elif channel == "email_smtp":
                        recipients = _parse_csv_list(target_value)
                        extra_recipients = config.get("recipients") if isinstance(config.get("recipients"), list) else []
                        for item in extra_recipients:
                            recipient = str(item).strip()
                            if recipient and recipient not in recipients:
                                recipients.append(recipient)
                        if recipients and args.smtp_host:
                            send_result = _send_email_alert(
                                smtp_host=str(args.smtp_host),
                                smtp_port=int(args.smtp_port),
                                smtp_user=str(args.smtp_user) if args.smtp_user else None,
                                smtp_password=str(args.smtp_password) if args.smtp_password else None,
                                smtp_use_tls=not bool(args.smtp_no_tls),
                                sender=str(args.alert_email_from),
                                recipients=recipients,
                                subject=f"[Synapse] Gatekeeper calibration alerts ({run_id})",
                                message=message,
                            )
                        else:
                            send_result = {"status": "failed", "error": "smtp_host_missing_or_no_recipients"}
                    else:
                        send_result = {"status": "failed", "error": f"unsupported_channel:{channel}"}

                    attempt_payload["status"] = (
                        "sent" if str(send_result.get("status")) == "sent" else "failed"
                    )
                    attempt_payload["error_message"] = send_result.get("error")
                    attempt_payload["response_payload"] = send_result
                    log_result = _post_gatekeeper_alert_attempt(args.api_url, attempt_payload)
                    db_delivery.append(
                        {
                            "project_id": project_id,
                            "channel": channel,
                            "target": target_value,
                            "status": attempt_payload["status"],
                            "send_result": send_result,
                            "log_result": log_result,
                        }
                    )
            delivery["db_targets"] = db_delivery

        alert_message = _format_alert_message(run_id, alerts, summary)
        webhook_url = str(args.alert_webhook_url or "").strip()
        if webhook_url:
            delivery["slack_webhook"] = _send_slack_alert(webhook_url, alert_message)
        email_recipients = _parse_project_ids(list(args.alert_email_to or []))
        env_email = _parse_csv_list(os.getenv("SYNAPSE_ALERT_EMAIL_TO"))
        for item in env_email:
            if item not in email_recipients:
                email_recipients.append(item)
        if email_recipients and args.smtp_host:
            delivery["email_smtp"] = _send_email_alert(
                smtp_host=str(args.smtp_host),
                smtp_port=int(args.smtp_port),
                smtp_user=str(args.smtp_user) if args.smtp_user else None,
                smtp_password=str(args.smtp_password) if args.smtp_password else None,
                smtp_use_tls=not bool(args.smtp_no_tls),
                sender=str(args.alert_email_from),
                recipients=email_recipients,
                subject=f"[Synapse] Gatekeeper calibration alerts ({run_id})",
                message=alert_message,
            )
        elif email_recipients and not args.smtp_host:
            delivery["email_smtp"] = {"status": "skipped", "reason": "smtp_host_missing"}
    summary["delivery"] = delivery
    if bool(args.persist_run_history):
        run_payload = {
            "run_id": run_id,
            "status": summary.get("status"),
            "started_at": summary.get("started_at"),
            "finished_at": summary.get("finished_at"),
            "total_schedules": int(summary.get("total_schedules") or 0),
            "executed_count": int(summary.get("executed_count") or 0),
            "alerts_count": int(summary.get("alerts_count") or 0),
            "summary": {
                "artifacts_dir": summary.get("artifacts_dir"),
                "delivery": summary.get("delivery"),
            },
            "projects": [
                {
                    "project_id": str(item.get("project_id") or ""),
                    "schedule_id": item.get("schedule_id"),
                    "schedule_name": item.get("schedule_name"),
                    "status": item.get("status"),
                    "project_cycle_status": item.get("project_cycle_status"),
                    "returncode": item.get("returncode"),
                    "alerts": item.get("regression_alerts") if isinstance(item.get("regression_alerts"), list) else [],
                    "result": item,
                }
                for item in schedule_results
                if str(item.get("project_id") or "").strip()
            ],
        }
        summary["history_persist"] = _post_calibration_run_history(args.api_url, run_payload)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if status == "partial_failure":
        sys.exit(1)
    if args.fail_on_alert and alerts:
        sys.exit(1)


if __name__ == "__main__":
    main()
