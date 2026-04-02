from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import re
from typing import Any
from uuid import UUID, uuid4

try:
    from psycopg.types.json import Jsonb
except Exception:  # pragma: no cover - offline mode without psycopg runtime
    class Jsonb:  # type: ignore[override]
        def __init__(self, obj: Any):
            self.obj = obj


TOKEN_RE = re.compile(r"[a-zA-Zа-яА-Я0-9_#:-]{2,}")

STOP_WORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "only",
    "will",
    "your",
    "you",
    "are",
    "was",
    "were",
    "is",
    "to",
    "of",
    "on",
    "in",
    "at",
    "a",
    "an",
    "и",
    "в",
    "на",
    "по",
    "с",
    "от",
    "до",
    "как",
    "что",
    "это",
    "для",
    "или",
    "не",
    "но",
}

RESTRICTIVE_TOKENS = {
    "must",
    "required",
    "only",
    "forbidden",
    "blocked",
    "closed",
    "ban",
    "cannot",
    "can’t",
    "can't",
    "deny",
    "запрещ",
    "обязат",
    "только",
    "закрыт",
    "нельзя",
    "доступ",
    "требует",
    "card-only",
    "card_only",
}

RELAXING_TOKENS = {
    "optional",
    "allowed",
    "open",
    "available",
    "without",
    "permit",
    "reopen",
    "доступен",
    "разреш",
    "можно",
    "открыт",
    "необяз",
}

FAILURE_TOKENS = {
    "error",
    "failed",
    "failure",
    "incident",
    "blocked",
    "timeout",
    "rollback",
    "bug",
    "ошибка",
    "сбой",
    "инцидент",
    "полом",
    "провал",
}

BYPASS_TOKENS = {
    "without",
    "skip",
    "bypass",
    "override",
    "manual",
    "handwritten",
    "без",
    "вручную",
    "обход",
    "пропустить",
}


@dataclass(slots=True)
class PolicyChangeInput:
    policy_id: str
    new_statement: str
    old_statement: str | None = None
    entity_key: str | None = None
    category: str | None = None
    metadata: dict[str, Any] | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any], *, index: int = 0) -> "PolicyChangeInput":
        if not isinstance(payload, dict):
            raise ValueError("policy change item must be an object")
        policy_id_raw = str(payload.get("policy_id") or payload.get("id") or f"policy_{index + 1}").strip()
        new_statement = str(payload.get("new_statement") or "").strip()
        if not new_statement:
            raise ValueError("policy change requires non-empty `new_statement`")
        old_statement_raw = payload.get("old_statement")
        old_statement = str(old_statement_raw).strip() if isinstance(old_statement_raw, str) and old_statement_raw.strip() else None
        entity_key_raw = payload.get("entity_key")
        entity_key = str(entity_key_raw).strip().lower() if isinstance(entity_key_raw, str) and entity_key_raw.strip() else None
        category_raw = payload.get("category")
        category = str(category_raw).strip().lower() if isinstance(category_raw, str) and category_raw.strip() else None
        metadata_raw = payload.get("metadata")
        metadata = dict(metadata_raw) if isinstance(metadata_raw, dict) else {}
        return cls(
            policy_id=policy_id_raw,
            new_statement=new_statement,
            old_statement=old_statement,
            entity_key=entity_key,
            category=category,
            metadata=metadata,
        )

    def keywords(self) -> set[str]:
        base = _tokenize(f"{self.new_statement} {self.old_statement or ''}")
        if self.entity_key:
            base |= _tokenize(self.entity_key)
        if self.category:
            base |= _tokenize(self.category)
        return base


@dataclass(slots=True)
class SessionSnapshot:
    session_id: str
    first_seen: datetime
    last_seen: datetime
    event_count: int
    text_corpus: str

    @classmethod
    def from_text(
        cls,
        *,
        session_id: str,
        text: str,
        event_count: int = 1,
        when: datetime | None = None,
    ) -> "SessionSnapshot":
        now = when or datetime.now(UTC)
        return cls(
            session_id=session_id,
            first_seen=now,
            last_seen=now,
            event_count=max(1, int(event_count)),
            text_corpus=text,
        )

    @property
    def tokens(self) -> set[str]:
        return _tokenize(self.text_corpus)


