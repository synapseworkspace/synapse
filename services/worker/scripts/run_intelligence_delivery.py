#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from app.db import get_conn
from app.delivery import IntelligenceDeliveryEngine
from app.intelligence import (
    INTELLIGENCE_DIGEST_KIND_DAILY,
    INTELLIGENCE_DIGEST_KIND_INCIDENT_ESCALATION_DAILY,
    INTELLIGENCE_DIGEST_KIND_WEEKLY,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deliver ready Synapse intelligence digests.")
    parser.add_argument(
        "--project-id",
        action="append",
        dest="project_ids",
        default=[],
        help="Project id to process. Can be repeated.",
    )
    parser.add_argument(
        "--kind",
        default=INTELLIGENCE_DIGEST_KIND_DAILY,
        choices=[
            INTELLIGENCE_DIGEST_KIND_DAILY,
            INTELLIGENCE_DIGEST_KIND_WEEKLY,
            INTELLIGENCE_DIGEST_KIND_INCIDENT_ESCALATION_DAILY,
        ],
        help="Digest kind to deliver.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of ready digests to process.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    engine = IntelligenceDeliveryEngine()
    with get_conn() as conn:
        summary = engine.dispatch_ready(
            conn,
            project_ids=args.project_ids or None,
            digest_kind=args.kind,
            limit=max(1, args.limit),
        )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
