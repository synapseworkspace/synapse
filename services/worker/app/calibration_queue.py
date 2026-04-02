from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
from typing import Any

try:
    from psycopg.types.json import Jsonb
except Exception:  # pragma: no cover
    class Jsonb:  # type: ignore[override]
        def __init__(self, obj: Any):
            self.obj = obj


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_API_URL = "http://127.0.0.1:8080"
DEFAULT_DATABASE_URL = "postgresql://synapse:synapse@localhost:55432/synapse"


def _extract_json_payload(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
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


def _operation_lock_key(project_id: str) -> int:
    digest = hashlib.sha256(f"gatekeeper_operation:{project_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False) & 0x7FFF_FFFF_FFFF_FFFF


class GatekeeperCalibrationOperationQueueEngine:
    def __init__(self, *, worker_id: str = "gatekeeper_calibration_queue_worker") -> None:
        self.worker_id = worker_id
        self.script_path = REPO_ROOT / "scripts" / "run_gatekeeper_calibration_scheduler.py"

    def process_queued_runs(
        self,
        conn,
        *,
        project_ids: list[str] | None = None,
        limit: int = 10,
        heartbeat_sec: float = 3.0,
    ) -> dict[str, Any]:
        if not self.script_path.exists():
            return {
                "status": "failed",
                "error": f"scheduler_script_not_found:{self.script_path}",
                "picked": 0,
                "completed": 0,
                "failed": 0,
                "canceled": 0,
                "requeued": 0,
                "results": [],
            }

        claimed = self._claim_queued_runs(conn, project_ids=project_ids, limit=limit)
        completed = 0
        failed = 0
        canceled = 0
        requeued = 0
        results: list[dict[str, Any]] = []

        for run in claimed:
            run_id = str(run["id"])
            project_id = str(run["project_id"])
            lock_acquired = self._try_acquire_project_lock(conn, project_id=project_id)
            if not lock_acquired:
                self._set_run_state(
                    conn,
                    run_id=run_id,
                    status="queued",
                    progress_phase="queued",
                    progress_percent=0.0,
                    error_message="project_lock_busy",
                    worker_id=None,
                )
                self._append_event(
                    conn,
                    run_id=run_id,
                    project_id=project_id,
                    event_type="requeued",
                    phase="queued",
                    message="Run re-queued because another calibration operation holds the project lock.",
                    progress_percent=0.0,
                    payload={"reason": "project_lock_busy"},
                )
                conn.commit()
                requeued += 1
                results.append({"run_id": run_id, "project_id": project_id, "status": "requeued", "reason": "project_lock_busy"})
                continue

            try:
                result = self._execute_run(conn, run=run, heartbeat_sec=heartbeat_sec)
            finally:
                self._release_project_lock(conn, project_id=project_id)

            status = str(result.get("status") or "failed")
            if status == "succeeded":
                completed += 1
            elif status == "canceled":
                canceled += 1
            elif status == "requeued":
                requeued += 1
            else:
                failed += 1
            results.append(result)

        return {
            "status": "ok",
            "picked": len(claimed),
            "completed": completed,
            "failed": failed,
            "canceled": canceled,
            "requeued": requeued,
            "results": results,
        }

    def _claim_queued_runs(
        self,
        conn,
        *,
        project_ids: list[str] | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        limit = max(1, int(limit))
        with conn.cursor() as cur:
            if project_ids:
                cur.execute(
                    """
                    WITH picked AS (
                      SELECT id
                      FROM gatekeeper_calibration_operation_runs
                      WHERE mode = 'async'
                        AND status = 'queued'
                        AND cancel_requested = FALSE
                        AND project_id = ANY(%s)
                        AND NOT EXISTS (
                          SELECT 1
                          FROM gatekeeper_calibration_queue_controls qc
                          WHERE qc.project_id = gatekeeper_calibration_operation_runs.project_id
                            AND qc.paused_until IS NOT NULL
                            AND qc.paused_until > NOW()
                        )
                      ORDER BY created_at ASC
                      FOR UPDATE SKIP LOCKED
                      LIMIT %s
                    )
                    UPDATE gatekeeper_calibration_operation_runs r
                    SET status = 'running',
                        worker_id = %s,
                        started_at = COALESCE(r.started_at, NOW()),
                        finished_at = NULL,
                        error_message = NULL,
                        progress_phase = 'running',
                        progress_percent = GREATEST(COALESCE(r.progress_percent, 0), 8),
                        heartbeat_at = NOW(),
                        updated_at = NOW()
                    FROM picked
                    WHERE r.id = picked.id
                    RETURNING r.id::text, r.project_id, r.operation_token, r.request_payload, r.dry_run, r.attempt_no, r.max_attempts
                    """,
                    (project_ids, limit, self.worker_id),
                )
            else:
                cur.execute(
                    """
                    WITH picked AS (
                      SELECT id
                      FROM gatekeeper_calibration_operation_runs
                      WHERE mode = 'async'
                        AND status = 'queued'
                        AND cancel_requested = FALSE
                        AND NOT EXISTS (
                          SELECT 1
                          FROM gatekeeper_calibration_queue_controls qc
                          WHERE qc.project_id = gatekeeper_calibration_operation_runs.project_id
                            AND qc.paused_until IS NOT NULL
                            AND qc.paused_until > NOW()
                        )
                      ORDER BY created_at ASC
                      FOR UPDATE SKIP LOCKED
                      LIMIT %s
                    )
                    UPDATE gatekeeper_calibration_operation_runs r
                    SET status = 'running',
                        worker_id = %s,
                        started_at = COALESCE(r.started_at, NOW()),
                        finished_at = NULL,
                        error_message = NULL,
                        progress_phase = 'running',
                        progress_percent = GREATEST(COALESCE(r.progress_percent, 0), 8),
                        heartbeat_at = NOW(),
                        updated_at = NOW()
                    FROM picked
                    WHERE r.id = picked.id
                    RETURNING r.id::text, r.project_id, r.operation_token, r.request_payload, r.dry_run, r.attempt_no, r.max_attempts
                    """,
                    (limit, self.worker_id),
                )
            rows = cur.fetchall()
        conn.commit()
        claimed: list[dict[str, Any]] = []
        for row in rows:
            request_payload = row[3] if isinstance(row[3], dict) else {}
            claimed.append(
                {
                    "id": row[0],
                    "project_id": row[1],
                    "operation_token": row[2],
                    "request_payload": request_payload,
                    "dry_run": bool(row[4]),
                    "attempt_no": int(row[5] or 1),
                    "max_attempts": int(row[6] or 1),
                }
            )
        return claimed

    def _execute_run(self, conn, *, run: dict[str, Any], heartbeat_sec: float) -> dict[str, Any]:
        run_id = str(run["id"])
        project_id = str(run["project_id"])
        request_payload = run.get("request_payload")
        req = request_payload if isinstance(request_payload, dict) else {}

        cmd, command_preview, timeout_sec, flags = self._build_scheduler_command(project_id=project_id, request_payload=req)
        self._append_event(
            conn,
            run_id=run_id,
            project_id=project_id,
            event_type="started",
            phase="running",
            message="Async worker started calibration scheduler command.",
            progress_percent=12.0,
            payload={"command_preview": command_preview},
        )
        self._set_run_state(
            conn,
            run_id=run_id,
            status="running",
            progress_phase="running",
            progress_percent=12.0,
            worker_id=self.worker_id,
        )
        conn.commit()

        started_at = datetime.now(UTC)
        proc = subprocess.Popen(
            cmd,
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        canceled = False
        timed_out = False
        next_heartbeat = time.monotonic() + max(0.5, float(heartbeat_sec))
        timeout = max(30, int(timeout_sec))
        start_tick = time.monotonic()

        while True:
            code = proc.poll()
            if code is not None:
                break
            now = time.monotonic()
            elapsed = now - start_tick
            if elapsed >= timeout:
                timed_out = True
                self._terminate_process(proc)
                break
            if self._is_cancel_requested(conn, run_id=run_id):
                canceled = True
                self._terminate_process(proc)
                break
            if now >= next_heartbeat:
                progress = min(88.0, 12.0 + (elapsed / timeout) * 70.0)
                self._set_run_state(
                    conn,
                    run_id=run_id,
                    status="running",
                    progress_phase="running",
                    progress_percent=progress,
                    worker_id=self.worker_id,
                )
                self._append_event(
                    conn,
                    run_id=run_id,
                    project_id=project_id,
                    event_type="heartbeat",
                    phase="running",
                    message=f"Worker heartbeat (elapsed={int(elapsed)}s).",
                    progress_percent=progress,
                    payload={"elapsed_sec": int(elapsed), "timeout_sec": timeout},
                )
                conn.commit()
                next_heartbeat = now + max(0.5, float(heartbeat_sec))
            time.sleep(0.35)

        try:
            stdout, stderr = proc.communicate(timeout=5)
        except Exception:
            stdout, stderr = "", ""
        rc = int(proc.returncode or 0)
        duration_ms = int((datetime.now(UTC) - started_at).total_seconds() * 1000)
        payload = _extract_json_payload(stdout or "")
        scheduler_status = str(payload.get("status") or "")
        allowed_nonzero = rc != 0 and scheduler_status in {"partial_failure", "alert"}

        operation_result = {
            "project_id": project_id,
            "dry_run": bool(flags["dry_run"]),
            "force_run": bool(flags["force_run"]),
            "skip_due_check": bool(flags["skip_due_check"]),
            "command_preview": command_preview,
            "process": {
                "returncode": rc,
                "duration_ms": duration_ms,
                "stderr_tail": (stderr or "").strip()[-2000:] or None,
            },
            "summary": payload if isinstance(payload, dict) else {},
            "generated_at": datetime.now(UTC).isoformat(),
        }

        if canceled:
            operation_result["status"] = "canceled"
            operation_result["detail"] = "cancel_requested"
            self._set_run_state(
                conn,
                run_id=run_id,
                status="canceled",
                progress_phase="canceled",
                progress_percent=100.0,
                result_payload=operation_result,
                error_message="cancel_requested",
                worker_id=self.worker_id,
                set_finished_at=True,
            )
            self._append_event(
                conn,
                run_id=run_id,
                project_id=project_id,
                event_type="canceled",
                phase="canceled",
                message="Operation canceled by user request.",
                progress_percent=100.0,
                payload={"duration_ms": duration_ms},
            )
            conn.commit()
            return {"run_id": run_id, "project_id": project_id, "status": "canceled", "duration_ms": duration_ms}

        if timed_out:
            operation_result["status"] = "failed"
            operation_result["detail"] = f"calibration_scheduler_timeout:{timeout}s"
            self._set_run_state(
                conn,
                run_id=run_id,
                status="failed",
                progress_phase="failed",
                progress_percent=100.0,
                result_payload=operation_result,
                error_message=str(operation_result["detail"]),
                worker_id=self.worker_id,
                set_finished_at=True,
            )
            self._append_event(
                conn,
                run_id=run_id,
                project_id=project_id,
                event_type="failed",
                phase="failed",
                message=f"Scheduler timed out after {timeout}s.",
                progress_percent=100.0,
                payload={"timeout_sec": timeout},
            )
            conn.commit()
            return {"run_id": run_id, "project_id": project_id, "status": "failed", "error": operation_result["detail"]}

        if rc != 0 and not allowed_nonzero:
            detail = {
                "code": "calibration_scheduler_failed",
                "returncode": rc,
                "stderr_tail": (stderr or "").strip()[-2000:] or None,
                "stdout_tail": (stdout or "")[-2000:] or None,
            }
            operation_result["status"] = "failed"
            operation_result["detail"] = detail
            self._set_run_state(
                conn,
                run_id=run_id,
                status="failed",
                progress_phase="failed",
                progress_percent=100.0,
                result_payload=operation_result,
                error_message=json.dumps(detail, ensure_ascii=False)[:4000],
                worker_id=self.worker_id,
                set_finished_at=True,
            )
            self._append_event(
                conn,
                run_id=run_id,
                project_id=project_id,
                event_type="failed",
                phase="failed",
                message="Scheduler command failed with non-retryable return code.",
                progress_percent=100.0,
                payload=detail,
            )
            conn.commit()
            return {"run_id": run_id, "project_id": project_id, "status": "failed", "returncode": rc}

        self._set_run_state(
            conn,
            run_id=run_id,
            status="succeeded",
            progress_phase="completed",
            progress_percent=100.0,
            result_payload=operation_result,
            error_message=None,
            worker_id=self.worker_id,
            set_finished_at=True,
        )
        self._append_event(
            conn,
            run_id=run_id,
            project_id=project_id,
            event_type="completed",
            phase="completed",
            message="Scheduler command finished successfully.",
            progress_percent=100.0,
            payload={"returncode": rc, "scheduler_status": scheduler_status or "ok"},
        )
        conn.commit()
        return {
            "run_id": run_id,
            "project_id": project_id,
            "status": "succeeded",
            "returncode": rc,
            "scheduler_status": scheduler_status or "ok",
            "duration_ms": duration_ms,
        }

    def _build_scheduler_command(self, *, project_id: str, request_payload: dict[str, Any]) -> tuple[list[str], str, int, dict[str, Any]]:
        api_url = str(request_payload.get("api_url") or os.getenv("SYNAPSE_API_URL") or DEFAULT_API_URL).strip()
        database_url = str(request_payload.get("database_url") or os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL).strip()
        dry_run = bool(request_payload.get("dry_run", False))
        force_run = bool(request_payload.get("force_run", True))
        skip_due_check = bool(request_payload.get("skip_due_check", False))
        fail_on_alert = bool(request_payload.get("fail_on_alert", False))
        timeout_sec = max(30, int(request_payload.get("timeout_sec") or 1200))

        cmd = [
            sys.executable,
            str(self.script_path),
            "--use-api-schedules",
            "--project-id",
            project_id,
            "--api-url",
            api_url,
            "--database-url",
            database_url,
        ]
        if dry_run:
            cmd.append("--dry-run")
        if force_run:
            cmd.append("--force-run")
        if skip_due_check:
            cmd.append("--skip-due-check")
        if fail_on_alert:
            cmd.append("--fail-on-alert")
        preview = " ".join(shlex.quote(item) for item in cmd)
        return (
            cmd,
            preview,
            timeout_sec,
            {
                "dry_run": dry_run,
                "force_run": force_run,
                "skip_due_check": skip_due_check,
                "fail_on_alert": fail_on_alert,
            },
        )

    def _set_run_state(
        self,
        conn,
        *,
        run_id: str,
        status: str,
        progress_phase: str,
        progress_percent: float,
        result_payload: dict[str, Any] | None = None,
        error_message: str | None = None,
        worker_id: str | None = None,
        set_finished_at: bool = False,
    ) -> None:
        updates = [
            "status = %s",
            "progress_phase = %s",
            "progress_percent = %s",
            "heartbeat_at = NOW()",
            "updated_at = NOW()",
        ]
        params: list[Any] = [
            status,
            progress_phase[:256],
            float(max(0.0, min(100.0, progress_percent))),
        ]
        if result_payload is not None:
            updates.append("result_payload = %s")
            params.append(Jsonb(result_payload))
        if error_message is not None:
            updates.append("error_message = %s")
            params.append(error_message[:4000])
        if worker_id is not None:
            updates.append("worker_id = %s")
            params.append(worker_id[:256])
        if set_finished_at:
            updates.append("finished_at = NOW()")
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE gatekeeper_calibration_operation_runs
                SET {", ".join(updates)}
                WHERE id = %s
                """,
                (*params, run_id),
            )

    def _append_event(
        self,
        conn,
        *,
        run_id: str,
        project_id: str,
        event_type: str,
        phase: str,
        message: str,
        progress_percent: float,
        payload: dict[str, Any] | None = None,
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO gatekeeper_calibration_operation_events (
                  operation_run_id,
                  project_id,
                  event_type,
                  phase,
                  message,
                  progress_percent,
                  payload
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    run_id,
                    project_id,
                    event_type[:128],
                    phase[:128],
                    message[:2000],
                    float(max(0.0, min(100.0, progress_percent))),
                    Jsonb(payload or {}),
                ),
            )

    def _is_cancel_requested(self, conn, *, run_id: str) -> bool:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT cancel_requested, status
                FROM gatekeeper_calibration_operation_runs
                WHERE id = %s
                LIMIT 1
                """,
                (run_id,),
            )
            row = cur.fetchone()
        if row is None:
            return True
        cancel_requested = bool(row[0])
        status = str(row[1] or "")
        return cancel_requested or status == "cancel_requested"

    def _try_acquire_project_lock(self, conn, *, project_id: str) -> bool:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s)", (_operation_lock_key(project_id),))
            row = cur.fetchone()
        return bool(row[0]) if row else False

    def _release_project_lock(self, conn, *, project_id: str) -> None:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(%s)", (_operation_lock_key(project_id),))
            cur.fetchone()
        conn.commit()

    @staticmethod
    def _terminate_process(proc: subprocess.Popen[str]) -> None:
        try:
            proc.terminate()
            proc.wait(timeout=5)
            return
        except Exception:
            pass
        try:
            proc.kill()
            proc.wait(timeout=3)
        except Exception:
            return
