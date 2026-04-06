#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

ROOT = Path(__file__).resolve().parent.parent
API_DIR = ROOT / "services" / "api"
DEFAULT_DATABASE_URL = "postgresql://synapse:synapse@localhost:55432/synapse"


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _http_json(
    base_url: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout_s: float,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    headers = {"content-type": "application/json"}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib_request.Request(f"{base_url}{path}", data=body, headers=headers, method=method)
    try:
        with urllib_request.urlopen(req, timeout=timeout_s) as response:
            raw = response.read().decode("utf-8")
            parsed = json.loads(raw) if raw else {}
            return {
                "status": int(response.getcode()),
                "headers": {k: v for k, v in response.headers.items()},
                "json": parsed if isinstance(parsed, dict) else {},
                "text": raw,
            }
    except urllib_error.HTTPError as err:
        raw = err.read().decode("utf-8") if err.fp is not None else ""
        parsed = json.loads(raw) if raw else {}
        return {
            "status": int(err.code),
            "headers": {k: v for k, v in (err.headers.items() if err.headers else [])},
            "json": parsed if isinstance(parsed, dict) else {},
            "text": raw,
        }


def _wait_for_api(
    base_url: str,
    *,
    timeout_s: float,
    request_timeout_s: float,
    process: subprocess.Popen[str] | None = None,
) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if process is not None and process.poll() is not None:
            stderr_output = ""
            if process.stderr is not None:
                try:
                    stderr_output = process.stderr.read()
                except Exception:
                    stderr_output = ""
            raise RuntimeError(f"API process exited early with code {process.returncode}: {stderr_output[-2000:]}")
        try:
            response = _http_json(base_url, "GET", "/health", timeout_s=request_timeout_s)
            status_value = str((response.get("json") or {}).get("status") or "").lower()
            if response["status"] == 200 and status_value in {"ok", "degraded"}:
                return
        except Exception:
            pass
        time.sleep(0.25)
    raise RuntimeError(f"API at {base_url} did not become ready in time")


def _api_get(base_url: str, path: str, *, timeout_s: float) -> dict[str, Any]:
    response = _http_json(base_url, "GET", path, timeout_s=timeout_s)
    _assert(response["status"] == 200, f"GET {path} failed: {response['status']} {response['text']}")
    return response["json"]


def _api_post(
    base_url: str,
    path: str,
    payload: dict[str, Any],
    *,
    timeout_s: float,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    response = _http_json(base_url, "POST", path, payload, timeout_s=timeout_s, idempotency_key=idempotency_key)
    _assert(response["status"] == 200, f"POST {path} failed: {response['status']} {response['text']}")
    return response["json"]


def _apply_migrations(database_url: str) -> None:
    env = dict(os.environ)
    env["DATABASE_URL"] = database_url
    result = subprocess.run(
        [str(ROOT / "scripts" / "apply_migrations.sh")],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    _assert(result.returncode == 0, f"migrations failed: {result.stderr or result.stdout}")


def _start_api_process(*, api_python: str, api_port: int, database_url: str) -> subprocess.Popen[str]:
    env = dict(os.environ)
    env["DATABASE_URL"] = database_url
    process = subprocess.Popen(
        [
            api_python,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(api_port),
        ],
        cwd=str(API_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return process


def _terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.send_signal(signal.SIGTERM)
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()


def _assert_action_totals(payload: dict[str, Any], expected: dict[str, tuple[int, int]]) -> None:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    actions = summary.get("actions") if isinstance(summary.get("actions"), list) else []
    by_action: dict[str, dict[str, Any]] = {}
    for item in actions:
        if not isinstance(item, dict):
            continue
        action_key = str(item.get("action_key") or "").strip()
        if not action_key:
            continue
        by_action[action_key] = item

    for action_key, (shown_total, applied_total) in expected.items():
        row = by_action.get(action_key)
        _assert(row is not None, f"missing action in telemetry summary: {action_key}")
        _assert(
            int(row.get("shown_total") or 0) == shown_total,
            f"shown_total mismatch for {action_key}: {row}",
        )
        _assert(
            int(row.get("applied_total") or 0) == applied_total,
            f"applied_total mismatch for {action_key}: {row}",
        )


def run_integration(args: argparse.Namespace) -> dict[str, Any]:
    api_process: subprocess.Popen[str] | None = None
    api_url = str(args.api_url or "").strip()
    started_local_api = False
    if not api_url:
        port = _pick_free_port()
        api_url = f"http://127.0.0.1:{port}"
        api_process = _start_api_process(api_python=args.api_python, api_port=port, database_url=args.database_url)
        started_local_api = True

    try:
        if not args.skip_migrations:
            _apply_migrations(args.database_url)
        _wait_for_api(
            api_url,
            timeout_s=args.startup_timeout,
            request_timeout_s=args.request_timeout,
            process=api_process,
        )

        project_id = f"telemetry_{uuid.uuid4().hex[:8]}"
        now_iso = datetime.now(UTC).isoformat()
        session_one = f"session_{uuid.uuid4().hex[:6]}"
        session_two = f"session_{uuid.uuid4().hex[:6]}"

        missing_project = _http_json(
            api_url,
            "GET",
            "/v1/wiki/lifecycle/telemetry?days=7",
            timeout_s=args.request_timeout,
        )
        _assert(
            missing_project["status"] == 422,
            f"expected 422 for missing project_id, got: {missing_project}",
        )

        payload_one = {
            "project_id": project_id,
            "session_id": session_one,
            "observed_at": now_iso,
            "source": "integration_test",
            "empty_scope_action_shown": {
                "create_page": 2,
                "review_open_drafts": 1,
            },
            "empty_scope_action_applied": {
                "create_page": 1,
            },
        }
        first = _api_post(
            api_url,
            "/v1/wiki/lifecycle/telemetry/snapshot",
            payload_one,
            timeout_s=args.request_timeout,
            idempotency_key=f"it-first-{project_id}",
        )
        _assert(int(first.get("ingested_rows") or 0) == 3, f"unexpected first ingest rows: {first}")
        _assert(
            int((first.get("delta_by_kind") or {}).get("empty_scope_action_shown") or 0) == 3,
            f"unexpected shown delta for first snapshot: {first}",
        )
        _assert(
            int((first.get("delta_by_kind") or {}).get("empty_scope_action_applied") or 0) == 1,
            f"unexpected applied delta for first snapshot: {first}",
        )

        replay = _api_post(
            api_url,
            "/v1/wiki/lifecycle/telemetry/snapshot",
            payload_one,
            timeout_s=args.request_timeout,
            idempotency_key=f"it-replay-{project_id}",
        )
        _assert(int(replay.get("ingested_rows") or 0) == 0, f"snapshot replay should be delta=0: {replay}")

        second = _api_post(
            api_url,
            "/v1/wiki/lifecycle/telemetry/snapshot",
            {
                "project_id": project_id,
                "session_id": session_one,
                "observed_at": now_iso,
                "source": "integration_test",
                "empty_scope_action_shown": {
                    "create_page": 5,
                    "review_open_drafts": 2,
                    "lower_threshold": 1,
                },
                "empty_scope_action_applied": {
                    "create_page": 2,
                    "lower_threshold": 1,
                },
            },
            timeout_s=args.request_timeout,
            idempotency_key=f"it-second-{project_id}",
        )
        _assert(int(second.get("ingested_rows") or 0) == 5, f"unexpected second ingest rows: {second}")
        _assert(
            int((second.get("delta_by_kind") or {}).get("empty_scope_action_shown") or 0) == 5,
            f"unexpected shown delta for second snapshot: {second}",
        )
        _assert(
            int((second.get("delta_by_kind") or {}).get("empty_scope_action_applied") or 0) == 2,
            f"unexpected applied delta for second snapshot: {second}",
        )

        third = _api_post(
            api_url,
            "/v1/wiki/lifecycle/telemetry/snapshot",
            {
                "project_id": project_id,
                "session_id": session_two,
                "observed_at": now_iso,
                "source": "integration_test",
                "empty_scope_action_shown": {
                    "review_open_drafts": 2,
                },
                "empty_scope_action_applied": {
                    "review_open_drafts": 1,
                },
            },
            timeout_s=args.request_timeout,
            idempotency_key=f"it-third-{project_id}",
        )
        _assert(int(third.get("ingested_rows") or 0) == 2, f"unexpected third ingest rows: {third}")

        summary = _api_get(
            api_url,
            f"/v1/wiki/lifecycle/telemetry?{urllib_parse.urlencode({'project_id': project_id, 'days': 7})}",
            timeout_s=args.request_timeout,
        )
        _assert(int(summary.get("days") or 0) == 7, f"days mismatch in summary: {summary}")
        summary_section = summary.get("summary") if isinstance(summary.get("summary"), dict) else {}
        _assert(int(summary_section.get("shown_total") or 0) == 10, f"shown_total mismatch: {summary}")
        _assert(int(summary_section.get("applied_total") or 0) == 4, f"applied_total mismatch: {summary}")
        _assert_action_totals(
            summary,
            expected={
                "create_page": (5, 2),
                "review_open_drafts": (4, 1),
                "lower_threshold": (1, 1),
            },
        )
        daily = summary.get("daily") if isinstance(summary.get("daily"), list) else []
        _assert(len(daily) == 7, f"expected 7-day series: {summary}")
        today_key = datetime.now(UTC).date().isoformat()
        today_bucket = next(
            (
                item
                for item in daily
                if isinstance(item, dict) and str(item.get("metric_date") or "").strip() == today_key
            ),
            None,
        )
        _assert(today_bucket is not None, f"today bucket missing in daily series: {daily}")
        _assert(
            int(today_bucket.get("shown_total") or 0) == 10 and int(today_bucket.get("applied_total") or 0) == 4,
            f"today bucket totals mismatch: {today_bucket}",
        )
        filtered = _api_get(
            api_url,
            f"/v1/wiki/lifecycle/telemetry?{urllib_parse.urlencode({'project_id': project_id, 'days': 7, 'action_key': 'create_page'})}",
            timeout_s=args.request_timeout,
        )
        filtered_summary = filtered.get("summary") if isinstance(filtered.get("summary"), dict) else {}
        _assert(str(filtered.get("action_key") or "") == "create_page", f"filtered action key mismatch: {filtered}")
        _assert(int(filtered_summary.get("shown_total") or 0) == 5, f"filtered shown_total mismatch: {filtered}")
        _assert(int(filtered_summary.get("applied_total") or 0) == 2, f"filtered applied_total mismatch: {filtered}")
        filtered_actions = filtered_summary.get("actions") if isinstance(filtered_summary.get("actions"), list) else []
        _assert(len(filtered_actions) == 1, f"filtered actions should contain only requested key: {filtered}")
        _assert(
            str((filtered_actions[0] or {}).get("action_key") or "") == "create_page",
            f"filtered action row mismatch: {filtered_actions}",
        )

        return {
            "status": "ok",
            "project_id": project_id,
            "api_url": api_url,
            "started_local_api": started_local_api,
            "summary": {
                "shown_total": int(summary_section.get("shown_total") or 0),
                "applied_total": int(summary_section.get("applied_total") or 0),
                "apply_rate": float(summary_section.get("apply_rate") or 0.0),
            },
            "filtered_summary": {
                "action_key": "create_page",
                "shown_total": int(filtered_summary.get("shown_total") or 0),
                "applied_total": int(filtered_summary.get("applied_total") or 0),
                "apply_rate": float(filtered_summary.get("apply_rate") or 0.0),
            },
            "actions": summary_section.get("actions") if isinstance(summary_section.get("actions"), list) else [],
            "daily": daily,
        }
    finally:
        if api_process is not None:
            _terminate_process(api_process)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Integration smoke for lifecycle empty-scope telemetry endpoints (real API + Postgres schema).",
    )
    parser.add_argument(
        "--api-url",
        default=os.getenv("INTEGRATION_API_URL", ""),
        help="Reuse existing Synapse API URL. If omitted, script starts local API process.",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL),
        help=f"Postgres DSN used by API/migrations (default: {DEFAULT_DATABASE_URL}).",
    )
    default_api_python = API_DIR / ".venv" / "bin" / "python"
    parser.add_argument(
        "--api-python",
        default=os.getenv(
            "INTEGRATION_API_PYTHON",
            str(default_api_python if default_api_python.exists() else sys.executable),
        ),
        help="Python executable for local API process.",
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=float(os.getenv("INTEGRATION_REQUEST_TIMEOUT", "8")),
        help="HTTP request timeout (seconds).",
    )
    parser.add_argument(
        "--startup-timeout",
        type=float,
        default=25.0,
        help="API startup timeout (seconds).",
    )
    parser.add_argument(
        "--skip-migrations",
        action="store_true",
        help="Skip migration step (use if schema is already up to date).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(argv or sys.argv[1:]))
    result = run_integration(args)
    print(json.dumps(result, indent=2))
    print("integration lifecycle telemetry ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