@dataclass(slots=True)
class SimulatorFinding:
    session_id: str
    policy_id: str
    entity_key: str | None
    category: str | None
    impact_kind: str
    severity: str
    impact_score: float
    rationale: str
    evidence_excerpt: str
    session_first_seen: datetime
    session_last_seen: datetime
    session_event_count: int
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "policy_id": self.policy_id,
            "entity_key": self.entity_key,
            "category": self.category,
            "impact_kind": self.impact_kind,
            "severity": self.severity,
            "impact_score": round(self.impact_score, 4),
            "rationale": self.rationale,
            "evidence_excerpt": self.evidence_excerpt,
            "session_first_seen": self.session_first_seen.isoformat(),
            "session_last_seen": self.session_last_seen.isoformat(),
            "session_event_count": int(self.session_event_count),
            "metadata": dict(self.metadata),
        }


class AgentSimulatorEngine:
    """Policy replay sandbox on historical sessions from events log."""

    def discover_projects(self, conn, *, limit: int = 500) -> list[str]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT project_id
                FROM events
                WHERE project_id IS NOT NULL
                  AND project_id <> ''
                GROUP BY project_id
                ORDER BY MAX(observed_at) DESC
                LIMIT %s
                """,
                (max(1, int(limit)),),
            )
            rows = cur.fetchall()
        return [str(row[0]) for row in rows]

    def run(
        self,
        conn,
        *,
        project_id: str,
        policy_changes: list[PolicyChangeInput] | list[dict[str, Any]],
        lookback_days: int = 14,
        max_sessions: int = 200,
        events_per_session: int = 80,
        relevance_floor: float = 0.22,
        max_findings: int = 1200,
        created_by: str = "simulator_script",
        persist: bool = True,
    ) -> dict[str, Any]:
        normalized_changes = self._normalize_policy_changes(policy_changes)
        now = datetime.now(UTC)
        run_id = uuid4()
        config = {
            "lookback_days": int(max(1, lookback_days)),
            "max_sessions": int(max(1, max_sessions)),
            "events_per_session": int(max(5, events_per_session)),
            "relevance_floor": float(max(0.0, min(1.0, relevance_floor))),
            "max_findings": int(max(1, max_findings)),
            "policy_count": len(normalized_changes),
            "policy_changes": [
                {
                    "policy_id": item.policy_id,
                    "new_statement": item.new_statement,
                    "old_statement": item.old_statement,
                    "entity_key": item.entity_key,
                    "category": item.category,
                    "metadata": dict(item.metadata or {}),
                }
                for item in normalized_changes
            ],
        }

        if persist:
            self._insert_run_start(
                conn,
                run_id=run_id,
                project_id=project_id,
                created_by=created_by,
                config=config,
                started_at=now,
            )

        result_payload = self._execute_simulation(
            conn,
            run_id=run_id,
            project_id=project_id,
            normalized_changes=normalized_changes,
            lookback_days=lookback_days,
            max_sessions=max_sessions,
            events_per_session=events_per_session,
            relevance_floor=relevance_floor,
            max_findings=max_findings,
            persist=persist,
        )
        result_payload.pop("_findings", None)
        return result_payload

    def process_queued_runs(
        self,
        conn,
        *,
        project_ids: list[str] | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        claimed = self._claim_queued_runs(conn, project_ids=project_ids, limit=limit)
        processed: list[dict[str, Any]] = []
        completed = 0
        failed = 0
        for item in claimed:
            run_id = item["run_id"]
            project_id = item["project_id"]
            config = item["config"]
            try:
                normalized_changes = self._normalize_policy_changes(list(config.get("policy_changes") or []))
                lookback_days = int(config.get("lookback_days", 14))
                max_sessions = int(config.get("max_sessions", 200))
                events_per_session = int(config.get("events_per_session", 80))
                relevance_floor = float(config.get("relevance_floor", 0.22))
                max_findings = int(config.get("max_findings", 1200))

                result_payload = self._execute_simulation(
                    conn,
                    run_id=run_id,
                    project_id=project_id,
                    normalized_changes=normalized_changes,
                    lookback_days=lookback_days,
                    max_sessions=max_sessions,
                    events_per_session=events_per_session,
                    relevance_floor=relevance_floor,
                    max_findings=max_findings,
                    persist=True,
                )
                completed += 1
                processed.append(
                    {
                        "run_id": str(run_id),
                        "project_id": project_id,
                        "status": "completed",
                        "findings_total": int(result_payload.get("findings_total", 0)),
                        "sessions_scanned": int(result_payload.get("sessions_scanned", 0)),
                    }
                )
            except Exception as exc:
                failed += 1
                processed.append(
                    {
                        "run_id": str(run_id),
                        "project_id": project_id,
                        "status": "failed",
                        "error": str(exc)[:300],
                    }
                )

        return {
            "status": "ok",
            "picked": len(claimed),
            "completed": completed,
            "failed": failed,
            "results": processed,
        }

    def _execute_simulation(
        self,
        conn,
        *,
        run_id: UUID,
        project_id: str,
        normalized_changes: list[PolicyChangeInput],
        lookback_days: int,
        max_sessions: int,
        events_per_session: int,
        relevance_floor: float,
        max_findings: int,
        persist: bool,
    ) -> dict[str, Any]:
        try:
            sessions = self._load_session_snapshots(
                conn,
                project_id=project_id,
                lookback_days=lookback_days,
                max_sessions=max_sessions,
                events_per_session=events_per_session,
            )
            sim = self.simulate_from_snapshots(
                policy_changes=normalized_changes,
                sessions=sessions,
                relevance_floor=relevance_floor,
                max_findings=max_findings,
            )
            result_payload = dict(sim)
            result_payload["run_id"] = str(run_id)
            result_payload["project_id"] = project_id
            result_payload["generated_at"] = datetime.now(UTC).isoformat()

            if persist:
                self._clear_findings(conn, run_id=run_id)
                self._insert_findings(conn, run_id=run_id, project_id=project_id, findings=sim["_findings"])
                self._mark_run_completed(
                    conn,
                    run_id=run_id,
                    sessions_scanned=int(sim["sessions_scanned"]),
                    findings_total=int(sim["findings_total"]),
                    result_payload={k: v for k, v in result_payload.items() if k != "_findings"},
                )
            return result_payload
        except Exception as exc:
            if persist:
                self._mark_run_failed(conn, run_id=run_id, error_message=str(exc))
            raise

    def simulate_from_snapshots(
        self,
        *,
        policy_changes: list[PolicyChangeInput] | list[dict[str, Any]],
        sessions: list[SessionSnapshot] | list[dict[str, Any]],
        relevance_floor: float = 0.22,
        max_findings: int = 1200,
    ) -> dict[str, Any]:
        normalized_changes = self._normalize_policy_changes(policy_changes)
        normalized_sessions = self._normalize_sessions(sessions)
        floor = max(0.0, min(1.0, float(relevance_floor)))
        max_items = max(1, int(max_findings))

        findings: list[SimulatorFinding] = []
        for session in normalized_sessions:
            session_tokens = session.tokens
            if not session_tokens:
                continue
            for policy in normalized_changes:
                finding = self._simulate_policy_on_session(policy=policy, session=session, session_tokens=session_tokens, floor=floor)
                if finding is not None:
                    findings.append(finding)
            if len(findings) >= max_items:
                break

        findings.sort(key=lambda item: item.impact_score, reverse=True)
        findings = findings[:max_items]
        summary = self._build_summary(policy_changes=normalized_changes, sessions=normalized_sessions, findings=findings)
        summary["_findings"] = findings
        return summary

    def _normalize_policy_changes(
        self,
        policy_changes: list[PolicyChangeInput] | list[dict[str, Any]],
    ) -> list[PolicyChangeInput]:
        normalized: list[PolicyChangeInput] = []
        for idx, item in enumerate(policy_changes):
            if isinstance(item, PolicyChangeInput):
                normalized.append(item)
            else:
                normalized.append(PolicyChangeInput.from_payload(item, index=idx))
        if not normalized:
            raise ValueError("at least one policy change is required")
        return normalized

    def _normalize_sessions(
        self,
        sessions: list[SessionSnapshot] | list[dict[str, Any]],
    ) -> list[SessionSnapshot]:
        normalized: list[SessionSnapshot] = []
        for item in sessions:
            if isinstance(item, SessionSnapshot):
                normalized.append(item)
                continue
            if not isinstance(item, dict):
                continue
            session_id = str(item.get("session_id") or "").strip()
            text = str(item.get("text_corpus") or item.get("text") or "").strip()
            if not session_id or not text:
                continue
            first_seen = _parse_datetime(item.get("first_seen")) or datetime.now(UTC)
            last_seen = _parse_datetime(item.get("last_seen")) or first_seen
            event_count_raw = item.get("event_count", 1)
            try:
                event_count = max(1, int(event_count_raw))
            except Exception:
                event_count = 1
            normalized.append(
                SessionSnapshot(
                    session_id=session_id,
                    first_seen=first_seen,
                    last_seen=last_seen,
                    event_count=event_count,
                    text_corpus=text,
                )
            )
        return normalized

    def _simulate_policy_on_session(
        self,
        *,
        policy: PolicyChangeInput,
        session: SessionSnapshot,
        session_tokens: set[str],
        floor: float,
    ) -> SimulatorFinding | None:
        policy_keywords = policy.keywords()
        if not policy_keywords:
            return None
        overlap_tokens = session_tokens & policy_keywords
        overlap_count = len(overlap_tokens)
        entity_bonus = 0.0
        category_bonus = 0.0
        if policy.entity_key and policy.entity_key in session_tokens:
            entity_bonus = 0.3
        if policy.category and policy.category in session_tokens:
            category_bonus = 0.12

        keyword_score = overlap_count / max(len(policy_keywords), 1)
        score = min(1.0, (keyword_score * 0.76) + entity_bonus + category_bonus)
        if score < floor:
            return None

        direction = _classify_direction(policy.old_statement, policy.new_statement)
        has_failure = bool(session_tokens & FAILURE_TOKENS)
        has_bypass = bool(session_tokens & BYPASS_TOKENS)

        impact_kind = "prompt_update"
        severity = "low"
        rationale_bits = [f"keyword_overlap={overlap_count}/{len(policy_keywords)}"]

        if direction == "restrictive":
            rationale_bits.append("direction=restrictive")
            if has_bypass:
                impact_kind = "policy_violation_risk"
                severity = "critical" if score >= 0.62 else "high"
                score = min(1.0, score + 0.28)
                rationale_bits.append("session_has_bypass_behavior")
            elif has_failure:
                impact_kind = "escalation_risk"
                severity = "high"
                score = min(1.0, score + 0.2)
                rationale_bits.append("session_has_failure_signals")
            else:
                impact_kind = "compliance_update"
                severity = "high" if score >= 0.66 else "medium"
                score = min(1.0, score + 0.12)
        elif direction == "relaxing":
            rationale_bits.append("direction=relaxing")
            if has_failure:
                impact_kind = "recovery_opportunity"
                severity = "medium"
                score = min(1.0, score + 0.15)
                rationale_bits.append("session_has_failure_signals")
            else:
                impact_kind = "policy_relief_update"
                severity = "low" if score < 0.55 else "medium"
        else:
            rationale_bits.append("direction=neutral_update")
            if score >= 0.7:
                severity = "medium"

        evidence_excerpt = _extract_relevant_excerpt(session.text_corpus, overlap_tokens, fallback=newline_safe(policy.new_statement))
        rationale = "; ".join(rationale_bits)

        return SimulatorFinding(
            session_id=session.session_id,
            policy_id=policy.policy_id,
            entity_key=policy.entity_key,
            category=policy.category,
            impact_kind=impact_kind,
            severity=severity,
            impact_score=round(score, 4),
            rationale=rationale,
            evidence_excerpt=evidence_excerpt,
            session_first_seen=session.first_seen,
            session_last_seen=session.last_seen,
            session_event_count=session.event_count,
            metadata={"overlap_tokens": sorted(list(overlap_tokens))[:12]},
        )

    def _build_summary(
        self,
        *,
        policy_changes: list[PolicyChangeInput],
        sessions: list[SessionSnapshot],
        findings: list[SimulatorFinding],
    ) -> dict[str, Any]:
        severity_counts: dict[str, int] = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        impact_kind_counts: dict[str, int] = {}
        policy_breakdown: dict[str, dict[str, Any]] = {}
        impacted_sessions: set[str] = set()

        for policy in policy_changes:
            policy_breakdown[policy.policy_id] = {
                "policy_id": policy.policy_id,
                "entity_key": policy.entity_key,
                "category": policy.category,
                "impacted_sessions": 0,
                "findings": 0,
                "max_score": 0.0,
            }

        policy_impacted_sessions: dict[str, set[str]] = {policy.policy_id: set() for policy in policy_changes}
        for item in findings:
            impacted_sessions.add(item.session_id)
            severity_counts[item.severity] = severity_counts.get(item.severity, 0) + 1
            impact_kind_counts[item.impact_kind] = impact_kind_counts.get(item.impact_kind, 0) + 1
            breakdown = policy_breakdown.get(item.policy_id)
            if breakdown is None:
                breakdown = {
                    "policy_id": item.policy_id,
                    "entity_key": item.entity_key,
                    "category": item.category,
                    "impacted_sessions": 0,
                    "findings": 0,
                    "max_score": 0.0,
                }
                policy_breakdown[item.policy_id] = breakdown
                policy_impacted_sessions[item.policy_id] = set()
            breakdown["findings"] = int(breakdown["findings"]) + 1
            breakdown["max_score"] = round(max(float(breakdown["max_score"]), float(item.impact_score)), 4)
            policy_impacted_sessions[item.policy_id].add(item.session_id)

        for policy_id, session_ids in policy_impacted_sessions.items():
            if policy_id in policy_breakdown:
                policy_breakdown[policy_id]["impacted_sessions"] = len(session_ids)

        sessions_scanned = len(sessions)
        impacted_sessions_count = len(impacted_sessions)
        high_critical = severity_counts.get("high", 0) + severity_counts.get("critical", 0)
        predicted_disruption_rate = round(
            (high_critical / max(sessions_scanned, 1)) * 100.0,
            2,
        )
        recommended_actions: list[str] = []
        if severity_counts.get("critical", 0) > 0:
            recommended_actions.append("Run staged rollout: critical policy_violation_risk findings detected.")
        if severity_counts.get("high", 0) >= 3:
            recommended_actions.append("Prepare fallback prompts and operator alerting for high-risk sessions.")
        if impacted_sessions_count == 0:
            recommended_actions.append("No immediate impact detected. Safe to test on canary traffic.")
        if not recommended_actions:
            recommended_actions.append("Run canary replay on recent sessions before full rollout.")

        top_findings = [item.as_dict() for item in findings[:20]]
        return {
            "mode": "policy_replay",
            "sessions_scanned": sessions_scanned,
            "policies_evaluated": len(policy_changes),
            "findings_total": len(findings),
            "impacted_sessions": impacted_sessions_count,
            "severity_counts": severity_counts,
            "impact_kind_counts": impact_kind_counts,
            "predicted_disruption_rate_pct": predicted_disruption_rate,
            "policy_breakdown": [policy_breakdown[key] for key in sorted(policy_breakdown.keys())],
            "top_findings": top_findings,
            "recommended_actions": recommended_actions,
        }

    def _load_session_snapshots(
        self,
        conn,
        *,
        project_id: str,
        lookback_days: int,
        max_sessions: int,
        events_per_session: int,
    ) -> list[SessionSnapshot]:
        since_ts = datetime.now(UTC) - timedelta(days=max(1, int(lookback_days)))
        max_sessions = max(1, int(max_sessions))
        events_per_session = max(5, int(events_per_session))

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT session_id
                FROM events
                WHERE project_id = %s
                  AND session_id IS NOT NULL
                  AND session_id <> ''
                  AND observed_at >= %s
                GROUP BY session_id
                ORDER BY MAX(observed_at) DESC
                LIMIT %s
                """,
                (project_id, since_ts, max_sessions),
            )
            rows = cur.fetchall()
        session_ids = [str(row[0]) for row in rows if row and row[0]]
        if not session_ids:
            return []

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  t.session_id,
                  t.observed_at,
                  t.event_type,
                  t.payload
                FROM (
                  SELECT
                    e.session_id,
                    e.observed_at,
                    e.event_type,
                    e.payload,
                    ROW_NUMBER() OVER (
                      PARTITION BY e.session_id
                      ORDER BY e.observed_at DESC
                    ) AS rn
                  FROM events e
                  WHERE e.project_id = %s
                    AND e.session_id = ANY(%s)
                ) t
                WHERE t.rn <= %s
                ORDER BY t.session_id ASC, t.observed_at ASC
                """,
                (project_id, session_ids, events_per_session),
            )
            event_rows = cur.fetchall()

        by_session: dict[str, dict[str, Any]] = {}
        for session_id, observed_at, event_type, payload in event_rows:
            sid = str(session_id)
            bucket = by_session.get(sid)
            if bucket is None:
                bucket = {
                    "first_seen": observed_at,
                    "last_seen": observed_at,
                    "event_count": 0,
                    "texts": [],
                }
                by_session[sid] = bucket

            bucket["event_count"] = int(bucket["event_count"]) + 1
            if observed_at < bucket["first_seen"]:
                bucket["first_seen"] = observed_at
            if observed_at > bucket["last_seen"]:
                bucket["last_seen"] = observed_at
            texts = bucket["texts"]
            texts.append(str(event_type))
            texts.extend(_extract_strings(payload, limit=80))
            if len(texts) > 320:
                del texts[:-320]

        snapshots: list[SessionSnapshot] = []
        for session_id in session_ids:
            bucket = by_session.get(session_id)
            if not bucket:
                continue
            text = _normalize_whitespace(" ".join(str(item) for item in bucket["texts"]))
            if not text:
                continue
            snapshots.append(
                SessionSnapshot(
                    session_id=session_id,
                    first_seen=bucket["first_seen"],
                    last_seen=bucket["last_seen"],
                    event_count=int(bucket["event_count"]),
                    text_corpus=text[:12000],
                )
            )
        return snapshots

    def _insert_run_start(
        self,
        conn,
        *,
        run_id: UUID,
        project_id: str,
        created_by: str,
        config: dict[str, Any],
        started_at: datetime,
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO agent_simulator_runs (
                  id, project_id, status, mode, created_by, config, result, sessions_scanned, findings_total, started_at
                )
                VALUES (%s, %s, 'running', 'policy_replay', %s, %s, '{}'::jsonb, 0, 0, %s)
                """,
                (run_id, project_id, created_by, Jsonb(config), started_at),
            )

    def _claim_queued_runs(
        self,
        conn,
        *,
        project_ids: list[str] | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        limit = max(1, int(limit))
        with conn.cursor() as cur:
            if project_ids:
                cur.execute(
                    """
                    WITH picked AS (
                      SELECT id
                      FROM agent_simulator_runs
                      WHERE status = 'queued'
                        AND project_id = ANY(%s)
                      ORDER BY created_at ASC
                      FOR UPDATE SKIP LOCKED
                      LIMIT %s
                    )
                    UPDATE agent_simulator_runs r
                    SET status = 'running',
                        started_at = COALESCE(r.started_at, NOW()),
                        finished_at = NULL,
                        error_message = NULL,
                        updated_at = NOW()
                    FROM picked
                    WHERE r.id = picked.id
                    RETURNING r.id, r.project_id, r.created_by, r.config
                    """,
                    (project_ids, limit),
                )
            else:
                cur.execute(
                    """
                    WITH picked AS (
                      SELECT id
                      FROM agent_simulator_runs
                      WHERE status = 'queued'
                      ORDER BY created_at ASC
                      FOR UPDATE SKIP LOCKED
                      LIMIT %s
                    )
                    UPDATE agent_simulator_runs r
                    SET status = 'running',
                        started_at = COALESCE(r.started_at, NOW()),
                        finished_at = NULL,
                        error_message = NULL,
                        updated_at = NOW()
                    FROM picked
                    WHERE r.id = picked.id
                    RETURNING r.id, r.project_id, r.created_by, r.config
                    """,
                    (limit,),
                )
            rows = cur.fetchall()
        claimed: list[dict[str, Any]] = []
        for row in rows:
            config_raw = row[3]
            config = dict(config_raw) if isinstance(config_raw, dict) else {}
            claimed.append(
                {
                    "run_id": row[0],
                    "project_id": str(row[1]),
                    "created_by": str(row[2] or "scheduler"),
                    "config": config,
                }
            )
        return claimed

    def _clear_findings(self, conn, *, run_id: UUID) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM agent_simulator_findings
                WHERE run_id = %s
                """,
                (run_id,),
            )

    def _insert_findings(self, conn, *, run_id: UUID, project_id: str, findings: list[SimulatorFinding]) -> None:
        if not findings:
            return
        with conn.cursor() as cur:
            for finding in findings:
                cur.execute(
                    """
                    INSERT INTO agent_simulator_findings (
                      id,
                      run_id,
                      project_id,
                      session_id,
                      policy_id,
                      entity_key,
                      category,
                      impact_kind,
                      severity,
                      impact_score,
                      rationale,
                      evidence_excerpt,
                      session_first_seen,
                      session_last_seen,
                      session_event_count,
                      metadata
                    )
                    VALUES (
                      %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        uuid4(),
                        run_id,
                        project_id,
                        finding.session_id,
                        finding.policy_id,
                        finding.entity_key,
                        finding.category,
                        finding.impact_kind,
                        finding.severity,
                        float(finding.impact_score),
                        finding.rationale,
                        finding.evidence_excerpt,
                        finding.session_first_seen,
                        finding.session_last_seen,
                        finding.session_event_count,
                        Jsonb(finding.metadata),
                    ),
                )

    def _mark_run_completed(
        self,
        conn,
        *,
        run_id: UUID,
        sessions_scanned: int,
        findings_total: int,
        result_payload: dict[str, Any],
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE agent_simulator_runs
                SET status = 'completed',
                    sessions_scanned = %s,
                    findings_total = %s,
                    result = %s,
                    finished_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (sessions_scanned, findings_total, Jsonb(result_payload), run_id),
            )

    def _mark_run_failed(self, conn, *, run_id: UUID, error_message: str) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE agent_simulator_runs
                SET status = 'failed',
                    error_message = %s,
                    finished_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (error_message[:4000], run_id),
            )


