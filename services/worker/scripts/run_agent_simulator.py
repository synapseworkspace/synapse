#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Synapse Agent Simulator (policy replay on historical sessions).")
    parser.add_argument("--project-id", required=True, help="Synapse project id.")
    parser.add_argument(
        "--policy-file",
        default=None,
        help="Path to JSON file with policy changes (array or object with policy_changes).",
    )
    parser.add_argument(
        "--policy-json",
        default=None,
        help="Inline JSON payload with policy changes (array or object with policy_changes).",
    )
    parser.add_argument("--lookback-days", type=int, default=14, help="Historical window in days.")
    parser.add_argument("--max-sessions", type=int, default=200, help="Max sessions scanned from historical logs.")
    parser.add_argument("--events-per-session", type=int, default=80, help="Max recent events sampled per session.")
    parser.add_argument("--relevance-floor", type=float, default=0.22, help="Minimum relevance score for findings.")
    parser.add_argument("--max-findings", type=int, default=1200, help="Hard limit on persisted findings.")
    parser.add_argument("--created-by", default="simulator_script", help="Actor label saved in run metadata.")
    parser.add_argument("--dry-run", action="store_true", help="Compute results but do not persist run/findings.")
    parser.add_argument("--findings-limit", type=int, default=10, help="How many top findings to print in output.")
    return parser.parse_args()


def _load_policy_changes(args: argparse.Namespace) -> list[dict[str, Any]]:
    raw_payload: Any = None
    if args.policy_file:
        payload_text = Path(args.policy_file).read_text(encoding="utf-8")
        raw_payload = json.loads(payload_text)
    elif args.policy_json:
        raw_payload = json.loads(args.policy_json)
    else:
        raise SystemExit("Provide --policy-file or --policy-json with at least one policy change.")

    if isinstance(raw_payload, dict):
        if isinstance(raw_payload.get("policy_changes"), list):
            policy_changes = raw_payload["policy_changes"]
        else:
            policy_changes = [raw_payload]
    elif isinstance(raw_payload, list):
        policy_changes = raw_payload
    else:
        raise SystemExit("Policy payload must be a JSON object or array.")

    if not policy_changes:
        raise SystemExit("No policy changes found in payload.")
    return [dict(item) for item in policy_changes if isinstance(item, dict)]


def main() -> None:
    args = parse_args()
    policy_changes = _load_policy_changes(args)
    try:
        from app.db import get_conn
        from app.simulator import AgentSimulatorEngine
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing runtime dependency. Install worker requirements (including psycopg) before running simulator."
        ) from exc

    engine = AgentSimulatorEngine()

    with get_conn() as conn:
        result = engine.run(
            conn,
            project_id=args.project_id,
            policy_changes=policy_changes,
            lookback_days=args.lookback_days,
            max_sessions=args.max_sessions,
            events_per_session=args.events_per_session,
            relevance_floor=args.relevance_floor,
            max_findings=args.max_findings,
            created_by=args.created_by,
            persist=not args.dry_run,
        )

    findings_limit = max(0, int(args.findings_limit))
    top_findings = list(result.get("top_findings") or [])[:findings_limit]
    out = dict(result)
    out["top_findings"] = top_findings
    if args.dry_run:
        out["status"] = "simulated_not_persisted"
    else:
        out["status"] = "completed"
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
