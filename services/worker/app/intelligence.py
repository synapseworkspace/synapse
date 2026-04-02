from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import uuid4

from psycopg.types.json import Jsonb

INTELLIGENCE_DIGEST_KIND_DAILY = "daily"
INTELLIGENCE_DIGEST_KIND_WEEKLY = "weekly"
INTELLIGENCE_DIGEST_KIND_INCIDENT_ESCALATION_DAILY = "incident_escalation_daily"
INTELLIGENCE_DIGEST_KINDS = {
    INTELLIGENCE_DIGEST_KIND_DAILY,
    INTELLIGENCE_DIGEST_KIND_WEEKLY,
    INTELLIGENCE_DIGEST_KIND_INCIDENT_ESCALATION_DAILY,
}

_QUEUE_INCIDENT_AGE_BUCKET_ORDER = (
    "under_1h",
    "between_1h_4h",
    "between_4h_12h",
    "between_12h_24h",
    "between_24h_72h",
    "over_72h",
    "unknown",
)


@dataclass(slots=True)
class DailyMetrics:
    claims_created: int
    drafts_created: int
    drafts_approved: int
    drafts_rejected: int
    statements_added: int
    conflicts_opened: int
    conflicts_resolved: int
    pending_drafts: int
    open_conflicts: int
    pages_touched: int
    knowledge_velocity: float