def _parse_datetime(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=UTC)
        return raw.astimezone(UTC)
    if not isinstance(raw, str):
        return None
    value = raw.strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _extract_strings(value: Any, *, limit: int = 80) -> list[str]:
    out: list[str] = []

    def walk(node: Any) -> None:
        if len(out) >= limit:
            return
        if node is None:
            return
        if isinstance(node, str):
            text = _normalize_whitespace(node)
            if text:
                out.append(text[:500])
            return
        if isinstance(node, (int, float, bool)):
            out.append(str(node))
            return
        if isinstance(node, dict):
            for key, child in node.items():
                if len(out) >= limit:
                    break
                out.append(str(key))
                walk(child)
            return
        if isinstance(node, list):
            for child in node:
                if len(out) >= limit:
                    break
                walk(child)
            return
        try:
            out.append(str(node))
        except Exception:
            return

    walk(value)
    return out[:limit]


def _tokenize(text: str) -> set[str]:
    tokens = {token.lower() for token in TOKEN_RE.findall(text.lower())}
    return {token for token in tokens if token and token not in STOP_WORDS}


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def newline_safe(value: str) -> str:
    return _normalize_whitespace(value.replace("\n", " "))


def _classify_direction(old_statement: str | None, new_statement: str) -> str:
    old_tokens = _tokenize(old_statement or "")
    new_tokens = _tokenize(new_statement)

    restrictive_delta = len(new_tokens & RESTRICTIVE_TOKENS) - len(old_tokens & RESTRICTIVE_TOKENS)
    relaxing_delta = len(new_tokens & RELAXING_TOKENS) - len(old_tokens & RELAXING_TOKENS)

    if restrictive_delta > relaxing_delta and restrictive_delta > 0:
        return "restrictive"
    if relaxing_delta > restrictive_delta and relaxing_delta > 0:
        return "relaxing"
    if relaxing_delta < 0 and restrictive_delta >= 0:
        return "restrictive"
    if restrictive_delta < 0 and relaxing_delta >= 0:
        return "relaxing"
    if len(new_tokens & RESTRICTIVE_TOKENS) > 0 and len(old_tokens & RESTRICTIVE_TOKENS) == 0:
        return "restrictive"
    if len(new_tokens & RELAXING_TOKENS) > 0 and len(old_tokens & RELAXING_TOKENS) == 0:
        return "relaxing"
    return "neutral"


def _extract_relevant_excerpt(text_corpus: str, overlap_tokens: set[str], *, fallback: str) -> str:
    if not text_corpus:
        return fallback[:240]
    text = text_corpus.strip()
    if not text:
        return fallback[:240]

    chunks = re.split(r"(?<=[.!?])\s+|\n+", text)
    lowered_overlap = {token.lower() for token in overlap_tokens if token}
    for chunk in chunks:
        normalized = _normalize_whitespace(chunk)
        if not normalized:
            continue
        chunk_lower = normalized.lower()
        if any(token in chunk_lower for token in lowered_overlap):
            return normalized[:280]
    return _normalize_whitespace(chunks[0])[:280] if chunks else fallback[:240]
