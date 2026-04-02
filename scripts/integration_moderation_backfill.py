#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

ROOT = Path(__file__).resolve().parent.parent
API_DIR = ROOT / "services" / "api"
WORKER_SRC = ROOT / "services" / "worker"

API_URL = os.getenv("INTEGRATION_API_URL", "")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://synapse:synapse@localhost:55432/synapse")
REQUEST_TIMEOUT = float(os.getenv("INTEGRATION_REQUEST_TIMEOUT", "8"))


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_api(base_url: str, process: subprocess.Popen[str], *, timeout_s: float = 20.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if process.poll() is not None:
            stderr_output = ""
            if process.stderr is not None:
                try:
                    stderr_output = process.stderr.read()
                except Exception:
                    stderr_output = ""
            raise RuntimeError(f"API process exited early with code {process.returncode}: {stderr_output[-2000:]}")
        try:
            response = _http_json("GET", "/health")
            if response["status"] == 200 and response["json"].get("status") in {"ok", "degraded"}:
                return
        except Exception:
            pass
        time.sleep(0.25)
    raise RuntimeError("API did not become ready in time")


def _http_json(method: str, path: str, payload: dict[str, Any] | None = None, *, idempotency_key: str | None = None) -> dict[str, Any]:
    headers = {"content-type": "application/json"}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib_request.Request(f"{API_URL}{path}", data=body, headers=headers, method=method)
    try:
        with urllib_request.urlopen(req, timeout=REQUEST_TIMEOUT) as res:
            raw = res.read().decode("utf-8")
            parsed = json.loads(raw) if raw else {}
            return {
                "status": res.getcode(),
                "headers": {k: v for k, v in res.headers.items()},
                "json": parsed,
                "text": raw,
            }
    except urllib_error.HTTPError as err:
        raw = err.read().decode("utf-8") if err.fp is not None else ""
        parsed = json.loads(raw) if raw else {}
        return {
            "status": err.code,
            "headers": {k: v for k, v in err.headers.items()} if err.headers else {},
            "json": parsed if isinstance(parsed, dict) else {},
            "text": raw,
        }


def _api_post(path: str, payload: dict[str, Any], *, idempotency_key: str | None = None) -> dict[str, Any]:
    return _http_json("POST", path, payload, idempotency_key=idempotency_key)


def _api_put(path: str, payload: dict[str, Any], *, idempotency_key: str | None = None) -> dict[str, Any]:
    return _http_json("PUT", path, payload, idempotency_key=idempotency_key)


def _api_get(path: str) -> dict[str, Any]:
    response = _http_json("GET", path)
    _assert(response["status"] == 200, f"GET {path} failed with {response['status']}: {response['text']}")
    return response["json"]


def _api_delete(path: str) -> dict[str, Any]:
    return _http_json("DELETE", path)


def _header_value(headers: dict[str, str], key: str) -> str | None:
    lookup = key.lower()
    for k, value in headers.items():
        if k.lower() == lookup:
            return value
    return None


def _status(response: dict[str, Any]) -> int:
    return int(response.get("status", 0))


def _json(response: dict[str, Any]) -> dict[str, Any]:
    payload = response.get("json")
    return payload if isinstance(payload, dict) else {}


def _text(response: dict[str, Any]) -> str:
    return str(response.get("text", ""))


def _api_post_assert_ok(path: str, payload: dict[str, Any], *, idempotency_key: str | None = None) -> dict[str, Any]:
    response = _api_post(path, payload, idempotency_key=idempotency_key)
    _assert(_status(response) == 200, f"{path} failed: {_status(response)} {_text(response)}")
    return response


def _api_put_assert_ok(path: str, payload: dict[str, Any], *, idempotency_key: str | None = None) -> dict[str, Any]:
    response = _api_put(path, payload, idempotency_key=idempotency_key)
    _assert(_status(response) == 200, f"{path} failed: {_status(response)} {_text(response)}")
    return response


def _api_delete_assert_ok(path: str) -> dict[str, Any]:
    response = _api_delete(path)
    _assert(_status(response) == 200, f"{path} failed: {_status(response)} {_text(response)}")
    return response


def _run_worker_once(api_python: str) -> dict[str, int]:
    env = dict(os.environ)
    env["DATABASE_URL"] = DATABASE_URL
    env["PYTHONPATH"] = str(WORKER_SRC)
    result = subprocess.run(
        [
            api_python,
            str(WORKER_SRC / "scripts" / "run_wiki_synthesis.py"),
            "--extract-limit",
            "50",
            "--limit",
            "50",
            "--cycles",
            "1",
        ],
        env=env,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    _assert(result.returncode == 0, f"worker run failed: {result.stderr or result.stdout}")
    payload = json.loads(result.stdout)
    extract = {
        "picked": payload.get("backfill_events_picked", 0),
        "events_completed": payload.get("backfill_events_completed", 0),
        "claims_generated": payload.get("backfill_claims_generated", 0),
    }
    synth = {
        "picked": payload.get("draft_claims_picked", 0),
        "processed": payload.get("draft_claims_processed", 0),
    }
    return {
        "backfill_picked": int(extract.get("picked", 0)),
        "backfill_completed": int(extract.get("events_completed", 0)),
        "backfill_claims_generated": int(extract.get("claims_generated", 0)),
        "draft_picked": int(synth.get("picked", 0)),
        "draft_processed": int(synth.get("processed", 0)),
    }


def _run_digest_once(api_python: str, *, project_id: str, anchor_date: str, kind: str = "daily") -> dict[str, Any]:
    env = dict(os.environ)
    env["DATABASE_URL"] = DATABASE_URL
    env["PYTHONPATH"] = str(WORKER_SRC)
    result = subprocess.run(
        [
            api_python,
            str(WORKER_SRC / "scripts" / "run_intelligence_digest.py"),
            "--project-id",
            project_id,
            "--kind",
            kind,
            "--date",
            anchor_date,
            "--generated-by",
            "integration_runner",
        ],
        env=env,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    _assert(result.returncode == 0, f"digest run failed: {result.stderr or result.stdout}")
    payload = json.loads(result.stdout)
    _assert(payload.get("status") == "ok", f"digest payload not ok: {payload}")
    _assert(payload.get("kind") == kind, f"digest kind mismatch: {payload}")
    _assert(int(payload.get("projects", 0)) >= 1, f"digest did not process project: {payload}")
    results = payload.get("results") or []
    _assert(isinstance(results, list) and results, f"digest results missing: {payload}")
    return results[0]


def _run_delivery_once(api_python: str, *, project_id: str, kind: str = "daily", limit: int = 20) -> dict[str, Any]:
    env = dict(os.environ)
    env["DATABASE_URL"] = DATABASE_URL
    env["PYTHONPATH"] = str(WORKER_SRC)
    result = subprocess.run(
        [
            api_python,
            str(WORKER_SRC / "scripts" / "run_intelligence_delivery.py"),
            "--project-id",
            project_id,
            "--kind",
            kind,
            "--limit",
            str(limit),
        ],
        env=env,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    _assert(result.returncode == 0, f"delivery run failed: {result.stderr or result.stdout}")
    payload = json.loads(result.stdout)
    _assert(int(payload.get("picked", 0)) >= 1, f"delivery run picked no digests: {payload}")
    return payload


def _start_webhook_receiver() -> tuple[HTTPServer, Thread, list[dict[str, Any]], str]:
    captured: list[dict[str, Any]] = []
    port = _pick_free_port()

    class _WebhookHandler(BaseHTTPRequestHandler):
        def do_POST(self):  # type: ignore[override]
            length = int(self.headers.get("content-length", "0"))
            raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
            try:
                parsed = json.loads(raw) if raw else {}
            except Exception:
                parsed = {"raw": raw}
            captured.append(parsed if isinstance(parsed, dict) else {"parsed": parsed})
            body = json.dumps({"ok": True}).encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):  # type: ignore[override]
            return

    server = HTTPServer(("127.0.0.1", port), _WebhookHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, captured, f"http://127.0.0.1:{port}/slack"


def main() -> None:
    global API_URL
    project_id = f"integration_{uuid.uuid4().hex[:8]}"
    batch_id = str(uuid.uuid4())
    webhook_server, webhook_thread, webhook_captured, webhook_url = _start_webhook_receiver()
    if not API_URL:
        API_URL = f"http://127.0.0.1:{_pick_free_port()}"
    api_port = API_URL.rsplit(":", 1)[-1]

    env = dict(os.environ)
    env["DATABASE_URL"] = DATABASE_URL
    default_api_python = API_DIR / ".venv" / "bin" / "python"
    api_python = os.getenv(
        "INTEGRATION_API_PYTHON",
        str(default_api_python if default_api_python.exists() else sys.executable),
    )
    process = subprocess.Popen(
        [
            api_python,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            api_port,
        ],
        cwd=str(API_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        _wait_for_api(API_URL, process)
        key_prefix = f"it-{project_id}"

        collecting_payload = {
            "batch": {
                "batch_id": batch_id,
                "project_id": project_id,
                "source_system": "integration_test",
                "created_by": "integration_runner",
                "finalize": False,
                "records": [
                    {
                        "source_id": "mem-1",
                        "content": "Warehouse 9 closed until 2026-04-15. Entry only with permit.",
                        "entity_key": "warehouse_9",
                        "category": "operations",
                        "observed_at": "2026-03-30T08:00:00Z",
                    }
                ],
            }
        }
        ready_payload = {
            "batch": {
                "batch_id": batch_id,
                "project_id": project_id,
                "source_system": "integration_test",
                "created_by": "integration_runner",
                "finalize": True,
                "records": [
                    {
                        "source_id": "mem-2",
                        "content": "BC Sigma gate now card-only after 09:00. Drivers confirmed this twice.",
                        "entity_key": "bc_sigma",
                        "category": "access",
                        "observed_at": "2026-03-30T09:00:00Z",
                    },
                    {
                        "source_id": "mem-3",
                        "content": "Warehouse 9 open for deliveries from 2026-04-16.",
                        "entity_key": "warehouse_9",
                        "category": "operations",
                        "observed_at": "2026-04-16T09:00:00Z",
                    }
                ],
            }
        }

        r1 = _api_post_assert_ok("/v1/backfill/memory", collecting_payload, idempotency_key=f"{key_prefix}-backfill-part1")
        _assert(_json(r1).get("status") == "collecting", f"expected collecting, got {_json(r1)}")

        r2 = _api_post_assert_ok("/v1/backfill/memory", ready_payload, idempotency_key=f"{key_prefix}-backfill-part2")
        _assert(_json(r2).get("status") == "ready", f"expected ready, got {_json(r2)}")

        r2_replay = _api_post_assert_ok("/v1/backfill/memory", ready_payload, idempotency_key=f"{key_prefix}-backfill-part2")
        _assert(
            _header_value(r2_replay["headers"], "X-Idempotent-Replay") == "true",
            f"expected idempotent replay header, got {r2_replay['headers']}",
        )

        batch_before = _api_get(f"/v1/backfill/batches/{batch_id}?project_id={project_id}")["batch"]
        _assert(batch_before["status"] == "ready", f"expected batch ready, got {batch_before}")
        _assert(batch_before["inserted_events"] == 3, f"expected 3 inserted events, got {batch_before}")

        config_upsert = _api_put_assert_ok(
            "/v1/gatekeeper/config",
            {
                "project_id": project_id,
                "updated_by": "integration_runner",
                "min_sources_for_golden": 2,
                "conflict_free_days": 5,
                "min_score_for_golden": 0.65,
                "operational_short_text_len": 28,
                "operational_short_token_len": 4,
                "llm_assist_enabled": True,
                "llm_provider": "openai",
                "llm_model": "gpt-4.1-mini",
                "llm_score_weight": 0.4,
                "llm_min_confidence": 0.7,
                "llm_timeout_ms": 3200,
            },
        )
        _assert(_json(config_upsert).get("status") == "ok", f"gatekeeper config upsert failed: {_json(config_upsert)}")
        config_read = _api_get(f"/v1/gatekeeper/config?project_id={project_id}")["config"]
        _assert(config_read["min_sources_for_golden"] == 2, f"gatekeeper config read mismatch: {config_read}")
        _assert("llm_assist_enabled" in config_read, f"gatekeeper llm config missing in response: {config_read}")
        _assert(config_read["llm_assist_enabled"] is True, f"expected llm_assist_enabled=true, got {config_read}")

        snapshot_create = _api_post_assert_ok(
            "/v1/gatekeeper/config/snapshots",
            {
                "project_id": project_id,
                "approved_by": "integration_runner",
                "source": "calibration_cycle",
                "note": "integration snapshot",
                "config": config_read,
                "guardrails_met": True,
                "holdout_meta": {"labeled_cases": 3},
                "calibration_report": {"dataset": "integration_fixture"},
                "artifact_refs": {"report_path": "/tmp/integration-report.json"},
            },
        )
        snapshot_created = _json(snapshot_create).get("snapshot") or {}
        _assert(snapshot_created.get("project_id") == project_id, f"snapshot create mismatch: {snapshot_create}")
        snapshots_payload = _api_get(f"/v1/gatekeeper/config/snapshots?project_id={project_id}&limit=5")
        snapshots = snapshots_payload.get("snapshots") or []
        _assert(snapshots, f"snapshot list empty: {snapshots_payload}")
        _assert(
            any(item.get("source") == "calibration_cycle" for item in snapshots),
            f"snapshot source not found in list: {snapshots_payload}",
        )
        trends_payload = _api_get(f"/v1/gatekeeper/calibration/trends?project_id={project_id}&limit=6")
        _assert(trends_payload.get("project_id") == project_id, f"trends project mismatch: {trends_payload}")
        _assert(
            isinstance(trends_payload.get("points"), list),
            f"calibration trends points payload invalid: {trends_payload}",
        )
        rollback_payload = _api_post_assert_ok(
            "/v1/gatekeeper/config/rollback",
            {
                "project_id": project_id,
                "snapshot_id": snapshot_created.get("id"),
                "updated_by": "integration_runner",
                "note": "integration rollback check",
            },
        )
        rollback_json = _json(rollback_payload)
        _assert(rollback_json.get("status") == "ok", f"rollback failed: {rollback_json}")
        snapshots_after_rollback = _api_get(f"/v1/gatekeeper/config/snapshots?project_id={project_id}&limit=10")
        _assert(
            any(item.get("source") == "rollback" for item in (snapshots_after_rollback.get("snapshots") or [])),
            f"rollback snapshot not found: {snapshots_after_rollback}",
        )
        rollback_preview = _api_post_assert_ok(
            "/v1/gatekeeper/config/rollback/preview",
            {
                "project_id": project_id,
                "snapshot_id": snapshot_created.get("id"),
                "lookback_days": 30,
                "limit": 1000,
                "sample_size": 10,
            },
        )
        rollback_preview_json = _json(rollback_preview)
        _assert(rollback_preview_json.get("status") == "ok", f"rollback preview failed: {rollback_preview_json}")
        _assert(
            isinstance((rollback_preview_json.get("preview") or {}).get("impact"), dict),
            f"rollback preview impact missing: {rollback_preview_json}",
        )
        rollback_request = _api_post_assert_ok(
            "/v1/gatekeeper/config/rollback/requests",
            {
                "project_id": project_id,
                "snapshot_id": snapshot_created.get("id"),
                "requested_by": "ops_director",
                "note": "integration dual approval rollback",
                "required_approvals": 2,
                "lookback_days": 30,
                "limit": 1000,
                "sample_size": 8,
            },
        )
        rollback_request_obj = (_json(rollback_request).get("request") or {})
        rollback_request_id = rollback_request_obj.get("id")
        _assert(rollback_request_id, f"rollback request id missing: {rollback_request_obj}")
        _assert(rollback_request_obj.get("state") == "pending_approval", f"rollback request state mismatch: {rollback_request_obj}")
        rollback_approve_first = _api_post_assert_ok(
            f"/v1/gatekeeper/config/rollback/requests/{rollback_request_id}/approve",
            {
                "project_id": project_id,
                "approved_by": "cto",
                "note": "first approval",
            },
        )
        rollback_approve_first_obj = (_json(rollback_approve_first).get("request") or {})
        _assert(
            rollback_approve_first_obj.get("state") == "pending_approval",
            f"rollback first approve state mismatch: {rollback_approve_first_obj}",
        )
        rollback_approve_second = _api_post_assert_ok(
            f"/v1/gatekeeper/config/rollback/requests/{rollback_request_id}/approve",
            {
                "project_id": project_id,
                "approved_by": "head_of_ai",
                "note": "second approval",
            },
        )
        rollback_approve_second_obj = (_json(rollback_approve_second).get("request") or {})
        _assert(
            rollback_approve_second_obj.get("state") == "applied",
            f"rollback second approve did not apply: {rollback_approve_second_obj}",
        )
        rollback_requests_list = _api_get(
            f"/v1/gatekeeper/config/rollback/requests?project_id={project_id}&status=applied&limit=10"
        )
        _assert(
            any(item.get("id") == rollback_request_id for item in (rollback_requests_list.get("requests") or [])),
            f"applied rollback request not found: {rollback_requests_list}",
        )
        schedule_upsert = _api_put_assert_ok(
            "/v1/gatekeeper/calibration/schedules",
            {
                "project_id": project_id,
                "name": "nightly-main",
                "enabled": True,
                "preset": "nightly",
                "lookback_days": 45,
                "limit_rows": 15000,
                "holdout_ratio": 0.3,
                "weights": [0.35, 0.5],
                "confidences": [0.65, 0.72],
                "score_thresholds": [0.72, 0.76],
                "top_k": 4,
                "updated_by": "integration_runner",
            },
        )
        schedule_json = _json(schedule_upsert)
        schedule_obj = schedule_json.get("schedule") or {}
        _assert(schedule_json.get("status") == "ok", f"schedule upsert failed: {schedule_json}")
        _assert(schedule_obj.get("project_id") == project_id, f"schedule project mismatch: {schedule_json}")
        schedule_id = schedule_obj.get("id")
        _assert(schedule_id, f"schedule id missing: {schedule_json}")

        schedule_list = _api_get(f"/v1/gatekeeper/calibration/schedules?project_id={project_id}&enabled=true")
        schedules = schedule_list.get("schedules") or []
        _assert(any(item.get("id") == schedule_id for item in schedules), f"schedule list missing new id: {schedule_list}")

        schedule_delete = _api_delete_assert_ok(
            f"/v1/gatekeeper/calibration/schedules/{schedule_id}?project_id={project_id}"
        )
        _assert(_json(schedule_delete).get("status") == "ok", f"schedule delete failed: {_json(schedule_delete)}")
        calibration_run_upsert = _api_post_assert_ok(
            "/v1/gatekeeper/calibration/runs",
            {
                "run_id": f"integration-run-{project_id}",
                "status": "alert",
                "started_at": "2026-03-31T08:00:00Z",
                "finished_at": "2026-03-31T08:15:00Z",
                "total_schedules": 1,
                "executed_count": 1,
                "alerts_count": 1,
                "summary": {"source": "integration"},
                "projects": [
                    {
                        "project_id": project_id,
                        "schedule_name": "nightly-main",
                        "status": "executed",
                        "project_cycle_status": "ok",
                        "returncode": 0,
                        "alerts": [{"code": "guardrails_regressed", "severity": "high"}],
                        "result": {"status": "executed"},
                    }
                ],
            },
        )
        _assert(_json(calibration_run_upsert).get("status") == "ok", f"run history upsert failed: {_json(calibration_run_upsert)}")
        calibration_runs_list = _api_get(f"/v1/gatekeeper/calibration/runs?project_id={project_id}&limit=5")
        _assert(
            any(item.get("run_id") == f"integration-run-{project_id}" for item in (calibration_runs_list.get("runs") or [])),
            f"calibration run not found: {calibration_runs_list}",
        )
        calibration_runs_trend = _api_get(f"/v1/gatekeeper/calibration/runs/trends?project_id={project_id}&days=30")
        _assert(calibration_runs_trend.get("project_id") == project_id, f"run trend project mismatch: {calibration_runs_trend}")
        _assert(
            isinstance((calibration_runs_trend.get("summary") or {}).get("top_alert_codes"), list),
            f"run trend summary invalid: {calibration_runs_trend}",
        )
        alert_target_upsert = _api_put_assert_ok(
            "/v1/gatekeeper/alerts/targets",
            {
                "project_id": project_id,
                "channel": "email_smtp",
                "target": "ops-alerts@example.com",
                "enabled": True,
                "config": {"min_severity": "medium"},
                "updated_by": "integration_runner",
            },
        )
        alert_target = _json(alert_target_upsert).get("target") or {}
        alert_target_id = alert_target.get("id")
        _assert(alert_target_id, f"alert target id missing: {alert_target_upsert}")
        alert_targets_payload = _api_get(f"/v1/gatekeeper/alerts/targets?project_id={project_id}&limit=10")
        _assert(
            any(item.get("id") == alert_target_id for item in (alert_targets_payload.get("targets") or [])),
            f"alert target missing in list: {alert_targets_payload}",
        )
        alert_attempt = _api_post_assert_ok(
            "/v1/gatekeeper/alerts/attempts",
            {
                "run_id": f"integration-{project_id}",
                "project_id": project_id,
                "channel": "email_smtp",
                "target": "ops-alerts@example.com",
                "status": "sent",
                "alert_codes": ["guardrails_regressed"],
                "response_payload": {"provider_message_id": "stub-msg"},
            },
        )
        _assert(_json(alert_attempt).get("status") == "ok", f"alert attempt create failed: {_json(alert_attempt)}")
        alert_attempts_payload = _api_get(f"/v1/gatekeeper/alerts/attempts?project_id={project_id}&limit=10")
        _assert(
            any(item.get("run_id") == f"integration-{project_id}" for item in (alert_attempts_payload.get("attempts") or [])),
            f"alert attempts missing expected run: {alert_attempts_payload}",
        )
        alert_target_delete = _api_delete_assert_ok(
            f"/v1/gatekeeper/alerts/targets/{alert_target_id}?project_id={project_id}"
        )
        _assert(_json(alert_target_delete).get("status") == "ok", f"alert target delete failed: {_json(alert_target_delete)}")

        worker_stats = _run_worker_once(api_python)
        _assert(worker_stats["backfill_completed"] >= 3, f"worker did not process backfill events: {worker_stats}")
        _assert(worker_stats["draft_processed"] >= 3, f"worker did not process drafted claims: {worker_stats}")

        batch_after = _api_get(f"/v1/backfill/batches/{batch_id}?project_id={project_id}")["batch"]
        _assert(batch_after["status"] == "completed", f"expected batch completed, got {batch_after}")
        _assert(batch_after["processed_events"] >= 3, f"expected processed events >=3, got {batch_after}")

        drafts = _api_get(f"/v1/wiki/drafts?project_id={project_id}&status=pending_review&limit=10")["drafts"]
        _assert(len(drafts) >= 3, f"expected at least 3 pending drafts, got {len(drafts)}")

        all_drafts = _api_get(f"/v1/wiki/drafts?project_id={project_id}&limit=20")["drafts"]
        warehouse_drafts = []
        for item in all_drafts:
            page_obj = item.get("page") if isinstance(item.get("page"), dict) else {}
            slug = str(item.get("page_slug") or page_obj.get("slug") or "").lower()
            if "warehouse" in slug:
                warehouse_drafts.append(item)
        _assert(warehouse_drafts, f"expected warehouse drafts in scenario, got {all_drafts}")
        _assert(
            all(item.get("status") != "blocked_conflict" for item in warehouse_drafts),
            f"temporal non-overlapping updates should not be blocked as conflicts: {warehouse_drafts}",
        )

        approve_candidates = [item for item in drafts if item.get("decision") != "conflict"]
        _assert(approve_candidates, f"no approvable draft candidates found: {drafts}")
        approve_draft_id = approve_candidates[0]["id"]
        reject_draft_id = next(item["id"] for item in drafts if item["id"] != approve_draft_id)
        detail_before = _api_get(f"/v1/wiki/drafts/{approve_draft_id}?project_id={project_id}")
        draft_before = detail_before.get("draft") or {}
        _assert(draft_before.get("id") == approve_draft_id, f"draft detail mismatch: {detail_before}")
        _assert("semantic_diff" in draft_before, f"draft detail missing semantic_diff: {detail_before}")
        _assert("markdown_patch" in draft_before, f"draft detail missing markdown_patch: {detail_before}")
        explain_before = _api_get(
            f"/v1/wiki/drafts/{approve_draft_id}/conflicts/explain?project_id={project_id}&limit=10"
        )
        _assert(
            explain_before.get("draft_id") == approve_draft_id,
            f"conflict explain draft id mismatch: {explain_before}",
        )
        _assert(
            isinstance(explain_before.get("conflicts"), list),
            f"conflict explain payload invalid: {explain_before}",
        )

        approve_payload = {
            "project_id": project_id,
            "reviewed_by": "integration_runner",
            "note": "approve from integration test",
            "section_edits": [
                {
                    "section_key": "ops_notes",
                    "heading": "Ops Notes",
                    "mode": "append",
                    "statements": ["Escalate BC Sigma access checks before 09:00 dispatch window."],
                }
            ],
        }
        approve1 = _api_post_assert_ok(
            f"/v1/wiki/drafts/{approve_draft_id}/approve",
            approve_payload,
            idempotency_key=f"{key_prefix}-approve-1",
        )
        approve_data = _json(approve1)
        _assert(approve_data.get("status") == "approved", f"unexpected approve response: {approve_data}")
        _assert(bool(approve_data.get("snapshot_id")), f"snapshot_id missing: {approve_data}")
        _assert(int(approve_data.get("structured_edits_applied", 0)) == 1, f"structured edits were not applied: {approve_data}")

        approve_replay = _api_post_assert_ok(
            f"/v1/wiki/drafts/{approve_draft_id}/approve",
            approve_payload,
            idempotency_key=f"{key_prefix}-approve-1",
        )
        _assert(
            _header_value(approve_replay["headers"], "X-Idempotent-Replay") == "true",
            "approve replay header missing",
        )

        reject_payload = {
            "project_id": project_id,
            "reviewed_by": "integration_runner",
            "reason": "reject from integration test",
        }
        reject1 = _api_post_assert_ok(
            f"/v1/wiki/drafts/{reject_draft_id}/reject",
            reject_payload,
            idempotency_key=f"{key_prefix}-reject-1",
        )
        _assert(_json(reject1).get("status") == "rejected", f"unexpected reject response: {_json(reject1)}")

        reject_replay = _api_post_assert_ok(
            f"/v1/wiki/drafts/{reject_draft_id}/reject",
            reject_payload,
            idempotency_key=f"{key_prefix}-reject-1",
        )
        _assert(
            _header_value(reject_replay["headers"], "X-Idempotent-Replay") == "true",
            "reject replay header missing",
        )

        approved_state = _api_get(f"/v1/wiki/drafts?project_id={project_id}&limit=20")["drafts"]
        by_id = {draft["id"]: draft for draft in approved_state}
        _assert(by_id[approve_draft_id]["status"] == "approved", f"approved draft state invalid: {by_id[approve_draft_id]}")
        _assert(by_id[reject_draft_id]["status"] == "rejected", f"rejected draft state invalid: {by_id[reject_draft_id]}")

        page_slug = str(approve_data.get("page_slug") or "")
        _assert(page_slug, f"approved payload missing page_slug: {approve_data}")
        page_data = _api_get(f"/v1/wiki/pages/{page_slug}?project_id={project_id}")
        sections = page_data.get("sections") or []
        section_keys = {item.get("section_key") for item in sections}
        _assert("ops_notes" in section_keys, f"structured section missing in wiki page: {sections}")

        moderation_feed = _api_get(f"/v1/wiki/moderation/actions?project_id={project_id}&limit=20")
        actions = moderation_feed.get("actions") or []
        action_types = [item.get("action_type") for item in actions]
        _assert("approve" in action_types and "reject" in action_types, f"moderation audit feed missing actions: {actions}")
        detail_after = _api_get(f"/v1/wiki/drafts/{approve_draft_id}?project_id={project_id}")
        detail_actions = detail_after.get("moderation_actions") or []
        _assert(detail_actions, f"draft detail missing moderation actions after approval: {detail_after}")
        explain_after = _api_get(
            f"/v1/wiki/drafts/{approve_draft_id}/conflicts/explain?project_id={project_id}&limit=10"
        )
        _assert("source" in explain_after, f"conflict explain source missing: {explain_after}")
        for item in explain_after.get("conflicts") or []:
            _assert("root_cause" in item, f"conflict explain item missing root_cause: {item}")
            _assert("recommendation" in item, f"conflict explain item missing recommendation: {item}")

        metric_date = datetime.now(UTC).date().isoformat()
        digest_result = _run_digest_once(api_python, project_id=project_id, anchor_date=metric_date, kind="daily")
        _assert(digest_result.get("project_id") == project_id, f"digest project mismatch: {digest_result}")

        weekly_result = _run_digest_once(api_python, project_id=project_id, anchor_date=metric_date, kind="weekly")
        _assert(weekly_result.get("digest_kind") == "weekly", f"weekly digest payload mismatch: {weekly_result}")
        incident_digest_result = _run_digest_once(
            api_python,
            project_id=project_id,
            anchor_date=metric_date,
            kind="incident_escalation_daily",
        )
        _assert(
            incident_digest_result.get("digest_kind") == "incident_escalation_daily",
            f"incident escalation digest payload mismatch: {incident_digest_result}",
        )

        metrics_payload = _api_get(
            f"/v1/intelligence/metrics/daily?project_id={project_id}&from_date={metric_date}&to_date={metric_date}&limit=5"
        )
        metrics = metrics_payload.get("metrics") or []
        _assert(metrics, f"metrics missing for {project_id} on {metric_date}: {metrics_payload}")

        digest_latest_payload = _api_get(f"/v1/intelligence/digests/latest?project_id={project_id}&kind=daily")
        digest_latest = digest_latest_payload.get("digest") or {}
        _assert(digest_latest.get("digest_kind") == "daily", f"latest digest kind mismatch: {digest_latest}")
        _assert(digest_latest.get("digest_date") == metric_date, f"latest digest date mismatch: {digest_latest}")
        _assert(bool(digest_latest.get("headline")), f"digest headline missing: {digest_latest}")

        weekly_latest_payload = _api_get(f"/v1/intelligence/digests/latest?project_id={project_id}&kind=weekly")
        weekly_latest = weekly_latest_payload.get("digest") or {}
        _assert(weekly_latest.get("digest_kind") == "weekly", f"latest weekly digest kind mismatch: {weekly_latest}")
        weekly_payload = weekly_latest.get("payload") or {}
        _assert("trend_breakdown" in weekly_payload, f"weekly trend breakdown missing: {weekly_latest}")
        _assert("current_rollup" in weekly_payload, f"weekly rollup missing: {weekly_latest}")
        incident_latest_payload = _api_get(
            f"/v1/intelligence/digests/latest?project_id={project_id}&kind=incident_escalation_daily"
        )
        incident_latest = incident_latest_payload.get("digest") or {}
        _assert(
            incident_latest.get("digest_kind") == "incident_escalation_daily",
            f"latest incident escalation digest kind mismatch: {incident_latest}",
        )
        incident_payload = incident_latest.get("payload") or {}
        _assert("snapshot" in incident_payload, f"incident escalation payload missing snapshot: {incident_latest}")
        _assert("suggestions" in incident_payload, f"incident escalation payload missing suggestions: {incident_latest}")

        weekly_trends = _api_get(f"/v1/intelligence/trends/weekly?project_id={project_id}&anchor_date={metric_date}&weeks=4")
        weeks_payload = weekly_trends.get("weeks") or []
        _assert(weeks_payload, f"weekly trends endpoint returned empty payload: {weekly_trends}")
        _assert("knowledge_velocity_avg" in weeks_payload[-1], f"weekly trends missing velocity average: {weekly_trends}")

        conflict_drilldown = _api_get(
            f"/v1/intelligence/conflicts/drilldown?project_id={project_id}&anchor_date={metric_date}&weeks=4&type_limit=5"
        )
        drilldown_weeks = conflict_drilldown.get("weeks") or []
        _assert(drilldown_weeks, f"conflict drilldown endpoint returned empty payload: {conflict_drilldown}")
        _assert("top_conflict_types" in conflict_drilldown, f"conflict drilldown missing top_conflict_types: {conflict_drilldown}")
        _assert("overall" in conflict_drilldown, f"conflict drilldown missing overall: {conflict_drilldown}")

        delivery_target = _api_put_assert_ok(
            "/v1/intelligence/delivery/targets",
            {
                "project_id": project_id,
                "channel": "slack_webhook",
                "target": webhook_url,
                "enabled": True,
                "config": {
                    "timeout_seconds": 5,
                    "digest_kinds": ["daily", "incident_escalation_daily"],
                    "incident_escalation_require_over_sla": False,
                    "incident_escalation_playbook": {
                        "enabled": True,
                        "owner_tier_enabled": True,
                        "owner_tier_max_candidates": 3,
                        "owner_tier_channels_by_severity": {
                            "info": "oncall_channel",
                            "warning": "oncall_channel",
                            "critical": "escalation_channel",
                        },
                        "owner_tier_fallback_recipients": ["#synapse-escalation-fallback"],
                        "severity_fanout": {
                            "info": ["#synapse-escalation-info"],
                            "warning": ["#synapse-escalation-warning"],
                            "critical": ["#synapse-escalation-critical"],
                        },
                        "quiet_hours": {
                            "enabled": False,
                            "timezone": "UTC",
                            "allow_severity_at_or_above": "critical",
                            "windows": [
                                {
                                    "days": ["mon", "tue", "wed", "thu", "fri"],
                                    "start": "22:00",
                                    "end": "08:00",
                                }
                            ],
                        },
                    },
                },
                "updated_by": "integration_runner",
            },
        )
        _assert(_json(delivery_target).get("status") == "ok", f"delivery target upsert failed: {_json(delivery_target)}")
        target_config = ((_json(delivery_target).get("target") or {}).get("config") or {})
        playbook_config = target_config.get("incident_escalation_playbook") if isinstance(target_config, dict) else {}
        _assert(isinstance(playbook_config, dict), f"playbook config missing in delivery target: {_json(delivery_target)}")
        _assert(bool(playbook_config.get("enabled")), f"playbook should be enabled: {playbook_config}")
        fanout_config = playbook_config.get("severity_fanout") if isinstance(playbook_config, dict) else {}
        _assert(
            isinstance(fanout_config, dict) and len(fanout_config.get("critical") or []) >= 1,
            f"playbook fanout config missing: {playbook_config}",
        )

        delivery_run = _run_delivery_once(api_python, project_id=project_id)
        _assert(int(delivery_run.get("attempts_sent", 0)) >= 1, f"delivery attempts not sent: {delivery_run}")
        incident_delivery_run = _run_delivery_once(
            api_python,
            project_id=project_id,
            kind="incident_escalation_daily",
        )
        _assert(
            int(incident_delivery_run.get("attempts_sent", 0)) >= 1,
            f"incident delivery attempts not sent: {incident_delivery_run}",
        )
        _assert(len(webhook_captured) >= 1, f"webhook did not receive payload: {webhook_captured}")

        attempts_payload = _api_get(f"/v1/intelligence/delivery/attempts?project_id={project_id}&status=sent&limit=20")
        attempts = attempts_payload.get("attempts") or []
        _assert(attempts, f"delivery attempts endpoint returned empty set: {attempts_payload}")
        incident_attempts_payload = _api_get(
            f"/v1/intelligence/delivery/attempts?project_id={project_id}&kind=incident_escalation_daily&limit=20"
        )
        incident_attempts = incident_attempts_payload.get("attempts") or []
        _assert(incident_attempts, f"incident delivery attempts endpoint returned empty set: {incident_attempts_payload}")
        routed_attempts = [
            item
            for item in incident_attempts
            if isinstance(item, dict)
            and isinstance(item.get("response_payload"), dict)
            and isinstance((item.get("response_payload") or {}).get("routing"), dict)
            and bool(((item.get("response_payload") or {}).get("routing") or {}).get("route_type"))
        ]
        _assert(
            routed_attempts,
            f"incident attempts missing routing metadata (playbook route trace): {incident_attempts_payload}",
        )

        summary = {
            "project_id": project_id,
            "batch_id": batch_id,
            "worker_stats": worker_stats,
            "approved_draft_id": approve_draft_id,
            "rejected_draft_id": reject_draft_id,
            "digest_id": digest_result.get("digest_id"),
            "incident_escalation_digest_id": incident_digest_result.get("digest_id"),
            "metric_date": metric_date,
            "delivery_attempts_sent": int(delivery_run.get("attempts_sent", 0))
            + int(incident_delivery_run.get("attempts_sent", 0)),
        }
        print(json.dumps(summary, indent=2))
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        webhook_server.shutdown()
        webhook_server.server_close()
        webhook_thread.join(timeout=3)


if __name__ == "__main__":
    main()
