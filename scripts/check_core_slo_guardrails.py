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


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("benchmark payload must be a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate core runtime SLO guardrails from benchmark snapshots."
    )
    parser.add_argument(
        "--benchmark-json",
        required=True,
        help="Path to benchmark JSON payload (for example eval/mcp_benchmark_latest_sample.json).",
    )
    parser.add_argument(
        "--max-average-p95-ms",
        type=float,
        default=250.0,
        help="Maximum allowed average retrieval p95 latency across benchmark cases.",
    )
    parser.add_argument(
        "--max-case-p95-ms",
        type=float,
        default=450.0,
        help="Maximum allowed p95 latency for an individual benchmark case.",
    )
    parser.add_argument(
        "--min-top1-accuracy",
        type=float,
        default=0.90,
        help="Minimum allowed average top-1 retrieval accuracy.",
    )
    parser.add_argument(
        "--min-cases",
        type=int,
        default=2,
        help="Minimum number of benchmark cases required in payload.",
    )
    args = parser.parse_args()

    payload = _read_json(Path(args.benchmark_json).resolve())
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    cases = payload.get("cases") if isinstance(payload.get("cases"), list) else []

    average_p95 = _safe_float(summary.get("average_case_p95_ms")) if isinstance(summary, dict) else None
    average_top1 = _safe_float(summary.get("average_quality_top1_accuracy")) if isinstance(summary, dict) else None

    violations: list[dict[str, Any]] = []

    if len(cases) < max(1, int(args.min_cases)):
        violations.append(
            {
                "code": "insufficient_case_coverage",
                "detail": f"Benchmark has {len(cases)} case(s); need at least {max(1, int(args.min_cases))}.",
            }
        )

    if average_p95 is None:
        violations.append(
            {
                "code": "missing_average_p95",
                "detail": "summary.average_case_p95_ms is missing.",
            }
        )
    elif average_p95 > float(args.max_average_p95_ms):
        violations.append(
            {
                "code": "average_p95_exceeded",
                "detail": (
                    f"average p95 {average_p95:.2f}ms exceeds max {float(args.max_average_p95_ms):.2f}ms."
                ),
            }
        )

    if average_top1 is None:
        violations.append(
            {
                "code": "missing_average_top1_accuracy",
                "detail": "summary.average_quality_top1_accuracy is missing.",
            }
        )
    elif average_top1 < float(args.min_top1_accuracy):
        violations.append(
            {
                "code": "average_top1_below_threshold",
                "detail": (
                    f"average top1 accuracy {average_top1:.3f} below min {float(args.min_top1_accuracy):.3f}."
                ),
            }
        )

    per_case_p95: list[dict[str, Any]] = []
    for item in cases:
        if not isinstance(item, dict):
            continue
        case_id = str(item.get("id") or "unknown_case")
        latency = item.get("latency_ms") if isinstance(item.get("latency_ms"), dict) else {}
        p95 = _safe_float(latency.get("p95")) if isinstance(latency, dict) else None
        per_case_p95.append({"id": case_id, "p95_ms": p95})
        if p95 is not None and p95 > float(args.max_case_p95_ms):
            violations.append(
                {
                    "code": "case_p95_exceeded",
                    "case_id": case_id,
                    "detail": f"case p95 {p95:.2f}ms exceeds max {float(args.max_case_p95_ms):.2f}ms.",
                }
            )

    result = {
        "status": "failed" if violations else "ok",
        "benchmark": {
            "path": str(Path(args.benchmark_json).resolve()),
            "project_id": payload.get("project_id"),
            "timestamp": payload.get("timestamp"),
            "cases": len(cases),
            "average_case_p95_ms": average_p95,
            "average_top1_accuracy": average_top1,
            "per_case_p95_ms": per_case_p95,
        },
        "thresholds": {
            "max_average_p95_ms": float(args.max_average_p95_ms),
            "max_case_p95_ms": float(args.max_case_p95_ms),
            "min_top1_accuracy": float(args.min_top1_accuracy),
            "min_cases": max(1, int(args.min_cases)),
        },
        "violations": violations,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
