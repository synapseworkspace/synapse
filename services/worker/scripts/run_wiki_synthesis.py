#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from app.db import get_conn
from app.wiki_engine import WikiSynthesisEngine


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one or many wiki synthesis cycles.")
    parser.add_argument("--limit", type=int, default=50, help="Maximum queued claim proposals per cycle.")
    parser.add_argument("--extract-limit", type=int, default=200, help="Maximum memory_backfill events to extract per cycle.")
    parser.add_argument("--cycles", type=int, default=1, help="How many consecutive cycles to execute.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    engine = WikiSynthesisEngine()
    total = {
        "backfill_events_picked": 0,
        "backfill_events_completed": 0,
        "backfill_claims_generated": 0,
        "backfill_failed": 0,
        "draft_claims_picked": 0,
        "draft_claims_processed": 0,
        "draft_claims_failed": 0,
    }

    for _ in range(args.cycles):
        with get_conn() as conn:
            extract_stats = engine.extract_backfill_claims(conn, limit=args.extract_limit)
            synth_stats = engine.run_once(conn, limit=args.limit)
        total["backfill_events_picked"] += extract_stats.get("picked", 0)
        total["backfill_events_completed"] += extract_stats.get("events_completed", 0)
        total["backfill_claims_generated"] += extract_stats.get("claims_generated", 0)
        total["backfill_failed"] += extract_stats.get("failed", 0)
        total["draft_claims_picked"] += synth_stats.get("picked", 0)
        total["draft_claims_processed"] += synth_stats.get("processed", 0)
        total["draft_claims_failed"] += synth_stats.get("failed", 0)
        if extract_stats.get("picked", 0) == 0 and synth_stats.get("picked", 0) == 0:
            break

    print(json.dumps(total, indent=2))


if __name__ == "__main__":
    main()
