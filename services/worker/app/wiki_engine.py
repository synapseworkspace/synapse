from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Protocol

SECTION_TAXONOMY: dict[str, list[tuple[str, str]]] = {
    "access": [
        ("access_rules", "Access Rules"),
        ("entry_path", "Entry Path"),
        ("gates", "Gates and Checkpoints"),
    ],
    "operations": [
        ("operations_policy", "Operations Policy"),
        ("time_windows", "Time Windows"),
        ("restrictions", "Restrictions"),
    ],
    "customer": [
        ("preferences", "Customer Preferences"),
        ("contacts", "Contacts"),
        ("notes", "Customer Notes"),
    ],
    "incident": [
        ("incidents", "Incidents"),
        ("workarounds", "Workarounds"),
    ],
    "general": [
        ("facts", "Facts"),
        ("notes", "Notes"),
    ],
}

SECTION_KEYWORDS: list[tuple[str, str]] = [
    ("access", "access_rules"),
    ("gate", "gates"),
    ("entry", "entry_path"),
    ("route", "entry_path"),
    ("time", "time_windows"),
    ("window", "time_windows"),
    ("policy", "operations_policy"),
    ("restriction", "restrictions"),
    ("prefer", "preferences"),
    ("contact", "contacts"),
    ("incident", "incidents"),
    ("error", "incidents"),
    ("workaround", "workarounds"),
]

CONTRADICTION_GROUPS: list[tuple[set[str], set[str]]] = [
    (
        {"open", "available", "allowed", "enabled"},
        {"closed", "unavailable", "blocked", "forbidden", "disabled"},
    ),
    (
        {"required", "mandatory", "must", "only"},
        {"optional", "without", "not", "any"},
    ),
    (
        {"before", "earlier"},
        {"after", "later"},
    ),
]

STOP_WORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "for",
    "in",
    "on",
    "at",
    "is",
    "are",
    "was",
    "were",
    "be",
    "this",
    "that",
    "it",
    "by",
    "with",
    "as",
}

BACKFILL_CATEGORY_HINTS: dict[str, tuple[str, ...]] = {
    "access": (
        "access",
        "gate",
        "entry",
        "badge",
        "card",
        "checkpoint",
        "шлагбаум",
        "доступ",
        "въезд",
        "пропуск",
        "карта",
    ),
    "incident": (
        "incident",
        "error",
        "failure",
        "outage",
        "broken",
        "problem",
        "issue",
        "сбой",
        "ошибка",
        "полом",
        "авар",
        "инцидент",
    ),
    "customer": (
        "customer",
        "client",
        "preference",
        "contact",
        "клиент",
        "предпочт",
        "контакт",
        "не звонить",
    ),
    "operations": (
        "warehouse",
        "depot",
        "terminal",
        "route",
        "delivery",
        "schedule",
        "policy",
        "склад",
        "терминал",
        "доставка",
        "маршрут",
        "график",
        "режим",
    ),
}

BACKFILL_ENTITY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\b(?P<prefix>warehouse|depot|terminal|hub|office|store|building|bc)\s*(?:#|№)?\s*(?P<value>[a-z0-9_-]{1,32})\b",
            re.IGNORECASE,
        ),
        "latin_prefix_id",
    ),
    (
        re.compile(
            r"\b(?P<prefix>driver|customer|client|route)\s*(?:#|№)?\s*(?P<value>[a-z0-9_-]{1,32})\b",
            re.IGNORECASE,
        ),
        "latin_actor_id",
    ),
    (
        re.compile(
            r"\b(?P<prefix>склад|бц|терминал|водитель|клиент|маршрут)\s*(?:#|№)?\s*(?P<value>[a-zа-я0-9_-]{1,32})\b",
            re.IGNORECASE,
        ),
        "cyrillic_prefix_id",
    ),
    (
        re.compile(
            r"\b(?P<prefix>bc|бц)\s*[\"'«“]?(?P<value>[a-zа-я0-9_-]{2,32})[\"'»”]?",
            re.IGNORECASE,
        ),
        "bc_named",
    ),
]


@dataclass(slots=True)
class ClaimInput:
    id: uuid.UUID
    project_id: str
    entity_key: str
    category: str
    claim_text: str
    evidence: list[dict[str, Any]]
    observed_at: datetime | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ClaimInput":
        claim_id = uuid.UUID(str(payload["id"]))
        observed_at = cls._parse_datetime(payload.get("observed_at"))
        valid_from = cls._parse_datetime(payload.get("valid_from"))
        valid_to = cls._parse_datetime(payload.get("valid_to"))
        return cls(
            id=claim_id,
            project_id=str(payload["project_id"]),
            entity_key=str(payload["entity_key"]).strip(),
            category=str(payload["category"]).strip(),
            claim_text=str(payload["claim_text"]).strip(),
            evidence=list(payload.get("evidence") or []),
            observed_at=observed_at,
            valid_from=valid_from,
            valid_to=valid_to,
        )

    @staticmethod
    def _parse_datetime(raw: Any) -> datetime | None:
        if raw is None:
            return None
        if isinstance(raw, datetime):
            if raw.tzinfo is None:
                return raw.replace(tzinfo=timezone.utc)
            return raw.astimezone(timezone.utc)
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
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)


@dataclass(slots=True)
class PageRecord:
    id: uuid.UUID
    project_id: str
    page_type: str
    title: str
    slug: str
    entity_key: str
    status: str
    aliases: list[str]


@dataclass(slots=True)
class SectionRecord:
    section_key: str
    heading: str
    order_index: int


@dataclass(slots=True)
class StatementRecord:
    id: uuid.UUID
    section_key: str
    statement_text: str
    normalized_text: str
    claim_fingerprint: str
    valid_from: datetime | None
    valid_to: datetime | None


@dataclass(slots=True)
class PageResolution:
    mode: str
    page: PageRecord | None
    confidence: float
    rationale: str


@dataclass(slots=True)
class DedupResult:
    decision: str
    matched_statement: StatementRecord | None
    confidence: float


@dataclass(slots=True)
class GatekeeperDecision:
    tier: str
    score: float
    rationale: str
    features: dict[str, Any]


@dataclass(slots=True)
class GatekeeperConfig:
    min_sources_for_golden: int
    conflict_free_days: int
    min_score_for_golden: float
    operational_short_text_len: int
    operational_short_token_len: int
    llm_assist_enabled: bool = False
    llm_provider: str = "openai"
    llm_model: str = "gpt-4.1-mini"
    llm_score_weight: float = 0.35
    llm_min_confidence: float = 0.65
    llm_timeout_ms: int = 3500


@dataclass(slots=True)
class GatekeeperLLMAssessment:
    status: str
    provider: str | None = None
    model: str | None = None
    suggested_tier: str | None = None
    score: float | None = None
    confidence: float | None = None
    rationale: str | None = None
    error: str | None = None


class GatekeeperLLMClassifier(Protocol):
    def classify(
        self,
        *,
        claim: ClaimInput,
        features: dict[str, Any],
        config: GatekeeperConfig,
    ) -> GatekeeperLLMAssessment: ...


class OpenAIGatekeeperClassifier:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")

    def classify(
        self,
        *,
        claim: ClaimInput,
        features: dict[str, Any],
        config: GatekeeperConfig,
    ) -> GatekeeperLLMAssessment:
        if not self.api_key:
            return GatekeeperLLMAssessment(
                status="skipped",
                provider="openai",
                model=config.llm_model,
                error="missing_openai_api_key",
            )

        payload = {
            "claim_text": claim.claim_text[:2000],
            "category": claim.category,
            "entity_key": claim.entity_key,
            "evidence_count": features.get("evidence_count"),
            "repeated_count": features.get("repeated_count"),
            "source_diversity": features.get("source_diversity"),
            "has_recent_open_conflict": features.get("has_recent_open_conflict"),
            "is_short": features.get("is_short"),
            "has_policy_signal": features.get("has_policy_signal"),
            "has_operational_pattern": features.get("has_operational_pattern"),
            "heuristic_tier": features.get("heuristic_tier"),
            "heuristic_score": features.get("heuristic_score"),
        }
        system_prompt = (
            "You are a strict gatekeeper classifier for enterprise agent memory. "
            "Classify a claim into one of: operational_memory, insight_candidate, golden_candidate. "
            "Return JSON with keys: suggested_tier, score, confidence, rationale. "
            "Use score/confidence in [0,1]."
        )
        request_body = {
            "model": config.llm_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        }

        url = f"{self.base_url}/chat/completions"
        body = json.dumps(request_body).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=max(config.llm_timeout_ms, 200) / 1000.0) as response:
                raw = response.read()
            parsed = json.loads(raw.decode("utf-8"))
            message = ((parsed.get("choices") or [{}])[0].get("message") or {}).get("content")
            if not isinstance(message, str) or not message.strip():
                return GatekeeperLLMAssessment(
                    status="error",
                    provider="openai",
                    model=config.llm_model,
                    error="empty_model_response",
                )
            model_json = json.loads(message)
        except urllib.error.URLError as exc:
            return GatekeeperLLMAssessment(
                status="error",
                provider="openai",
                model=config.llm_model,
                error=f"url_error:{exc}",
            )
        except Exception as exc:
            return GatekeeperLLMAssessment(
                status="error",
                provider="openai",
                model=config.llm_model,
                error=f"parse_error:{exc}",
            )

        tier = str(model_json.get("suggested_tier") or "").strip().lower()
        if tier not in {"operational_memory", "insight_candidate", "golden_candidate"}:
            return GatekeeperLLMAssessment(
                status="error",
                provider="openai",
                model=config.llm_model,
                error=f"invalid_tier:{tier or 'empty'}",
            )

        try:
            score = max(0.0, min(1.0, float(model_json.get("score", 0.0))))
            confidence = max(0.0, min(1.0, float(model_json.get("confidence", 0.0))))
        except Exception:
            return GatekeeperLLMAssessment(
                status="error",
                provider="openai",
                model=config.llm_model,
                error="invalid_numeric_fields",
            )

        return GatekeeperLLMAssessment(
            status="ok",
            provider="openai",
            model=config.llm_model,
            suggested_tier=tier,
            score=round(score, 4),
            confidence=round(confidence, 4),
            rationale=str(model_json.get("rationale") or "")[:500],
        )


