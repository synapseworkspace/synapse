#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
from typing import Any


BENCHMARK_SCRIPT = Path(__file__).resolve().with_name("benchmark_mcp_retrieval.py")

CONTEXT_POLICY_PROFILES: dict[str, dict[str, Any]] = {
    "off": {
        "context_policy_mode": "off",
        "description": "Disable context-policy filtering and keep baseline ranking.",
    },
    "advisory": {
        "context_policy_mode": "advisory",
        "description": "No filtering, only explainability diagnostics in retrieval payloads.",
    },
    "enforced": {
        "context_policy_mode": "enforced",
        "min_retrieval_confidence": 0.45,
        "min_total_score": 0.20,
        "min_lexical_score": 0.08,
        "min_token_overlap_ratio": 0.15,
        "description": "Balanced production-safe filtering for context injection.",
    },
    "strict_enforced": {
        "context_policy_mode": "enforced",
        "min_retrieval_confidence": 0.60,
        "min_total_score": 0.30,
        "min_lexical_score": 0.10,
        "min_token_overlap_ratio": 0.20,
        "description": "High-precision filtering for strict/high-risk workflows.",
    },
}


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _build_config_hash(payload: dict[str, Any]) -> str:
    config = payload.get("config")
    if not isinstance(config, dict):
        return "unknown"
    encoded = json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(encoded.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def _load_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        data = json.loads(stripped)
        if not isinstance(data, dict):
            raise ValueError(f"Invalid history line at {path}:{lineno}")
        rows.append(data)
    return rows


def _append_history(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        fh.write("\n")


def _run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(BENCHMARK_SCRIPT),
        "--project-id",
        str(args.project_id),
        "--limit",
        str(args.limit),
        "--warmup",
        str(args.warmup),
        "--iterations",
        str(args.iterations),
        "--max-graph-hops",
        str(args.max_graph_hops),
        "--graph-boost-hop1",
        str(args.graph_boost_hop1),
        "--graph-boost-hop2",
        str(args.graph_boost_hop2),
        "--graph-boost-hop3",
        str(args.graph_boost_hop3),
        "--graph-boost-other",
        str(args.graph_boost_other),
        "--seed-pages",
        str(args.seed_pages),
        "--statements-per-page",
        str(args.statements_per_page),
        "--edge-fanout",
        str(args.edge_fanout),
        "--seed-random",
        str(args.seed_random),
    ]
    if args.database_url:
        cmd.extend(["--database-url", str(args.database_url)])
    if args.replace:
        cmd.append("--replace")
    if args.skip_seed:
        cmd.append("--skip-seed")

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        message = "MCP benchmark command failed."
        if proc.stderr.strip():
            message = f"{message}\n{proc.stderr.strip()}"
        raise RuntimeError(message)
    try:
        payload = json.loads(proc.stdout)
    except Exception as exc:
        raise RuntimeError("Benchmark output is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Benchmark output must be JSON object.")
    return payload


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(statistics.mean(values))


def _collect_case_maps(payload: dict[str, Any]) -> tuple[dict[str, float], dict[str, float]]:
    p95_by_case: dict[str, float] = {}
    quality_by_case: dict[str, float] = {}
    cases = payload.get("cases")
    if not isinstance(cases, list):
        return p95_by_case, quality_by_case
    for case in cases:
        if not isinstance(case, dict):
            continue
        case_id = str(case.get("id") or "").strip()
        if not case_id:
            continue
        latency = case.get("latency_ms")
        if isinstance(latency, dict):
            p95 = _safe_float(latency.get("p95"))
            if p95 is not None:
                p95_by_case[case_id] = p95
        quality = _safe_float(case.get("quality_top1_accuracy"))
        if quality is not None:
            quality_by_case[case_id] = quality
    return p95_by_case, quality_by_case


def _recommend_graph_profile(latest: dict[str, Any], *, measured_quality_regression: bool) -> dict[str, Any] | None:
    if not measured_quality_regression:
        return None
    config = latest.get("config")
    if not isinstance(config, dict):
        return None
    hop1 = _safe_float(config.get("graph_boost_hop1"))
    hop2 = _safe_float(config.get("graph_boost_hop2"))
    hop3 = _safe_float(config.get("graph_boost_hop3"))
    max_hops = int(config.get("max_graph_hops") or 3)
    if hop1 is None or hop2 is None or hop3 is None:
        return None
    return {
        "reason": "quality_regression_detected",
        "current": {
            "max_graph_hops": max_hops,
            "graph_boost_hop1": round(hop1, 4),
            "graph_boost_hop2": round(hop2, 4),
            "graph_boost_hop3": round(hop3, 4),
        },
        "suggested": {
            "max_graph_hops": min(3, max_hops + 1),
            "graph_boost_hop1": round(min(0.35, hop1 + 0.02), 4),
            "graph_boost_hop2": round(min(0.25, hop2 + 0.015), 4),
            "graph_boost_hop3": round(min(0.15, hop3 + 0.01), 4),
        },
    }


def _profile_thresholds(name: str) -> dict[str, Any]:
    profile = CONTEXT_POLICY_PROFILES.get(name) or CONTEXT_POLICY_PROFILES["enforced"]
    out = {
        "context_policy_mode": str(profile.get("context_policy_mode") or "advisory"),
    }
    for key in ("min_retrieval_confidence", "min_total_score", "min_lexical_score", "min_token_overlap_ratio"):
        if profile.get(key) is not None:
            out[key] = float(profile[key])
    return out


def _recommend_context_policy_profile(
    *,
    latest_avg_quality: float | None,
    latest_avg_p95: float,
    measured_quality_regression: bool,
    measured_latency_regression: bool,
    strict_profile_min_average_quality: float,
    strict_profile_max_average_p95_ms: float,
    enforced_relax_quality_floor: float,
) -> dict[str, Any]:
    if latest_avg_quality is None:
        selected = "enforced"
        reason = "quality_signal_missing_default_enforced"
        thresholds = _profile_thresholds(selected)
    elif measured_quality_regression or latest_avg_quality < float(enforced_relax_quality_floor):
        selected = "advisory"
        reason = "quality_regression_or_low_quality_advisory_fallback"
        thresholds = _profile_thresholds(selected)
    elif (
        not measured_latency_regression
        and latest_avg_quality >= float(strict_profile_min_average_quality)
        and latest_avg_p95 <= float(strict_profile_max_average_p95_ms)
    ):
        selected = "strict_enforced"
        reason = "high_quality_and_stable_latency_promote_strict"
        thresholds = _profile_thresholds(selected)
    else:
        selected = "enforced"
        reason = "balanced_enforced_profile"
        thresholds = _profile_thresholds(selected)
        if latest_avg_quality < min(0.99, float(strict_profile_min_average_quality)):
            thresholds = {
                "context_policy_mode": "enforced",
                "min_retrieval_confidence": 0.40,
                "min_total_score": 0.18,
                "min_lexical_score": 0.07,
                "min_token_overlap_ratio": 0.12,
            }
            reason = "balanced_enforced_with_relaxed_thresholds"

    description = str((CONTEXT_POLICY_PROFILES.get(selected) or {}).get("description") or "")
    return {
        "profile": selected,
        "reason": reason,
        "description": description,
        "thresholds": thresholds,
        "sdk_hints": {
            "python_default_context_policy_profile": selected,
            "typescript_defaultContextPolicyProfile": selected,
        },
        "signal_snapshot": {
            "latest_average_quality_top1_accuracy": round(latest_avg_quality, 4) if latest_avg_quality is not None else None,
            "latest_average_case_p95_ms": round(latest_avg_p95, 3),
            "measured_quality_regression": measured_quality_regression,
            "measured_latency_regression": measured_latency_regression,
        },
    }


def _annotate(payload: dict[str, Any], *, source: str) -> dict[str, Any]:
    stamped = dict(payload)
    meta = dict(stamped.get("_trend") or {})
    meta["captured_at"] = datetime.now(UTC).isoformat()
    meta["config_hash"] = _build_config_hash(stamped)
    meta["source"] = source
    stamped["_trend"] = meta
    return stamped


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run/inspect MCP retrieval benchmark, compare with recent history, and alert on "
            "latency/quality regressions."
        )
    )
    parser.add_argument("--project-id", default="mcp_bench", help="Project id scope for trend history.")
    parser.add_argument(
        "--history-file",
        default="eval/mcp_retrieval_benchmark_history.jsonl",
        help="JSONL file with benchmark snapshots.",
    )
    parser.add_argument("--latest-benchmark", default=None, help="Path to benchmark JSON payload.")
    parser.add_argument("--run-benchmark", action="store_true", help="Run benchmark script and use its output as latest snapshot.")
    parser.add_argument("--append-history", action="store_true", help="Append latest snapshot into history file.")
    parser.add_argument("--write-latest", default=None, help="Optional path to persist latest benchmark JSON.")

    parser.add_argument("--baseline-window", type=int, default=4, help="How many recent runs to use as baseline.")
    parser.add_argument("--min-baseline-runs", type=int, default=2, help="Minimum baseline runs required for delta checks.")

    parser.add_argument("--max-average-p95-ms", type=float, default=120.0, help="Alert if latest average p95 exceeds this cap.")
    parser.add_argument(
        "--max-average-p95-regression-ms",
        type=float,
        default=12.0,
        help="Alert if latest average p95 rises above baseline by this many milliseconds.",
    )
    parser.add_argument(
        "--max-average-p95-regression-ratio",
        type=float,
        default=0.35,
        help="Alert if latest average p95 rises above baseline by this relative factor.",
    )
    parser.add_argument(
        "--max-case-p95-regression-ms",
        type=float,
        default=18.0,
        help="Alert if any retrieval case p95 rises above case baseline by this many milliseconds.",
    )
    parser.add_argument(
        "--min-average-quality-top1",
        type=float,
        default=0.95,
        help="Alert if latest average top1 quality goes below this value.",
    )
    parser.add_argument(
        "--min-case-quality-top1",
        type=float,
        default=0.9,
        help="Alert if any quality-tracked case drops below this value.",
    )
    parser.add_argument(
        "--max-average-quality-drop",
        type=float,
        default=0.03,
        help="Alert if latest average quality drops from baseline by more than this amount.",
    )
    parser.add_argument(
        "--strict-context-min-average-quality",
        type=float,
        default=0.985,
        help="Minimum average top1 quality required to auto-promote to strict context profile.",
    )
    parser.add_argument(
        "--strict-context-max-average-p95-ms",
        type=float,
        default=85.0,
        help="Maximum average p95 latency allowed to auto-promote to strict context profile.",
    )
    parser.add_argument(
        "--enforced-relax-quality-floor",
        type=float,
        default=0.96,
        help="Below this quality floor, fallback to advisory context profile recommendation.",
    )

    parser.add_argument("--database-url", default=None, help="Forwarded to benchmark script when --run-benchmark is used.")
    parser.add_argument("--replace", action="store_true", help="Forwarded benchmark flag.")
    parser.add_argument("--skip-seed", action="store_true", help="Forwarded benchmark flag.")
    parser.add_argument("--seed-pages", type=int, default=1200, help="Forwarded benchmark flag.")
    parser.add_argument("--statements-per-page", type=int, default=3, help="Forwarded benchmark flag.")
    parser.add_argument("--edge-fanout", type=int, default=1, help="Forwarded benchmark flag.")
    parser.add_argument("--seed-random", type=int, default=42, help="Forwarded benchmark flag.")
    parser.add_argument("--limit", type=int, default=10, help="Forwarded benchmark flag.")
    parser.add_argument("--warmup", type=int, default=20, help="Forwarded benchmark flag.")
    parser.add_argument("--iterations", type=int, default=200, help="Forwarded benchmark flag.")
    parser.add_argument("--max-graph-hops", type=int, default=3, help="Forwarded benchmark flag.")
    parser.add_argument("--graph-boost-hop1", type=float, default=0.20, help="Forwarded benchmark flag.")
    parser.add_argument("--graph-boost-hop2", type=float, default=0.12, help="Forwarded benchmark flag.")
    parser.add_argument("--graph-boost-hop3", type=float, default=0.06, help="Forwarded benchmark flag.")
    parser.add_argument("--graph-boost-other", type=float, default=0.03, help="Forwarded benchmark flag.")
    return parser.parse_args()


