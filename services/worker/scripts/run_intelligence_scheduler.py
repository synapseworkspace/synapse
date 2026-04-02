#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime, timedelta
from typing import Any

from app.db import get_conn
from app.delivery import IntelligenceDeliveryEngine
from app.intelligence import (
    INTELLIGENCE_DIGEST_KIND_DAILY,
    INTELLIGENCE_DIGEST_KIND_INCIDENT_ESCALATION_DAILY,
    INTELLIGENCE_DIGEST_KIND_WEEKLY,
    KnowledgeIntelligenceEngine,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run intelligence generation + delivery pipeline.")
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
        help="Auto-discover projects if explicit project ids are not provided.",
    )
    parser.add_argument(
        "--date",
        dest="target_date",
        default=None,
        help="Digest date in YYYY-MM-DD. Default: yesterday in UTC.",
    )
    parser.add_argument(
        "--delivery-kind",
        default=INTELLIGENCE_DIGEST_KIND_DAILY,
        choices=[
            INTELLIGENCE_DIGEST_KIND_DAILY,
            INTELLIGENCE_DIGEST_KIND_WEEKLY,
            INTELLIGENCE_DIGEST_KIND_INCIDENT_ESCALATION_DAILY,
        ],
        help="Digest kind for delivery stage.",
    )
    parser.add_argument(
        "--generate-kind",
        default=INTELLIGENCE_DIGEST_KIND_DAILY,
        choices=[
            INTELLIGENCE_DIGEST_KIND_DAILY,
            INTELLIGENCE_DIGEST_KIND_WEEKLY,
            INTELLIGENCE_DIGEST_KIND_INCIDENT_ESCALATION_DAILY,
        ],
        help="Digest kind for generation stage.",
    )
    parser.add_argument(
        "--skip-generate",
        action="store_true",
        help="Skip digest generation stage.",
    )
    parser.add_argument(
        "--skip-deliver",
        action="store_true",
        help="Skip digest delivery stage.",
    )
    parser.add_argument(
        "--delivery-limit",
        type=int,
        default=200,
        help="Maximum ready digests for delivery stage.",
    )
    parser.add_argument(
        "--generated-by",
        default="scheduler",
        help="Actor label for generated digests.",
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
        help="Maximum incident candidates in escalation digest payload.",
    )
    return parser.parse_args()


def _resolve_target_date(raw: str | None) -> date:
    if raw:
        return date.fromisoformat(raw)
    return (datetime.now(UTC) - timedelta(days=1)).date()


def main() -> None:
    args = parse_args()
    target_date = _resolve_target_date(args.target_date)
    intel = KnowledgeIntelligenceEngine()
    delivery = IntelligenceDeliveryEngine()

    summary: dict[str, Any] = {
        "metric_date": target_date.isoformat(),
        "generate_kind": args.generate_kind,
        "delivery_kind": args.delivery_kind,
        "generated": {"projects": 0, "results": []},
        "delivered": {},
    }
    with get_conn() as conn:
        project_ids = list(dict.fromkeys(args.project_ids))
        if args.all_projects or not project_ids:
            discovered = intel.discover_projects(conn)
            for project_id in discovered:
                if project_id not in project_ids:
                    project_ids.append(project_id)

        if not args.skip_generate:
            for project_id in project_ids:
                if args.generate_kind == INTELLIGENCE_DIGEST_KIND_WEEKLY:
                    result = intel.run_weekly(
                        conn,
                        project_id=project_id,
                        anchor_date=target_date,
                        generated_by=args.generated_by,
                    )
                elif args.generate_kind == INTELLIGENCE_DIGEST_KIND_INCIDENT_ESCALATION_DAILY:
                    result = intel.run_incident_escalation_daily(
                        conn,
                        project_id=project_id,
                        metric_date=target_date,
                        generated_by=args.generated_by,
                        incident_sla_hours=max(1, min(168, int(args.incident_sla_hours))),
                        top_n=max(1, min(50, int(args.top_n))),
                    )
                else:
                    result = intel.run_daily(
                        conn,
                        project_id=project_id,
                        metric_date=target_date,
                        generated_by=args.generated_by,
                    )
                summary["generated"]["results"].append(result)
            summary["generated"]["projects"] = len(summary["generated"]["results"])

        if not args.skip_deliver:
            summary["delivered"] = delivery.dispatch_ready(
                conn,
                project_ids=project_ids or None,
                digest_kind=args.delivery_kind,
                limit=max(1, args.delivery_limit),
            )

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
