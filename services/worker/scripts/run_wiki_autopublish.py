#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Synapse wiki auto-publish policy execution.")
    parser.add_argument("--api-url", default=os.getenv("SYNAPSE_API_URL", "http://localhost:8080"))
    parser.add_argument("--project-id", default=None)
    parser.add_argument("--project-ids", default=None, help="Comma-separated list of project ids.")
    parser.add_argument("--limit-per-project", type=int, default=50)
    parser.add_argument("--reviewed-by", default=os.getenv("SYNAPSE_AUTOPUBLISH_REVIEWED_BY", "synapse_autopublisher"))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _parse_project_ids(project_ids_raw: str | None) -> list[str]:
    if not project_ids_raw:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in project_ids_raw.split(","):
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _build_request_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
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


def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=_build_request_headers(),
        method="POST",
    )
    try:
        with urlopen(request, timeout=20.0) as response:
            body = response.read().decode("utf-8")
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


def main() -> int:
    args = parse_args()
    project_ids = _parse_project_ids(args.project_ids)
    if args.project_id and str(args.project_id).strip():
        first = str(args.project_id).strip()
        if first not in project_ids:
            project_ids.insert(0, first)
    payload = {
        "project_ids": project_ids or None,
        "project_id": str(args.project_id).strip() if args.project_id else None,
        "limit_per_project": max(1, int(args.limit_per_project)),
        "reviewed_by": str(args.reviewed_by).strip() or "synapse_autopublisher",
        "dry_run": bool(args.dry_run),
    }
    endpoint = f"{str(args.api_url).rstrip('/')}/v1/wiki/auto-publish/run"
    result = _post_json(endpoint, payload)
    print(json.dumps(result, ensure_ascii=False))
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    failures = int(summary.get("failed") or 0)
    return 1 if failures > 0 else 0


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.append(str(repo_root))
    raise SystemExit(main())