def main() -> None:
    try:
        args = parse_args()
        history_path = Path(args.history_file).resolve()
        history = _load_history(history_path)

        latest: dict[str, Any] | None = None
        latest_source = "history"
        if args.run_benchmark:
            latest = _annotate(_run_benchmark(args), source="run_benchmark")
            latest_source = "run_benchmark"
        elif args.latest_benchmark:
            latest = _annotate(_load_json(Path(args.latest_benchmark).resolve()), source="latest_file")
            latest_source = "latest_file"

        if latest is None:
            candidates = [row for row in history if str(row.get("project_id") or "") == str(args.project_id)]
            if not candidates:
                raise SystemExit("No latest benchmark provided and no matching history entries found.")
            latest = dict(candidates[-1])
            latest_source = "history"

        latest_project_id = str(latest.get("project_id") or args.project_id)
        latest_hash = str((latest.get("_trend") or {}).get("config_hash") or _build_config_hash(latest))
        latest["_trend"] = dict(latest.get("_trend") or {})
        latest["_trend"]["config_hash"] = latest_hash

        if args.write_latest:
            out_path = Path(args.write_latest).resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(latest, ensure_ascii=False, indent=2), encoding="utf-8")

        if args.append_history and latest_source != "history":
            _append_history(history_path, latest)
            history.append(latest)

        filtered = []
        for row in history:
            if str(row.get("project_id") or "") != latest_project_id:
                continue
            row_hash = str((row.get("_trend") or {}).get("config_hash") or _build_config_hash(row))
            if row_hash != latest_hash:
                continue
            filtered.append(row)

        baseline_candidates = filtered
        if latest_source == "history" and baseline_candidates:
            baseline_candidates = baseline_candidates[:-1]
        baseline_window = max(1, int(args.baseline_window))
        baseline = baseline_candidates[-baseline_window:]

        latest_summary = latest.get("summary") if isinstance(latest.get("summary"), dict) else {}
        latest_avg_p95 = _safe_float(latest_summary.get("average_case_p95_ms")) or 0.0
        latest_avg_quality = _safe_float(latest_summary.get("average_quality_top1_accuracy"))
        latest_case_p95, latest_case_quality = _collect_case_maps(latest)

        baseline_avg_p95_vals: list[float] = []
        baseline_avg_quality_vals: list[float] = []
        baseline_case_p95_vals: dict[str, list[float]] = {}
        baseline_case_quality_vals: dict[str, list[float]] = {}
        for row in baseline:
            summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
            row_p95 = _safe_float(summary.get("average_case_p95_ms"))
            if row_p95 is not None:
                baseline_avg_p95_vals.append(row_p95)
            row_quality = _safe_float(summary.get("average_quality_top1_accuracy"))
            if row_quality is not None:
                baseline_avg_quality_vals.append(row_quality)
            case_p95, case_quality = _collect_case_maps(row)
            for case_id, value in case_p95.items():
                baseline_case_p95_vals.setdefault(case_id, []).append(value)
            for case_id, value in case_quality.items():
                baseline_case_quality_vals.setdefault(case_id, []).append(value)

        baseline_avg_p95 = _mean(baseline_avg_p95_vals) if baseline_avg_p95_vals else None
        baseline_avg_quality = _mean(baseline_avg_quality_vals) if baseline_avg_quality_vals else None

        alerts: list[str] = []
        if latest_avg_p95 > float(args.max_average_p95_ms):
            alerts.append(
                f"average_p95_above_cap: latest={latest_avg_p95:.3f}ms cap={float(args.max_average_p95_ms):.3f}ms"
            )

        if len(baseline) >= int(args.min_baseline_runs) and baseline_avg_p95 is not None:
            p95_delta = latest_avg_p95 - baseline_avg_p95
            p95_ratio = (p95_delta / baseline_avg_p95) if baseline_avg_p95 > 0 else 0.0
            if p95_delta > float(args.max_average_p95_regression_ms):
                alerts.append(
                    "average_p95_regression_ms: "
                    f"latest={latest_avg_p95:.3f} baseline={baseline_avg_p95:.3f} delta={p95_delta:.3f}"
                )
            if p95_ratio > float(args.max_average_p95_regression_ratio):
                alerts.append(
                    "average_p95_regression_ratio: "
                    f"latest={latest_avg_p95:.3f} baseline={baseline_avg_p95:.3f} ratio={p95_ratio:.4f}"
                )

            for case_id, latest_val in latest_case_p95.items():
                values = baseline_case_p95_vals.get(case_id) or []
                if not values:
                    continue
                case_base = _mean(values)
                case_delta = latest_val - case_base
                if case_delta > float(args.max_case_p95_regression_ms):
                    alerts.append(
                        "case_p95_regression_ms: "
                        f"case={case_id} latest={latest_val:.3f} baseline={case_base:.3f} delta={case_delta:.3f}"
                    )

        if latest_avg_quality is not None and latest_avg_quality < float(args.min_average_quality_top1):
            alerts.append(
                "average_quality_below_floor: "
                f"latest={latest_avg_quality:.4f} floor={float(args.min_average_quality_top1):.4f}"
            )

        for case_id, latest_quality in latest_case_quality.items():
            if latest_quality < float(args.min_case_quality_top1):
                alerts.append(
                    "case_quality_below_floor: "
                    f"case={case_id} latest={latest_quality:.4f} floor={float(args.min_case_quality_top1):.4f}"
                )

        if (
            len(baseline) >= int(args.min_baseline_runs)
            and baseline_avg_quality is not None
            and latest_avg_quality is not None
        ):
            quality_drop = baseline_avg_quality - latest_avg_quality
            if quality_drop > float(args.max_average_quality_drop):
                alerts.append(
                    "average_quality_drop: "
                    f"latest={latest_avg_quality:.4f} baseline={baseline_avg_quality:.4f} drop={quality_drop:.4f}"
                )

        measured_quality_regression = any(
            marker in alert
            for alert in alerts
            for marker in ("average_quality_below_floor", "case_quality_below_floor", "average_quality_drop")
        )
        measured_latency_regression = any("p95" in alert for alert in alerts)
        recommendation = _recommend_graph_profile(latest, measured_quality_regression=measured_quality_regression)
        context_policy_recommendation = _recommend_context_policy_profile(
            latest_avg_quality=latest_avg_quality,
            latest_avg_p95=latest_avg_p95,
            measured_quality_regression=measured_quality_regression,
            measured_latency_regression=measured_latency_regression,
            strict_profile_min_average_quality=float(args.strict_context_min_average_quality),
            strict_profile_max_average_p95_ms=float(args.strict_context_max_average_p95_ms),
            enforced_relax_quality_floor=float(args.enforced_relax_quality_floor),
        )

        status = "ok" if not alerts else "alert"
        payload = {
            "status": status,
            "generated_at": datetime.now(UTC).isoformat(),
            "project_id": latest_project_id,
            "history_file": str(history_path),
            "latest_source": latest_source,
            "latest_config_hash": latest_hash,
            "baseline": {
                "runs_used": len(baseline),
                "window": baseline_window,
                "min_required": int(args.min_baseline_runs),
                "average_case_p95_ms": round(baseline_avg_p95, 3) if baseline_avg_p95 is not None else None,
                "average_quality_top1_accuracy": round(baseline_avg_quality, 4) if baseline_avg_quality is not None else None,
            },
            "latest": {
                "average_case_p95_ms": round(latest_avg_p95, 3),
                "average_quality_top1_accuracy": round(latest_avg_quality, 4) if latest_avg_quality is not None else None,
                "config": latest.get("config"),
            },
            "thresholds": {
                "max_average_p95_ms": float(args.max_average_p95_ms),
                "max_average_p95_regression_ms": float(args.max_average_p95_regression_ms),
                "max_average_p95_regression_ratio": float(args.max_average_p95_regression_ratio),
                "max_case_p95_regression_ms": float(args.max_case_p95_regression_ms),
                "min_average_quality_top1": float(args.min_average_quality_top1),
                "min_case_quality_top1": float(args.min_case_quality_top1),
                "max_average_quality_drop": float(args.max_average_quality_drop),
            },
            "signals": {
                "measured_latency_regression": measured_latency_regression,
                "measured_quality_regression": measured_quality_regression,
            },
            "recommended_graph_profile": recommendation,
            "recommended_context_policy_profile": context_policy_recommendation,
            "alerts": alerts,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if status != "ok":
            sys.exit(1)
    except SystemExit:
        raise
    except Exception as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
