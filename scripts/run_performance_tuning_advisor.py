#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
MCP_TREND_SCRIPT = ROOT / "scripts" / "check_mcp_retrieval_trend.py"


PROFILE_PRESETS: dict[str, dict[str, int]] = {
    "conserve": {
        "synthesis_interval_sec": 20,
        "synthesis_limit": 80,
        "synthesis_extract_limit": 120,
        "queue_depth_warn": 60,
        "worker_lag_sla_minutes": 30,
    },
    "balanced": {
        "synthesis_interval_sec": 12,
        "synthesis_limit": 140,
        "synthesis_extract_limit": 240,
        "queue_depth_warn": 120,
        "worker_lag_sla_minutes": 20,
    },
    "burst": {
        "synthesis_interval_sec": 6,
        "synthesis_limit": 260,
        "synthesis_extract_limit": 420,
        "queue_depth_warn": 250,
        "worker_lag_sla_minutes": 10,
    },
}


@dataclass(slots=True)
class QueueSnapshot:
    queued: int
    processing: int
    processed_total: int
    failed_total: int
    queued_age_p50_min: float
    queued_age_p95_min: float
    arrivals_window: int
    processed_window: int
    failed_window: int
    drafts_pending_review: int
    drafts_blocked_conflict: int
    conflicts_open: int

    @property
    def backlog(self) -> int:
        return self.queued + self.processing


@dataclass(slots=True)
class QueueControls:
    worker_lag_sla_minutes: int
    queue_depth_warn: int
    exists: bool


@dataclass(slots=True)
class WorkerSizing:
    recommended_workers: int
    delta_workers: int
    required_rate_per_min: float
    effective_capacity_per_worker_per_min: float
    observed_capacity_per_worker_per_min: float | None
    theoretical_capacity_per_worker_per_min: float


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Recommend production tuning profile for Synapse core runtime "
            "(worker sizing, queue limits, MCP graph knobs)."
        )
    )
    parser.add_argument("--project-id", required=True, help="Project id to evaluate.")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", "postgresql://synapse:synapse@localhost:55432/synapse"),
        help="PostgreSQL connection string.",
    )
    parser.add_argument("--window-hours", type=int, default=6, help="Observation window for rate calculations.")
    parser.add_argument(
        "--current-worker-replicas",
        type=int,
        default=max(1, _safe_int(os.getenv("SYNAPSE_WORKER_REPLICAS", "1"), default=1)),
        help="Current worker replica count.",
    )
    parser.add_argument(
        "--current-synthesis-interval-sec",
        type=int,
        default=max(1, _safe_int(os.getenv("SYNAPSE_WORKER_SYNTHESIS_INTERVAL_SEC", "15"), default=15)),
        help="Current SYNAPSE_WORKER_SYNTHESIS_INTERVAL_SEC value.",
    )
    parser.add_argument(
        "--current-synthesis-limit",
        type=int,
        default=max(1, _safe_int(os.getenv("SYNAPSE_WORKER_SYNTHESIS_LIMIT", "100"), default=100)),
        help="Current SYNAPSE_WORKER_SYNTHESIS_LIMIT value.",
    )
    parser.add_argument(
        "--current-synthesis-extract-limit",
        type=int,
        default=max(1, _safe_int(os.getenv("SYNAPSE_WORKER_SYNTHESIS_EXTRACT_LIMIT", "200"), default=200)),
        help="Current SYNAPSE_WORKER_SYNTHESIS_EXTRACT_LIMIT value.",
    )
    parser.add_argument(
        "--headroom-factor",
        type=float,
        default=1.25,
        help="Safety multiplier over observed arrival rate.",
    )
    parser.add_argument(
        "--backlog-clear-target-minutes",
        type=int,
        default=45,
        help="Target time to burn current backlog.",
    )
    parser.add_argument(
        "--api-url",
        default=os.getenv("SYNAPSE_API_URL", "http://localhost:8080"),
        help="API base URL used in generated apply commands.",
    )

    parser.add_argument(
        "--mcp-history-file",
        default="eval/mcp_retrieval_benchmark_history.jsonl",
        help="History file for MCP trend evaluation.",
    )
    parser.add_argument("--mcp-latest-benchmark", default=None, help="Path to latest benchmark JSON file.")
    parser.add_argument(
        "--mcp-run-benchmark",
        action="store_true",
        help="Run benchmark before evaluating MCP graph recommendations.",
    )
    parser.add_argument(
        "--mcp-append-history",
        action="store_true",
        help="Append newly captured benchmark to history file.",
    )
    parser.add_argument("--mcp-benchmark-project-id", default="mcp_bench", help="Project id for MCP benchmark dataset.")
    parser.add_argument("--mcp-seed-pages", type=int, default=1200, help="Benchmark seed pages.")
    parser.add_argument("--mcp-iterations", type=int, default=200, help="Benchmark measured iterations per case.")

    parser.add_argument(
        "--current-mcp-max-graph-hops",
        type=int,
        default=max(1, _safe_int(os.getenv("SYNAPSE_MCP_GRAPH_MAX_HOPS", "3"), default=3)),
        help="Current SYNAPSE_MCP_GRAPH_MAX_HOPS.",
    )
    parser.add_argument(
        "--current-mcp-graph-boost-hop1",
        type=float,
        default=_safe_float(os.getenv("SYNAPSE_MCP_GRAPH_BOOST_HOP1", "0.20"), default=0.20),
        help="Current SYNAPSE_MCP_GRAPH_BOOST_HOP1.",
    )
    parser.add_argument(
        "--current-mcp-graph-boost-hop2",
        type=float,
        default=_safe_float(os.getenv("SYNAPSE_MCP_GRAPH_BOOST_HOP2", "0.12"), default=0.12),
        help="Current SYNAPSE_MCP_GRAPH_BOOST_HOP2.",
    )
    parser.add_argument(
        "--current-mcp-graph-boost-hop3",
        type=float,
        default=_safe_float(os.getenv("SYNAPSE_MCP_GRAPH_BOOST_HOP3", "0.06"), default=0.06),
        help="Current SYNAPSE_MCP_GRAPH_BOOST_HOP3.",
    )
    parser.add_argument(
        "--current-mcp-graph-boost-other",
        type=float,
        default=_safe_float(os.getenv("SYNAPSE_MCP_GRAPH_BOOST_OTHER", "0.03"), default=0.03),
        help="Current SYNAPSE_MCP_GRAPH_BOOST_OTHER.",
    )

    parser.add_argument(
        "--write-report",
        default=None,
        help="Optional markdown report output path.",
    )
    return parser.parse_args()


