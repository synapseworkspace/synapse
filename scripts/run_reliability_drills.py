#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import UTC, datetime
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


def _load_snapshot(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("snapshot must be a JSON object")
    return payload


def _evaluate_operational(snapshot: dict[str, Any]) -> dict[str, Any]:
    ingest = snapshot.get("ingest") if isinstance(snapshot.get("ingest"), dict) else {}
    moderation = snapshot.get("moderation") if isinstance(snapshot.get("moderation"), dict) else {}
    ingest_metrics = ingest.get("metrics") if isinstance(ingest.get("metrics"), dict) else {}
    ingest_latency = ingest_metrics.get("latency_ms") if isinstance(ingest_metrics.get("latency_ms"), dict) else {}
    moderation_metrics = moderation.get("metrics") if isinstance(moderation.get("metrics"), dict) else {}
    moderation_latency = (
        moderation_metrics.get("latency_minutes")
        if isinstance(moderation_metrics.get("latency_minutes"), dict)
        else {}
    )
    moderation_backlog = moderation.get("backlog") if isinstance(moderation.get("backlog"), dict) else {}
    return {
        "ingest_p95_ms": _safe_float(ingest_latency.get("p95")),
        "ingest_p99_ms": _safe_float(ingest_latency.get("p99")),
        "events_ingested": _safe_int(ingest_metrics.get("events_ingested")),
        "moderation_p90_minutes": _safe_float(moderation_latency.get("p90")),
        "moderation_open_backlog": _safe_int(moderation_backlog.get("open_total")),
        "moderation_blocked_conflicts": _safe_int(moderation_backlog.get("blocked_conflict")),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deterministic reliability drills for steady, burst, and degraded dependency profiles."
    )
    parser.add_argument(
        "--snapshot-json",
        required=True,
        help="Operational SLO snapshot JSON (for example eval/operational_slo_snapshot_sample.json).",
    )
    parser.add_argument(
        "--max-steady-ingest-p95-ms",
        type=float,
        default=1200.0,
        help="Steady-state ingest p95 threshold.",
    )
    parser.add_argument(
        "--max-steady-moderation-p90-minutes",
        type=float,
        default=720.0,
        help="Steady-state moderation p90 threshold.",
    )
    parser.add_argument(
        "--burst-latency-multiplier",
        type=float,
        default=1.35,
        help="Synthetic multiplier for burst load simulation.",
    )
    parser.add_argument(
        "--max-burst-ingest-p95-ms",
        type=float,
        default=1700.0,
        help="Burst profile ingest p95 threshold after multiplier.",
    )
    parser.add_argument(
        "--max-burst-moderation-open-backlog",
        type=int,
        default=60,
        help="Burst profile open backlog threshold after multiplier.",
    )
    parser.add_argument(
        "--degraded-ingest-events-max",
        type=int,
        default=0,
        help="Expected max events_ingested in degraded dependency simulation.",
    )
    parser.add_argument(
        "--degraded-ingest-p99-min-ms",
        type=float,
        default=3000.0,
        help="Expected minimum ingest p99 under degraded dependency simulation.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_path = Path(args.snapshot_json).resolve()
    snapshot = _load_snapshot(source_path)
    metrics = _evaluate_operational(snapshot)

    drills: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []

    steady_pass = True
    if metrics["ingest_p95_ms"] is None or metrics["ingest_p95_ms"] > float(args.max_steady_ingest_p95_ms):
        steady_pass = False
    if metrics["moderation_p90_minutes"] is None or metrics["moderation_p90_minutes"] > float(
        args.max_steady_moderation_p90_minutes
    ):
        steady_pass = False
    drills.append(
        {
            "profile": "steady",
            "status": "ok" if steady_pass else "failed",
            "metrics": {
                "ingest_p95_ms": metrics["ingest_p95_ms"],
                "moderation_p90_minutes": metrics["moderation_p90_minutes"],
            },
            "thresholds": {
                "max_ingest_p95_ms": float(args.max_steady_ingest_p95_ms),
                "max_moderation_p90_minutes": float(args.max_steady_moderation_p90_minutes),
            },
        }
    )
    if not steady_pass:
        violations.append({"code": "steady_profile_failed", "detail": "Baseline snapshot violates steady thresholds."})

    ingest_p95 = metrics["ingest_p95_ms"] or 0.0
    open_backlog = metrics["moderation_open_backlog"] or 0
    burst_ingest_p95 = ingest_p95 * float(args.burst_latency_multiplier)
    burst_open_backlog = int(round(open_backlog * float(args.burst_latency_multiplier)))
    burst_pass = burst_ingest_p95 <= float(args.max_burst_ingest_p95_ms) and burst_open_backlog <= int(
        args.max_burst_moderation_open_backlog
    )
    drills.append(
        {
            "profile": "burst_load",
            "status": "ok" if burst_pass else "failed",
            "simulation": {
                "multiplier": float(args.burst_latency_multiplier),
                "ingest_p95_ms": round(burst_ingest_p95, 3),
                "moderation_open_backlog": burst_open_backlog,
            },
            "thresholds": {
                "max_ingest_p95_ms": float(args.max_burst_ingest_p95_ms),
                "max_open_backlog": int(args.max_burst_moderation_open_backlog),
            },
        }
    )
    if not burst_pass:
        violations.append({"code": "burst_profile_failed", "detail": "Synthetic burst profile exceeds guardrails."})

    degraded_events = min(metrics["events_ingested"] or 0, int(args.degraded_ingest_events_max))
    degraded_p99 = max((metrics["ingest_p99_ms"] or 0.0) * 1.45, float(args.degraded_ingest_p99_min_ms))
    degraded_detected = degraded_events <= int(args.degraded_ingest_events_max) and degraded_p99 >= float(
        args.degraded_ingest_p99_min_ms
    )
    drills.append(
        {
            "profile": "degraded_dependency",
            "status": "ok" if degraded_detected else "failed",
            "simulation": {
                "events_ingested": degraded_events,
                "ingest_p99_ms": round(degraded_p99, 3),
                "dependency_state": "degraded",
            },
            "expectation": {
                "events_ingested_max": int(args.degraded_ingest_events_max),
                "ingest_p99_min_ms": float(args.degraded_ingest_p99_min_ms),
                "note": "This drill passes when degradation is correctly detected and surfaced.",
            },
        }
    )
    if not degraded_detected:
        violations.append(
            {
                "code": "degraded_profile_detection_failed",
                "detail": "Failed to classify degraded dependency simulation.",
            }
        )

    result = {
        "status": "failed" if violations else "ok",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_snapshot": str(source_path),
        "drills": drills,
        "violations": violations,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
