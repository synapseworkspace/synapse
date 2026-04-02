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
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

ROOT = Path(__file__).resolve().parent.parent
API_DIR = ROOT / "services" / "api"
WORKER_SRC = ROOT / "services" / "worker"
MCP_SRC = ROOT / "services" / "mcp"


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
    request = urllib_request.Request(f"{base_url}{path}", data=body, headers=headers, method=method)
    try:
        with urllib_request.urlopen(request, timeout=timeout_s) as response:
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


def _wait_for_port(host: str, port: int, *, timeout_s: float) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.8)
            try:
                sock.connect((host, int(port)))
                return
            except OSError:
                pass
        time.sleep(0.25)
    raise RuntimeError(f"TCP port {host}:{port} did not become reachable in time")


def _api_get(base_url: str, path: str, *, timeout_s: float) -> dict[str, Any]:
    response = _http_json(base_url, "GET", path, timeout_s=timeout_s)
    _assert(response["status"] == 200, f"GET {path} failed: {response['status']} {response['text']}")
    return response["json"]


def _api_put(base_url: str, path: str, payload: dict[str, Any], *, timeout_s: float) -> dict[str, Any]:
    response = _http_json(base_url, "PUT", path, payload, timeout_s=timeout_s)
    _assert(response["status"] == 200, f"PUT {path} failed: {response['status']} {response['text']}")
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
    return response


def _header_value(headers: dict[str, str], key: str) -> str | None:
    lookup = key.lower()
    for header_key, value in headers.items():
        if header_key.lower() == lookup:
            return value
    return None


def _run_worker_cycle(api_python: str, *, database_url: str) -> dict[str, int]:
    env = dict(os.environ)
    env["DATABASE_URL"] = database_url
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
    _assert(result.returncode == 0, f"wiki synthesis worker failed: {result.stderr or result.stdout}")
    payload = json.loads(result.stdout or "{}")
    return {
        "backfill_completed": int(payload.get("backfill_events_completed", 0)),
        "claims_generated": int(payload.get("backfill_claims_generated", 0)),
        "draft_processed": int(payload.get("draft_claims_processed", 0)),
    }