def _load_queue_snapshot(conn, *, project_id: str, since: datetime) -> QueueSnapshot:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              COUNT(*) FILTER (WHERE cp.status = 'queued')::int,
              COUNT(*) FILTER (WHERE cp.status = 'processing')::int,
              COUNT(*) FILTER (WHERE cp.status = 'processed')::int,
              COUNT(*) FILTER (WHERE cp.status = 'failed')::int,
              COALESCE((
                SELECT percentile_cont(0.50) WITHIN GROUP (
                  ORDER BY EXTRACT(EPOCH FROM (NOW() - q.created_at)) / 60.0
                )
                FROM claim_proposals q
                WHERE q.project_id = %s
                  AND q.status = 'queued'
              ), 0)::float8,
              COALESCE((
                SELECT percentile_cont(0.95) WITHIN GROUP (
                  ORDER BY EXTRACT(EPOCH FROM (NOW() - q.created_at)) / 60.0
                )
                FROM claim_proposals q
                WHERE q.project_id = %s
                  AND q.status = 'queued'
              ), 0)::float8
            FROM claim_proposals cp
            WHERE cp.project_id = %s
            """,
            (project_id, project_id, project_id),
        )
        totals = cur.fetchone() or (0, 0, 0, 0, 0.0, 0.0)

        cur.execute(
            """
            SELECT
              COUNT(*) FILTER (WHERE created_at >= %s)::int,
              COUNT(*) FILTER (WHERE status = 'processed' AND updated_at >= %s)::int,
              COUNT(*) FILTER (WHERE status = 'failed' AND updated_at >= %s)::int
            FROM claim_proposals
            WHERE project_id = %s
            """,
            (since, since, since, project_id),
        )
        recent = cur.fetchone() or (0, 0, 0)

        cur.execute(
            """
            SELECT
              COUNT(*) FILTER (WHERE status = 'pending_review')::int,
              COUNT(*) FILTER (WHERE status = 'blocked_conflict')::int
            FROM wiki_draft_changes
            WHERE project_id = %s
            """,
            (project_id,),
        )
        draft_counts = cur.fetchone() or (0, 0)

        cur.execute(
            """
            SELECT COUNT(*)::int
            FROM wiki_conflicts
            WHERE project_id = %s
              AND resolution_status = 'open'
            """,
            (project_id,),
        )
        conflict_count = cur.fetchone()

    return QueueSnapshot(
        queued=_safe_int(totals[0]),
        processing=_safe_int(totals[1]),
        processed_total=_safe_int(totals[2]),
        failed_total=_safe_int(totals[3]),
        queued_age_p50_min=round(_safe_float(totals[4]), 3),
        queued_age_p95_min=round(_safe_float(totals[5]), 3),
        arrivals_window=_safe_int(recent[0]),
        processed_window=_safe_int(recent[1]),
        failed_window=_safe_int(recent[2]),
        drafts_pending_review=_safe_int(draft_counts[0]),
        drafts_blocked_conflict=_safe_int(draft_counts[1]),
        conflicts_open=_safe_int((conflict_count or (0,))[0]),
    )


def _load_queue_controls(conn, *, project_id: str) -> QueueControls:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT worker_lag_sla_minutes, queue_depth_warn
            FROM gatekeeper_calibration_queue_controls
            WHERE project_id = %s
            LIMIT 1
            """,
            (project_id,),
        )
        row = cur.fetchone()
    if not row:
        return QueueControls(worker_lag_sla_minutes=20, queue_depth_warn=12, exists=False)
    return QueueControls(
        worker_lag_sla_minutes=max(1, _safe_int(row[0], default=20)),
        queue_depth_warn=max(1, _safe_int(row[1], default=12)),
        exists=True,
    )


