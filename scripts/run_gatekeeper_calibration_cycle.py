#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest


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


def _json_load_file(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"expected JSON object in {path}")
    return data


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


def _discover_projects_from_db(database_url: str, lookback_days: int) -> list[str]:
    try:
        import psycopg
    except Exception as exc:  # pragma: no cover
        raise SystemExit("Install psycopg[binary] to use --all-projects discovery.") from exc

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


def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(
        url=url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlrequest.urlopen(req, timeout=25) as resp:
            raw = resp.read().decode("utf-8")
    except urlerror.HTTPError as exc:
        details = exc.read().decode("utf-8") if exc.fp is not None else ""
        raise RuntimeError(f"snapshot API request failed: {exc.code} {details}") from exc
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"snapshot API request failed: {exc}") from exc
    data = json.loads(raw) if raw else {}
    if not isinstance(data, dict):
        raise RuntimeError(f"unexpected response payload from {url}")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Execute Gatekeeper production calibration cycle (build_holdout -> calibrate -> apply -> snapshot)."
    )
    parser.add_argument("--project-id", action="append", default=[], help="Project id(s), can be repeated or comma-separated.")
    parser.add_argument("--all-projects", action="store_true", help="Auto-discover active projects from gatekeeper_decisions.")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", "postgresql://synapse:synapse@localhost:55432/synapse"),
        help="Postgres connection URL for holdout build/discovery.",
    )
    parser.add_argument("--api-url", default="http://localhost:8080", help="Synapse API base URL.")
    parser.add_argument("--lookback-days", type=int, default=60, help="Holdout lookback horizon in days.")
    parser.add_argument("--limit", type=int, default=20000, help="Max DB rows for holdout build.")
    parser.add_argument("--holdout-ratio", type=float, default=0.3, help="Deterministic holdout ratio.")
    parser.add_argument("--split-seed", default="synapse-gatekeeper-prod-holdout-v1", help="Deterministic split seed.")
    parser.add_argument("--weights", default=None, help="Calibration grid override for llm_score_weight.")
    parser.add_argument("--confidences", default=None, help="Calibration grid override for llm_min_confidence.")
    parser.add_argument("--score-thresholds", default=None, help="Calibration grid override for min_score_for_golden.")
    parser.add_argument("--top-k", type=int, default=5, help="Number of top calibration candidates in report.")
    parser.add_argument(
        "--python-bin",
        default=None,
        help="Python interpreter path for helper scripts. Defaults to current interpreter with fallback to services/api/.venv/bin/python when psycopg is unavailable.",
    )
    parser.add_argument("--updated-by", default="gatekeeper_calibration_bot", help="Actor for config update/snapshot.")
    parser.add_argument("--allow-guardrail-fail", action="store_true", help="Allow apply even when guardrails fail.")
    parser.add_argument("--snapshot-note", default=None, help="Optional note persisted in snapshot record.")
    parser.add_argument(
        "--artifacts-dir",
        default="artifacts/gatekeeper_calibration",
        help="Directory for holdout/report/apply artifacts.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Run cycle without applying config/snapshot.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    scripts_dir = root / "scripts"
    worker_src = root / "services" / "worker"
    fallback_python = root / "services" / "api" / ".venv" / "bin" / "python"
    runner_python = str(args.python_bin or sys.executable)
    if args.python_bin is None:
        try:
            import psycopg  # type: ignore  # noqa: F401
        except Exception:
            if fallback_python.exists():
                runner_python = str(fallback_python)
    cycle_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    artifacts_root = (root / args.artifacts_dir / cycle_id).resolve()
    artifacts_root.mkdir(parents=True, exist_ok=True)

    project_ids = _parse_project_ids(list(args.project_id or []))
    if args.all_projects:
        discovered = _discover_projects_from_db(args.database_url, int(args.lookback_days))
        for item in discovered:
            if item not in project_ids:
                project_ids.append(item)
    if not project_ids:
        raise SystemExit("No projects provided. Use --project-id or --all-projects.")

    cycle_started_at = datetime.now(UTC).isoformat()
    project_results: list[dict[str, Any]] = []

    for project_id in project_ids:
        project_started_at = datetime.now(UTC).isoformat()
        project_dir = artifacts_root / _safe_slug(project_id)
        project_dir.mkdir(parents=True, exist_ok=True)
        holdout_path = project_dir / "holdout.json"
        report_path = project_dir / "calibration_report.json"
        apply_path = project_dir / "apply_result.json"
        snapshot_path = project_dir / "snapshot_result.json"

        result: dict[str, Any] = {
            "project_id": project_id,
            "status": "in_progress",
            "started_at": project_started_at,
            "artifacts": {
                "holdout_path": str(holdout_path),
                "report_path": str(report_path),
                "apply_path": str(apply_path),
                "snapshot_path": str(snapshot_path),
            },
        }

        build_cmd = [
            runner_python,
            str(scripts_dir / "build_gatekeeper_holdout_from_db.py"),
            "--database-url",
            str(args.database_url),
            "--project-id",
            project_id,
            "--lookback-days",
            str(int(args.lookback_days)),
            "--limit",
            str(int(args.limit)),
            "--holdout-ratio",
            str(float(args.holdout_ratio)),
            "--split-seed",
            str(args.split_seed),
            "--output",
            str(holdout_path),
        ]
        build_rc, build_payload, _, build_stderr = _run_command(build_cmd)
        result["build_holdout"] = {"returncode": build_rc, "summary": build_payload}
        if build_stderr.strip():
            result["build_holdout"]["stderr"] = build_stderr.strip()
        if build_rc != 0:
            result["status"] = "failed"
            result["error"] = "build_holdout_failed"
            result["finished_at"] = datetime.now(UTC).isoformat()
            project_results.append(result)
            continue

        calibrate_cmd = [
            runner_python,
            str(scripts_dir / "calibrate_gatekeeper_llm_thresholds.py"),
            "--dataset",
            str(holdout_path),
            "--holdout-ratio",
            str(float(args.holdout_ratio)),
            "--seed",
            str(args.split_seed),
            "--top-k",
            str(int(args.top_k)),
            "--output",
            str(report_path),
        ]
        if args.weights:
            calibrate_cmd.extend(["--weights", str(args.weights)])
        if args.confidences:
            calibrate_cmd.extend(["--confidences", str(args.confidences)])
        if args.score_thresholds:
            calibrate_cmd.extend(["--score-thresholds", str(args.score_thresholds)])

        env = dict(os.environ)
        existing_py = env.get("PYTHONPATH")
        env["PYTHONPATH"] = str(worker_src) if not existing_py else f"{worker_src}{os.pathsep}{existing_py}"
        calibrate_rc, calibrate_payload, _, calibrate_stderr = _run_command(calibrate_cmd, env=env)
        result["calibrate"] = {"returncode": calibrate_rc, "summary": calibrate_payload}
        if calibrate_stderr.strip():
            result["calibrate"]["stderr"] = calibrate_stderr.strip()

        if not report_path.exists():
            result["status"] = "failed"
            result["error"] = "calibration_report_missing"
            result["finished_at"] = datetime.now(UTC).isoformat()
            project_results.append(result)
            continue

        report_payload = _json_load_file(report_path)
        result["calibration_report"] = {
            "guardrails_met": bool((report_payload.get("best_candidate") or {}).get("guardrails_met")),
            "dataset": report_payload.get("dataset"),
            "split": report_payload.get("split"),
        }
        guardrails_met = bool((report_payload.get("best_candidate") or {}).get("guardrails_met"))

        if calibrate_rc not in (0, 1):
            result["status"] = "failed"
            result["error"] = "calibration_failed"
            result["finished_at"] = datetime.now(UTC).isoformat()
            project_results.append(result)
            continue

        if args.dry_run:
            result["status"] = "dry_run"
            result["finished_at"] = datetime.now(UTC).isoformat()
            project_results.append(result)
            continue

        if not guardrails_met and not bool(args.allow_guardrail_fail):
            result["status"] = "blocked_guardrails"
            result["error"] = "guardrails_not_met"
            result["finished_at"] = datetime.now(UTC).isoformat()
            project_results.append(result)
            continue

        apply_cmd = [
            runner_python,
            str(scripts_dir / "apply_gatekeeper_calibration.py"),
            "--report",
            str(report_path),
            "--project-id",
            project_id,
            "--api-url",
            str(args.api_url),
            "--updated-by",
            str(args.updated_by),
        ]
        if not guardrails_met and bool(args.allow_guardrail_fail):
            apply_cmd.append("--allow-guardrail-fail")
        apply_rc, apply_payload, _, apply_stderr = _run_command(apply_cmd)
        apply_path.write_text(json.dumps(apply_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        result["apply"] = {"returncode": apply_rc, "summary": apply_payload}
        if apply_stderr.strip():
            result["apply"]["stderr"] = apply_stderr.strip()
        if apply_rc != 0:
            result["status"] = "failed"
            result["error"] = "apply_failed"
            result["finished_at"] = datetime.now(UTC).isoformat()
            project_results.append(result)
            continue

        api_result = apply_payload.get("api_result") if isinstance(apply_payload, dict) else None
        applied_config = api_result.get("config") if isinstance(api_result, dict) else None
        if not isinstance(applied_config, dict):
            applied_config = apply_payload.get("update_payload") if isinstance(apply_payload, dict) else {}
        if not isinstance(applied_config, dict):
            applied_config = {}

        holdout_payload = _json_load_file(holdout_path)
        snapshot_payload = {
            "project_id": project_id,
            "approved_by": str(args.updated_by),
            "source": "calibration_cycle",
            "note": args.snapshot_note,
            "config": applied_config,
            "guardrails_met": guardrails_met,
            "holdout_meta": holdout_payload.get("meta") if isinstance(holdout_payload.get("meta"), dict) else {},
            "calibration_report": {
                "dataset": report_payload.get("dataset"),
                "split": report_payload.get("split"),
                "guardrails": report_payload.get("guardrails"),
                "best_candidate": report_payload.get("best_candidate"),
                "recommended_gatekeeper_config_payload": report_payload.get("recommended_gatekeeper_config_payload"),
            },
            "artifact_refs": {
                "cycle_id": cycle_id,
                "holdout_path": str(holdout_path),
                "report_path": str(report_path),
                "apply_path": str(apply_path),
            },
        }
        snapshot_response = _post_json(f"{str(args.api_url).rstrip('/')}/v1/gatekeeper/config/snapshots", snapshot_payload)
        snapshot_path.write_text(json.dumps(snapshot_response, ensure_ascii=False, indent=2), encoding="utf-8")
        result["snapshot"] = snapshot_response
        result["status"] = "ok"
        result["finished_at"] = datetime.now(UTC).isoformat()
        project_results.append(result)

    overall_status = "ok"
    if any(item.get("status") not in {"ok", "dry_run"} for item in project_results):
        overall_status = "partial_failure"

    summary = {
        "status": overall_status,
        "cycle_id": cycle_id,
        "started_at": cycle_started_at,
        "finished_at": datetime.now(UTC).isoformat(),
        "artifacts_root": str(artifacts_root),
        "runner_python": runner_python,
        "projects": project_results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if overall_status != "ok":
        sys.exit(1)


if __name__ == "__main__":
    main()
