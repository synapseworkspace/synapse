#!/usr/bin/env python3
from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        path = parsed.path
        if path == "/v1/adoption/sync/cursor-health":
            if not query.get("project_id"):
                self._send({"detail": "missing_project_id"}, status=422)
                return
            self._send(
                {
                    "status": "ok",
                    "summary": {"healthy": 1, "warning": 0, "critical": 0},
                    "sources": [{"source_ref": "postgres_sql:ops_kb_items:polling", "health": "healthy", "cursor_age_hours": 1}],
                }
            )
            return
        if path == "/v1/wiki/drafts":
            self._send(
                {
                    "drafts": [
                        {
                            "id": "draft_1",
                            "status": "pending_review",
                            "confidence": 0.91,
                            "claim": {"category": "policy"},
                            "page": {"slug": "operations/access-policy"},
                        }
                    ],
                    "total": 1,
                }
            )
            return
        if path == "/v1/adoption/pipeline/visibility":
            self._send(
                {
                    "stages": {"accepted": 12, "events": 10, "claims": 8, "drafts": 5, "pages": 3},
                    "conversion": {"accepted_to_claims": 0.66, "claims_to_drafts": 0.62, "drafts_to_pages": 0.6},
                    "bottlenecks": [{"stage": "claims", "severity": "medium", "hint": "Tune source-quality filters"}],
                }
            )
            return
        if path == "/v1/adoption/rejections/diagnostics":
            self._send(
                {
                    "summary": {"rejected_total": 17, "distinct_reasons": 3, "sources_blocked": 2},
                    "top_reasons": [{"reason_code": "event_like_low_signal", "count": 9, "share": 0.53}],
                }
            )
            return
        self._send({"detail": "not_found"}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            payload = {}
        if path == "/v1/adoption/project-reset":
            self._send({"status": "ok", "summary": {"tables_touched": 5, "matched_rows": 12, "deleted_rows": 0}, "echo": payload})
            return
        if path == "/v1/wiki/drafts/bulk-review":
            self._send({"status": "ok", "summary": {"scanned": 10, "matched": 4, "applied": 0, "failed": 0}, "echo": payload})
            return
        if path == "/v1/adoption/sync-presets/execute":
            self._send(
                {
                    "status": "ok",
                    "summary": {"sources_queued": 2, "pipeline_runs": 1, "drafts_matched": 3, "drafts_applied": 0},
                    "diagnostics": {"items": [{"severity": "info", "message": "dry-run"}]},
                    "echo": payload,
                }
            )
            return
        self._send({"detail": "not_found"}, status=404)

    def log_message(self, fmt: str, *args: object) -> None:  # noqa: A003
        return

    def _send(self, payload: dict[str, object], *, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _run_json_cmd(cmd: list[str]) -> dict[str, object]:
    out = subprocess.check_output(cmd, text=True)
    parsed = json.loads(out)
    if not isinstance(parsed, dict):
        raise AssertionError(f"Expected JSON object, got: {type(parsed)!r}")
    return parsed


def main() -> int:
    port = _free_port()
    server = HTTPServer(("127.0.0.1", port), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    api_url = f"http://127.0.0.1:{port}"
    base_cmd = [sys.executable, "-m", "synapse_sdk.cli", "adoption"]
    try:
        cursor = _run_json_cmd(base_cmd + ["cursor-health", "--api-url", api_url, "--project-id", "omega_demo", "--json"])
        assert cursor.get("status") == "ok", cursor
        reset = _run_json_cmd(
            base_cmd
            + [
                "project-reset",
                "--api-url",
                api_url,
                "--project-id",
                "omega_demo",
                "--requested-by",
                "ops_admin",
                "--json",
            ]
        )
        assert reset.get("status") == "ok", reset
        drafts = _run_json_cmd(
            base_cmd + ["list-drafts", "--api-url", api_url, "--project-id", "omega_demo", "--status", "pending_review", "--json"]
        )
        assert int(drafts.get("total", 0) or 0) >= 1, drafts
        bulk = _run_json_cmd(
            base_cmd
            + [
                "bulk-review-drafts",
                "--api-url",
                api_url,
                "--project-id",
                "omega_demo",
                "--reviewed-by",
                "ops_reviewer",
                "--action",
                "approve",
                "--json",
            ]
        )
        assert bulk.get("status") == "ok", bulk
        sync = _run_json_cmd(
            base_cmd
            + [
                "sync-preset",
                "--api-url",
                api_url,
                "--project-id",
                "omega_demo",
                "--updated-by",
                "ops_admin",
                "--with-pipeline",
                "--json",
            ]
        )
        assert sync.get("status") == "ok", sync
        pipeline = sync.get("pipeline")
        assert isinstance(pipeline, dict) and isinstance(pipeline.get("stages"), dict), sync
        funnel = _run_json_cmd(base_cmd + ["pipeline", "--api-url", api_url, "--project-id", "omega_demo", "--json"])
        assert isinstance(funnel.get("stages"), dict), funnel
        rejections = _run_json_cmd(
            base_cmd + ["rejections", "--api-url", api_url, "--project-id", "omega_demo", "--days", "14", "--sample-limit", "5", "--json"]
        )
        assert isinstance(rejections.get("top_reasons"), list), rejections
    finally:
        server.shutdown()
        server.server_close()
    Path("/tmp/synapse-cli-adoption-ops-smoke.json").write_text(
        json.dumps({"status": "ok", "api_url": api_url}, indent=2),
        encoding="utf-8",
    )
    print("synapse-cli adoption ops smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