def _pick_profile(snapshot: QueueSnapshot, *, arrival_rate_per_min: float) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if snapshot.backlog >= 400:
        reasons.append(f"backlog={snapshot.backlog}>=400")
    if snapshot.queued_age_p95_min >= 120:
        reasons.append(f"queued_age_p95_min={snapshot.queued_age_p95_min}>=120")
    if arrival_rate_per_min >= 20.0:
        reasons.append(f"arrival_rate_per_min={arrival_rate_per_min:.3f}>=20")
    if snapshot.drafts_pending_review >= 300:
        reasons.append(f"drafts_pending_review={snapshot.drafts_pending_review}>=300")
    if reasons:
        return "burst", reasons

    reasons = []
    if snapshot.backlog >= 120:
        reasons.append(f"backlog={snapshot.backlog}>=120")
    if snapshot.queued_age_p95_min >= 45:
        reasons.append(f"queued_age_p95_min={snapshot.queued_age_p95_min}>=45")
    if arrival_rate_per_min >= 8.0:
        reasons.append(f"arrival_rate_per_min={arrival_rate_per_min:.3f}>=8")
    if snapshot.drafts_pending_review >= 80:
        reasons.append(f"drafts_pending_review={snapshot.drafts_pending_review}>=80")
    if reasons:
        return "balanced", reasons

    return "conserve", ["steady_or_low_traffic"]


def _recommend_workers(
    *,
    current_workers: int,
    synthesis_limit: int,
    synthesis_interval_sec: int,
    arrival_rate_per_min: float,
    processed_rate_per_min: float,
    backlog: int,
    headroom_factor: float,
    backlog_clear_target_minutes: int,
) -> WorkerSizing:
    current_workers = max(1, int(current_workers))
    synthesis_limit = max(1, int(synthesis_limit))
    synthesis_interval_sec = max(1, int(synthesis_interval_sec))
    theoretical_per_worker = (float(synthesis_limit) / float(synthesis_interval_sec)) * 60.0

    observed_per_worker: float | None = None
    if processed_rate_per_min > 0:
        observed_per_worker = processed_rate_per_min / float(current_workers)

    if observed_per_worker is None:
        effective_per_worker = max(0.1, theoretical_per_worker * 0.70)
    else:
        effective_per_worker = max(
            0.1,
            min(theoretical_per_worker, observed_per_worker * 1.15),
        )

    required_rate = (max(0.0, arrival_rate_per_min) * max(1.0, headroom_factor)) + (
        max(0, backlog) / float(max(1, backlog_clear_target_minutes))
    )

    recommended = max(1, int(math.ceil(required_rate / max(0.1, effective_per_worker))))
    if backlog <= 0 and arrival_rate_per_min < 0.5:
        recommended = 1

    return WorkerSizing(
        recommended_workers=recommended,
        delta_workers=recommended - current_workers,
        required_rate_per_min=round(required_rate, 3),
        effective_capacity_per_worker_per_min=round(effective_per_worker, 3),
        observed_capacity_per_worker_per_min=(
            round(observed_per_worker, 3) if observed_per_worker is not None else None
        ),
        theoretical_capacity_per_worker_per_min=round(theoretical_per_worker, 3),
    )