def _run_mcp_probe(
    api_python: str,
    *,
    database_url: str,
    project_id: str,
    entity_key: str,
    query: str,
) -> dict[str, Any]:
    env = dict(os.environ)
    env["DATABASE_URL"] = database_url
    env["PYTHONPATH"] = str(MCP_SRC)
    script = """
import json
from app.runtime import build_runtime_from_env

runtime = build_runtime_from_env()
search = runtime.search_knowledge(
    project_id={project_id!r},
    query={query!r},
    limit=5,
    entity_key={entity_key!r},
    category="access",
)
facts = runtime.get_entity_facts(
    project_id={project_id!r},
    entity_key={entity_key!r},
    limit=10,
    category="access",
    include_non_current=False,
)
changes = runtime.get_recent_changes(
    project_id={project_id!r},
    limit=10,
    since_hours=24 * 7,
)
print(json.dumps({{"search": search, "facts": facts, "changes": changes}}))
""".format(project_id=project_id, query=query, entity_key=entity_key)
    result = subprocess.run(
        [api_python, "-c", script],
        env=env,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    _assert(result.returncode == 0, f"mcp probe failed: {result.stderr or result.stdout}")
    parsed = json.loads((result.stdout or "").strip() or "{}")
    _assert(isinstance(parsed, dict), f"mcp probe returned invalid payload: {parsed}")
    return parsed


def _run_mcp_probe_container(
    *,
    container_name: str,
    project_id: str,
    entity_key: str,
    query: str,
) -> dict[str, Any]:
    script = """
import json
from app.runtime import build_runtime_from_env

runtime = build_runtime_from_env()
search = runtime.search_knowledge(
    project_id={project_id!r},
    query={query!r},
    limit=5,
    entity_key={entity_key!r},
    category="access",
)
facts = runtime.get_entity_facts(
    project_id={project_id!r},
    entity_key={entity_key!r},
    limit=10,
    category="access",
    include_non_current=False,
)
changes = runtime.get_recent_changes(
    project_id={project_id!r},
    limit=10,
    since_hours=24 * 7,
)
print(json.dumps({{"search": search, "facts": facts, "changes": changes}}))
""".format(project_id=project_id, query=query, entity_key=entity_key)
    result = subprocess.run(
        ["docker", "exec", container_name, "python", "-c", script],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    _assert(result.returncode == 0, f"container mcp probe failed: {result.stderr or result.stdout}")
    parsed = json.loads((result.stdout or "").strip() or "{}")
    _assert(isinstance(parsed, dict), f"container mcp probe returned invalid payload: {parsed}")
    return parsed


def _default_api_python() -> str:
    venv_python = API_DIR / ".venv" / "bin" / "python"
    return str(venv_python if venv_python.exists() else Path(sys.executable))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Core acceptance scenario: ingest -> draft -> approve -> MCP retrieval."
    )
    parser.add_argument("--api-url", default=os.getenv("INTEGRATION_API_URL", "").strip(), help="Existing API base URL.")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", "postgresql://synapse:synapse@localhost:55432/synapse"),
        help="Postgres DSN used by API/worker/MCP runtime.",
    )
    parser.add_argument(
        "--api-python",
        default=os.getenv("INTEGRATION_API_PYTHON", _default_api_python()),
        help="Python executable for API and worker subprocesses.",
    )
    parser.add_argument("--project-id", default=f"core_acceptance_{uuid.uuid4().hex[:8]}", help="Project id scope.")
    parser.add_argument("--request-timeout", type=float, default=8.0, help="HTTP request timeout in seconds.")
    parser.add_argument("--max-worker-cycles", type=int, default=5, help="Max synthesis worker cycles before failing.")
    parser.add_argument(
        "--worker-mode",
        choices=["local", "poll"],
        default=os.getenv("INTEGRATION_WORKER_MODE", "local"),
        help="`local`: run worker synthesis cycles locally; `poll`: wait for external worker to produce drafts.",
    )
    parser.add_argument(
        "--worker-poll-interval",
        type=float,
        default=float(os.getenv("INTEGRATION_WORKER_POLL_INTERVAL", "1.0")),
        help="Polling interval (seconds) when worker mode is `poll`.",
    )
    parser.add_argument(
        "--mcp-probe-mode",
        choices=["local", "container"],
        default=os.getenv("INTEGRATION_MCP_PROBE_MODE", "local"),
        help="`local`: run MCP runtime probe with local python; `container`: exec probe inside running MCP container.",
    )
    parser.add_argument(
        "--mcp-container-name",
        default=os.getenv("INTEGRATION_MCP_CONTAINER_NAME", "synapse-mcp"),
        help="Container name used for `--mcp-probe-mode container`.",
    )
    parser.add_argument(
        "--mcp-host",
        default=os.getenv("INTEGRATION_MCP_HOST", "127.0.0.1"),
        help="MCP host reachability check target for container probe mode.",
    )
    parser.add_argument(
        "--mcp-port",
        type=int,
        default=int(os.getenv("INTEGRATION_MCP_PORT", "8091")),
        help="MCP port reachability check target for container probe mode.",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    base_url = args.api_url.rstrip("/")
    api_process: subprocess.Popen[str] | None = None

    if not base_url:
        api_port = _pick_free_port()
        base_url = f"http://127.0.0.1:{api_port}"
        env = dict(os.environ)
        env["DATABASE_URL"] = args.database_url
        api_process = subprocess.Popen(
            [
                args.api_python,
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

    try:
        _wait_for_api(
            base_url,
            timeout_s=25.0,
            request_timeout_s=args.request_timeout,
            process=api_process,
        )

        project_id = args.project_id
        entity_key = "bc_omega"
        key_prefix = f"core-loop-{project_id}"
        batch_id = str(uuid.uuid4())

        gatekeeper_config = _api_put(
            base_url,
            "/v1/gatekeeper/config",
            {
                "project_id": project_id,
                "updated_by": "core_acceptance_runner",
                "min_sources_for_golden": 2,
                "conflict_free_days": 1,
                "min_score_for_golden": 0.55,
                "operational_short_text_len": 8,
                "operational_short_token_len": 2,
            },
            timeout_s=args.request_timeout,
        )
        _assert(gatekeeper_config.get("status") == "ok", f"gatekeeper config update failed: {gatekeeper_config}")

        backfill_payload = {
            "batch": {
                "batch_id": batch_id,
                "project_id": project_id,
                "source_system": "core_acceptance",
                "created_by": "core_acceptance_runner",
                "finalize": True,
                "records": [
                    {
                        "source_id": "obs-1",
                        "content": "BC Omega gate requires a physical access card after 10:00 for courier entry.",
                        "entity_key": entity_key,
                        "category": "access",
                        "observed_at": "2026-04-01T10:15:00Z",
                    },
                    {
                        "source_id": "obs-2",
                        "content": "Dispatch note: BC Omega security confirmed card-only gate policy after 10:00.",
                        "entity_key": entity_key,
                        "category": "access",
                        "observed_at": "2026-04-01T10:45:00Z",
                    },
                ],
            }
        }
        backfill = _api_post(
            base_url,
            "/v1/backfill/memory",
            backfill_payload,
            timeout_s=args.request_timeout,
            idempotency_key=f"{key_prefix}-backfill",
        )
        _assert((backfill.get("json") or {}).get("status") == "ready", f"backfill did not reach ready: {backfill}")

        backfill_replay = _api_post(
            base_url,
            "/v1/backfill/memory",
            backfill_payload,
            timeout_s=args.request_timeout,
            idempotency_key=f"{key_prefix}-backfill",
        )
        _assert(
            _header_value(backfill_replay.get("headers") or {}, "X-Idempotent-Replay") == "true",
            f"missing replay header for backfill: {backfill_replay}",
        )

        batch_state = _api_get(
            base_url,
            f"/v1/backfill/batches/{batch_id}?project_id={project_id}",
            timeout_s=args.request_timeout,
        ).get("batch") or {}
        _assert(batch_state.get("status") in {"ready", "processing", "completed"}, f"batch status invalid: {batch_state}")

        drafts: list[dict[str, Any]] = []
        worker_stats: list[dict[str, Any]] = []
        for _ in range(max(1, int(args.max_worker_cycles))):
            if args.worker_mode == "local":
                cycle_stats = _run_worker_cycle(args.api_python, database_url=args.database_url)
                worker_stats.append(cycle_stats)
            else:
                worker_stats.append({"mode": "poll"})

            drafts_payload = _api_get(
                base_url,
                f"/v1/wiki/drafts?project_id={project_id}&status=pending_review&limit=20",
                timeout_s=args.request_timeout,
            )
            raw_drafts = drafts_payload.get("drafts") or []
            if isinstance(raw_drafts, list):
                drafts = [item for item in raw_drafts if isinstance(item, dict)]
            if drafts:
                break
            time.sleep(max(0.05, float(args.worker_poll_interval)))

        _assert(drafts, f"no pending drafts after worker cycles: stats={worker_stats}")
        approve_candidate = next((item for item in drafts if item.get("decision") != "conflict"), drafts[0])
        draft_id = str(approve_candidate.get("id") or "")
        _assert(draft_id, f"draft id missing: {approve_candidate}")

        approve_payload = {
            "project_id": project_id,
            "reviewed_by": "core_acceptance_runner",
            "note": "core loop approval",
        }
        approve_response = _api_post(
            base_url,
            f"/v1/wiki/drafts/{draft_id}/approve",
            approve_payload,
            timeout_s=args.request_timeout,
            idempotency_key=f"{key_prefix}-approve",
        )
        approve_json = approve_response.get("json") or {}
        _assert(approve_json.get("status") == "approved", f"draft approval failed: {approve_response}")
        page_slug = str(approve_json.get("page_slug") or "")
        _assert(page_slug, f"approve response missing page slug: {approve_response}")

        approve_replay = _api_post(
            base_url,
            f"/v1/wiki/drafts/{draft_id}/approve",
            approve_payload,
            timeout_s=args.request_timeout,
            idempotency_key=f"{key_prefix}-approve",
        )
        _assert(
            _header_value(approve_replay.get("headers") or {}, "X-Idempotent-Replay") == "true",
            f"missing replay header for approval: {approve_replay}",
        )

        page = _api_get(
            base_url,
            f"/v1/wiki/pages/{page_slug}?project_id={project_id}",
            timeout_s=args.request_timeout,
        )
        page_sections = page.get("sections") or []
        _assert(isinstance(page_sections, list) and page_sections, f"published page sections missing: {page}")
        page_statements: list[str] = []
        top_level_statements = page.get("statements") or []
        if isinstance(top_level_statements, list):
            for item in top_level_statements:
                if isinstance(item, dict):
                    text = str(item.get("statement_text") or "").strip()
                    if text:
                        page_statements.append(text)
        if not page_statements:
            for section in page_sections:
                statements = (section or {}).get("statements") if isinstance(section, dict) else []
                if isinstance(statements, list):
                    for item in statements:
                        if isinstance(item, dict):
                            text = str(item.get("statement_text") or "").strip()
                            if text:
                                page_statements.append(text)
        _assert(page_statements, f"page statements missing after approval: {page}")
        _assert(
            any("card" in text.lower() for text in page_statements),
            f"expected card-related statement in page: {page_statements}",
        )

        if args.mcp_probe_mode == "container":
            _wait_for_port(args.mcp_host, args.mcp_port, timeout_s=20.0)
            mcp_probe = _run_mcp_probe_container(
                container_name=args.mcp_container_name,
                project_id=project_id,
                entity_key=entity_key,
                query="BC Omega gate card access after 10:00",
            )
        else:
            mcp_probe = _run_mcp_probe(
                args.api_python,
                database_url=args.database_url,
                project_id=project_id,
                entity_key=entity_key,
                query="BC Omega gate card access after 10:00",
            )
        search_payload = mcp_probe.get("search") if isinstance(mcp_probe, dict) else {}
        facts_payload = mcp_probe.get("facts") if isinstance(mcp_probe, dict) else {}
        changes_payload = mcp_probe.get("changes") if isinstance(mcp_probe, dict) else {}
        search_results = (search_payload or {}).get("results") if isinstance(search_payload, dict) else []
        facts = (facts_payload or {}).get("facts") if isinstance(facts_payload, dict) else []
        changes = (changes_payload or {}).get("changes") if isinstance(changes_payload, dict) else []
        _assert(isinstance(search_results, list) and search_results, f"mcp search returned no results: {mcp_probe}")
        _assert(isinstance(facts, list) and facts, f"mcp entity facts returned no results: {mcp_probe}")
        _assert(isinstance(changes, list) and changes, f"mcp recent changes returned no results: {mcp_probe}")
        _assert(
            any("card" in str(item.get("statement_text", "")).lower() for item in search_results if isinstance(item, dict)),
            f"mcp search missing card policy statement: {search_results}",
        )
        _assert(
            any("card" in str(item.get("statement_text", "")).lower() for item in facts if isinstance(item, dict)),
            f"mcp facts missing card policy statement: {facts}",
        )

        summary = {
            "status": "ok",
            "project_id": project_id,
            "batch_id": batch_id,
            "approved_draft_id": draft_id,
            "page_slug": page_slug,
            "worker_cycles": len(worker_stats),
            "worker_mode": args.worker_mode,
            "worker_stats": worker_stats,
            "mcp_probe_mode": args.mcp_probe_mode,
            "mcp_search_results": len(search_results),
            "mcp_entity_facts": len(facts),
            "mcp_recent_changes": len(changes),
        }
        print(json.dumps(summary, indent=2))
    finally:
        if api_process is not None and api_process.poll() is None:
            api_process.send_signal(signal.SIGINT)
            try:
                api_process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                api_process.kill()
                api_process.wait(timeout=5)


if __name__ == "__main__":
    main()
