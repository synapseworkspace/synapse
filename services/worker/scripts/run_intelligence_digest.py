#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime, timedelta

from app.db import get_conn
from app.intelligence import (
    INTELLIGENCE_DIGEST_KIND_DAILY,
    INTELLIGENCE_DIGEST_KIND_INCIDENT_ESCALATION_DAILY,
    INTELLIGENCE_DIGEST_KIND_WEEKLY,
    KnowledgeIntelligenceEngine,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Synapse intelligence digest(s).")
    parser.add_argument(
        "--project-id",
        action="append",
        dest="project_ids",
        default=[],
        help="Project id to process. Can be repeated.",
    )
    parser.add_argument(
        "--all-projects",
        action="store_true",
        help="Auto-discover projects from DB if explicit --project-id is not provided.",
    )
    parser.add_argument(
        "--kind",
        default=INTELLIGENCE_DIGEST_KIND_DAILY,
        choices=[
            INTELLIGENCE_DIGEST_KIND_DAILY,
            INTELLIGENCE_DIGEST_KIND_WEEKLY,
            INTELLIGENCE_DIGEST_KIND_INCIDENT_ESCALATION_DAILY,
        ],
        help="Digest kind to generate.",
    )
    parser.add_argument(
        "--date",
        dest="target_date",
        default=None,
        help="Anchor date in YYYY-MM-DD. Default: yesterday in UTC.",
    )
    parser.add_argument(
        "--generated-by",
        default="system",
        help="Actor name stored in digest metadata.",
    )
    parser.add_argument(
        "--incident-sla-hours",
        type=int,
        default=24,
        help="SLA in hours for incident escalation digest generation.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Maximum top incident candidates included in incident escalation digest payload.",
    )
    return parser.parse_args()


def _resolve_target_date(raw: str | None) -> date:
    if raw:
        return date.fromisoformat(raw)
    return (datetime.now(UTC) - timedelta(days=1)).date()


def main() -> None:
    args = parse_args()
    target_date = _resolve_target_date(args.target_date)
    engine = KnowledgeIntelligenceEngine()

    with get_conn() as conn:
        project_ids = list(dict.fromkeys(args.project_ids))
        if args.all_projects or not project_ids:
            discovered = engine.discover_projects(conn)
            for project_id in discovered:
                if project_id not in project_ids:
                    project_ids.append(project_id)

        if not project_ids:
            print(
                json.dumps(
                    {
                        "status": "skipped",
                        "reason": "no_projects_found",
                        "kind": args.kind,
                        "anchor_date": target_date.isoformat(),
                    },
                    indent=2,
                )
            )
            return

        results = []
        for project_id in project_ids:
            if args.kind == INTELLIGENCE_DIGEST_KIND_WEEKLY:
                results.append(
                    engine.run_weekly(
                        conn,
                        project_id=project_id,
                        anchor_date=target_date,
                        generated_by=args.generated_by,
                    )
                )
            elif args.kind == INTELLIGENCE_DIGEST_KIND_INCIDENT_ESCALATION_DAILY:
                results.append(
                    engine.run_incident_escalation_daily(
                        conn,
                        project_id=project_id,
                        metric_date=target_date,
                        generated_by=args.generated_by,
                        incident_sla_hours=max(1, min(168, int(args.incident_sla_hours))),
                        top_n=max(1, min(50, int(args.top_n))),
                    )
                )
            else:
                results.append(
                    engine.run_daily(
                        conn,
                        project_id=project_id,
                        metric_date=target_date,
                        generated_by=args.generated_by,
                    )
                )

    print(
        json.dumps(
            {
                "status": "ok",
                "kind": args.kind,
                "anchor_date": target_date.isoformat(),
                "projects": len(results),
                "results": results,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