def _run_mcp_trend(args: argparse.Namespace) -> dict[str, Any]:
    if not args.mcp_run_benchmark and not args.mcp_latest_benchmark and not Path(args.mcp_history_file).exists():
        return {
            "status": "skipped",
            "reason": "mcp_history_missing_and_benchmark_not_requested",
        }

    cmd = [
        sys.executable,
        str(MCP_TREND_SCRIPT),
        "--project-id",
        str(args.mcp_benchmark_project_id),
        "--history-file",
        str(args.mcp_history_file),
    ]

    if args.mcp_latest_benchmark:
        cmd.extend(["--latest-benchmark", str(args.mcp_latest_benchmark)])
    if args.mcp_run_benchmark:
        cmd.extend(
            [
                "--run-benchmark",
                "--database-url",
                str(args.database_url),
                "--replace",
                "--seed-pages",
                str(max(10, int(args.mcp_seed_pages))),
                "--iterations",
                str(max(20, int(args.mcp_iterations))),
                "--max-graph-hops",
                str(max(1, int(args.current_mcp_max_graph_hops))),
                "--graph-boost-hop1",
                str(float(args.current_mcp_graph_boost_hop1)),
                "--graph-boost-hop2",
                str(float(args.current_mcp_graph_boost_hop2)),
                "--graph-boost-hop3",
                str(float(args.current_mcp_graph_boost_hop3)),
                "--graph-boost-other",
                str(float(args.current_mcp_graph_boost_other)),
            ]
        )
    if args.mcp_append_history and (args.mcp_run_benchmark or args.mcp_latest_benchmark):
        cmd.append("--append-history")

    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()

    parsed: dict[str, Any] | None = None
    if stdout:
        try:
            loaded = json.loads(stdout)
            if isinstance(loaded, dict):
                parsed = loaded
        except Exception:
            parsed = None

    if parsed is None:
        payload: dict[str, Any] = {
            "status": "unavailable",
            "reason": "mcp_trend_json_parse_error",
            "returncode": proc.returncode,
        }
        if stderr:
            payload["stderr"] = stderr[-2000:]
        if stdout:
            payload["stdout"] = stdout[-2000:]
        return payload

    payload = dict(parsed)
    payload["returncode"] = proc.returncode
    if stderr:
        payload["stderr"] = stderr[-2000:]
    return payload


def _current_mcp_config_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "max_graph_hops": max(1, int(args.current_mcp_max_graph_hops)),
        "graph_boost_hop1": round(float(args.current_mcp_graph_boost_hop1), 4),
        "graph_boost_hop2": round(float(args.current_mcp_graph_boost_hop2), 4),
        "graph_boost_hop3": round(float(args.current_mcp_graph_boost_hop3), 4),
        "graph_boost_other": round(float(args.current_mcp_graph_boost_other), 4),
    }