class KnowledgeIntelligenceEngine:
    """Builds daily metrics and digest summaries for project intelligence pulse."""

    def run_daily(
        self,
        conn,
        *,
        project_id: str,
        metric_date: date,
        generated_by: str = "system",
    ) -> dict[str, Any]:
        period_start = datetime.combine(metric_date, time.min, tzinfo=UTC)
        period_end = period_start + timedelta(days=1)

        metrics = self._compute_daily_metrics(conn, project_id=project_id, period_start=period_start, period_end=period_end)
        self._upsert_daily_metrics(conn, project_id=project_id, metric_date=metric_date, metrics=metrics)

        key_learnings = self._collect_key_learnings(
            conn,
            project_id=project_id,
            period_start=period_start,
            period_end=period_end,
            limit=5,
        )
        moderation_backlog = self._collect_moderation_backlog(conn, project_id=project_id, limit=5)
        open_conflicts = self._collect_open_conflicts(conn, project_id=project_id, limit=5)
        suggestions = self._derive_suggestions(metrics, moderation_backlog, open_conflicts)

        headline = (
            f"{metrics.drafts_approved} approved, {metrics.pending_drafts} pending, "
            f"{metrics.open_conflicts} open conflicts"
        )
        summary_markdown = self._render_summary_markdown(
            metric_date=metric_date,
            project_id=project_id,
            metrics=metrics,
            key_learnings=key_learnings,
            moderation_backlog=moderation_backlog,
            open_conflicts=open_conflicts,
            suggestions=suggestions,
        )

        payload = {
            "project_id": project_id,
            "digest_kind": INTELLIGENCE_DIGEST_KIND_DAILY,
            "metric_date": metric_date.isoformat(),
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "metrics": asdict(metrics),
            "key_learnings": key_learnings,
            "moderation_backlog": moderation_backlog,
            "open_conflicts": open_conflicts,
            "suggestions": suggestions,
        }

        digest_id = self._upsert_digest(
            conn,
            project_id=project_id,
            digest_kind=INTELLIGENCE_DIGEST_KIND_DAILY,
            metric_date=metric_date,
            period_start=period_start,
            period_end=period_end,
            generated_by=generated_by,
            headline=headline,
            summary_markdown=summary_markdown,
            payload=payload,
        )
        return {
            "digest_id": str(digest_id),
            "project_id": project_id,
            "metric_date": metric_date.isoformat(),
            "headline": headline,
            "metrics": asdict(metrics),
        }

    def run_weekly(
        self,
        conn,
        *,
        project_id: str,
        anchor_date: date,
        generated_by: str = "system",
    ) -> dict[str, Any]:
        week_start_date = anchor_date - timedelta(days=anchor_date.weekday())
        week_end_date = week_start_date + timedelta(days=6)
        period_start = datetime.combine(week_start_date, time.min, tzinfo=UTC)
        period_end = datetime.combine(week_end_date + timedelta(days=1), time.min, tzinfo=UTC)

        # Keep weekly rollups deterministic even if daily generation was skipped before.
        for offset in range(7):
            day = week_start_date + timedelta(days=offset)
            day_start = datetime.combine(day, time.min, tzinfo=UTC)
            day_end = day_start + timedelta(days=1)
            metrics = self._compute_daily_metrics(conn, project_id=project_id, period_start=day_start, period_end=day_end)
            self._upsert_daily_metrics(conn, project_id=project_id, metric_date=day, metrics=metrics)

        current_rows = self._load_daily_metrics_range(
            conn,
            project_id=project_id,
            from_date=week_start_date,
            to_date=week_end_date,
        )
        previous_start = week_start_date - timedelta(days=7)
        previous_end = week_start_date - timedelta(days=1)
        previous_rows = self._load_daily_metrics_range(
            conn,
            project_id=project_id,
            from_date=previous_start,
            to_date=previous_end,
        )

        current_rollup = self._aggregate_weekly_rollup(current_rows)
        previous_rollup = self._aggregate_weekly_rollup(previous_rows)
        trend_breakdown = self._build_weekly_trend_breakdown(current_rollup=current_rollup, previous_rollup=previous_rollup)
        daily_velocity = [
            {
                "metric_date": row["metric_date"],
                "knowledge_velocity": row["knowledge_velocity"],
                "drafts_approved": row["drafts_approved"],
                "conflicts_opened": row["conflicts_opened"],
            }
            for row in current_rows
        ]

        key_learnings = self._collect_key_learnings(
            conn,
            project_id=project_id,
            period_start=period_start,
            period_end=period_end,
            limit=8,
        )
        moderation_backlog = self._collect_moderation_backlog(conn, project_id=project_id, limit=8)
        open_conflicts = self._collect_open_conflicts(conn, project_id=project_id, limit=8)
        weekly_suggestions = self._derive_weekly_suggestions(
            current_rollup=current_rollup,
            trend_breakdown=trend_breakdown,
            moderation_backlog=moderation_backlog,
            open_conflicts=open_conflicts,
        )

        approvals_delta = trend_breakdown["drafts_approved"]["delta_abs"]
        approvals_direction = "up" if approvals_delta >= 0 else "down"
        headline = (
            f"Week {week_start_date.isoformat()}..{week_end_date.isoformat()}: "
            f"{current_rollup['drafts_approved']} approvals ({approvals_direction} {abs(approvals_delta)} WoW)"
        )
        summary_markdown = self._render_weekly_summary_markdown(
            project_id=project_id,
            week_start=week_start_date,
            week_end=week_end_date,
            current_rollup=current_rollup,
            previous_rollup=previous_rollup,
            trend_breakdown=trend_breakdown,
            daily_velocity=daily_velocity,
            key_learnings=key_learnings,
            moderation_backlog=moderation_backlog,
            open_conflicts=open_conflicts,
            suggestions=weekly_suggestions,
        )

        payload = {
            "project_id": project_id,
            "digest_kind": INTELLIGENCE_DIGEST_KIND_WEEKLY,
            "week_start": week_start_date.isoformat(),
            "week_end": week_end_date.isoformat(),
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "current_rollup": current_rollup,
            "previous_rollup": previous_rollup,
            "trend_breakdown": trend_breakdown,
            "daily_velocity": daily_velocity,
            "key_learnings": key_learnings,
            "moderation_backlog": moderation_backlog,
            "open_conflicts": open_conflicts,
            "suggestions": weekly_suggestions,
        }

        digest_id = self._upsert_digest(
            conn,
            project_id=project_id,
            digest_kind=INTELLIGENCE_DIGEST_KIND_WEEKLY,
            metric_date=week_end_date,
            period_start=period_start,
            period_end=period_end,
            generated_by=generated_by,
            headline=headline,
            summary_markdown=summary_markdown,
            payload=payload,
        )
        return {
            "digest_id": str(digest_id),
            "project_id": project_id,
            "digest_kind": INTELLIGENCE_DIGEST_KIND_WEEKLY,
            "week_start": week_start_date.isoformat(),
            "week_end": week_end_date.isoformat(),
            "headline": headline,
            "current_rollup": current_rollup,
            "trend_breakdown": trend_breakdown,
        }

    def discover_projects(self, conn, *, limit: int = 500) -> list[str]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT project_id
                FROM (
                  SELECT project_id FROM events
                  UNION
                  SELECT project_id FROM claims
                  UNION
                  SELECT project_id FROM wiki_pages
                  UNION
                  SELECT project_id FROM wiki_draft_changes
                  UNION
                  SELECT project_id FROM gatekeeper_calibration_operation_runs
                  UNION
                  SELECT project_id FROM gatekeeper_calibration_queue_controls
                  UNION
                  SELECT project_id FROM gatekeeper_calibration_queue_incident_hooks
                  UNION
                  SELECT project_id FROM gatekeeper_calibration_queue_incident_policies
                  UNION
                  SELECT project_id FROM gatekeeper_calibration_queue_incidents
                  UNION
                  SELECT project_id FROM gatekeeper_calibration_queue_ownership
                ) p
                WHERE project_id IS NOT NULL
                  AND project_id <> ''
                ORDER BY project_id ASC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
        return [str(row[0]) for row in rows]

    def run_incident_escalation_daily(
        self,
        conn,
        *,
        project_id: str,
        metric_date: date,
        generated_by: str = "system",
        incident_sla_hours: int = 24,
        top_n: int = 10,
    ) -> dict[str, Any]:
        period_start = datetime.combine(metric_date, time.min, tzinfo=UTC)
        period_end = period_start + timedelta(days=1)
        snapshot = self._collect_incident_escalation_snapshot(
            conn,
            project_id=project_id,
            period_end=period_end,
            incident_sla_hours=incident_sla_hours,
            top_n=top_n,
        )
        summary = snapshot.get("summary") if isinstance(snapshot.get("summary"), dict) else {}
        open_incidents = int(summary.get("open_incidents") or 0)
        over_sla = int(summary.get("open_incidents_over_sla") or 0)
        routing_ready = int(summary.get("routing_ready_open_incidents") or 0)
        routing_ready_rate = float(summary.get("routing_ready_rate") or 0.0)
        if open_incidents <= 0:
            headline = "No open queue incidents; escalation queue is clear"
        else:
            headline = (
                f"{over_sla}/{open_incidents} open incidents over SLA "
                f"({int(max(1, min(168, incident_sla_hours)))}h) • routing ready {routing_ready}/{open_incidents}"
            )
        suggestions = self._derive_incident_escalation_suggestions(
            summary=summary,
            escalation_candidates=snapshot.get("escalation_candidates") if isinstance(snapshot.get("escalation_candidates"), list) else [],
            ownership_gaps=snapshot.get("ownership_gaps") if isinstance(snapshot.get("ownership_gaps"), list) else [],
        )
        summary_markdown = self._render_incident_escalation_summary_markdown(
            metric_date=metric_date,
            project_id=project_id,
            incident_sla_hours=int(max(1, min(168, incident_sla_hours))),
            snapshot=snapshot,
            suggestions=suggestions,
        )
        payload = {
            "project_id": project_id,
            "digest_kind": INTELLIGENCE_DIGEST_KIND_INCIDENT_ESCALATION_DAILY,
            "metric_date": metric_date.isoformat(),
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "incident_sla_hours": int(max(1, min(168, incident_sla_hours))),
            "routing_ready_rate": routing_ready_rate,
            "snapshot": snapshot,
            "suggestions": suggestions,
        }
        digest_id = self._upsert_digest(
            conn,
            project_id=project_id,
            digest_kind=INTELLIGENCE_DIGEST_KIND_INCIDENT_ESCALATION_DAILY,
            metric_date=metric_date,
            period_start=period_start,
            period_end=period_end,
            generated_by=generated_by,
            headline=headline,
            summary_markdown=summary_markdown,
            payload=payload,
        )
        return {
            "digest_id": str(digest_id),
            "project_id": project_id,
            "digest_kind": INTELLIGENCE_DIGEST_KIND_INCIDENT_ESCALATION_DAILY,
            "metric_date": metric_date.isoformat(),
            "headline": headline,
            "summary": summary,
            "routing_ready_rate": routing_ready_rate,
        }

    def _compute_daily_metrics(
        self,
        conn,
        *,
        project_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> DailyMetrics:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM claims c
                   WHERE c.project_id = %s
                     AND c.created_at >= %s
                     AND c.created_at < %s) AS claims_created,
                  (SELECT COUNT(*) FROM wiki_draft_changes d
                   WHERE d.project_id = %s
                     AND d.created_at >= %s
                     AND d.created_at < %s) AS drafts_created,
                  (SELECT COUNT(*) FROM wiki_draft_changes d
                   WHERE d.project_id = %s
                     AND d.status = 'approved'
                     AND d.updated_at >= %s
                     AND d.updated_at < %s) AS drafts_approved,
                  (SELECT COUNT(*) FROM wiki_draft_changes d
                   WHERE d.project_id = %s
                     AND d.status = 'rejected'
                     AND d.updated_at >= %s
                     AND d.updated_at < %s) AS drafts_rejected,
                  (SELECT COUNT(*) FROM wiki_statements s
                   WHERE s.project_id = %s
                     AND s.created_at >= %s
                     AND s.created_at < %s) AS statements_added,
                  (SELECT COUNT(*) FROM wiki_conflicts wc
                   WHERE wc.project_id = %s
                     AND wc.created_at >= %s
                     AND wc.created_at < %s) AS conflicts_opened,
                  (SELECT COUNT(*) FROM wiki_conflicts wc
                   WHERE wc.project_id = %s
                     AND wc.resolution_status IN ('resolved', 'dismissed')
                     AND wc.resolved_at >= %s
                     AND wc.resolved_at < %s) AS conflicts_resolved,
                  (SELECT COUNT(*) FROM wiki_draft_changes d
                   WHERE d.project_id = %s
                     AND d.status IN ('pending_review', 'blocked_conflict')) AS pending_drafts,
                  (SELECT COUNT(*) FROM wiki_conflicts wc
                   WHERE wc.project_id = %s
                     AND wc.resolution_status = 'open') AS open_conflicts,
                  (SELECT COUNT(*) FROM wiki_pages p
                   WHERE p.project_id = %s
                     AND p.updated_at >= %s
                     AND p.updated_at < %s) AS pages_touched
                """,
                (
                    project_id,
                    period_start,
                    period_end,
                    project_id,
                    period_start,
                    period_end,
                    project_id,
                    period_start,
                    period_end,
                    project_id,
                    period_start,
                    period_end,
                    project_id,
                    period_start,
                    period_end,
                    project_id,
                    period_start,
                    period_end,
                    project_id,
                    period_start,
                    period_end,
                    project_id,
                    project_id,
                    project_id,
                    period_start,
                    period_end,
                ),
            )
            row = cur.fetchone()

        claims_created = int(row[0] or 0)
        drafts_created = int(row[1] or 0)
        drafts_approved = int(row[2] or 0)
        drafts_rejected = int(row[3] or 0)
        statements_added = int(row[4] or 0)
        conflicts_opened = int(row[5] or 0)
        conflicts_resolved = int(row[6] or 0)
        pending_drafts = int(row[7] or 0)
        open_conflicts = int(row[8] or 0)
        pages_touched = int(row[9] or 0)

        # A simple interpretable score for weekly trend charts.
        knowledge_velocity = round(
            max(
                0.0,
                (drafts_approved * 1.0)
                + (conflicts_resolved * 0.7)
                + (statements_added * 0.35)
                + (claims_created * 0.1)
                - (open_conflicts * 0.25)
                - (pending_drafts * 0.1),
            ),
            3,
        )
        return DailyMetrics(
            claims_created=claims_created,
            drafts_created=drafts_created,
            drafts_approved=drafts_approved,
            drafts_rejected=drafts_rejected,
            statements_added=statements_added,
            conflicts_opened=conflicts_opened,
            conflicts_resolved=conflicts_resolved,
            pending_drafts=pending_drafts,
            open_conflicts=open_conflicts,
            pages_touched=pages_touched,
            knowledge_velocity=knowledge_velocity,
        )

    def _upsert_daily_metrics(self, conn, *, project_id: str, metric_date: date, metrics: DailyMetrics) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO knowledge_daily_metrics (
                  project_id,
                  metric_date,
                  claims_created,
                  drafts_created,
                  drafts_approved,
                  drafts_rejected,
                  statements_added,
                  conflicts_opened,
                  conflicts_resolved,
                  pending_drafts,
                  open_conflicts,
                  pages_touched,
                  knowledge_velocity,
                  computed_at
                )
                VALUES (
                  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                )
                ON CONFLICT (project_id, metric_date) DO UPDATE
                SET claims_created = EXCLUDED.claims_created,
                    drafts_created = EXCLUDED.drafts_created,
                    drafts_approved = EXCLUDED.drafts_approved,
                    drafts_rejected = EXCLUDED.drafts_rejected,
                    statements_added = EXCLUDED.statements_added,
                    conflicts_opened = EXCLUDED.conflicts_opened,
                    conflicts_resolved = EXCLUDED.conflicts_resolved,
                    pending_drafts = EXCLUDED.pending_drafts,
                    open_conflicts = EXCLUDED.open_conflicts,
                    pages_touched = EXCLUDED.pages_touched,
                    knowledge_velocity = EXCLUDED.knowledge_velocity,
                    computed_at = NOW()
                """,
                (
                    project_id,
                    metric_date,
                    metrics.claims_created,
                    metrics.drafts_created,
                    metrics.drafts_approved,
                    metrics.drafts_rejected,
                    metrics.statements_added,
                    metrics.conflicts_opened,
                    metrics.conflicts_resolved,
                    metrics.pending_drafts,
                    metrics.open_conflicts,
                    metrics.pages_touched,
                    metrics.knowledge_velocity,
                ),
            )

    def _upsert_digest(
        self,
        conn,
        *,
        project_id: str,
        digest_kind: str,
        metric_date: date,
        period_start: datetime,
        period_end: datetime,
        generated_by: str,
        headline: str,
        summary_markdown: str,
        payload: dict[str, Any],
    ):
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence_digests (
                  id,
                  project_id,
                  digest_kind,
                  digest_date,
                  period_start,
                  period_end,
                  status,
                  headline,
                  summary_markdown,
                  payload,
                  generated_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'ready', %s, %s, %s, %s)
                ON CONFLICT (project_id, digest_kind, digest_date) DO UPDATE
                SET period_start = EXCLUDED.period_start,
                    period_end = EXCLUDED.period_end,
                    status = 'ready',
                    headline = EXCLUDED.headline,
                    summary_markdown = EXCLUDED.summary_markdown,
                    payload = EXCLUDED.payload,
                    generated_by = EXCLUDED.generated_by,
                    generated_at = NOW(),
                    sent_at = NULL
                RETURNING id
                """,
                (
                    uuid4(),
                    project_id,
                    digest_kind,
                    metric_date,
                    period_start,
                    period_end,
                    headline,
                    summary_markdown,
                    Jsonb(payload),
                    generated_by,
                ),
            )
            return cur.fetchone()[0]

    def _load_daily_metrics_range(
        self,
        conn,
        *,
        project_id: str,
        from_date: date,
        to_date: date,
    ) -> list[dict[str, Any]]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  metric_date,
                  claims_created,
                  drafts_created,
                  drafts_approved,
                  drafts_rejected,
                  statements_added,
                  conflicts_opened,
                  conflicts_resolved,
                  pending_drafts,
                  open_conflicts,
                  pages_touched,
                  knowledge_velocity
                FROM knowledge_daily_metrics
                WHERE project_id = %s
                  AND metric_date >= %s
                  AND metric_date <= %s
                ORDER BY metric_date ASC
                """,
                (project_id, from_date, to_date),
            )
            rows = cur.fetchall()
        return [
            {
                "metric_date": row[0].isoformat(),
                "claims_created": int(row[1]),
                "drafts_created": int(row[2]),
                "drafts_approved": int(row[3]),
                "drafts_rejected": int(row[4]),
                "statements_added": int(row[5]),
                "conflicts_opened": int(row[6]),
                "conflicts_resolved": int(row[7]),
                "pending_drafts": int(row[8]),
                "open_conflicts": int(row[9]),
                "pages_touched": int(row[10]),
                "knowledge_velocity": float(row[11]),
            }
            for row in rows
        ]

    def _aggregate_weekly_rollup(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not rows:
            return {
                "days_covered": 0,
                "claims_created": 0,
                "drafts_created": 0,
                "drafts_approved": 0,
                "drafts_rejected": 0,
                "statements_added": 0,
                "conflicts_opened": 0,
                "conflicts_resolved": 0,
                "pages_touched": 0,
                "pending_drafts_end": 0,
                "open_conflicts_end": 0,
                "knowledge_velocity_sum": 0.0,
                "knowledge_velocity_avg": 0.0,
            }
        return {
            "days_covered": len(rows),
            "claims_created": sum(row["claims_created"] for row in rows),
            "drafts_created": sum(row["drafts_created"] for row in rows),
            "drafts_approved": sum(row["drafts_approved"] for row in rows),
            "drafts_rejected": sum(row["drafts_rejected"] for row in rows),
            "statements_added": sum(row["statements_added"] for row in rows),
            "conflicts_opened": sum(row["conflicts_opened"] for row in rows),
            "conflicts_resolved": sum(row["conflicts_resolved"] for row in rows),
            "pages_touched": sum(row["pages_touched"] for row in rows),
            "pending_drafts_end": int(rows[-1]["pending_drafts"]),
            "open_conflicts_end": int(rows[-1]["open_conflicts"]),
            "knowledge_velocity_sum": round(sum(row["knowledge_velocity"] for row in rows), 3),
            "knowledge_velocity_avg": round(sum(row["knowledge_velocity"] for row in rows) / max(len(rows), 1), 3),
        }

    def _build_weekly_trend_breakdown(
        self,
        *,
        current_rollup: dict[str, Any],
        previous_rollup: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        keys = [
            "claims_created",
            "drafts_created",
            "drafts_approved",
            "drafts_rejected",
            "statements_added",
            "conflicts_opened",
            "conflicts_resolved",
            "pages_touched",
            "knowledge_velocity_sum",
            "knowledge_velocity_avg",
            "pending_drafts_end",
            "open_conflicts_end",
        ]
        breakdown: dict[str, dict[str, Any]] = {}
        for key in keys:
            current = float(current_rollup.get(key, 0.0))
            previous = float(previous_rollup.get(key, 0.0))
            delta_abs = current - previous
            if previous == 0:
                delta_pct = 100.0 if current > 0 else 0.0
            else:
                delta_pct = (delta_abs / previous) * 100.0
            breakdown[key] = {
                "current": round(current, 3),
                "previous": round(previous, 3),
                "delta_abs": round(delta_abs, 3),
                "delta_pct": round(delta_pct, 2),
            }
        return breakdown

    def _collect_key_learnings(
        self,
        conn,
        *,
        project_id: str,
        period_start: datetime,
        period_end: datetime,
        limit: int,
    ) -> list[dict[str, Any]]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  d.id::text,
                  COALESCE(p.title, c.entity_key, 'unknown'),
                  COALESCE(p.slug, c.entity_key, 'unknown'),
                  COALESCE(c.claim_text, ''),
                  d.decision,
                  d.confidence,
                  d.updated_at
                FROM wiki_draft_changes d
                LEFT JOIN claims c ON c.id = d.claim_id
                LEFT JOIN wiki_pages p ON p.id = d.page_id
                WHERE d.project_id = %s
                  AND d.status = 'approved'
                  AND d.updated_at >= %s
                  AND d.updated_at < %s
                ORDER BY d.confidence DESC, d.updated_at DESC
                LIMIT %s
                """,
                (project_id, period_start, period_end, limit),
            )
            rows = cur.fetchall()
        return [
            {
                "draft_id": row[0],
                "page_title": row[1],
                "page_slug": row[2],
                "claim_text": row[3],
                "decision": row[4],
                "confidence": float(row[5]),
                "approved_at": row[6].isoformat(),
            }
            for row in rows
        ]

    def _collect_moderation_backlog(self, conn, *, project_id: str, limit: int) -> list[dict[str, Any]]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  d.id::text,
                  COALESCE(p.title, c.entity_key, 'unknown'),
                  COALESCE(p.slug, c.entity_key, 'unknown'),
                  d.decision,
                  d.created_at,
                  EXTRACT(EPOCH FROM (NOW() - d.created_at)) / 3600.0 AS age_hours
                FROM wiki_draft_changes d
                LEFT JOIN claims c ON c.id = d.claim_id
                LEFT JOIN wiki_pages p ON p.id = d.page_id
                WHERE d.project_id = %s
                  AND d.status IN ('pending_review', 'blocked_conflict')
                ORDER BY d.created_at ASC
                LIMIT %s
                """,
                (project_id, limit),
            )
            rows = cur.fetchall()
        return [
            {
                "draft_id": row[0],
                "page_title": row[1],
                "page_slug": row[2],
                "decision": row[3],
                "created_at": row[4].isoformat(),
                "age_hours": round(float(row[5] or 0.0), 2),
            }
            for row in rows
        ]

    def _collect_open_conflicts(self, conn, *, project_id: str, limit: int) -> list[dict[str, Any]]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  wc.id::text,
                  COALESCE(p.title, 'unknown'),
                  wc.conflict_type,
                  wc.created_at,
                  wc.details
                FROM wiki_conflicts wc
                LEFT JOIN wiki_pages p ON p.id = wc.page_id
                WHERE wc.project_id = %s
                  AND wc.resolution_status = 'open'
                ORDER BY wc.created_at DESC
                LIMIT %s
                """,
                (project_id, limit),
            )
            rows = cur.fetchall()
        return [
            {
                "conflict_id": row[0],
                "page_title": row[1],
                "conflict_type": row[2],
                "created_at": row[3].isoformat(),
                "details": row[4],
            }
            for row in rows
        ]

    def _queue_incident_age_bucket(self, age_minutes: float | None) -> str:
        if age_minutes is None:
            return "unknown"
        if age_minutes < 60.0:
            return "under_1h"
        if age_minutes < 240.0:
            return "between_1h_4h"
        if age_minutes < 720.0:
            return "between_4h_12h"
        if age_minutes < 1440.0:
            return "between_12h_24h"
        if age_minutes < 4320.0:
            return "between_24h_72h"
        return "over_72h"

    def _collect_incident_escalation_snapshot(
        self,
        conn,
        *,
        project_id: str,
        period_end: datetime,
        incident_sla_hours: int,
        top_n: int,
    ) -> dict[str, Any]:
        sla_hours = int(max(1, min(168, incident_sla_hours)))
        incident_sla_minutes = sla_hours * 60
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH queue_stats AS (
                  SELECT
                    COUNT(*) FILTER (WHERE status IN ('queued', 'running', 'cancel_requested'))::integer AS depth_total,
                    COUNT(*) FILTER (WHERE status = 'queued')::integer AS queued,
                    COUNT(*) FILTER (WHERE status = 'running')::integer AS running,
                    MIN(created_at) FILTER (WHERE status = 'queued') AS oldest_queued_at
                  FROM gatekeeper_calibration_operation_runs
                  WHERE project_id = %s
                )
                SELECT
                  i.id::text,
                  i.project_id,
                  i.status,
                  i.trigger_health,
                  i.external_provider,
                  i.external_ticket_id,
                  i.external_ticket_url,
                  i.opened_at,
                  i.last_sync_at,
                  o.owner_name,
                  o.owner_contact,
                  o.oncall_channel,
                  o.escalation_channel,
                  c.paused_until,
                  c.pause_reason,
                  c.queue_depth_warn,
                  c.worker_lag_sla_minutes,
                  qs.depth_total,
                  qs.queued,
                  qs.running,
                  qs.oldest_queued_at
                FROM gatekeeper_calibration_queue_incidents i
                LEFT JOIN gatekeeper_calibration_queue_ownership o
                  ON o.project_id = i.project_id
                LEFT JOIN gatekeeper_calibration_queue_controls c
                  ON c.project_id = i.project_id
                CROSS JOIN queue_stats qs
                WHERE i.project_id = %s
                  AND i.status = 'open'
                  AND i.resolved_at IS NULL
                ORDER BY i.opened_at ASC
                LIMIT %s
                """,
                (
                    project_id,
                    project_id,
                    max(1, min(250, int(top_n) * 3)),
                ),
            )
            rows = cur.fetchall()

        now = period_end
        age_buckets = {key: 0 for key in _QUEUE_INCIDENT_AGE_BUCKET_ORDER}
        escalation_candidates: list[dict[str, Any]] = []
        ownership_gaps: list[dict[str, Any]] = []
        open_over_sla = 0
        critical_open = 0
        missing_owner = 0
        missing_oncall = 0
        missing_escalation = 0
        without_ticket = 0
        routing_ready = 0
        paused_open = 0

        for row in rows:
            trigger_health = str(row[3] or "critical").strip().lower() or "critical"
            if trigger_health not in {"healthy", "watch", "critical"}:
                trigger_health = "critical"
            queue_depth_warn = max(1, int(row[15] or 12))
            queue_depth = int(row[17] or 0)
            queued = int(row[18] or 0)
            running = int(row[19] or 0)
            oldest_queued_at = row[20] if isinstance(row[20], datetime) else None
            queue_oldest_age_minutes = (
                round(max(0.0, (now - oldest_queued_at).total_seconds() / 60.0), 3) if oldest_queued_at is not None else None
            )
            incident_opened_at = row[7] if isinstance(row[7], datetime) else None
            incident_age_minutes = (
                round(max(0.0, (now - incident_opened_at).total_seconds() / 60.0), 3) if incident_opened_at is not None else None
            )
            paused_until = row[13] if isinstance(row[13], datetime) else None
            pause_active = paused_until is not None and paused_until > now
            if pause_active:
                paused_open += 1

            owner_name = str(row[9] or "").strip()
            owner_contact = str(row[10] or "").strip()
            oncall_channel = str(row[11] or "").strip()
            escalation_channel = str(row[12] or "").strip()

            ticket_id = str(row[5] or "").strip()
            ticket_url = str(row[6] or "").strip()
            has_ticket = bool(ticket_id or ticket_url)
            over_sla = incident_age_minutes is not None and incident_age_minutes >= incident_sla_minutes

            missing_fields: list[str] = []
            if not owner_name:
                missing_fields.append("owner_name")
                missing_owner += 1
            if not oncall_channel:
                missing_fields.append("oncall_channel")
                missing_oncall += 1
            if not escalation_channel:
                missing_fields.append("escalation_channel")
                missing_escalation += 1
            if not has_ticket:
                without_ticket += 1

            if over_sla:
                open_over_sla += 1
            if trigger_health == "critical":
                critical_open += 1
            if not missing_fields and has_ticket:
                routing_ready += 1

            age_bucket = self._queue_incident_age_bucket(incident_age_minutes)
            age_buckets[age_bucket] = int(age_buckets.get(age_bucket, 0)) + 1

            risk_score = 0
            if trigger_health == "critical":
                risk_score += 4
            elif trigger_health == "watch":
                risk_score += 2
            if queue_depth >= queue_depth_warn:
                risk_score += 1
            if queue_depth >= queue_depth_warn * 2:
                risk_score += 1
            if incident_age_minutes is not None:
                if incident_age_minutes >= 60.0:
                    risk_score += 1
                if incident_age_minutes >= 240.0:
                    risk_score += 2
                if incident_age_minutes >= 1440.0:
                    risk_score += 2
            if over_sla:
                risk_score += 2
            if pause_active:
                risk_score += 1
            if not has_ticket:
                risk_score += 2
            risk_score += len(missing_fields)

            if "owner_name" in missing_fields:
                recommended_action = "assign_owner_now"
            elif "oncall_channel" in missing_fields:
                recommended_action = "set_oncall_channel"
            elif "escalation_channel" in missing_fields:
                recommended_action = "set_escalation_channel"
            elif not has_ticket:
                recommended_action = "attach_or_create_ticket"
            elif over_sla and escalation_channel:
                recommended_action = "escalate_to_escalation_channel"
            elif over_sla and oncall_channel:
                recommended_action = "escalate_to_oncall_channel"
            else:
                recommended_action = "monitor_until_next_sync"

            ownership_gap = bool(missing_fields)
            if ownership_gap:
                ownership_gaps.append(
                    {
                        "project_id": str(row[1] or project_id),
                        "missing_fields": missing_fields,
                        "gap_score": int(len(missing_fields) + (3 if trigger_health == "critical" else 1 if trigger_health == "watch" else 0)),
                        "ownership": {
                            "owner_name": owner_name or None,
                            "owner_contact": owner_contact or None,
                            "oncall_channel": oncall_channel or None,
                            "escalation_channel": escalation_channel or None,
                        },
                    }
                )

            escalation_candidates.append(
                {
                    "incident_id": str(row[0] or ""),
                    "project_id": str(row[1] or project_id),
                    "health": trigger_health,
                    "external_provider": str(row[4] or "webhook"),
                    "opened_at": incident_opened_at.isoformat() if incident_opened_at is not None else None,
                    "last_sync_at": row[8].isoformat() if isinstance(row[8], datetime) else None,
                    "age_minutes": incident_age_minutes,
                    "age_bucket": age_bucket,
                    "over_sla": bool(over_sla),
                    "risk_score": int(risk_score),
                    "recommended_action": recommended_action,
                    "ticket_id": ticket_id or None,
                    "ticket_url": ticket_url or None,
                    "has_ticket": has_ticket,
                    "queue": {
                        "depth_total": queue_depth,
                        "queued": queued,
                        "running": running,
                        "oldest_queued_age_minutes": queue_oldest_age_minutes,
                        "depth_warn_threshold": queue_depth_warn,
                    },
                    "control": {
                        "pause_active": bool(pause_active),
                        "paused_until": paused_until.isoformat() if paused_until is not None else None,
                        "pause_reason": str(row[14] or "").strip() or None,
                        "worker_lag_sla_minutes": max(1, int(row[16] or 20)),
                    },
                    "ownership": {
                        "owner_name": owner_name or None,
                        "owner_contact": owner_contact or None,
                        "oncall_channel": oncall_channel or None,
                        "escalation_channel": escalation_channel or None,
                    },
                    "missing_fields": missing_fields,
                }
            )

        escalation_candidates.sort(
            key=lambda item: (
                0 if bool(item.get("over_sla")) else 1,
                -int(item.get("risk_score") or 0),
                -float(item.get("age_minutes") or 0.0),
                str(item.get("project_id") or ""),
            )
        )
        ownership_gaps.sort(
            key=lambda item: (
                -int(item.get("gap_score") or 0),
                str(item.get("project_id") or ""),
            )
        )

        open_total = len(escalation_candidates)
        summary = {
            "open_incidents": open_total,
            "open_incidents_over_sla": int(open_over_sla),
            "critical_open_incidents": int(critical_open),
            "incidents_missing_owner": int(missing_owner),
            "incidents_missing_oncall_channel": int(missing_oncall),
            "incidents_missing_escalation_channel": int(missing_escalation),
            "incidents_without_ticket": int(without_ticket),
            "routing_ready_open_incidents": int(routing_ready),
            "routing_ready_rate": round(float(routing_ready) / float(max(1, open_total)), 4),
            "ownership_gap_incidents": len(ownership_gaps),
            "pause_active_open_incidents": int(paused_open),
        }
        return {
            "generated_at": now.isoformat(),
            "incident_sla_hours": sla_hours,
            "summary": summary,
            "age_buckets": age_buckets,
            "escalation_candidates": escalation_candidates[: max(1, min(50, int(top_n)))],
            "over_sla_candidates": [
                item for item in escalation_candidates if bool(item.get("over_sla"))
            ][: max(1, min(20, int(top_n)))],
            "ownership_gaps": ownership_gaps[: max(1, min(50, int(top_n) * 2))],
        }

    def _derive_incident_escalation_suggestions(
        self,
        *,
        summary: dict[str, Any],
        escalation_candidates: list[dict[str, Any]],
        ownership_gaps: list[dict[str, Any]],
    ) -> list[str]:
        suggestions: list[str] = []
        over_sla = int(summary.get("open_incidents_over_sla") or 0)
        open_total = int(summary.get("open_incidents") or 0)
        if over_sla > 0:
            suggestions.append(f"Escalate over-SLA incidents now: {over_sla} open tickets exceeded SLA.")
        if int(summary.get("incidents_without_ticket") or 0) > 0:
            suggestions.append("Create or attach missing tickets for unresolved incidents before next sync.")
        if int(summary.get("incidents_missing_owner") or 0) > 0:
            suggestions.append("Assign ownership for unresolved incidents to avoid escalation dead-ends.")
        if int(summary.get("incidents_missing_oncall_channel") or 0) > 0:
            suggestions.append("Set on-call channels for projects with unresolved incidents.")
        if int(summary.get("incidents_missing_escalation_channel") or 0) > 0:
            suggestions.append("Set escalation channels for projects with unresolved incidents.")
        if open_total > 0 and float(summary.get("routing_ready_rate") or 0.0) < 0.7:
            suggestions.append("Routing readiness below 70%; prioritize ownership/contact hygiene.")
        if escalation_candidates:
            highest = escalation_candidates[0]
            if bool(highest.get("over_sla")):
                suggestions.append(
                    f"Highest risk incident: {highest.get('project_id')} ({highest.get('recommended_action')})."
                )
        if ownership_gaps and not suggestions:
            suggestions.append("Close ownership gaps to improve escalation responsiveness.")
        if not suggestions:
            suggestions.append("No urgent escalation actions. Continue routine monitoring.")
        return suggestions

    def _render_incident_escalation_summary_markdown(
        self,
        *,
        metric_date: date,
        project_id: str,
        incident_sla_hours: int,
        snapshot: dict[str, Any],
        suggestions: list[str],
    ) -> str:
        summary = snapshot.get("summary") if isinstance(snapshot.get("summary"), dict) else {}
        over_sla_candidates = snapshot.get("over_sla_candidates") if isinstance(snapshot.get("over_sla_candidates"), list) else []
        escalation_candidates = (
            snapshot.get("escalation_candidates") if isinstance(snapshot.get("escalation_candidates"), list) else []
        )
        ownership_gaps = snapshot.get("ownership_gaps") if isinstance(snapshot.get("ownership_gaps"), list) else []
        age_buckets = snapshot.get("age_buckets") if isinstance(snapshot.get("age_buckets"), dict) else {}

        lines = [
            f"# Queue Incident Escalation Pulse {metric_date.isoformat()}",
            "",
            f"Project: `{project_id}`",
            "",
            "## Summary",
            f"- Open incidents: {int(summary.get('open_incidents') or 0)}",
            f"- Over SLA ({incident_sla_hours}h): {int(summary.get('open_incidents_over_sla') or 0)}",
            f"- Critical open incidents: {int(summary.get('critical_open_incidents') or 0)}",
            f"- Routing-ready incidents: {int(summary.get('routing_ready_open_incidents') or 0)} ({float(summary.get('routing_ready_rate') or 0.0) * 100:.1f}%)",
            f"- Missing owner/on-call/escalation: {int(summary.get('incidents_missing_owner') or 0)}/{int(summary.get('incidents_missing_oncall_channel') or 0)}/{int(summary.get('incidents_missing_escalation_channel') or 0)}",
            f"- Incidents without ticket: {int(summary.get('incidents_without_ticket') or 0)}",
            "",
            "## Age Buckets",
            f"- under_1h: {int(age_buckets.get('under_1h') or 0)}",
            f"- 1h-4h: {int(age_buckets.get('between_1h_4h') or 0)}",
            f"- 4h-12h: {int(age_buckets.get('between_4h_12h') or 0)}",
            f"- 12h-24h: {int(age_buckets.get('between_12h_24h') or 0)}",
            f"- 24h-72h: {int(age_buckets.get('between_24h_72h') or 0)}",
            f"- over_72h: {int(age_buckets.get('over_72h') or 0)}",
            "",
            "## Over-SLA Candidates",
        ]
        if over_sla_candidates:
            for item in over_sla_candidates:
                lines.append(
                    f"- `{item.get('project_id')}` age={item.get('age_minutes')}m "
                    f"provider={item.get('external_provider')} "
                    f"action={item.get('recommended_action')} "
                    f"ticket={(item.get('ticket_id') or 'missing')}"
                )
        else:
            lines.append("- No over-SLA incidents.")

        lines.extend(["", "## Top Open Incidents"])
        if escalation_candidates:
            for item in escalation_candidates[:10]:
                lines.append(
                    f"- `{item.get('project_id')}` risk={item.get('risk_score')} "
                    f"health={item.get('health')} over_sla={bool(item.get('over_sla'))} "
                    f"missing={','.join(item.get('missing_fields') or []) or 'none'}"
                )
        else:
            lines.append("- No open incidents.")

        lines.extend(["", "## Ownership Gaps"])
        if ownership_gaps:
            for item in ownership_gaps[:10]:
                lines.append(
                    f"- `{item.get('project_id')}` missing={','.join(item.get('missing_fields') or [])} "
                    f"(gap_score={item.get('gap_score')})"
                )
        else:
            lines.append("- No ownership gaps across open incidents.")

        lines.extend(["", "## Suggested Actions"])
        lines.extend([f"- {item}" for item in suggestions] if suggestions else ["- No urgent actions."])
        return "\n".join(lines).rstrip() + "\n"

    def _derive_suggestions(
        self,
        metrics: DailyMetrics,
        moderation_backlog: list[dict[str, Any]],
        open_conflicts: list[dict[str, Any]],
    ) -> list[str]:
        suggestions: list[str] = []
        if metrics.pending_drafts >= 10:
            suggestions.append("Prioritize moderation queue: pending drafts crossed 10.")
        if metrics.open_conflicts >= 5:
            suggestions.append("Run conflict review session: open contradictions reached 5+.")
        if metrics.knowledge_velocity < 1.0 and metrics.claims_created > 0:
            suggestions.append("Conversion is low: many claims are not turning into approved knowledge.")
        if moderation_backlog:
            oldest_hours = max(item.get("age_hours", 0) for item in moderation_backlog)
            if oldest_hours >= 24:
                suggestions.append("Oldest pending draft is older than 24 hours.")
        if open_conflicts and metrics.conflicts_resolved == 0:
            suggestions.append("No conflicts resolved today despite open conflict backlog.")
        return suggestions

    def _derive_weekly_suggestions(
        self,
        *,
        current_rollup: dict[str, Any],
        trend_breakdown: dict[str, dict[str, Any]],
        moderation_backlog: list[dict[str, Any]],
        open_conflicts: list[dict[str, Any]],
    ) -> list[str]:
        suggestions: list[str] = []
        if current_rollup.get("drafts_approved", 0) < current_rollup.get("drafts_created", 0) * 0.5:
            suggestions.append("Approval throughput is below 50% of created drafts this week.")
        if trend_breakdown["open_conflicts_end"]["delta_abs"] > 0:
            suggestions.append("Open conflicts increased week-over-week; prioritize conflict triage.")
        if trend_breakdown["knowledge_velocity_avg"]["delta_abs"] < 0:
            suggestions.append("Knowledge velocity average dropped week-over-week; review extraction quality.")
        if moderation_backlog:
            oldest_hours = max(item.get("age_hours", 0) for item in moderation_backlog)
            if oldest_hours >= 72:
                suggestions.append("Moderation backlog contains drafts older than 72 hours.")
        if open_conflicts and current_rollup.get("conflicts_resolved", 0) == 0:
            suggestions.append("No conflicts resolved this week despite unresolved contradictions.")
        return suggestions

    def _render_summary_markdown(
        self,
        *,
        metric_date: date,
        project_id: str,
        metrics: DailyMetrics,
        key_learnings: list[dict[str, Any]],
        moderation_backlog: list[dict[str, Any]],
        open_conflicts: list[dict[str, Any]],
        suggestions: list[str],
    ) -> str:
        lines = [
            f"# Intelligence Pulse {metric_date.isoformat()}",
            "",
            f"Project: `{project_id}`",
            "",
            "## Metrics",
            f"- Claims created: {metrics.claims_created}",
            f"- Drafts created: {metrics.drafts_created}",
            f"- Drafts approved: {metrics.drafts_approved}",
            f"- Drafts rejected: {metrics.drafts_rejected}",
            f"- Statements added: {metrics.statements_added}",
            f"- Conflicts opened/resolved: {metrics.conflicts_opened}/{metrics.conflicts_resolved}",
            f"- Pending drafts: {metrics.pending_drafts}",
            f"- Open conflicts: {metrics.open_conflicts}",
            f"- Knowledge velocity: {metrics.knowledge_velocity}",
            "",
            "## Key Learnings",
        ]
        if key_learnings:
            lines.extend(
                [
                    f"- {item['claim_text']} (page: `{item['page_slug']}`, confidence: {item['confidence']:.2f})"
                    for item in key_learnings
                ]
            )
        else:
            lines.append("- No approved learnings for the selected day.")

        lines.extend(["", "## Moderation Backlog"])
        if moderation_backlog:
            lines.extend(
                [
                    f"- Draft `{item['draft_id']}` on `{item['page_slug']}` pending for {item['age_hours']}h"
                    for item in moderation_backlog
                ]
            )
        else:
            lines.append("- Queue is healthy: no pending drafts.")

        lines.extend(["", "## Open Conflicts"])
        if open_conflicts:
            lines.extend(
                [f"- Conflict `{item['conflict_id']}` ({item['conflict_type']}) on `{item['page_title']}`" for item in open_conflicts]
            )
        else:
            lines.append("- No open conflicts.")

        lines.extend(["", "## Suggested Actions"])
        if suggestions:
            lines.extend([f"- {item}" for item in suggestions])
        else:
            lines.append("- No urgent actions.")

        return "\n".join(lines).rstrip() + "\n"

    def _render_weekly_summary_markdown(
        self,
        *,
        project_id: str,
        week_start: date,
        week_end: date,
        current_rollup: dict[str, Any],
        previous_rollup: dict[str, Any],
        trend_breakdown: dict[str, dict[str, Any]],
        daily_velocity: list[dict[str, Any]],
        key_learnings: list[dict[str, Any]],
        moderation_backlog: list[dict[str, Any]],
        open_conflicts: list[dict[str, Any]],
        suggestions: list[str],
    ) -> str:
        lines = [
            f"# Weekly Intelligence Pulse {week_start.isoformat()}..{week_end.isoformat()}",
            "",
            f"Project: `{project_id}`",
            "",
            "## Weekly Rollup",
            f"- Claims created: {current_rollup['claims_created']}",
            f"- Drafts created: {current_rollup['drafts_created']}",
            f"- Drafts approved: {current_rollup['drafts_approved']}",
            f"- Drafts rejected: {current_rollup['drafts_rejected']}",
            f"- Statements added: {current_rollup['statements_added']}",
            f"- Conflicts opened/resolved: {current_rollup['conflicts_opened']}/{current_rollup['conflicts_resolved']}",
            f"- Pending drafts (end of week): {current_rollup['pending_drafts_end']}",
            f"- Open conflicts (end of week): {current_rollup['open_conflicts_end']}",
            f"- Knowledge velocity (avg): {current_rollup['knowledge_velocity_avg']}",
            "",
            "## Trend Breakdown (WoW)",
            f"- Drafts approved delta: {trend_breakdown['drafts_approved']['delta_abs']} ({trend_breakdown['drafts_approved']['delta_pct']}%)",
            f"- Statements added delta: {trend_breakdown['statements_added']['delta_abs']} ({trend_breakdown['statements_added']['delta_pct']}%)",
            f"- Conflicts opened delta: {trend_breakdown['conflicts_opened']['delta_abs']} ({trend_breakdown['conflicts_opened']['delta_pct']}%)",
            f"- Open conflicts end delta: {trend_breakdown['open_conflicts_end']['delta_abs']} ({trend_breakdown['open_conflicts_end']['delta_pct']}%)",
            f"- Knowledge velocity avg delta: {trend_breakdown['knowledge_velocity_avg']['delta_abs']} ({trend_breakdown['knowledge_velocity_avg']['delta_pct']}%)",
            "",
            "## Daily Velocity",
        ]
        if daily_velocity:
            lines.extend(
                [
                    f"- {item['metric_date']}: velocity={item['knowledge_velocity']} approvals={item['drafts_approved']} conflicts={item['conflicts_opened']}"
                    for item in daily_velocity
                ]
            )
        else:
            lines.append("- No daily metrics available for this week.")

        lines.extend(["", "## Key Learnings"])
        if key_learnings:
            lines.extend(
                [
                    f"- {item['claim_text']} (page: `{item['page_slug']}`, confidence: {item['confidence']:.2f})"
                    for item in key_learnings
                ]
            )
        else:
            lines.append("- No approved learnings this week.")

        lines.extend(["", "## Moderation Backlog"])
        if moderation_backlog:
            lines.extend(
                [
                    f"- Draft `{item['draft_id']}` on `{item['page_slug']}` pending for {item['age_hours']}h"
                    for item in moderation_backlog
                ]
            )
        else:
            lines.append("- Queue is healthy: no pending drafts.")

        lines.extend(["", "## Open Conflicts"])
        if open_conflicts:
            lines.extend(
                [f"- Conflict `{item['conflict_id']}` ({item['conflict_type']}) on `{item['page_title']}`" for item in open_conflicts]
            )
        else:
            lines.append("- No open conflicts.")

        lines.extend(["", "## Suggested Actions"])
        if suggestions:
            lines.extend([f"- {item}" for item in suggestions])
        else:
            lines.append("- No urgent actions.")

        lines.extend(["", "## Previous Week Baseline"])
        lines.append(f"- Drafts approved: {previous_rollup['drafts_approved']}")
        lines.append(f"- Statements added: {previous_rollup['statements_added']}")
        lines.append(f"- Open conflicts end: {previous_rollup['open_conflicts_end']}")
        lines.append(f"- Knowledge velocity (avg): {previous_rollup['knowledge_velocity_avg']}")

        return "\n".join(lines).rstrip() + "\n"
