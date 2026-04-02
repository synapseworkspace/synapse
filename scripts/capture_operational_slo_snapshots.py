#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _get_json(url: str, *, timeout_seconds: float) -> dict[str, Any]:
    request = Request(url, method="GET")
    with urlopen(request, timeout=timeout_seconds) as response:
        body = response.read().decode("utf-8")
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object payload from {url}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture operational SLO snapshots from API endpoints (ingest + moderation throughput)."
    )
    parser.add_argument("--api-base-url", default="http://localhost:8080", help="Synapse API base URL.")
    parser.add_argument("--project-id", required=True, help="Project identifier for metrics queries.")
    parser.add_argument("--window-hours", type=int, default=24, help="Metrics window in hours.")
    parser.add_argument(
        "--output",
        default="eval/operational_slo_snapshot_latest.json",
        help="Output JSON path for captured snapshot bundle.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=10.0, help="HTTP timeout for each API request.")
    args = parser.parse_args()

    base_url = str(args.api_base_url).rstrip("/")
    query = urlencode({"project_id": args.project_id, "window_hours": max(1, int(args.window_hours))})

    ingest_url = f"{base_url}/v1/events/throughput?{query}"
    moderation_url = f"{base_url}/v1/wiki/moderation/throughput?{query}"

    ingest_payload = _get_json(ingest_url, timeout_seconds=max(1.0, float(args.timeout_seconds)))
    moderation_payload = _get_json(moderation_url, timeout_seconds=max(1.0, float(args.timeout_seconds)))

    snapshot = {
        "generated_at": datetime.now(UTC).isoformat(),
        "api_base_url": base_url,
        "project_id": args.project_id,
        "window_hours": max(1, int(args.window_hours)),
        "ingest": ingest_payload,
        "moderation": moderation_payload,
    }

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"status": "ok", "output": str(output_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