def _recommend_mcp_graph_knobs(args: argparse.Namespace, trend_payload: dict[str, Any]) -> dict[str, Any]:
    fallback_current = _current_mcp_config_from_args(args)

    latest = trend_payload.get("latest") if isinstance(trend_payload.get("latest"), dict) else {}
    latest_config = latest.get("config") if isinstance(latest.get("config"), dict) else {}
    current = {
        "max_graph_hops": int(latest_config.get("max_graph_hops") or fallback_current["max_graph_hops"]),
        "graph_boost_hop1": round(_safe_float(latest_config.get("graph_boost_hop1"), default=fallback_current["graph_boost_hop1"]), 4),
        "graph_boost_hop2": round(_safe_float(latest_config.get("graph_boost_hop2"), default=fallback_current["graph_boost_hop2"]), 4),
        "graph_boost_hop3": round(_safe_float(latest_config.get("graph_boost_hop3"), default=fallback_current["graph_boost_hop3"]), 4),
        "graph_boost_other": round(_safe_float(latest_config.get("graph_boost_other"), default=fallback_current["graph_boost_other"]), 4),
    }

    signals = trend_payload.get("signals") if isinstance(trend_payload.get("signals"), dict) else {}
    quality_regression = bool(signals.get("measured_quality_regression"))
    latency_regression = bool(signals.get("measured_latency_regression"))

    recommendation = trend_payload.get("recommended_graph_profile")
    if quality_regression and isinstance(recommendation, dict):
        suggested = recommendation.get("suggested") if isinstance(recommendation.get("suggested"), dict) else {}
        merged = {
            "max_graph_hops": int(suggested.get("max_graph_hops") or current["max_graph_hops"]),
            "graph_boost_hop1": round(_safe_float(suggested.get("graph_boost_hop1"), default=current["graph_boost_hop1"]), 4),
            "graph_boost_hop2": round(_safe_float(suggested.get("graph_boost_hop2"), default=current["graph_boost_hop2"]), 4),
            "graph_boost_hop3": round(_safe_float(suggested.get("graph_boost_hop3"), default=current["graph_boost_hop3"]), 4),
            "graph_boost_other": round(_safe_float(suggested.get("graph_boost_other"), default=current["graph_boost_other"]), 4),
        }
        return {
            "current": current,
            "suggested": merged,
            "changed": merged != current,
            "reason": "quality_regression_detected",
        }

    if latency_regression and not quality_regression:
        tuned = {
            "max_graph_hops": max(1, current["max_graph_hops"] - 1),
            "graph_boost_hop1": round(max(0.01, current["graph_boost_hop1"] * 0.85), 4),
            "graph_boost_hop2": round(max(0.01, current["graph_boost_hop2"] * 0.85), 4),
            "graph_boost_hop3": round(max(0.005, current["graph_boost_hop3"] * 0.85), 4),
            "graph_boost_other": round(max(0.003, current["graph_boost_other"] * 0.85), 4),
        }
        return {
            "current": current,
            "suggested": tuned,
            "changed": tuned != current,
            "reason": "latency_regression_without_quality_drop",
        }

    return {
        "current": current,
        "suggested": current,
        "changed": False,
        "reason": "stable_or_insufficient_signal",
    }


def _recommend_mcp_context_policy(trend_payload: dict[str, Any]) -> dict[str, Any]:
    raw = trend_payload.get("recommended_context_policy_profile")
    if not isinstance(raw, dict):
        return {
            "profile": "enforced",
            "reason": "trend_recommendation_missing_default_enforced",
            "thresholds": {
                "context_policy_mode": "enforced",
                "min_retrieval_confidence": 0.45,
                "min_total_score": 0.20,
                "min_lexical_score": 0.08,
                "min_token_overlap_ratio": 0.15,
            },
            "changed": False,
        }

    profile = str(raw.get("profile") or "enforced").strip().lower() or "enforced"
    reason = str(raw.get("reason") or "trend_recommendation").strip() or "trend_recommendation"
    thresholds_raw = raw.get("thresholds")
    thresholds = thresholds_raw if isinstance(thresholds_raw, dict) else {}
    normalized: dict[str, Any] = {
        "context_policy_mode": str(thresholds.get("context_policy_mode") or "advisory").strip().lower() or "advisory"
    }
    for key in ("min_retrieval_confidence", "min_total_score", "min_lexical_score", "min_token_overlap_ratio"):
        value = thresholds.get(key)
        if value is None:
            continue
        normalized[key] = round(_safe_float(value), 4)
    return {
        "profile": profile,
        "reason": reason,
        "thresholds": normalized,
        "changed": profile != "enforced",
        "sdk_hints": raw.get("sdk_hints") if isinstance(raw.get("sdk_hints"), dict) else {},
    }


