#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _safe_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("snapshot payload must be a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate operational SLO guardrails from API snapshot payloads."
    )
    parser.add_argument(
        "--snapshot-json",
        required=True,
        help="Path to operational SLO snapshot JSON (contains ingest + moderation sections).",
    )
    parser.add_argument(
        "--max-ingest-p95-ms",
        type=float,
        default=1200.0,
        help="Maximum allowed ingest p95 latency in milliseconds.",
    )
    parser.add_argument(
        "--max-ingest-p99-ms",
        type=float,
        default=2500.0,
        help="Maximum allowed ingest p99 latency in milliseconds.",
    )
    parser.add_argument(
        "--min-ingest-events",
        type=int,
        default=1,
        help="Minimum events ingested in selected window.",
    )
    parser.add_argument(
        "--max-moderation-p90-minutes",
        type=float,
        default=720.0,
        help="Maximum allowed moderation decision p90 latency (minutes).",
    )
    parser.add_argument(
        "--max-moderation-open-backlog",
        type=int,
        default=30,
        help="Maximum allowed moderation open backlog size.",
    )
    parser.add_argument(
        "--max-moderation-blocked-conflicts",
        type=int,
        default=10,
        help="Maximum allowed blocked_conflict backlog size.",
    )
    args = parser.parse_args()

    payload = _read_json(Path(args.snapshot_json).resolve())
    ingest = payload.get("ingest") if isinstance(payload.get("ingest"), dict) else {}
    moderation = payload.get("moderation") if isinstance(payload.get("moderation"), dict) else {}

    ingest_metrics = ingest.get("metrics") if isinstance(ingest.get("metrics"), dict) else {}
    ingest_latency = ingest_metrics.get("latency_ms") if isinstance(ingest_metrics.get("latency_ms"), dict) else {}

    moderation_metrics = moderation.get("metrics") if isinstance(moderation.get("metrics"), dict) else {}
    moderation_latency = (
        moderation_metrics.get("latency_minutes")
        if isinstance(moderation_metrics.get("latency_minutes"), dict)
        else {}
    )
    moderation_backlog = moderation.get("backlog") if isinstance(moderation.get("backlog"), dict) else {}

    ingest_events = _safe_int(ingest_metrics.get("events_ingested"))
    ingest_p95_ms = _safe_float(ingest_latency.get("p95"))
    ingest_p99_ms = _safe_float(ingest_latency.get("p99"))

    moderation_p90_minutes = _safe_float(moderation_latency.get("p90"))
    moderation_open_backlog = _safe_int(moderation_backlog.get("open_total"))
    moderation_blocked_conflicts = _safe_int(moderation_backlog.get("blocked_conflict"))

    violations: list[dict[str, Any]] = []

    if ingest_events is None:
        violations.append(
            {
                "code": "missing_ingest_events",
                "detail": "ingest.metrics.events_ingested is missing.",
            }
        )
    elif ingest_events < max(0, int(args.min_ingest_events)):
        violations.append(
            {
                "code": "ingest_events_below_threshold",
                "detail": (
                    f"events_ingested {ingest_events} is below min "
                    f"{max(0, int(args.min_ingest_events))}."
                ),
            }
        )

    if ingest_p95_ms is None:
        violations.append(
            {
                "code": "missing_ingest_p95",
                "detail": "ingest.metrics.latency_ms.p95 is missing.",
            }
        )
    elif ingest_p95_ms > float(args.max_ingest_p95_ms):
        violations.append(
            {
                "code": "ingest_p95_exceeded",
                "detail": (
                    f"ingest p95 {ingest_p95_ms:.2f}ms exceeds max "
                    f"{float(args.max_ingest_p95_ms):.2f}ms."
                ),
            }
        )

    if ingest_p99_ms is None:
        violations.append(
            {
                "code": "missing_ingest_p99",
                "detail": "ingest.metrics.latency_ms.p99 is missing.",
            }
        )
    elif ingest_p99_ms > float(args.max_ingest_p99_ms):
        violations.append(
            {
                "code": "ingest_p99_exceeded",
                "detail": (
                    f"ingest p99 {ingest_p99_ms:.2f}ms exceeds max "
                    f"{float(args.max_ingest_p99_ms):.2f}ms."
                ),
            }
        )

    if moderation_p90_minutes is None:
        violations.append(
            {
                "code": "missing_moderation_p90",
                "detail": "moderation.metrics.latency_minutes.p90 is missing.",
            }
        )
    elif moderation_p90_minutes > float(args.max_moderation_p90_minutes):
        violations.append(
            {
                "code": "moderation_p90_exceeded",
                "detail": (
                    f"moderation p90 {moderation_p90_minutes:.2f}m exceeds max "
                    f"{float(args.max_moderation_p90_minutes):.2f}m."
                ),
            }
        )

    if moderation_open_backlog is None:
        violations.append(
            {
                "code": "missing_moderation_open_backlog",
                "detail": "moderation.backlog.open_total is missing.",
            }
        )
    elif moderation_open_backlog > int(args.max_moderation_open_backlog):
        violations.append(
            {
                "code": "moderation_open_backlog_exceeded",
                "detail": (
                    f"moderation open backlog {moderation_open_backlog} exceeds max "
                    f"{int(args.max_moderation_open_backlog)}."
                ),
            }
        )

    if moderation_blocked_conflicts is None:
        violations.append(
            {
                "code": "missing_moderation_blocked_conflicts",
                "detail": "moderation.backlog.blocked_conflict is missing.",
            }
        )
    elif moderation_blocked_conflicts > int(args.max_moderation_blocked_conflicts):
        violations.append(
            {
                "code": "moderation_blocked_conflicts_exceeded",
                "detail": (
                    f"moderation blocked conflicts {moderation_blocked_conflicts} exceeds max "
                    f"{int(args.max_moderation_blocked_conflicts)}."
                ),
            }
        )

    result = {
        "status": "failed" if violations else "ok",
        "snapshot": {
            "path": str(Path(args.snapshot_json).resolve()),
            "project_id": payload.get("project_id"),
            "generated_at": payload.get("generated_at"),
            "window_hours": payload.get("window_hours"),
            "ingest": {
                "events_ingested": ingest_events,
                "p95_ms": ingest_p95_ms,
                "p99_ms": ingest_p99_ms,
            },
            "moderation": {
                "p90_minutes": moderation_p90_minutes,
                "open_backlog": moderation_open_backlog,
                "blocked_conflicts": moderation_blocked_conflicts,
            },
        },
        "thresholds": {
            "max_ingest_p95_ms": float(args.max_ingest_p95_ms),
            "max_ingest_p99_ms": float(args.max_ingest_p99_ms),
            "min_ingest_events": max(0, int(args.min_ingest_events)),
            "max_moderation_p90_minutes": float(args.max_moderation_p90_minutes),
            "max_moderation_open_backlog": int(args.max_moderation_open_backlog),
            "max_moderation_blocked_conflicts": int(args.max_moderation_blocked_conflicts),
        },
        "violations": violations,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