class WikiSynthesisEngine:
    """Deterministic resolver from queued claims into wiki draft changes."""
    BACKFILL_PIPELINE = "backfill_claim_extraction"

    def __init__(
        self,
        *,
        threshold_high: float = 0.82,
        threshold_mid: float = 0.55,
        gatekeeper_min_sources_for_golden: int = 3,
        gatekeeper_conflict_free_days: int = 7,
        gatekeeper_min_score_for_golden: float = 0.72,
        gatekeeper_operational_short_text_len: int = 32,
        gatekeeper_operational_short_token_len: int = 5,
        gatekeeper_llm_assist_enabled: bool = False,
        gatekeeper_llm_provider: str = "openai",
        gatekeeper_llm_model: str = "gpt-4.1-mini",
        gatekeeper_llm_score_weight: float = 0.35,
        gatekeeper_llm_min_confidence: float = 0.65,
        gatekeeper_llm_timeout_ms: int = 3500,
        llm_classifier: GatekeeperLLMClassifier | None = None,
    ) -> None:
        self.threshold_high = threshold_high
        self.threshold_mid = threshold_mid
        self.gatekeeper_min_sources_for_golden = max(2, gatekeeper_min_sources_for_golden)
        self.gatekeeper_conflict_free_days = max(1, gatekeeper_conflict_free_days)
        self.gatekeeper_min_score_for_golden = max(0.0, min(1.0, gatekeeper_min_score_for_golden))
        self.gatekeeper_operational_short_text_len = max(8, gatekeeper_operational_short_text_len)
        self.gatekeeper_operational_short_token_len = max(1, gatekeeper_operational_short_token_len)
        self.gatekeeper_llm_assist_enabled = bool(gatekeeper_llm_assist_enabled)
        self.gatekeeper_llm_provider = (gatekeeper_llm_provider or "openai").strip().lower()
        self.gatekeeper_llm_model = gatekeeper_llm_model.strip() if gatekeeper_llm_model else "gpt-4.1-mini"
        self.gatekeeper_llm_score_weight = max(0.0, min(1.0, gatekeeper_llm_score_weight))
        self.gatekeeper_llm_min_confidence = max(0.0, min(1.0, gatekeeper_llm_min_confidence))
        self.gatekeeper_llm_timeout_ms = max(200, gatekeeper_llm_timeout_ms)
        self._llm_classifier = llm_classifier or OpenAIGatekeeperClassifier()
        self._claims_has_fingerprint_column_cache: bool | None = None
        self._gatekeeper_config_has_llm_columns_cache: bool | None = None

    def run_once(self, conn, *, limit: int = 50) -> dict[str, int]:
        picked = self._pick_claim_proposals(conn, limit=limit)
        metrics = {"picked": len(picked), "processed": 0, "failed": 0}
        for claim_id, payload in picked:
            try:
                with conn.transaction():
                    claim = ClaimInput.from_payload(payload)
                    self._process_claim(conn, claim)
                    self._set_proposal_status(conn, claim_id, "processed")
                metrics["processed"] += 1
            except Exception:
                with conn.transaction():
                    self._set_proposal_status(conn, claim_id, "failed")
                metrics["failed"] += 1
        return metrics

    def extract_backfill_claims(self, conn, *, limit: int = 200) -> dict[str, int]:
        picked = self._pick_backfill_events(conn, limit=limit)
        metrics = {"picked": len(picked), "claims_generated": 0, "events_completed": 0, "failed": 0}
        for event_id, project_id, agent_id, session_id, payload, observed_at in picked:
            payload_dict = payload if isinstance(payload, dict) else {}
            try:
                with conn.transaction():
                    self._set_event_pipeline_state(conn, event_id, status="processing")
                    claim_payload = self._claim_payload_from_backfill_event(
                        event_id=event_id,
                        project_id=project_id,
                        agent_id=agent_id,
                        session_id=session_id,
                        payload=payload_dict,
                        observed_at=observed_at,
                    )
                    generated = 0
                    if claim_payload is not None:
                        self._enqueue_claim_proposal(conn, claim_payload)
                        generated = 1
                    self._set_event_pipeline_state(conn, event_id, status="completed")
                    self._update_backfill_batch_metrics(
                        conn,
                        payload_dict,
                        processed_increment=1,
                        generated_increment=generated,
                        failed=False,
                    )
                metrics["claims_generated"] += generated
                metrics["events_completed"] += 1
            except Exception as exc:
                with conn.transaction():
                    self._set_event_pipeline_state(conn, event_id, status="failed", last_error=str(exc))
                    self._update_backfill_batch_metrics(
                        conn,
                        payload_dict,
                        processed_increment=0,
                        generated_increment=0,
                        failed=True,
                    )
                metrics["failed"] += 1
        with conn.transaction():
            self._finalize_ready_backfill_batches(conn)
        return metrics

    def _pick_backfill_events(
        self,
        conn,
        *,
        limit: int,
    ) -> list[tuple[uuid.UUID, str, str | None, str | None, dict[str, Any], datetime]]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  e.id,
                  e.project_id,
                  e.agent_id,
                  e.session_id,
                  e.payload,
                  e.observed_at
                FROM events e
                WHERE e.event_type = 'memory_backfill'
                  AND NOT EXISTS (
                    SELECT 1
                    FROM event_pipeline_state s
                    WHERE s.event_id = e.id
                      AND s.pipeline = %s
                      AND s.status = 'completed'
                  )
                ORDER BY e.observed_at ASC, e.received_at ASC
                LIMIT %s
                FOR UPDATE SKIP LOCKED
                """,
                (self.BACKFILL_PIPELINE, limit),
            )
            rows = cur.fetchall()
        return [(row[0], row[1], row[2], row[3], row[4], row[5]) for row in rows]

    def _set_event_pipeline_state(
        self,
        conn,
        event_id: uuid.UUID,
        *,
        status: str,
        last_error: str | None = None,
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO event_pipeline_state (event_id, pipeline, status, last_error)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (event_id, pipeline) DO UPDATE
                SET status = EXCLUDED.status,
                    last_error = EXCLUDED.last_error,
                    updated_at = NOW()
                """,
                (event_id, self.BACKFILL_PIPELINE, status, last_error[:2000] if last_error else None),
            )

    def _claim_payload_from_backfill_event(
        self,
        *,
        event_id: uuid.UUID,
        project_id: str,
        agent_id: str | None,
        session_id: str | None,
        payload: dict[str, Any],
        observed_at: datetime | None,
    ) -> dict[str, Any] | None:
        content = str(payload.get("content") or "").strip()
        if len(content) < 8:
            return None
        content = content[:4000]

        source_id = str(payload.get("source_id") or event_id)
        metadata = payload.get("metadata")
        metadata_dict = metadata if isinstance(metadata, dict) else {}
        entity_key, entity_source = self._resolve_backfill_entity_key(payload=payload, metadata=metadata_dict, source_id=source_id, content=content)
        category, category_source = self._resolve_backfill_category(payload=payload, metadata=metadata_dict, content=content)

        fingerprint_material = "|".join(
            [
                self._normalize_text(project_id),
                self._normalize_text(entity_key),
                self._normalize_text(category),
                self._normalize_text(content),
            ]
        )
        claim_id = self._stable_uuid(f"synapse:backfill-claim:{fingerprint_material}")
        observed_iso = observed_at.isoformat() if observed_at else None
        evidence = [
            {
                "source_type": "external_event",
                "source_id": source_id,
                "session_id": session_id,
                "snippet": content[:280],
                "observed_at": observed_iso,
                "tool_name": "memory_backfill",
                "url": None,
                "event_id": str(event_id),
                "agent_id": agent_id,
                "entity_inference_source": entity_source,
                "category_inference_source": category_source,
            }
        ]
        return {
            "id": str(claim_id),
            "schema_version": "v1",
            "project_id": project_id,
            "entity_key": entity_key,
            "category": category,
            "claim_text": content,
            "status": "draft",
            "observed_at": observed_iso,
            "valid_from": payload.get("valid_from"),
            "valid_to": payload.get("valid_to"),
            "evidence": evidence,
        }

    def _resolve_backfill_entity_key(
        self,
        *,
        payload: dict[str, Any],
        metadata: dict[str, Any],
        source_id: str,
        content: str,
    ) -> tuple[str, str]:
        explicit = payload.get("entity_key") or metadata.get("entity_key")
        if isinstance(explicit, str) and explicit.strip():
            return explicit.strip(), "explicit_entity_key"

        for meta_key in ("entity", "subject", "resource_id", "object_id"):
            value = metadata.get(meta_key)
            if isinstance(value, str) and value.strip():
                slug = self._slugify(value)
                if slug:
                    return slug, f"metadata:{meta_key}"

        normalized_content = self._normalize_text(content)
        cyrillic_prefix_map = {
            "склад": "warehouse",
            "бц": "bc",
            "терминал": "terminal",
            "водитель": "driver",
            "клиент": "customer",
            "маршрут": "route",
        }
        for pattern, source in BACKFILL_ENTITY_PATTERNS:
            match = pattern.search(normalized_content)
            if not match:
                continue
            prefix = str(match.group("prefix") or "").strip().lower()
            value = str(match.group("value") or "").strip().lower()
            if not value:
                continue
            canonical_prefix = cyrillic_prefix_map.get(prefix, prefix)
            entity = self._slugify(f"{canonical_prefix}_{value}")
            if entity:
                return entity, f"inferred:{source}"

        quoted = re.search(r"[\"'«“](?P<name>[a-zа-я0-9][a-zа-я0-9 _-]{1,40})[\"'»”]", content.lower())
        if quoted:
            name = str(quoted.group("name") or "").strip()
            slug = self._slugify(name)
            if slug:
                return slug, "inferred:quoted_name"

        return f"memory_{self._slugify(source_id) or 'unknown'}", "fallback:source_id"

    def _resolve_backfill_category(
        self,
        *,
        payload: dict[str, Any],
        metadata: dict[str, Any],
        content: str,
    ) -> tuple[str, str]:
        explicit = payload.get("category") or metadata.get("category")
        if isinstance(explicit, str) and explicit.strip():
            return self._normalize_category_label(explicit), "explicit_category"

        inferred = self._infer_backfill_category_from_text(content)
        if inferred:
            return inferred, "inferred:keyword_score"

        return "general", "fallback:general"

    def _normalize_category_label(self, value: str) -> str:
        raw = value.strip()
        if not raw:
            return "general"
        page_type = self._category_to_page_type(raw)
        if page_type != "general":
            return page_type
        normalized = self._normalize_text(raw)
        if normalized in {"access", "incident", "customer", "operations", "general"}:
            return normalized
        return normalized or "general"

    def _infer_backfill_category_from_text(self, text: str) -> str | None:
        normalized = self._normalize_text(text)
        if not normalized:
            return None
        scores: dict[str, int] = {name: 0 for name in BACKFILL_CATEGORY_HINTS}
        for category, hints in BACKFILL_CATEGORY_HINTS.items():
            for hint in hints:
                if hint in normalized:
                    scores[category] += 1
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        top_category, top_score = ranked[0]
        if top_score <= 0:
            return None
        return top_category

    def _enqueue_claim_proposal(self, conn, claim_payload: dict[str, Any]) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO claim_proposals (claim_id, project_id, claim_payload, status)
                VALUES (%s, %s, %s, 'queued')
                ON CONFLICT (claim_id) DO UPDATE
                SET claim_payload = EXCLUDED.claim_payload,
                    status = 'queued',
                    updated_at = NOW()
                """,
                (
                    claim_payload["id"],
                    claim_payload["project_id"],
                    self._jsonb(claim_payload),
                ),
            )

    def _update_backfill_batch_metrics(
        self,
        conn,
        payload: dict[str, Any],
        *,
        processed_increment: int,
        generated_increment: int,
        failed: bool,
    ) -> None:
        backfill = payload.get("backfill")
        if not isinstance(backfill, dict):
            return
        raw_batch_id = backfill.get("batch_id")
        if not raw_batch_id:
            return
        try:
            batch_id = uuid.UUID(str(raw_batch_id))
        except ValueError:
            return

        with conn.cursor() as cur:
            if failed:
                cur.execute(
                    """
                    UPDATE memory_backfill_batches
                    SET status = 'failed', updated_at = NOW()
                    WHERE id = %s
                    """,
                    (batch_id,),
                )
                return

            cur.execute(
                """
                UPDATE memory_backfill_batches
                SET processed_events = processed_events + %s,
                    generated_claims = generated_claims + %s,
                    status = CASE
                      WHEN status = 'ready' THEN 'processing'
                      ELSE status
                    END,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (processed_increment, generated_increment, batch_id),
            )
            cur.execute(
                """
                UPDATE memory_backfill_batches
                SET status = 'completed',
                    updated_at = NOW()
                WHERE id = %s
                  AND status IN ('ready', 'processing')
                  AND inserted_events > 0
                  AND processed_events >= inserted_events
                """,
                (batch_id,),
            )

    def _finalize_ready_backfill_batches(self, conn) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE memory_backfill_batches
                SET status = 'completed',
                    updated_at = NOW()
                WHERE status IN ('ready', 'processing')
                  AND inserted_events > 0
                  AND processed_events >= inserted_events
                """
            )

    def _pick_claim_proposals(self, conn, *, limit: int) -> list[tuple[uuid.UUID, dict[str, Any]]]:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH picked AS (
                  SELECT claim_id
                  FROM claim_proposals
                  WHERE status = 'queued'
                  ORDER BY created_at
                  LIMIT %s
                  FOR UPDATE SKIP LOCKED
                )
                UPDATE claim_proposals cp
                SET status = 'processing', updated_at = NOW()
                FROM picked
                WHERE cp.claim_id = picked.claim_id
                RETURNING cp.claim_id, cp.claim_payload
                """,
                (limit,),
            )
            rows = cur.fetchall()
        return [(row[0], row[1]) for row in rows]

    def _set_proposal_status(self, conn, claim_id: uuid.UUID, status: str) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE claim_proposals
                SET status = %s, updated_at = NOW()
                WHERE claim_id = %s
                """,
                (status, claim_id),
            )

    def _process_claim(self, conn, claim: ClaimInput) -> None:
        valid_from, valid_to, temporal_source = self._resolve_claim_valid_window(claim)
        fingerprint = self._claim_fingerprint(claim)
        gate = self._gatekeeper_decide(conn, claim, fingerprint)
        self._record_gatekeeper_decision(conn, claim, gate)
        self._upsert_claim(
            conn,
            claim,
            gate_tier=gate.tier,
            valid_from=valid_from,
            valid_to=valid_to,
            temporal_source=temporal_source,
        )

        if gate.tier == "operational_memory":
            return

        page_candidates = self._load_pages(conn, claim.project_id)
        page_resolution = self._resolve_page(claim, page_candidates)

        page = page_resolution.page
        decision = "new_page" if page_resolution.mode == "new_page" else "new_statement"
        section_key = "facts"
        section_heading = "Facts"
        sections: list[SectionRecord] = []

        if page_resolution.mode == "new_page":
            page_type = self._category_to_page_type(claim.category)
            section_key, section_heading, _ = self._resolve_section(
                page_type=page_type,
                category=claim.category,
                claim_text=claim.claim_text,
                existing_sections=[],
            )
            page = self._create_draft_page(conn, claim, page_type, section_key, section_heading)
        elif page is not None:
            sections = self._load_sections(conn, page.id)
            section_key, section_heading, created_new = self._resolve_section(
                page_type=page.page_type,
                category=claim.category,
                claim_text=claim.claim_text,
                existing_sections=sections,
            )
            if created_new:
                decision = "new_section"
                page_resolution.rationale += "; section not found and draft section proposed"

        assert page is not None
        self._expire_outdated_statements(
            conn,
            page_id=page.id,
            section_key=section_key,
            reference_time=claim.observed_at or datetime.now(timezone.utc),
        )
        statements = self._load_statements(conn, page.id, section_key=section_key)
        dedup = self._deduplicate(
            claim_text=claim.claim_text,
            fingerprint=fingerprint,
            statements=statements,
            incoming_valid_from=valid_from,
            incoming_valid_to=valid_to,
        )
        conflict = self._detect_conflict(
            claim.claim_text,
            statements,
            incoming_valid_from=valid_from,
            incoming_valid_to=valid_to,
        )

        draft_status = "pending_review"
        if conflict is not None:
            decision = "conflict"
            draft_status = "blocked_conflict"
            self._insert_conflict(
                conn,
                claim,
                page.id,
                conflict[0],
                conflict[1],
                claim.claim_text,
                conflict[2],
                incoming_valid_from=valid_from,
                incoming_valid_to=valid_to,
            )
        elif dedup.decision in {"reinforcement", "duplicate_ignored"}:
            decision = dedup.decision
        elif page_resolution.mode == "existing_low_confidence":
            decision = "new_statement"

        patch = self._build_markdown_patch(
            decision=decision,
            claim=claim,
            page=page,
            section_key=section_key,
            section_heading=section_heading,
        )
        semantic_diff = self._build_semantic_diff(decision, claim.claim_text, dedup.matched_statement)
        confidence = self._merge_confidence(page_resolution.confidence, dedup.confidence, decision)
        rationale = self._build_rationale(
            page_resolution.rationale,
            dedup,
            decision,
            temporal_source=temporal_source,
            valid_from=valid_from,
            valid_to=valid_to,
        )

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO wiki_draft_changes (
                  id, project_id, claim_id, page_id, section_key, decision, markdown_patch,
                  semantic_diff, evidence, confidence, rationale, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (claim_id) DO UPDATE
                SET page_id = EXCLUDED.page_id,
                    section_key = EXCLUDED.section_key,
                    decision = EXCLUDED.decision,
                    markdown_patch = EXCLUDED.markdown_patch,
                    semantic_diff = EXCLUDED.semantic_diff,
                    evidence = EXCLUDED.evidence,
                    confidence = EXCLUDED.confidence,
                    rationale = EXCLUDED.rationale,
                    status = EXCLUDED.status,
                    updated_at = NOW()
                """,
                (
                    uuid.uuid4(),
                    claim.project_id,
                    claim.id,
                    page.id,
                    section_key,
                    decision,
                    patch,
                    self._jsonb(semantic_diff),
                    self._jsonb(claim.evidence),
                    confidence,
                    rationale,
                    draft_status,
                ),
            )
            cur.execute(
                """
                INSERT INTO wiki_claim_links (claim_id, page_id, section_key, insertion_status)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (claim_id, page_id, section_key) DO UPDATE
                SET insertion_status = EXCLUDED.insertion_status,
                    created_at = NOW()
                """,
                (claim.id, page.id, section_key, decision),
            )

    def _upsert_claim(
        self,
        conn,
        claim: ClaimInput,
        *,
        gate_tier: str,
        valid_from: datetime | None,
        valid_to: datetime | None,
        temporal_source: str,
    ) -> None:
        source_ids = self._extract_source_ids(claim.evidence)
        metadata = {
            "source": "claim_proposal",
            "evidence_count": len(claim.evidence),
            "source_ids": source_ids,
            "gate_tier": gate_tier,
            "temporal_source": temporal_source,
        }
        if valid_from is not None:
            metadata["valid_from"] = valid_from.isoformat()
        if valid_to is not None:
            metadata["valid_to"] = valid_to.isoformat()
        fingerprint = self._claim_fingerprint(claim)
        status = "draft"
        if gate_tier == "operational_memory":
            status = "rejected"
            metadata["gatekeeper"] = "operational_memory"
        if self._claims_has_fingerprint_column(conn):
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO claims (
                      id, project_id, entity_key, category, claim_text, status, claim_fingerprint, valid_from, valid_to, metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE
                    SET entity_key = EXCLUDED.entity_key,
                        category = EXCLUDED.category,
                        claim_text = EXCLUDED.claim_text,
                        status = EXCLUDED.status,
                        claim_fingerprint = EXCLUDED.claim_fingerprint,
                        valid_from = EXCLUDED.valid_from,
                        valid_to = EXCLUDED.valid_to,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                    """,
                    (
                        claim.id,
                        claim.project_id,
                        claim.entity_key,
                        claim.category,
                        claim.claim_text,
                        status,
                        fingerprint,
                        valid_from,
                        valid_to,
                        self._jsonb(metadata),
                    ),
                )
        else:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO claims (
                      id, project_id, entity_key, category, claim_text, status, valid_from, valid_to, metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE
                    SET entity_key = EXCLUDED.entity_key,
                        category = EXCLUDED.category,
                        claim_text = EXCLUDED.claim_text,
                        status = EXCLUDED.status,
                        valid_from = EXCLUDED.valid_from,
                        valid_to = EXCLUDED.valid_to,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                    """,
                    (
                        claim.id,
                        claim.project_id,
                        claim.entity_key,
                        claim.category,
                        claim.claim_text,
                        status,
                        valid_from,
                        valid_to,
                        self._jsonb(metadata),
                    ),
                )

    def _gatekeeper_decide(self, conn, claim: ClaimInput, fingerprint: str) -> GatekeeperDecision:
        config = self._resolve_gatekeeper_config(conn, claim.project_id)
        repeated_count = self._count_existing_claims_by_fingerprint(conn, claim.project_id, fingerprint)
        historical_source_count = self._count_source_diversity_by_fingerprint(conn, claim.project_id, fingerprint)
        incoming_source_ids = self._extract_source_ids(claim.evidence)
        has_recent_open_conflict = self._has_recent_open_conflict_for_entity(
            conn,
            claim.project_id,
            claim.entity_key,
            days=config.conflict_free_days,
        )
        return self._gatekeeper_decide_from_inputs(
            claim=claim,
            config=config,
            repeated_count=repeated_count,
            historical_source_count=historical_source_count,
            incoming_source_ids=incoming_source_ids,
            has_recent_open_conflict=has_recent_open_conflict,
        )

    def _gatekeeper_decide_from_inputs(
        self,
        *,
        claim: ClaimInput,
        config: GatekeeperConfig,
        repeated_count: int,
        historical_source_count: int,
        incoming_source_ids: list[str],
        has_recent_open_conflict: bool,
        llm_assessment_override: GatekeeperLLMAssessment | None = None,
    ) -> GatekeeperDecision:
        text = self._normalize_text(claim.claim_text)
        tokens = self._tokens(claim.claim_text)
        evidence_count = len(claim.evidence)
        is_short = len(text) < config.operational_short_text_len or len(tokens) < config.operational_short_token_len
        operational_verbs = {"sent", "send", "clicked", "click", "opened", "processed", "done", "ok"}
        has_operational_pattern = bool(set(tokens) & operational_verbs)
        policy_words = {"must", "required", "only", "forbidden", "until", "closed", "open", "policy", "quarantine"}
        has_policy_signal = bool(set(tokens) & policy_words)
        category_hint = self._category_to_page_type(claim.category)
        source_diversity = max(historical_source_count, len(incoming_source_ids))

        score = 0.35
        if has_policy_signal:
            score += 0.2
        if evidence_count >= 2:
            score += 0.2
        if repeated_count >= 1:
            score += min(0.25, repeated_count * 0.12)
        if source_diversity >= config.min_sources_for_golden:
            score += 0.1
        if not is_short:
            score += 0.1
        if has_operational_pattern and is_short:
            score -= 0.2
        if has_recent_open_conflict:
            score -= 0.1
        score = max(0.0, min(1.0, round(score, 4)))
        score_before_llm = score

        if has_operational_pattern and is_short and repeated_count == 0:
            tier = "operational_memory"
            rationale = "short operational event with low reusable signal"
        elif has_policy_signal and (evidence_count >= 2 or repeated_count >= 1):
            tier = "golden_candidate"
            rationale = "policy-like fact with multi-signal support"
        elif repeated_count >= 2:
            tier = "golden_candidate"
            rationale = "repeated claim pattern reached promotion threshold"
        else:
            tier = "insight_candidate"
            rationale = "informative fact requires moderation before promotion"

        if (
            tier == "insight_candidate"
            and source_diversity >= config.min_sources_for_golden
            and score >= config.min_score_for_golden
            and not has_recent_open_conflict
        ):
            tier = "golden_candidate"
            rationale = "auto-promoted by source diversity threshold and conflict-free horizon"

        llm_assessment = llm_assessment_override or self._run_gatekeeper_llm_assessment(
            claim=claim,
            config=config,
            features={
                "evidence_count": evidence_count,
                "repeated_count": repeated_count,
                "historical_source_count": historical_source_count,
                "incoming_source_count": len(incoming_source_ids),
                "source_diversity": source_diversity,
                "is_short": is_short,
                "has_operational_pattern": has_operational_pattern,
                "has_policy_signal": has_policy_signal,
                "has_recent_open_conflict": has_recent_open_conflict,
                "heuristic_score": score,
                "heuristic_tier": tier,
            },
        )
        llm_applied = False
        llm_weight = config.llm_score_weight
        if (
            llm_assessment.status == "ok"
            and llm_assessment.confidence is not None
            and llm_assessment.score is not None
            and llm_assessment.confidence >= config.llm_min_confidence
        ):
            score = max(0.0, min(1.0, round((1.0 - llm_weight) * score + llm_weight * llm_assessment.score, 4)))
            llm_applied = True
            suggested = llm_assessment.suggested_tier
            if suggested == "golden_candidate":
                if not has_recent_open_conflict and score >= config.min_score_for_golden:
                    if tier != "golden_candidate":
                        tier = "golden_candidate"
                        rationale = "llm-assisted promotion: high-confidence model signal and score threshold met"
            elif suggested == "operational_memory":
                if is_short and repeated_count == 0 and not has_policy_signal:
                    if tier != "operational_memory":
                        tier = "operational_memory"
                        rationale = "llm-assisted demotion: short low-value operational event"
            elif suggested == "insight_candidate":
                if tier == "golden_candidate" and not has_policy_signal:
                    tier = "insight_candidate"
                    rationale = "llm-assisted moderation: held in insight queue pending more evidence"

        if has_recent_open_conflict and tier == "golden_candidate":
            tier = "insight_candidate"
            rationale = "open conflicts for entity in recent horizon; kept as insight candidate"

        features = {
            "evidence_count": evidence_count,
            "repeated_count": repeated_count,
            "historical_source_count": historical_source_count,
            "incoming_source_count": len(incoming_source_ids),
            "source_diversity": source_diversity,
            "is_short": is_short,
            "has_operational_pattern": has_operational_pattern,
            "has_policy_signal": has_policy_signal,
            "has_recent_open_conflict": has_recent_open_conflict,
            "gatekeeper_min_sources_for_golden": config.min_sources_for_golden,
            "gatekeeper_conflict_free_days": config.conflict_free_days,
            "gatekeeper_min_score_for_golden": config.min_score_for_golden,
            "gatekeeper_operational_short_text_len": config.operational_short_text_len,
            "gatekeeper_operational_short_token_len": config.operational_short_token_len,
            "gatekeeper_llm_assist_enabled": config.llm_assist_enabled,
            "gatekeeper_llm_provider": config.llm_provider,
            "gatekeeper_llm_model": config.llm_model,
            "gatekeeper_llm_score_weight": config.llm_score_weight,
            "gatekeeper_llm_min_confidence": config.llm_min_confidence,
            "gatekeeper_llm_timeout_ms": config.llm_timeout_ms,
            "llm_status": llm_assessment.status,
            "llm_provider": llm_assessment.provider,
            "llm_model": llm_assessment.model,
            "llm_suggested_tier": llm_assessment.suggested_tier,
            "llm_score": llm_assessment.score,
            "llm_confidence": llm_assessment.confidence,
            "llm_rationale": llm_assessment.rationale,
            "llm_error": llm_assessment.error,
            "llm_applied": llm_applied,
            "score_before_llm": score_before_llm,
            "category_hint": category_hint,
            "token_count": len(tokens),
        }
        return GatekeeperDecision(tier=tier, score=score, rationale=rationale, features=features)

    def _run_gatekeeper_llm_assessment(
        self,
        *,
        claim: ClaimInput,
        config: GatekeeperConfig,
        features: dict[str, Any],
    ) -> GatekeeperLLMAssessment:
        if not config.llm_assist_enabled:
            return GatekeeperLLMAssessment(
                status="disabled",
                provider=config.llm_provider,
                model=config.llm_model,
            )
        if config.llm_provider != "openai":
            return GatekeeperLLMAssessment(
                status="error",
                provider=config.llm_provider,
                model=config.llm_model,
                error=f"unsupported_provider:{config.llm_provider}",
            )
        if self._llm_classifier is None:
            return GatekeeperLLMAssessment(
                status="error",
                provider=config.llm_provider,
                model=config.llm_model,
                error="classifier_unavailable",
            )
        try:
            result = self._llm_classifier.classify(claim=claim, features=features, config=config)
            return result
        except Exception as exc:
            return GatekeeperLLMAssessment(
                status="error",
                provider=config.llm_provider,
                model=config.llm_model,
                error=f"classifier_error:{exc}",
            )

    def _gatekeeper_config_has_llm_columns(self, conn) -> bool:
        if self._gatekeeper_config_has_llm_columns_cache is not None:
            return self._gatekeeper_config_has_llm_columns_cache
        required = {
            "llm_assist_enabled",
            "llm_provider",
            "llm_model",
            "llm_score_weight",
            "llm_min_confidence",
            "llm_timeout_ms",
        }
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'gatekeeper_project_configs'
                """
            )
            present = {str(row[0]) for row in cur.fetchall()}
        self._gatekeeper_config_has_llm_columns_cache = required.issubset(present)
        return self._gatekeeper_config_has_llm_columns_cache

    def _resolve_gatekeeper_config(self, conn, project_id: str) -> GatekeeperConfig:
        has_llm_columns = self._gatekeeper_config_has_llm_columns(conn)
        with conn.cursor() as cur:
            if has_llm_columns:
                cur.execute(
                    """
                    SELECT
                      min_sources_for_golden,
                      conflict_free_days,
                      min_score_for_golden,
                      operational_short_text_len,
                      operational_short_token_len,
                      llm_assist_enabled,
                      llm_provider,
                      llm_model,
                      llm_score_weight,
                      llm_min_confidence,
                      llm_timeout_ms
                    FROM gatekeeper_project_configs
                    WHERE project_id = %s
                    LIMIT 1
                    """,
                    (project_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT
                      min_sources_for_golden,
                      conflict_free_days,
                      min_score_for_golden,
                      operational_short_text_len,
                      operational_short_token_len
                    FROM gatekeeper_project_configs
                    WHERE project_id = %s
                    LIMIT 1
                    """,
                    (project_id,),
                )
            row = cur.fetchone()

        if row is None:
            config = GatekeeperConfig(
                min_sources_for_golden=self.gatekeeper_min_sources_for_golden,
                conflict_free_days=self.gatekeeper_conflict_free_days,
                min_score_for_golden=self.gatekeeper_min_score_for_golden,
                operational_short_text_len=self.gatekeeper_operational_short_text_len,
                operational_short_token_len=self.gatekeeper_operational_short_token_len,
                llm_assist_enabled=self.gatekeeper_llm_assist_enabled,
                llm_provider=self.gatekeeper_llm_provider,
                llm_model=self.gatekeeper_llm_model,
                llm_score_weight=self.gatekeeper_llm_score_weight,
                llm_min_confidence=self.gatekeeper_llm_min_confidence,
                llm_timeout_ms=self.gatekeeper_llm_timeout_ms,
            )
        else:
            if has_llm_columns:
                config = GatekeeperConfig(
                    min_sources_for_golden=max(2, int(row[0])),
                    conflict_free_days=max(1, int(row[1])),
                    min_score_for_golden=max(0.0, min(1.0, float(row[2]))),
                    operational_short_text_len=max(8, int(row[3])),
                    operational_short_token_len=max(1, int(row[4])),
                    llm_assist_enabled=bool(row[5]),
                    llm_provider=str(row[6] or "openai").strip().lower(),
                    llm_model=str(row[7] or "gpt-4.1-mini"),
                    llm_score_weight=max(0.0, min(1.0, float(row[8]))),
                    llm_min_confidence=max(0.0, min(1.0, float(row[9]))),
                    llm_timeout_ms=max(200, int(row[10])),
                )
            else:
                config = GatekeeperConfig(
                    min_sources_for_golden=max(2, int(row[0])),
                    conflict_free_days=max(1, int(row[1])),
                    min_score_for_golden=max(0.0, min(1.0, float(row[2]))),
                    operational_short_text_len=max(8, int(row[3])),
                    operational_short_token_len=max(1, int(row[4])),
                    llm_assist_enabled=self.gatekeeper_llm_assist_enabled,
                    llm_provider=self.gatekeeper_llm_provider,
                    llm_model=self.gatekeeper_llm_model,
                    llm_score_weight=self.gatekeeper_llm_score_weight,
                    llm_min_confidence=self.gatekeeper_llm_min_confidence,
                    llm_timeout_ms=self.gatekeeper_llm_timeout_ms,
                )
        return config

    def _record_gatekeeper_decision(self, conn, claim: ClaimInput, decision: GatekeeperDecision) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO gatekeeper_decisions (claim_id, project_id, tier, score, rationale, features)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (claim_id) DO UPDATE
                SET tier = EXCLUDED.tier,
                    score = EXCLUDED.score,
                    rationale = EXCLUDED.rationale,
                    features = EXCLUDED.features,
                    updated_at = NOW()
                """,
                (
                    claim.id,
                    claim.project_id,
                    decision.tier,
                    decision.score,
                    decision.rationale,
                    self._jsonb(decision.features),
                ),
            )

    def _count_existing_claims_by_fingerprint(self, conn, project_id: str, fingerprint: str) -> int:
        with conn.cursor() as cur:
            if self._claims_has_fingerprint_column(conn):
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM claims
                    WHERE project_id = %s
                      AND claim_fingerprint = %s
                      AND status <> 'rejected'
                    """,
                    (project_id, fingerprint),
                )
            else:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM claims
                    WHERE project_id = %s
                      AND encode(digest(
                        lower(trim(project_id)) || '|' ||
                        lower(trim(entity_key)) || '|' ||
                        lower(trim(category)) || '|' ||
                        lower(trim(claim_text)),
                        'sha256'
                      ), 'hex') = %s
                      AND status <> 'rejected'
                    """,
                    (project_id, fingerprint),
                )
            row = cur.fetchone()
        return int(row[0]) if row else 0

    def _count_source_diversity_by_fingerprint(self, conn, project_id: str, fingerprint: str) -> int:
        with conn.cursor() as cur:
            if self._claims_has_fingerprint_column(conn):
                cur.execute(
                    """
                    SELECT COUNT(DISTINCT src.source_id)
                    FROM (
                      SELECT jsonb_array_elements_text(COALESCE(metadata->'source_ids', '[]'::jsonb)) AS source_id
                      FROM claims
                      WHERE project_id = %s
                        AND claim_fingerprint = %s
                        AND status <> 'rejected'
                    ) src
                    """,
                    (project_id, fingerprint),
                )
            else:
                cur.execute(
                    """
                    SELECT COUNT(DISTINCT src.source_id)
                    FROM (
                      SELECT jsonb_array_elements_text(COALESCE(metadata->'source_ids', '[]'::jsonb)) AS source_id
                      FROM claims
                      WHERE project_id = %s
                        AND encode(digest(
                          lower(trim(project_id)) || '|' ||
                          lower(trim(entity_key)) || '|' ||
                          lower(trim(category)) || '|' ||
                          lower(trim(claim_text)),
                          'sha256'
                        ), 'hex') = %s
                        AND status <> 'rejected'
                    ) src
                    """,
                    (project_id, fingerprint),
                )
            row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    def _has_recent_open_conflict_for_entity(self, conn, project_id: str, entity_key: str, *, days: int) -> bool:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM wiki_conflicts wc
                JOIN claims c ON c.id = wc.claim_id
                WHERE wc.project_id = %s
                  AND c.entity_key = %s
                  AND wc.resolution_status = 'open'
                  AND wc.created_at >= NOW() - (%s::text || ' days')::interval
                LIMIT 1
                """,
                (project_id, entity_key, days),
            )
            return cur.fetchone() is not None

    def _load_pages(self, conn, project_id: str) -> list[PageRecord]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  p.id,
                  p.project_id,
                  p.page_type,
                  p.title,
                  p.slug,
                  p.entity_key,
                  p.status,
                  COALESCE(array_agg(a.alias_text) FILTER (WHERE a.alias_text IS NOT NULL), '{}') AS aliases
                FROM wiki_pages p
                LEFT JOIN wiki_page_aliases a ON a.page_id = p.id
                WHERE p.project_id = %s
                GROUP BY p.id, p.project_id, p.page_type, p.title, p.slug, p.entity_key, p.status
                """,
                (project_id,),
            )
            rows = cur.fetchall()
        return [
            PageRecord(
                id=row[0],
                project_id=row[1],
                page_type=row[2],
                title=row[3],
                slug=row[4],
                entity_key=row[5],
                status=row[6],
                aliases=list(row[7] or []),
            )
            for row in rows
        ]

    def _load_sections(self, conn, page_id: uuid.UUID) -> list[SectionRecord]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT section_key, heading, order_index
                FROM wiki_sections
                WHERE page_id = %s
                ORDER BY order_index ASC, section_key ASC
                """,
                (page_id,),
            )
            rows = cur.fetchall()
        return [SectionRecord(section_key=r[0], heading=r[1], order_index=r[2]) for r in rows]

    def _expire_outdated_statements(
        self,
        conn,
        *,
        page_id: uuid.UUID,
        section_key: str,
        reference_time: datetime,
    ) -> None:
        ref = self._ensure_utc(reference_time)
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE wiki_statements
                SET status = 'superseded',
                    updated_at = NOW()
                WHERE page_id = %s
                  AND section_key = %s
                  AND status = 'active'
                  AND valid_to IS NOT NULL
                  AND valid_to < %s
                """,
                (page_id, section_key, ref),
            )

    def _load_statements(self, conn, page_id: uuid.UUID, *, section_key: str) -> list[StatementRecord]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, section_key, statement_text, normalized_text, claim_fingerprint, valid_from, valid_to
                FROM wiki_statements
                WHERE page_id = %s
                  AND section_key = %s
                  AND status = 'active'
                ORDER BY created_at DESC
                LIMIT 200
                """,
                (page_id, section_key),
            )
            rows = cur.fetchall()
        return [
            StatementRecord(
                id=row[0],
                section_key=row[1],
                statement_text=row[2],
                normalized_text=row[3],
                claim_fingerprint=row[4],
                valid_from=row[5],
                valid_to=row[6],
            )
            for row in rows
        ]

    def _resolve_page(self, claim: ClaimInput, candidates: list[PageRecord]) -> PageResolution:
        if not candidates:
            return PageResolution(mode="new_page", page=None, confidence=0.45, rationale="no page candidates found")

        scored: list[tuple[float, PageRecord]] = []
        claim_tokens = set(self._tokens(claim.claim_text))
        entity_norm = self._normalize_text(claim.entity_key)
        page_type = self._category_to_page_type(claim.category)

        for page in candidates:
            score = 0.0
            page_entity_norm = self._normalize_text(page.entity_key)
            if entity_norm and entity_norm == page_entity_norm:
                score += 0.65
            if entity_norm and entity_norm == self._normalize_text(page.slug):
                score += 0.55
            if page.page_type == page_type:
                score += 0.15

            candidate_tokens = set(self._tokens(page.title + " " + page.entity_key + " " + " ".join(page.aliases)))
            if claim_tokens and candidate_tokens:
                overlap = len(claim_tokens & candidate_tokens) / max(len(claim_tokens), 1)
                score += min(overlap * 0.4, 0.2)

            title_similarity = self._text_similarity(claim.entity_key, page.title)
            score += min(title_similarity * 0.2, 0.1)
            score = min(score, 1.0)
            scored.append((score, page))

        scored.sort(key=lambda item: item[0], reverse=True)
        top_score, top_page = scored[0]

        if top_score >= self.threshold_high:
            return PageResolution(
                mode="existing",
                page=top_page,
                confidence=top_score,
                rationale=f"matched existing page by entity/title similarity score={top_score:.2f}",
            )
        if top_score >= self.threshold_mid:
            return PageResolution(
                mode="existing_low_confidence",
                page=top_page,
                confidence=top_score,
                rationale=f"weak page match score={top_score:.2f}, human validation required",
            )
        return PageResolution(
            mode="new_page",
            page=None,
            confidence=top_score,
            rationale=f"no reliable page match score={top_score:.2f}",
        )

    def _resolve_section(
        self,
        *,
        page_type: str,
        category: str,
        claim_text: str,
        existing_sections: list[SectionRecord],
    ) -> tuple[str, str, bool]:
        taxonomy = SECTION_TAXONOMY.get(page_type, SECTION_TAXONOMY["general"])
        existing_map = {s.section_key: s for s in existing_sections}

        preferred = self._section_by_keywords(category + " " + claim_text, taxonomy)
        if preferred in existing_map:
            section = existing_map[preferred]
            return section.section_key, section.heading, False

        if preferred:
            heading = next((h for key, h in taxonomy if key == preferred), preferred.replace("_", " ").title())
            return preferred, heading, True

        fallback_key, fallback_heading = taxonomy[0]
        if fallback_key in existing_map:
            section = existing_map[fallback_key]
            return section.section_key, section.heading, False
        return fallback_key, fallback_heading, True

    def _create_draft_page(
        self,
        conn,
        claim: ClaimInput,
        page_type: str,
        section_key: str,
        section_heading: str,
    ) -> PageRecord:
        page_id = uuid.uuid4()
        title = self._title_from_entity(claim.entity_key)
        slug_base = self._slugify(claim.entity_key) or self._slugify(claim.category) or "page"
        slug = self._ensure_unique_slug(conn, claim.project_id, slug_base)
        bootstrap_markdown = (
            f"# {title}\n\n"
            f"## Summary\n"
            f"- Draft page generated from claim `{claim.id}`.\n\n"
            f"## {section_heading}\n"
            f"- Pending approval.\n"
        )
        metadata = {"created_from_claim": str(claim.id), "mode": "draft_generation"}
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO wiki_pages (
                  id, project_id, page_type, title, slug, entity_key, status, current_version, metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'draft', 1, %s)
                """,
                (page_id, claim.project_id, page_type, title, slug, claim.entity_key, self._jsonb(metadata)),
            )
            cur.execute(
                """
                INSERT INTO wiki_page_versions (
                  id, page_id, version, markdown, ast_json, source, created_by, change_summary
                )
                VALUES (%s, %s, 1, %s, %s, 'system', 'synapse-worker', 'initial draft shell')
                """,
                (uuid.uuid4(), page_id, bootstrap_markdown, self._jsonb([])),
            )
            cur.execute(
                """
                INSERT INTO wiki_sections (page_id, section_key, heading, order_index, statement_count)
                VALUES (%s, %s, %s, 0, 0)
                ON CONFLICT (page_id, section_key) DO NOTHING
                """,
                (page_id, section_key, section_heading),
            )

        return PageRecord(
            id=page_id,
            project_id=claim.project_id,
            page_type=page_type,
            title=title,
            slug=slug,
            entity_key=claim.entity_key,
            status="draft",
            aliases=[],
        )

    def _ensure_unique_slug(self, conn, project_id: str, slug_base: str) -> str:
        slug = slug_base
        index = 2
        with conn.cursor() as cur:
            while True:
                cur.execute(
                    """
                    SELECT 1
                    FROM wiki_pages
                    WHERE project_id = %s
                      AND slug = %s
                    LIMIT 1
                    """,
                    (project_id, slug),
                )
                if cur.fetchone() is None:
                    return slug
                slug = f"{slug_base}-{index}"
                index += 1

    def _deduplicate(
        self,
        *,
        claim_text: str,
        fingerprint: str,
        statements: list[StatementRecord],
        incoming_valid_from: datetime | None,
        incoming_valid_to: datetime | None,
    ) -> DedupResult:
        incoming = self._normalize_text(claim_text)
        best_similarity = 0.0
        best_statement: StatementRecord | None = None

        for statement in statements:
            if not self._temporal_ranges_overlap(
                incoming_valid_from,
                incoming_valid_to,
                statement.valid_from,
                statement.valid_to,
            ):
                continue
            if statement.claim_fingerprint == fingerprint:
                return DedupResult(decision="reinforcement", matched_statement=statement, confidence=0.97)
            similarity = self._text_similarity(incoming, statement.normalized_text)
            if similarity > best_similarity:
                best_similarity = similarity
                best_statement = statement

        if best_statement is None:
            return DedupResult(decision="new_statement", matched_statement=None, confidence=0.5)
        if best_similarity >= 0.94:
            return DedupResult(decision="reinforcement", matched_statement=best_statement, confidence=best_similarity)
        if best_similarity >= 0.88:
            return DedupResult(decision="duplicate_ignored", matched_statement=best_statement, confidence=best_similarity)
        return DedupResult(decision="new_statement", matched_statement=best_statement, confidence=max(best_similarity, 0.5))

    def _detect_conflict(
        self,
        incoming_claim_text: str,
        statements: list[StatementRecord],
        *,
        incoming_valid_from: datetime | None,
        incoming_valid_to: datetime | None,
    ) -> tuple[uuid.UUID, str, StatementRecord] | None:
        incoming_tokens = set(self._tokens(incoming_claim_text))
        for statement in statements:
            if not self._temporal_ranges_overlap(
                incoming_valid_from,
                incoming_valid_to,
                statement.valid_from,
                statement.valid_to,
            ):
                continue
            existing_tokens = set(self._tokens(statement.statement_text))
            for positive, negative in CONTRADICTION_GROUPS:
                incoming_is_positive = bool(incoming_tokens & positive)
                incoming_is_negative = bool(incoming_tokens & negative)
                existing_is_positive = bool(existing_tokens & positive)
                existing_is_negative = bool(existing_tokens & negative)

                contradiction = (incoming_is_positive and existing_is_negative) or (
                    incoming_is_negative and existing_is_positive
                )
                if not contradiction:
                    continue

                context_overlap = len((incoming_tokens & existing_tokens) - positive - negative - STOP_WORDS)
                if context_overlap >= 1:
                    return (statement.id, "predicate_polarity_mismatch", statement)
        return None

    def _insert_conflict(
        self,
        conn,
        claim: ClaimInput,
        page_id: uuid.UUID,
        conflicting_statement_id: uuid.UUID,
        conflict_type: str,
        incoming_text: str,
        existing_statement: StatementRecord,
        *,
        incoming_valid_from: datetime | None,
        incoming_valid_to: datetime | None,
    ) -> None:
        details = {
            "incoming": incoming_text,
            "existing": existing_statement.statement_text,
            "claim_id": str(claim.id),
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "incoming_valid_from": incoming_valid_from.isoformat() if incoming_valid_from else None,
            "incoming_valid_to": incoming_valid_to.isoformat() if incoming_valid_to else None,
            "existing_valid_from": existing_statement.valid_from.isoformat() if existing_statement.valid_from else None,
            "existing_valid_to": existing_statement.valid_to.isoformat() if existing_statement.valid_to else None,
        }
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO wiki_conflicts (
                  id, project_id, claim_id, page_id, conflicting_statement_id, conflict_type, resolution_status, details
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'open', %s)
                """,
                (
                    uuid.uuid4(),
                    claim.project_id,
                    claim.id,
                    page_id,
                    conflicting_statement_id,
                    conflict_type,
                    self._jsonb(details),
                ),
            )

    def _build_markdown_patch(
        self,
        *,
        decision: str,
        claim: ClaimInput,
        page: PageRecord,
        section_key: str,
        section_heading: str,
    ) -> str:
        evidence_suffix = self._format_evidence_suffix(claim.evidence)
        line = f"- {claim.claim_text}{evidence_suffix}"

        if decision == "new_page":
            return (
                f"# {page.title}\n\n"
                "## Summary\n"
                f"- Draft created from claim `{claim.id}`.\n\n"
                f"## {section_heading}\n"
                f"{line}\n"
            )
        if decision == "new_section":
            return f"@@ page:{page.slug}\n\n## {section_heading}\n{line}\n"
        if decision == "new_statement":
            return f"@@ page:{page.slug} section:{section_key}\n+ {line}\n"
        if decision == "reinforcement":
            return f"@@ page:{page.slug} section:{section_key}\n= reinforcement evidence attached to existing statement\n"
        if decision == "duplicate_ignored":
            return f"@@ page:{page.slug} section:{section_key}\n= duplicate ignored; no textual insertion\n"
        if decision == "conflict":
            return f"@@ page:{page.slug} section:{section_key}\n! conflict detected; human resolution required\n+ {line}\n"
        return f"@@ page:{page.slug} section:{section_key}\n+ {line}\n"

    def _build_semantic_diff(
        self,
        decision: str,
        incoming_text: str,
        matched_statement: StatementRecord | None,
    ) -> dict[str, Any]:
        before = matched_statement.statement_text if matched_statement else ""
        return {
            "decision": decision,
            "before": before,
            "after": incoming_text,
            "summary": self._semantic_summary(decision),
        }

    def _semantic_summary(self, decision: str) -> str:
        if decision == "new_page":
            return "new knowledge domain page proposed"
        if decision == "new_section":
            return "new section proposed for existing page"
        if decision == "new_statement":
            return "new statement proposed for existing section"
        if decision == "reinforcement":
            return "existing statement reinforced with new evidence"
        if decision == "duplicate_ignored":
            return "duplicate meaning detected and ignored"
        if decision == "conflict":
            return "incoming claim conflicts with active statement"
        return "draft proposal generated"

    def _build_rationale(
        self,
        page_rationale: str,
        dedup: DedupResult,
        decision: str,
        *,
        temporal_source: str,
        valid_from: datetime | None,
        valid_to: datetime | None,
    ) -> str:
        dedup_context = f"dedup={dedup.decision}, similarity_confidence={dedup.confidence:.2f}"
        temporal_context = (
            f"temporal_source={temporal_source}, valid_from={valid_from.isoformat() if valid_from else 'null'}, "
            f"valid_to={valid_to.isoformat() if valid_to else 'null'}"
        )
        return f"{page_rationale}; {dedup_context}; {temporal_context}; final_decision={decision}"

    def _merge_confidence(self, page_confidence: float, dedup_confidence: float, decision: str) -> float:
        base = (page_confidence * 0.55) + (dedup_confidence * 0.45)
        if decision == "conflict":
            base = max(base, 0.9)
        if decision == "new_page":
            base = min(base, 0.78)
        return max(0.0, min(1.0, round(base, 4)))

    def _claim_fingerprint(self, claim: ClaimInput) -> str:
        normalized = "|".join(
            [
                self._normalize_text(claim.project_id),
                self._normalize_text(claim.entity_key),
                self._normalize_text(claim.category),
                self._normalize_text(claim.claim_text),
            ]
        )
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _resolve_claim_valid_window(self, claim: ClaimInput) -> tuple[datetime | None, datetime | None, str]:
        explicit_from = self._ensure_utc(claim.valid_from) if claim.valid_from else None
        explicit_to = self._ensure_utc(claim.valid_to) if claim.valid_to else None
        if explicit_from is not None or explicit_to is not None:
            if explicit_from and explicit_to and explicit_from > explicit_to:
                return (explicit_from, None, "explicit_payload_invalid_window")
            return (explicit_from, explicit_to, "explicit_payload")

        inferred_from, inferred_to, inferred_source = self._extract_temporal_range_from_text(
            claim.claim_text,
            observed_at=claim.observed_at,
        )
        if inferred_from is not None or inferred_to is not None:
            return (inferred_from, inferred_to, inferred_source)

        if claim.observed_at is not None:
            return (self._ensure_utc(claim.observed_at), None, "observed_at_fallback")
        return (None, None, "none")

    def _extract_temporal_range_from_text(
        self,
        text: str,
        *,
        observed_at: datetime | None,
    ) -> tuple[datetime | None, datetime | None, str]:
        normalized = self._normalize_text(text)
        base_dt = self._ensure_utc(observed_at) if observed_at else datetime.now(timezone.utc)
        base_date = base_dt.date()
        date_pattern = r"\d{4}-\d{2}-\d{2}|\d{1,2}[./-]\d{1,2}(?:[./-]\d{2,4})?"

        between_match = re.search(
            rf"\b(?:between|между)\s+(?P<start>{date_pattern})\s+(?:and|и)\s+(?P<end>{date_pattern})\b",
            normalized,
        )
        if between_match is not None:
            start = self._parse_temporal_date(between_match.group("start"), base_date=base_date)
            end = self._parse_temporal_date(between_match.group("end"), base_date=base_date)
            if start and end:
                end_of_day = end.replace(hour=23, minute=59, second=59, microsecond=999999)
                if start <= end_of_day:
                    return (start, end_of_day, "text_between_range")

        from_to_match = re.search(
            rf"\b(?:from|since|starting|start|с|со)\s+(?P<start>{date_pattern})\s+(?:to|until|till|through|по|до)\s+(?P<end>{date_pattern})\b",
            normalized,
        )
        if from_to_match is not None:
            start = self._parse_temporal_date(from_to_match.group("start"), base_date=base_date)
            end = self._parse_temporal_date(from_to_match.group("end"), base_date=base_date)
            if start and end:
                end_of_day = end.replace(hour=23, minute=59, second=59, microsecond=999999)
                if start <= end_of_day:
                    return (start, end_of_day, "text_from_to_range")

        until_match = re.search(
            rf"\b(?:until|till|through|upto|up to|до)\s+(?P<end>{date_pattern})\b",
            normalized,
        )
        if until_match is not None:
            end = self._parse_temporal_date(until_match.group("end"), base_date=base_date)
            if end:
                start = self._ensure_utc(observed_at) if observed_at else base_dt
                end_of_day = end.replace(hour=23, minute=59, second=59, microsecond=999999)
                if start <= end_of_day:
                    return (start, end_of_day, "text_until")

        from_match = re.search(
            rf"\b(?:from|since|starting|start|с|со|после)\s+(?P<start>{date_pattern})\b",
            normalized,
        )
        if from_match is not None:
            start = self._parse_temporal_date(from_match.group("start"), base_date=base_date)
            if start:
                return (start, None, "text_from")

        return (None, None, "none")

    def _parse_temporal_date(self, value: str, *, base_date) -> datetime | None:
        token = value.strip()
        if not token:
            return None

        iso_match = re.fullmatch(r"\d{4}-\d{2}-\d{2}", token)
        if iso_match:
            try:
                parsed = datetime.fromisoformat(f"{token}T00:00:00+00:00")
            except ValueError:
                return None
            return parsed.astimezone(timezone.utc)

        parts = re.split(r"[./-]", token)
        if len(parts) not in {2, 3}:
            return None
        try:
            nums = [int(part) for part in parts]
        except ValueError:
            return None

        day: int
        month: int
        year: int
        if len(nums) == 3:
            if len(parts[0]) == 4:
                year, month, day = nums[0], nums[1], nums[2]
            else:
                day, month, year = nums[0], nums[1], nums[2]
                if year < 100:
                    year += 2000
        else:
            day, month = nums[0], nums[1]
            year = int(base_date.year)

        try:
            return datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            return None

    def _temporal_ranges_overlap(
        self,
        left_from: datetime | None,
        left_to: datetime | None,
        right_from: datetime | None,
        right_to: datetime | None,
    ) -> bool:
        lf = self._ensure_utc(left_from) if left_from else None
        lt = self._ensure_utc(left_to) if left_to else None
        rf = self._ensure_utc(right_from) if right_from else None
        rt = self._ensure_utc(right_to) if right_to else None

        if lt is not None and rf is not None and lt < rf:
            return False
        if rt is not None and lf is not None and rt < lf:
            return False
        return True

    def _ensure_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _category_to_page_type(self, category: str) -> str:
        value = self._normalize_text(category)
        if any(token in value for token in ("access", "gate", "entry", "доступ", "шлагбаум", "въезд", "пропуск", "карта")):
            return "access"
        if any(token in value for token in ("incident", "problem", "error", "сбой", "ошибка", "полом", "авар", "инцидент")):
            return "incident"
        if any(token in value for token in ("customer", "client", "preference", "клиент", "предпочт", "контакт")):
            return "customer"
        if any(token in value for token in ("policy", "ops", "operations", "restriction", "склад", "терминал", "доставка", "маршрут", "график")):
            return "operations"
        return "general"

    def _section_by_keywords(self, text: str, taxonomy: list[tuple[str, str]]) -> str | None:
        allowed_keys = {key for key, _ in taxonomy}
        normalized = self._normalize_text(text)
        for keyword, section_key in SECTION_KEYWORDS:
            if keyword in normalized and section_key in allowed_keys:
                return section_key
        return None

    def _format_evidence_suffix(self, evidence: list[dict[str, Any]]) -> str:
        if not evidence:
            return ""
        ids: list[str] = []
        for item in evidence[:3]:
            source_id = item.get("source_id") or item.get("id")
            if source_id:
                ids.append(str(source_id))
        if not ids:
            return ""
        return f" _(evidence: {', '.join(ids)})_"

    def _extract_source_ids(self, evidence: list[dict[str, Any]]) -> list[str]:
        source_ids: set[str] = set()
        for item in evidence:
            if not isinstance(item, dict):
                continue
            source_id = item.get("source_id") or item.get("id")
            if source_id:
                source_ids.add(str(source_id))
        return sorted(source_ids)

    def _normalize_text(self, text: str) -> str:
        normalized = unicodedata.normalize("NFKC", text).lower().strip()
        normalized = re.sub(r"[^\w\s:.-]+", " ", normalized, flags=re.UNICODE)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def _tokens(self, text: str) -> list[str]:
        normalized = self._normalize_text(text)
        return [token for token in re.split(r"[\s:.-]+", normalized) if token and token not in STOP_WORDS]

    def _text_similarity(self, a: str, b: str) -> float:
        return SequenceMatcher(None, self._normalize_text(a), self._normalize_text(b)).ratio()

    def _title_from_entity(self, entity_key: str) -> str:
        compact = re.sub(r"[_-]+", " ", entity_key).strip()
        if not compact:
            return "Untitled Knowledge Page"
        return " ".join(part.capitalize() for part in compact.split())

    def _slugify(self, value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value).lower().strip()
        normalized = re.sub(r"[^\w]+", "-", normalized, flags=re.UNICODE)
        normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
        return normalized[:96]

    def _stable_uuid(self, value: str) -> uuid.UUID:
        return uuid.uuid5(uuid.NAMESPACE_URL, value)

    def _claims_has_fingerprint_column(self, conn) -> bool:
        if self._claims_has_fingerprint_column_cache is not None:
            return self._claims_has_fingerprint_column_cache
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'claims'
                  AND column_name = 'claim_fingerprint'
                LIMIT 1
                """
            )
            self._claims_has_fingerprint_column_cache = cur.fetchone() is not None
        return self._claims_has_fingerprint_column_cache

    def debug_explain_claim(self, claim_payload: dict[str, Any]) -> str:
        """Small helper for local debugging and observability."""
        claim = ClaimInput.from_payload(claim_payload)
        fingerprint = self._claim_fingerprint(claim)
        summary = {
            "claim_id": str(claim.id),
            "project_id": claim.project_id,
            "entity_key": claim.entity_key,
            "category": claim.category,
            "fingerprint": fingerprint,
            "tokens": self._tokens(claim.claim_text),
        }
        return json.dumps(summary, indent=2, ensure_ascii=False)

    def _jsonb(self, payload: Any) -> Any:
        from psycopg.types.json import Jsonb

        return Jsonb(payload)