def _render_report(payload: dict[str, Any]) -> str:
    queue = payload["queue_snapshot"]
    rates = payload["rates_per_minute"]
    profile = payload["queue_profile"]
    workers = payload["worker_recommendation"]
    current_worker_env = payload["current_worker_env"]
    worker_env = payload["recommended_worker_env"]
    queue_controls_current = payload["current_queue_controls"]
    queue_controls = payload["recommended_queue_controls"]
    mcp = payload["mcp_graph_recommendation"]
    mcp_context = payload["mcp_context_policy_recommendation"]

    lines = [
        "# Synapse Performance Tuning Report",
        "",
        f"Generated: {payload['generated_at']}",
        f"Project: `{payload['project_id']}`",
        "",
        "## Queue Snapshot",
        "",
        f"- Backlog (queued+processing): **{queue['backlog']}**",
        f"- Queue age p50/p95 (min): **{queue['queued_age_p50_min']} / {queue['queued_age_p95_min']}**",
        f"- Pending drafts / blocked conflicts: **{queue['drafts_pending_review']} / {queue['drafts_blocked_conflict']}**",
        f"- Open conflicts: **{queue['conflicts_open']}**",
        "",
        "## Throughput Rates (per minute)",
        "",
        f"- Arrival: **{rates['arrival']}**",
        f"- Processed: **{rates['processed']}**",
        f"- Failed: **{rates['failed']}**",
        "",
        "## Recommended Queue Profile",
        "",
        f"- Profile: **{profile['selected']}**",
        f"- Reasons: `{', '.join(profile.get('reasons') or [])}`",
        "",
        "## Worker Recommendations",
        "",
        f"- Current worker replicas: **{workers['current_workers']}**",
        f"- Recommended worker replicas: **{workers['recommended_workers']}**",
        f"- Delta: **{workers['delta_workers']}**",
        f"- Required rate (claims/min): **{workers['required_rate_per_min']}**",
        f"- Effective capacity per worker (claims/min): **{workers['effective_capacity_per_worker_per_min']}**",
        "",
        "### Worker Env",
        "",
        "```bash",
        f"# current: interval={current_worker_env['SYNAPSE_WORKER_SYNTHESIS_INTERVAL_SEC']} "
        f"limit={current_worker_env['SYNAPSE_WORKER_SYNTHESIS_LIMIT']} "
        f"extract={current_worker_env['SYNAPSE_WORKER_SYNTHESIS_EXTRACT_LIMIT']}",
        f"export SYNAPSE_WORKER_SYNTHESIS_INTERVAL_SEC={worker_env['SYNAPSE_WORKER_SYNTHESIS_INTERVAL_SEC']}",
        f"export SYNAPSE_WORKER_SYNTHESIS_LIMIT={worker_env['SYNAPSE_WORKER_SYNTHESIS_LIMIT']}",
        f"export SYNAPSE_WORKER_SYNTHESIS_EXTRACT_LIMIT={worker_env['SYNAPSE_WORKER_SYNTHESIS_EXTRACT_LIMIT']}",
        "```",
        "",
        "## Queue Control Recommendation",
        "",
        f"- Current queue control: lag_sla={queue_controls_current['worker_lag_sla_minutes']} min, "
        f"depth_warn={queue_controls_current['queue_depth_warn']}",
        "",
        "```json",
        json.dumps(queue_controls, ensure_ascii=False, indent=2),
        "```",
        "",
        "## MCP Graph Recommendation",
        "",
        f"- Reason: `{mcp['reason']}`",
        f"- Changed: **{str(bool(mcp['changed'])).lower()}**",
        "",
        "```json",
        json.dumps(mcp["suggested"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## MCP Context Policy Recommendation",
        "",
        f"- Profile: **{mcp_context['profile']}**",
        f"- Reason: `{mcp_context['reason']}`",
        "",
        "```json",
        json.dumps(mcp_context["thresholds"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Apply Commands",
        "",
        "```bash",
        payload["apply_commands"]["scale_workers"],
        payload["apply_commands"]["apply_queue_control"],
        payload["apply_commands"]["set_mcp_graph_knobs"],
        payload["apply_commands"]["set_mcp_context_policy"],
        "```",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    args = _parse_args()

    try:
        import psycopg
    except Exception:
        print(
            json.dumps(
                {
                    "status": "unavailable",
                    "reason": "psycopg_missing",
                    "detail": "Install psycopg[binary] to run tuning advisor.",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    now = datetime.now(UTC)
    window_hours = max(1, min(168, int(args.window_hours)))
    since = now - timedelta(hours=window_hours)
    window_minutes = float(window_hours * 60)

    try:
        with psycopg.connect(args.database_url) as conn:
            snapshot = _load_queue_snapshot(conn, project_id=str(args.project_id), since=since)
            queue_controls_current = _load_queue_controls(conn, project_id=str(args.project_id))
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "unavailable",
                    "reason": "db_connection_failed",
                    "database_url_redacted": str(args.database_url).split("@")[-1],
                    "detail": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    arrival_rate = round(snapshot.arrivals_window / window_minutes, 3)
    processed_rate = round(snapshot.processed_window / window_minutes, 3)
    failed_rate = round(snapshot.failed_window / window_minutes, 3)

    profile_name, profile_reasons = _pick_profile(snapshot, arrival_rate_per_min=arrival_rate)
    profile = PROFILE_PRESETS[profile_name]

    sizing = _recommend_workers(
        current_workers=max(1, int(args.current_worker_replicas)),
        synthesis_limit=int(profile["synthesis_limit"]),
        synthesis_interval_sec=int(profile["synthesis_interval_sec"]),
        arrival_rate_per_min=arrival_rate,
        processed_rate_per_min=processed_rate,
        backlog=snapshot.backlog,
        headroom_factor=max(1.0, float(args.headroom_factor)),
        backlog_clear_target_minutes=max(5, int(args.backlog_clear_target_minutes)),
    )

    trend_payload = _run_mcp_trend(args)
    mcp_recommendation = _recommend_mcp_graph_knobs(args, trend_payload)
    mcp_context_policy_recommendation = _recommend_mcp_context_policy(trend_payload)

    recommended_worker_env = {
        "SYNAPSE_WORKER_SYNTHESIS_INTERVAL_SEC": int(profile["synthesis_interval_sec"]),
        "SYNAPSE_WORKER_SYNTHESIS_LIMIT": int(profile["synthesis_limit"]),
        "SYNAPSE_WORKER_SYNTHESIS_EXTRACT_LIMIT": int(profile["synthesis_extract_limit"]),
    }
    current_worker_env = {
        "SYNAPSE_WORKER_SYNTHESIS_INTERVAL_SEC": max(1, int(args.current_synthesis_interval_sec)),
        "SYNAPSE_WORKER_SYNTHESIS_LIMIT": max(1, int(args.current_synthesis_limit)),
        "SYNAPSE_WORKER_SYNTHESIS_EXTRACT_LIMIT": max(1, int(args.current_synthesis_extract_limit)),
    }
    recommended_queue_controls = {
        "project_id": str(args.project_id),
        "worker_lag_sla_minutes": int(profile["worker_lag_sla_minutes"]),
        "queue_depth_warn": int(profile["queue_depth_warn"]),
        "updated_by": "synapse_perf_advisor",
    }

    apply_queue_json = json.dumps(recommended_queue_controls, ensure_ascii=True, separators=(",", ":"))
    apply_commands = {
        "scale_workers": (
            "docker compose --env-file .env.selfhost -f infra/docker-compose.selfhost.yml "
            f"up -d --scale worker={sizing.recommended_workers}"
        ),
        "apply_queue_control": (
            "curl -fsS -X PUT "
            f"\"{str(args.api_url).rstrip('/')}/v1/gatekeeper/calibration/operations/throughput/control\" "
            "-H 'Content-Type: application/json' "
            f"-d '{apply_queue_json}'"
        ),
        "set_mcp_graph_knobs": (
            f"export SYNAPSE_MCP_GRAPH_MAX_HOPS={int(mcp_recommendation['suggested']['max_graph_hops'])} && "
            f"export SYNAPSE_MCP_GRAPH_BOOST_HOP1={float(mcp_recommendation['suggested']['graph_boost_hop1']):.4f} && "
            f"export SYNAPSE_MCP_GRAPH_BOOST_HOP2={float(mcp_recommendation['suggested']['graph_boost_hop2']):.4f} && "
            f"export SYNAPSE_MCP_GRAPH_BOOST_HOP3={float(mcp_recommendation['suggested']['graph_boost_hop3']):.4f} && "
            f"export SYNAPSE_MCP_GRAPH_BOOST_OTHER={float(mcp_recommendation['suggested']['graph_boost_other']):.4f}"
        ),
        "set_mcp_context_policy": (
            f"export SYNAPSE_CONTEXT_POLICY_PROFILE={str(mcp_context_policy_recommendation['profile'])} && "
            f"export SYNAPSE_CONTEXT_POLICY_MODE={str(mcp_context_policy_recommendation['thresholds'].get('context_policy_mode', 'advisory'))} && "
            "export SYNAPSE_CONTEXT_MIN_RETRIEVAL_CONFIDENCE="
            f"{float(mcp_context_policy_recommendation['thresholds'].get('min_retrieval_confidence', 0.0)):.4f} && "
            "export SYNAPSE_CONTEXT_MIN_TOTAL_SCORE="
            f"{float(mcp_context_policy_recommendation['thresholds'].get('min_total_score', 0.0)):.4f} && "
            "export SYNAPSE_CONTEXT_MIN_LEXICAL_SCORE="
            f"{float(mcp_context_policy_recommendation['thresholds'].get('min_lexical_score', 0.0)):.4f} && "
            "export SYNAPSE_CONTEXT_MIN_TOKEN_OVERLAP_RATIO="
            f"{float(mcp_context_policy_recommendation['thresholds'].get('min_token_overlap_ratio', 0.0)):.4f}"
        ),
    }

    output = {
        "status": "ok",
        "generated_at": now.isoformat(),
        "project_id": str(args.project_id),
        "window_hours": window_hours,
        "queue_snapshot": {
            "queued": snapshot.queued,
            "processing": snapshot.processing,
            "backlog": snapshot.backlog,
            "processed_total": snapshot.processed_total,
            "failed_total": snapshot.failed_total,
            "queued_age_p50_min": snapshot.queued_age_p50_min,
            "queued_age_p95_min": snapshot.queued_age_p95_min,
            "arrivals_window": snapshot.arrivals_window,
            "processed_window": snapshot.processed_window,
            "failed_window": snapshot.failed_window,
            "drafts_pending_review": snapshot.drafts_pending_review,
            "drafts_blocked_conflict": snapshot.drafts_blocked_conflict,
            "conflicts_open": snapshot.conflicts_open,
        },
        "rates_per_minute": {
            "arrival": arrival_rate,
            "processed": processed_rate,
            "failed": failed_rate,
        },
        "queue_profile": {
            "selected": profile_name,
            "reasons": profile_reasons,
        },
        "worker_recommendation": {
            "current_workers": max(1, int(args.current_worker_replicas)),
            "recommended_workers": sizing.recommended_workers,
            "delta_workers": sizing.delta_workers,
            "required_rate_per_min": sizing.required_rate_per_min,
            "effective_capacity_per_worker_per_min": sizing.effective_capacity_per_worker_per_min,
            "observed_capacity_per_worker_per_min": sizing.observed_capacity_per_worker_per_min,
            "theoretical_capacity_per_worker_per_min": sizing.theoretical_capacity_per_worker_per_min,
        },
        "current_worker_env": current_worker_env,
        "recommended_worker_env": recommended_worker_env,
        "worker_env_changed": current_worker_env != recommended_worker_env,
        "current_queue_controls": {
            "worker_lag_sla_minutes": queue_controls_current.worker_lag_sla_minutes,
            "queue_depth_warn": queue_controls_current.queue_depth_warn,
            "exists": queue_controls_current.exists,
        },
        "recommended_queue_controls": recommended_queue_controls,
        "queue_controls_changed": (
            queue_controls_current.worker_lag_sla_minutes != int(recommended_queue_controls["worker_lag_sla_minutes"])
            or queue_controls_current.queue_depth_warn != int(recommended_queue_controls["queue_depth_warn"])
        ),
        "mcp_trend": {
            "status": str(trend_payload.get("status") or "unknown"),
            "alerts": trend_payload.get("alerts") if isinstance(trend_payload.get("alerts"), list) else [],
            "signals": trend_payload.get("signals") if isinstance(trend_payload.get("signals"), dict) else {},
            "latest": trend_payload.get("latest") if isinstance(trend_payload.get("latest"), dict) else None,
        },
        "mcp_graph_recommendation": mcp_recommendation,
        "mcp_context_policy_recommendation": mcp_context_policy_recommendation,
        "apply_commands": apply_commands,
    }

    if args.write_report:
        report_path = Path(args.write_report).resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(_render_report(output), encoding="utf-8")
        output["report_path"] = str(report_path)

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
