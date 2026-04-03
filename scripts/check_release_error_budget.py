#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from typing import Any


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _read_history(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except Exception as exc:
            raise ValueError(f"Invalid JSON on line {lineno} in {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"Expected JSON object on line {lineno} in {path}.")
        rows.append(payload)
    return rows


def _extract_status(entry: dict[str, Any]) -> str:
    if isinstance(entry.get("status"), str):
        return str(entry["status"]).strip().lower() or "unknown"
    checks = entry.get("checks")
    if isinstance(checks, dict):
        states = [str(value).strip().lower() for value in checks.values() if isinstance(value, str)]
        if states and all(value == "ok" for value in states):
            return "ok"
        if states:
            return "failed"
    return "unknown"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate rolling release error budget from SLO check history (release-blocking gate)."
    )
    parser.add_argument(
        "--history-jsonl",
        required=True,
        help="Path to JSONL history with status/check snapshots.",
    )
    parser.add_argument(
        "--window-days",
        type=int,
        default=7,
        help="Rolling window in days.",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=4,
        help="Minimum samples required in window.",
    )
    parser.add_argument(
        "--max-failure-rate",
        type=float,
        default=0.15,
        help="Maximum allowed failed sample ratio in rolling window.",
    )
    parser.add_argument(
        "--max-consecutive-failures",
        type=int,
        default=2,
        help="Maximum allowed consecutive failed samples in rolling window.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    history_path = Path(args.history_jsonl).resolve()
    if not history_path.exists():
        raise SystemExit(f"history file not found: {history_path}")

    now = datetime.now(UTC)
    window_start = now - timedelta(days=max(1, int(args.window_days)))
    rows = _read_history(history_path)

    filtered: list[dict[str, Any]] = []
    for row in rows:
        ts = (
            _parse_timestamp(row.get("captured_at"))
            or _parse_timestamp(row.get("generated_at"))
            or _parse_timestamp(row.get("timestamp"))
            or _parse_timestamp(row.get("created_at"))
        )
        if ts is None or ts < window_start:
            continue
        status = _extract_status(row)
        filtered.append(
            {
                "timestamp": ts.isoformat(),
                "status": status,
            }
        )

    filtered.sort(key=lambda item: item["timestamp"])
    total = len(filtered)
    failed = sum(1 for item in filtered if item["status"] != "ok")
    failure_rate = (failed / total) if total > 0 else 0.0

    consecutive = 0
    max_consecutive = 0
    for item in filtered:
        if item["status"] == "ok":
            consecutive = 0
        else:
            consecutive += 1
            max_consecutive = max(max_consecutive, consecutive)

    violations: list[dict[str, Any]] = []
    if total < max(1, int(args.min_samples)):
        violations.append(
            {
                "code": "insufficient_samples",
                "detail": f"found {total} sample(s); require >= {max(1, int(args.min_samples))} in rolling window",
            }
        )
    if failure_rate > float(args.max_failure_rate):
        violations.append(
            {
                "code": "failure_rate_exceeded",
                "detail": f"failure rate {failure_rate:.4f} exceeds max {float(args.max_failure_rate):.4f}",
            }
        )
    if max_consecutive > int(args.max_consecutive_failures):
        violations.append(
            {
                "code": "consecutive_failures_exceeded",
                "detail": (
                    f"max consecutive failures {max_consecutive} exceeds limit "
                    f"{int(args.max_consecutive_failures)}"
                ),
            }
        )

    result = {
        "status": "failed" if violations else "ok",
        "window": {
            "history_file": str(history_path),
            "window_days": max(1, int(args.window_days)),
            "window_start": window_start.isoformat(),
            "window_end": now.isoformat(),
        },
        "budget": {
            "samples_total": total,
            "samples_failed": failed,
            "failure_rate": round(failure_rate, 6),
            "max_consecutive_failures": max_consecutive,
        },
        "thresholds": {
            "min_samples": max(1, int(args.min_samples)),
            "max_failure_rate": float(args.max_failure_rate),
            "max_consecutive_failures": int(args.max_consecutive_failures),
        },
        "violations": violations,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
