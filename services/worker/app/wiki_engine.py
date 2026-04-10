from __future__ import annotations

import hashlib
import json
import os
import re
import time
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
    "process": [
        ("triggers", "Triggers"),
        ("steps", "Steps"),
        ("exceptions", "Exceptions"),
        ("escalation", "Escalation"),
        ("verification", "Outcome Verification"),
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
    ("process", "steps"),
    ("procedure", "steps"),
    ("runbook", "steps"),
    ("playbook", "steps"),
    ("sop", "steps"),
    ("workflow", "steps"),
    ("step", "steps"),
    ("if", "triggers"),
    ("when", "triggers"),
    ("then", "steps"),
    ("except", "exceptions"),
    ("unless", "exceptions"),
    ("escalat", "escalation"),
    ("handoff", "escalation"),
    ("verify", "verification"),
    ("checklist", "verification"),
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

DEFAULT_GATEKEEPER_ROUTING_POLICY: dict[str, Any] = {
    "blocked_category_keywords": [
        "order",
        "заказ",
        "telemetry",
        "trace",
        "runtime_event",
        "event_stream",
        "status_update",
        "message_log",
        "task_event",
    ],
    "blocked_source_system_keywords": [
        "order_stream",
        "event_stream",
        "telemetry",
        "trace",
        "runtime",
        "queue",
        "webhook_events",
        "task_runtime",
        "wand_employee",
        "wand_transport_vehicle",
        "sheet",
    ],
    "blocked_source_type_keywords": [
        "external_event",
        "webhook_event",
        "event",
        "trace_event",
    ],
    "blocked_entity_keywords": [
        "order_snapshot",
        "invoice_snapshot",
        "event_snapshot",
        "raw_payload",
        "order_event",
        "invoice_event",
    ],
    "blocked_source_id_keywords": [
        "order_snapshot",
        "invoice_snapshot",
        "event_snapshot",
        "orders_feed",
        "status_stream",
        "webhook_event",
        "telemetry",
        "trace",
        "payload_dump",
        "wand_employee",
        "wand_transport_vehicle",
        "_sheet_",
    ],
    "event_stream_token_keywords": [
        "order",
        "заказ",
        "event",
        "telemetry",
        "trace",
        "log",
        "queue",
        "task",
        "status",
        "state",
        "created",
        "updated",
        "assigned",
        "shipped",
        "delivered",
        "cancelled",
        "processing",
        "completed",
        "shipment",
        "dispatch",
        "delivery",
    ],
    "durable_signal_keywords": [
        "policy",
        "process",
        "procedure",
        "instruction",
        "rule",
        "runbook",
        "manual",
        "playbook",
        "preference",
        "prefer",
        "prefers",
        "contact",
        "workaround",
        "incident",
        "required",
        "must",
        "forbidden",
        "закрыт",
        "карантин",
        "регламент",
        "правило",
        "процесс",
        "инструкция",
        "предпочт",
        "контакт",
        "обход",
        "инцидент",
    ],
    "ingestion_classification_default_deny_classes": [
        "operational_stream",
        "pii_sensitive_stream",
    ],
    "operational_stream_keywords": [
        "order_snapshot",
        "invoice_snapshot",
        "wand_employee",
        "wand_transport_vehicle",
        "_sheet_",
        "telemetry",
        "runtime_event",
        "event_stream",
        "payload_dump",
    ],
    "pii_sensitive_keywords": [
        "passport",
        "ssn",
        "credit card",
        "card_number",
        "personal_data",
        "персональ",
        "паспорт",
    ],
    "event_stream_min_numeric_token_ratio": 0.45,
    "event_stream_min_token_hits": 2,
    "event_stream_min_kv_hits": 2,
    "min_durable_signal_hits": 1,
    "min_durable_signal_hits_for_backfill": 1,
    "high_signal_route_keywords": [
        "policy",
        "process",
        "procedure",
        "runbook",
        "playbook",
        "sop",
        "manual",
        "instruction",
        "escalation",
        "access",
        "compliance",
        "business_rule",
        "company_operating_model",
        "operating_model",
        "logistics_kpi_framework",
        "kpi_framework",
        "регламент",
        "правило",
        "процесс",
        "инструкция",
        "эскалац",
        "доступ",
    ],
    "high_signal_min_keyword_hits": 1,
    "claims_floor_min_events": 120,
    "claims_floor_alert_after_minutes": 20,
    "claims_floor_min_conversion_ratio": 0.01,
    "publish_mode_by_assertion_class": {
        "policy": "conditional",
        "process": "conditional",
        "preference": "auto_publish",
        "incident": "human_required",
        "event": "human_required",
        "fact": "conditional",
    },
    "auto_publish_risk_keywords_high": [
        "legal",
        "compliance",
        "privacy",
        "gdpr",
        "security",
        "credential",
        "payment",
        "payout",
        "invoice",
        "refund",
        "chargeback",
        "billing",
        "pii",
        "персональн",
        "платеж",
        "возврат",
        "комплаенс",
        "безопас",
        "юрид",
    ],
    "auto_publish_risk_keywords_medium": [
        "sla",
        "finance",
        "contract",
        "discount",
        "pricing",
        "price",
        "settlement",
        "tax",
        "штраф",
        "договор",
        "финанс",
        "цена",
        "скидк",
    ],
    "auto_publish_force_human_required_levels": ["high"],
    "process_simulation_require_for_page_types": ["process", "policy", "incident"],
    "process_simulation_block_levels": ["high"],
    "process_simulation_sample_limit": 10,
    "retrieval_feedback_window_days": 30,
    "retrieval_feedback_min_events": 3,
    "retrieval_feedback_block_negative_ratio": 0.7,
    "retrieval_feedback_block_balance": 2,
    "require_multi_source_for_wiki": True,
    "min_sources_for_wiki_candidate": 2,
    "min_evidence_for_wiki_candidate": 2,
    "allow_policy_or_incident_override": True,
    "backfill_requires_policy_signal": True,
    "backfill_llm_classifier_mode": "off",
    "backfill_llm_classifier_min_confidence": 0.78,
    "backfill_llm_classifier_ambiguous_only": True,
    "backfill_llm_classifier_model": "",
    "emit_reinforcement_drafts": False,
    "draft_flood_max_open_per_page": 200,
    "draft_flood_max_open_per_entity": 400,
    "queue_pressure_safe_mode_open_drafts_threshold": 5000,
    "queue_pressure_safe_mode_open_drafts_per_page_threshold": 200,
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
    "process": (
        "process",
        "procedure",
        "workflow",
        "runbook",
        "playbook",
        "sop",
        "step",
        "when",
        "if",
        "then",
        "escalation",
        "handoff",
        "verification",
        "процесс",
        "процедур",
        "регламент",
        "инструкц",
        "шаг",
        "эскалац",
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
    metadata: dict[str, Any]
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
            metadata=dict(payload.get("metadata") or {}) if isinstance(payload.get("metadata"), dict) else {},
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
    publish_mode_default: str = "auto_publish"
    publish_mode_by_category: dict[str, str] | None = None
    routing_policy: dict[str, Any] | None = None
    auto_publish_min_score: float = 0.9
    auto_publish_min_sources: int = 3
    auto_publish_require_golden: bool = True
    auto_publish_allow_conflicts: bool = False


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
        threshold_new_page_margin: float = 0.08,
        threshold_route_ambiguity_gap: float = 0.06,
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
        self.threshold_new_page_margin = max(0.0, min(0.3, threshold_new_page_margin))
        self.threshold_route_ambiguity_gap = max(0.0, min(1.0, threshold_route_ambiguity_gap))
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
        self._backfill_batches_have_decision_counters_cache: bool | None = None
        self._backfill_batches_have_reason_counters_cache: bool | None = None
        self._gatekeeper_config_has_llm_columns_cache: bool | None = None
        self._gatekeeper_config_has_publish_columns_cache: bool | None = None
        self._gatekeeper_config_has_routing_policy_column_cache: bool | None = None
        self._routing_feedback_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._page_context_cache: dict[str, tuple[float, str]] = {}
        self.routing_feedback_cache_ttl_sec = max(
            15,
            int(str(os.getenv("SYNAPSE_ROUTING_FEEDBACK_CACHE_TTL_SEC", "120")).strip() or "120"),
        )
        self.page_context_cache_ttl_sec = max(
            15,
            int(str(os.getenv("SYNAPSE_PAGE_CONTEXT_CACHE_TTL_SEC", "60")).strip() or "60"),
        )
        self.route_rerank_top_k = max(
            1,
            int(str(os.getenv("SYNAPSE_ROUTE_RERANK_TOP_K", "8")).strip() or "8"),
        )

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

    def extract_backfill_claims(self, conn, *, limit: int = 200) -> dict[str, Any]:
        picked = self._pick_backfill_events(conn, limit=limit)
        project_routing_policy_cache: dict[str, dict[str, Any]] = {}
        drop_reason_counts: dict[str, int] = {}
        keep_reason_counts: dict[str, int] = {}

        def _bump(counter: dict[str, int], reason: str | None) -> None:
            key = self._normalize_counter_reason(reason)
            if not key:
                return
            counter[key] = int(counter.get(key, 0)) + 1

        metrics = {
            "picked": len(picked),
            "claims_generated": 0,
            "events_completed": 0,
            "failed": 0,
            "dropped_event_like": 0,
            "kept_durable": 0,
            "trusted_bypass": 0,
            "drop_reason_counts": drop_reason_counts,
            "keep_reason_counts": keep_reason_counts,
        }
        for event_id, project_id, agent_id, session_id, payload, observed_at in picked:
            payload_dict = payload if isinstance(payload, dict) else {}
            try:
                with conn.transaction():
                    self._set_event_pipeline_state(conn, event_id, status="processing")
                    content = str(payload_dict.get("content") or "").strip()[:4000]
                    metadata_raw = payload_dict.get("metadata")
                    metadata_dict = metadata_raw if isinstance(metadata_raw, dict) else {}
                    source_id = str(payload_dict.get("source_id") or event_id)
                    if project_id not in project_routing_policy_cache:
                        project_config = self._resolve_gatekeeper_config(conn, project_id)
                        routing_policy = (
                            project_config.routing_policy if isinstance(project_config.routing_policy, dict) else None
                        )
                        project_routing_policy_cache[project_id] = self._normalize_gatekeeper_routing_policy(
                            routing_policy
                        )
                    project_routing_policy = project_routing_policy_cache.get(project_id)
                    suppression_eval: dict[str, Any] | None = None
                    if len(content) >= 8:
                        category_for_eval, _ = self._resolve_backfill_category(
                            payload=payload_dict,
                            metadata=metadata_dict,
                            content=content,
                        )
                        suppression_eval = self._evaluate_backfill_suppression(
                            source_id=source_id,
                            content=content,
                            category=category_for_eval,
                            payload=payload_dict,
                            metadata=metadata_dict,
                            routing_policy=project_routing_policy,
                        )
                    claim_payload = self._claim_payload_from_backfill_event(
                        event_id=event_id,
                        project_id=project_id,
                        agent_id=agent_id,
                        session_id=session_id,
                        payload=payload_dict,
                        observed_at=observed_at,
                        suppression_eval=suppression_eval,
                        routing_policy=project_routing_policy,
                    )
                    generated = 0
                    dropped_event_like_increment = 0
                    kept_durable_increment = 0
                    trusted_bypass_increment = 0
                    suppression_reason: str | None = None
                    keep_reason: str | None = None
                    if claim_payload is not None:
                        self._enqueue_claim_proposal(conn, claim_payload)
                        generated = 1
                        if suppression_eval and bool(suppression_eval.get("trusted_hint")):
                            trusted_bypass_increment = 1
                            keep_reason = "trusted_hint"
                        elif suppression_eval and bool(suppression_eval.get("has_durable_signal")):
                            kept_durable_increment = 1
                            keep_reason = str(
                                suppression_eval.get("durable_signal_reason")
                                or "durable_signal"
                            )
                        else:
                            keep_reason = "kept_unsuppressed"
                    elif suppression_eval:
                        reason = str(suppression_eval.get("reason") or "")
                        suppression_reason = reason or "suppressed_unknown"
                        if reason in {
                            "event_like_low_signal",
                            "event_transport_low_signal",
                            "blocked_source_id",
                            "llm_override_skip_event",
                        }:
                            dropped_event_like_increment = 1
                    self._set_event_pipeline_state(conn, event_id, status="completed")
                    self._update_backfill_batch_metrics(
                        conn,
                        payload_dict,
                        processed_increment=1,
                        generated_increment=generated,
                        dropped_event_like_increment=dropped_event_like_increment,
                        kept_durable_increment=kept_durable_increment,
                        trusted_bypass_increment=trusted_bypass_increment,
                        drop_reason=suppression_reason,
                        keep_reason=keep_reason,
                        failed=False,
                    )
                metrics["claims_generated"] += generated
                metrics["events_completed"] += 1
                metrics["dropped_event_like"] += dropped_event_like_increment
                metrics["kept_durable"] += kept_durable_increment
                metrics["trusted_bypass"] += trusted_bypass_increment
                _bump(drop_reason_counts, suppression_reason)
                _bump(keep_reason_counts, keep_reason)
            except Exception as exc:
                with conn.transaction():
                    self._set_event_pipeline_state(conn, event_id, status="failed", last_error=str(exc))
                    self._update_backfill_batch_metrics(
                        conn,
                        payload_dict,
                        processed_increment=0,
                        generated_increment=0,
                        drop_reason="worker_exception",
                        failed=True,
                    )
                metrics["failed"] += 1
                _bump(drop_reason_counts, "worker_exception")
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
        suppression_eval: dict[str, Any] | None = None,
        routing_policy: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        content = str(payload.get("content") or "").strip()
        if len(content) < 8:
            return None
        content = content[:4000]

        source_id = str(payload.get("source_id") or event_id)
        metadata = payload.get("metadata")
        metadata_dict = metadata if isinstance(metadata, dict) else {}
        ingest_lane = self._resolve_backfill_ingest_lane(payload=payload, metadata=metadata_dict)
        entity_key, entity_source = self._resolve_backfill_entity_key(payload=payload, metadata=metadata_dict, source_id=source_id, content=content)
        category, category_source = self._resolve_backfill_category(payload=payload, metadata=metadata_dict, content=content)
        evaluation = suppression_eval or self._evaluate_backfill_suppression(
            source_id=source_id,
            content=content,
            category=category,
            payload=payload,
            metadata=metadata_dict,
            routing_policy=routing_policy,
        )
        if bool(evaluation.get("skip")):
            return None
        process_triplet = self._extract_process_triplet(content) if self._category_to_page_type(category) == "process" else None

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
        evidence_source_type = "knowledge_ingest" if ingest_lane == "knowledge" else "external_event"
        evidence_tool_name = "knowledge_backfill" if ingest_lane == "knowledge" else "memory_backfill"
        backfill_meta = payload.get("backfill")
        backfill_source_system = None
        if isinstance(backfill_meta, dict):
            raw_backfill_source_system = str(backfill_meta.get("source_system") or "").strip()
            if raw_backfill_source_system:
                backfill_source_system = raw_backfill_source_system
        if backfill_source_system is None:
            raw_metadata_source_system = str(
                metadata_dict.get("source_system") or metadata_dict.get("source") or ""
            ).strip()
            if raw_metadata_source_system:
                backfill_source_system = raw_metadata_source_system
        evidence = [
            {
                "source_type": evidence_source_type,
                "source_id": source_id,
                "session_id": session_id,
                "snippet": content[:280],
                "observed_at": observed_iso,
                "tool_name": evidence_tool_name,
                "url": None,
                "event_id": str(event_id),
                "agent_id": agent_id,
                "ingest_lane": ingest_lane,
                "source_system": backfill_source_system,
                "entity_inference_source": entity_source,
                "category_inference_source": category_source,
                "process_triplet": process_triplet,
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

    def _should_skip_backfill_claim(
        self,
        *,
        source_id: str,
        content: str,
        category: str,
        payload: dict[str, Any],
        metadata: dict[str, Any],
        routing_policy: dict[str, Any] | None = None,
    ) -> bool:
        evaluation = self._evaluate_backfill_suppression(
            source_id=source_id,
            content=content,
            category=category,
            payload=payload,
            metadata=metadata,
            routing_policy=routing_policy,
        )
        return bool(evaluation.get("skip"))

    def _evaluate_backfill_suppression(
        self,
        *,
        source_id: str,
        content: str,
        category: str,
        payload: dict[str, Any],
        metadata: dict[str, Any],
        routing_policy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ingest_lane = self._resolve_backfill_ingest_lane(payload=payload, metadata=metadata)
        trusted_hint = self._has_backfill_trusted_knowledge_hint(payload=payload, metadata=metadata)
        if trusted_hint:
            return {
                "skip": False,
                "reason": None,
                "trusted_hint": True,
                "has_durable_signal": True,
                "ingest_lane": ingest_lane,
            }

        policy = self._normalize_gatekeeper_routing_policy(routing_policy)
        normalized_source_id = self._normalize_text(source_id)
        if any(keyword in normalized_source_id for keyword in policy.get("blocked_source_id_keywords", []) if keyword):
            return {
                "skip": True,
                "reason": "blocked_source_id",
                "trusted_hint": False,
                "has_durable_signal": False,
            }

        normalized_content = self._normalize_text(content)
        token_set = set(self._tokens(content))
        expanded_token_set = set(token_set)
        for token in token_set:
            for chunk in re.split(r"[_/]+", token):
                value = chunk.strip()
                if value:
                    expanded_token_set.add(value)
        event_stream_token_keywords = set(
            str(item).strip().lower() for item in policy.get("event_stream_token_keywords", []) if str(item).strip()
        )
        durable_signal_keywords = list(policy.get("durable_signal_keywords", []))
        high_signal_route_keywords = list(policy.get("high_signal_route_keywords", []))
        min_durable_signal_hits_for_backfill = int(policy.get("min_durable_signal_hits_for_backfill", 1))
        high_signal_min_keyword_hits = int(policy.get("high_signal_min_keyword_hits", 1))
        event_stream_min_token_hits = int(policy.get("event_stream_min_token_hits", 2))
        event_stream_min_kv_hits = int(policy.get("event_stream_min_kv_hits", 2))
        event_stream_min_numeric_token_ratio = float(policy.get("event_stream_min_numeric_token_ratio", 0.45))
        durable_hits = self._count_keyword_hits(
            normalized_text=normalized_content,
            token_set=expanded_token_set,
            keywords=durable_signal_keywords,
        )
        policy_signal_tokens = {
            "policy",
            "rule",
            "rules",
            "must",
            "required",
            "forbidden",
            "access",
            "quarantine",
            "runbook",
            "process",
            "procedure",
            "escalation",
        }
        has_durable_keyword_signal = bool(expanded_token_set & policy_signal_tokens)
        has_durable_signal = (
            durable_hits >= min_durable_signal_hits_for_backfill
            or has_durable_keyword_signal
        )
        durable_signal_reason = "none"
        if has_durable_keyword_signal:
            durable_signal_reason = "policy_token"
        elif durable_hits >= min_durable_signal_hits_for_backfill:
            durable_signal_reason = "durable_keyword"
        event_hits = sum(1 for token in expanded_token_set if token in event_stream_token_keywords)
        kv_hits = len(
            re.findall(
                r"\b(order_id|invoice_id|status|state|created_at|updated_at|customer_id|task_id|event_id)\s*[:=]",
                normalized_content,
            )
        )
        numeric_token_count = sum(1 for token in expanded_token_set if any(ch.isdigit() for ch in token))
        numeric_token_ratio = float(numeric_token_count) / float(max(len(expanded_token_set), 1))
        has_order_like_id_pattern = bool(
            re.search(
                r"\b(order|заказ|task|event|ticket|shipment|delivery)[\s_:#-]{0,12}[a-z0-9_-]{3,}\b",
                normalized_content,
            )
        )
        has_structured_blob = bool(
            (normalized_content.count("{") >= 1 and normalized_content.count("}") >= 1 and normalized_content.count(":") >= 3)
            or kv_hits >= event_stream_min_kv_hits
        )
        has_event_stream_shape = event_hits >= event_stream_min_token_hits and (
            has_structured_blob or kv_hits >= event_stream_min_kv_hits or numeric_token_ratio >= event_stream_min_numeric_token_ratio or has_order_like_id_pattern
        )

        source_system_values: set[str] = set()
        source_type_values: set[str] = set()
        for container in (payload, metadata):
            if not isinstance(container, dict):
                continue
            for key in ("source_system", "source", "stream", "topic", "queue", "feed", "channel"):
                value = self._normalize_text(str(container.get(key) or ""))
                if value:
                    source_system_values.add(value)
            for key in ("source_type", "event_type", "type", "record_type", "message_type", "kind"):
                value = self._normalize_text(str(container.get(key) or ""))
                if value:
                    source_type_values.add(value)
        blocked_source_system_keywords = list(policy.get("blocked_source_system_keywords", []))
        blocked_source_type_keywords = list(policy.get("blocked_source_type_keywords", []))
        operational_stream_keywords = list(policy.get("operational_stream_keywords", []))
        pii_sensitive_keywords = list(policy.get("pii_sensitive_keywords", []))
        ingestion_default_deny_classes = {
            str(item).strip().lower()
            for item in (policy.get("ingestion_classification_default_deny_classes") or [])
            if str(item).strip()
        }
        if not ingestion_default_deny_classes:
            ingestion_default_deny_classes = {"operational_stream", "pii_sensitive_stream"}
        blocked_by_source_system = any(
            self._keyword_matches_identifier(system, keyword)
            for system in source_system_values
            for keyword in blocked_source_system_keywords
            if keyword
        )
        blocked_by_source_type = any(
            self._keyword_matches_identifier(source_type, keyword)
            for source_type in source_type_values
            for keyword in blocked_source_type_keywords
            if keyword
        )
        category_hint = self._category_to_page_type(category)
        source_noise_only = (
            (blocked_by_source_system or blocked_by_source_type)
            and not has_durable_signal
            and category_hint in {"general", "operations"}
            and ingest_lane != "knowledge"
        )
        ingestion_classification_explicit = str(
            metadata.get("ingestion_classification")
            or payload.get("ingestion_classification")
            or (
                payload.get("backfill", {}).get("ingestion_classification")
                if isinstance(payload.get("backfill"), dict)
                else ""
            )
            or ""
        ).strip().lower()
        ingestion_classification_explicit_flag = bool(ingestion_classification_explicit)
        classification_haystack = " ".join(
            item
            for item in (
                normalized_content,
                self._normalize_text(category),
                self._normalize_text(source_id),
                " ".join(source_system_values),
                " ".join(source_type_values),
            )
            if item
        )
        classification_token_set = set(self._tokens(classification_haystack))
        high_signal_hits: list[str] = []
        for raw_keyword in high_signal_route_keywords:
            keyword = str(raw_keyword or "").strip().lower()
            if not keyword:
                continue
            if any(ch in keyword for ch in (" ", "_", "-", "/", ":")):
                matched = keyword in classification_haystack
            else:
                matched = keyword in classification_token_set
            if matched and keyword not in high_signal_hits:
                high_signal_hits.append(keyword)
            if len(high_signal_hits) >= 24:
                break
        has_high_signal_route = len(high_signal_hits) >= max(1, high_signal_min_keyword_hits)
        if has_high_signal_route:
            has_durable_signal = True
            durable_signal_reason = "high_signal_route"
        operational_keyword_hits = [
            keyword for keyword in operational_stream_keywords if keyword and keyword in classification_haystack
        ]
        pii_keyword_hits = [
            keyword for keyword in pii_sensitive_keywords if keyword and keyword in classification_haystack
        ]
        pii_regex_hits = bool(
            re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", content or "")
            or re.search(
                r"(?<!\d)(?:\+\d{7,15}|\d{10,15}|\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{4})(?!\d)",
                content or "",
            )
        )
        if ingestion_classification_explicit in {"evergreen_knowledge", "operational_stream", "pii_sensitive_stream"}:
            ingestion_classification = ingestion_classification_explicit
        elif pii_keyword_hits or pii_regex_hits:
            ingestion_classification = "pii_sensitive_stream"
        elif has_event_stream_shape or bool(operational_keyword_hits) or (
            (blocked_by_source_system or blocked_by_source_type) and not has_durable_signal
        ):
            ingestion_classification = "operational_stream"
        else:
            ingestion_classification = "evergreen_knowledge"
        ingestion_classification_hard_block = (
            (
                (ingestion_classification_explicit_flag and ingestion_classification in ingestion_default_deny_classes)
                or ingestion_classification == "pii_sensitive_stream"
            )
            and not trusted_hint
            and not (ingest_lane == "knowledge" and has_durable_signal)
        )
        heuristic_skip = False
        heuristic_reason: str | None = None
        if ingestion_classification_hard_block:
            heuristic_skip = True
            heuristic_reason = f"ingestion_classification:{ingestion_classification}"
        elif has_event_stream_shape and not has_durable_signal:
            heuristic_skip = True
            heuristic_reason = "event_like_low_signal"
        elif source_noise_only:
            heuristic_skip = True
            heuristic_reason = "event_transport_low_signal"

        llm_mode = str(policy.get("backfill_llm_classifier_mode") or "off").strip().lower()
        if llm_mode not in {"off", "assist", "enforce"}:
            llm_mode = "off"
        try:
            llm_min_confidence = float(policy.get("backfill_llm_classifier_min_confidence", 0.78))
        except Exception:
            llm_min_confidence = 0.78
        llm_min_confidence = max(0.0, min(1.0, llm_min_confidence))
        llm_ambiguous_only = bool(policy.get("backfill_llm_classifier_ambiguous_only", True))

        llm_assessment: GatekeeperLLMAssessment | None = None
        llm_applied = False
        llm_reason_code = "off"
        llm_ambiguous = bool(
            heuristic_skip
            or (has_event_stream_shape and has_durable_signal)
            or (not has_event_stream_shape and not has_durable_signal and len(normalized_content) >= 80)
        )

        if ingestion_classification_hard_block:
            llm_reason_code = "ingestion_classification_hard_block"
        elif llm_mode != "off" and (llm_ambiguous or not llm_ambiguous_only):
            llm_config = GatekeeperConfig(
                min_sources_for_golden=max(2, self.gatekeeper_min_sources_for_golden),
                conflict_free_days=max(1, self.gatekeeper_conflict_free_days),
                min_score_for_golden=max(0.0, min(1.0, self.gatekeeper_min_score_for_golden)),
                operational_short_text_len=max(8, self.gatekeeper_operational_short_text_len),
                operational_short_token_len=max(1, self.gatekeeper_operational_short_token_len),
                llm_assist_enabled=True,
                llm_provider=str(self.gatekeeper_llm_provider or "openai").strip().lower(),
                llm_model=str(
                    policy.get("backfill_llm_classifier_model")
                    or self.gatekeeper_llm_model
                    or "gpt-4.1-mini"
                ),
                llm_score_weight=1.0,
                llm_min_confidence=llm_min_confidence,
                llm_timeout_ms=max(200, self.gatekeeper_llm_timeout_ms),
            )
            synthetic_claim = ClaimInput(
                id=uuid.uuid4(),
                project_id="backfill",
                entity_key=str(source_id or "backfill_record"),
                category=str(category or "general"),
                claim_text=content[:4000],
                evidence=[{"source_type": "external_event", "source_id": str(source_id)}],
                metadata={"backfill_suppression_probe": True},
            )
            llm_assessment = self._run_gatekeeper_llm_assessment(
                claim=synthetic_claim,
                config=llm_config,
                features={
                    "evidence_count": 1,
                    "repeated_count": 0,
                    "source_diversity": 1,
                    "has_recent_open_conflict": False,
                    "is_short": len(normalized_content) <= max(8, self.gatekeeper_operational_short_text_len),
                    "has_policy_signal": has_durable_signal,
                    "has_operational_pattern": has_event_stream_shape,
                    "heuristic_tier": "operational_memory" if heuristic_skip else "insight_candidate",
                    "heuristic_score": 0.2 if heuristic_skip else 0.7,
                },
            )
            if llm_assessment.status == "ok" and llm_assessment.confidence is not None:
                if llm_assessment.confidence >= llm_min_confidence:
                    llm_reason_code = "confidence_ok"
                    llm_event_like = llm_assessment.suggested_tier == "operational_memory"
                    if llm_mode == "enforce":
                        if llm_event_like and not heuristic_skip:
                            heuristic_skip = True
                            heuristic_reason = "llm_override_skip_event"
                            llm_applied = True
                            llm_reason_code = "override_skip_event"
                        elif (not llm_event_like) and heuristic_skip:
                            heuristic_skip = False
                            heuristic_reason = "llm_override_keep_knowledge"
                            llm_applied = True
                            llm_reason_code = "override_keep_knowledge"
                        else:
                            llm_reason_code = "no_override_needed"
                    else:
                        llm_reason_code = "assist_only"
                else:
                    llm_reason_code = "below_confidence_threshold"
            elif llm_assessment is not None:
                llm_reason_code = str(llm_assessment.error or llm_assessment.status or "llm_unavailable")
        elif llm_mode != "off":
            llm_reason_code = "ambiguous_only_skipped"

        response: dict[str, Any] = {
            "skip": heuristic_skip,
            "reason": heuristic_reason,
            "trusted_hint": False,
            "has_durable_signal": has_durable_signal,
            "ingest_lane": ingest_lane,
            "heuristic_reason": heuristic_reason,
            "ingestion_classification": ingestion_classification,
            "ingestion_classification_hard_block": ingestion_classification_hard_block,
            "ingestion_default_deny_classes": sorted(ingestion_default_deny_classes),
            "ingestion_operational_keyword_hits": operational_keyword_hits[:20],
            "ingestion_pii_keyword_hits": pii_keyword_hits[:20],
            "ingestion_pii_regex_hits": pii_regex_hits,
            "llm_mode": llm_mode,
            "llm_ambiguous": llm_ambiguous,
            "llm_applied": llm_applied,
            "llm_reason_code": llm_reason_code,
            "durable_signal_reason": durable_signal_reason,
            "high_signal_route_hits": high_signal_hits,
            "high_signal_route_matched": has_high_signal_route,
        }
        if llm_assessment is not None:
            response["llm_status"] = llm_assessment.status
            response["llm_provider"] = llm_assessment.provider
            response["llm_model"] = llm_assessment.model
            response["llm_suggested_tier"] = llm_assessment.suggested_tier
            response["llm_confidence"] = llm_assessment.confidence
            response["llm_rationale"] = llm_assessment.rationale
            response["llm_error"] = llm_assessment.error
        return response

    def _has_backfill_trusted_knowledge_hint(
        self,
        *,
        payload: dict[str, Any],
        metadata: dict[str, Any],
    ) -> bool:
        for container in (payload, metadata):
            if not isinstance(container, dict):
                continue
            for key in ("knowledge_signal", "is_knowledge"):
                raw = container.get(key)
                if isinstance(raw, bool) and raw:
                    return True
                if isinstance(raw, (int, float)) and int(raw) == 1:
                    return True
                if isinstance(raw, str) and raw.strip().lower() in {"1", "true", "yes", "y", "on"}:
                    return True
            kind = str(container.get("record_kind") or container.get("kind") or "").strip().lower()
            if kind in {"knowledge", "policy", "incident", "preference", "runbook", "manual", "sop"}:
                return True
        return False

    def _resolve_backfill_ingest_lane(
        self,
        *,
        payload: dict[str, Any],
        metadata: dict[str, Any],
    ) -> str:
        candidates: list[Any] = []
        backfill = payload.get("backfill")
        if isinstance(backfill, dict):
            candidates.append(backfill.get("ingest_lane"))
        candidates.append(payload.get("ingest_lane"))
        candidates.append(metadata.get("ingest_lane"))
        for raw in candidates:
            lane = str(raw or "").strip().lower()
            if lane in {"knowledge", "event"}:
                return lane
        return "event"

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

    def _normalize_counter_reason(self, value: str | None) -> str:
        text = str(value or "").strip().lower()
        if not text:
            return ""
        text = re.sub(r"[^a-z0-9:_-]+", "_", text).strip("_")
        return text[:80]

    def _update_backfill_batch_metrics(
        self,
        conn,
        payload: dict[str, Any],
        *,
        processed_increment: int,
        generated_increment: int,
        dropped_event_like_increment: int = 0,
        kept_durable_increment: int = 0,
        trusted_bypass_increment: int = 0,
        drop_reason: str | None = None,
        keep_reason: str | None = None,
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

            normalized_drop_reason = self._normalize_counter_reason(drop_reason)
            normalized_keep_reason = self._normalize_counter_reason(keep_reason)
            has_reason_counters = self._backfill_batches_have_reason_counters(conn)

            if self._backfill_batches_have_decision_counters(conn):
                if has_reason_counters:
                    cur.execute(
                        """
                        UPDATE memory_backfill_batches
                        SET processed_events = processed_events + %s,
                            generated_claims = generated_claims + %s,
                            dropped_event_like = dropped_event_like + %s,
                            kept_durable = kept_durable + %s,
                            trusted_bypass = trusted_bypass + %s,
                            drop_reason_counts = CASE
                              WHEN %s = '' THEN COALESCE(drop_reason_counts, '{}'::jsonb)
                              ELSE jsonb_set(
                                COALESCE(drop_reason_counts, '{}'::jsonb),
                                ARRAY[%s],
                                to_jsonb(COALESCE((COALESCE(drop_reason_counts, '{}'::jsonb)->>%s)::int, 0) + 1),
                                TRUE
                              )
                            END,
                            keep_reason_counts = CASE
                              WHEN %s = '' THEN COALESCE(keep_reason_counts, '{}'::jsonb)
                              ELSE jsonb_set(
                                COALESCE(keep_reason_counts, '{}'::jsonb),
                                ARRAY[%s],
                                to_jsonb(COALESCE((COALESCE(keep_reason_counts, '{}'::jsonb)->>%s)::int, 0) + 1),
                                TRUE
                              )
                            END,
                            status = CASE
                              WHEN status = 'ready' THEN 'processing'
                              ELSE status
                            END,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            processed_increment,
                            generated_increment,
                            dropped_event_like_increment,
                            kept_durable_increment,
                            trusted_bypass_increment,
                            normalized_drop_reason,
                            normalized_drop_reason,
                            normalized_drop_reason,
                            normalized_keep_reason,
                            normalized_keep_reason,
                            normalized_keep_reason,
                            batch_id,
                        ),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE memory_backfill_batches
                        SET processed_events = processed_events + %s,
                            generated_claims = generated_claims + %s,
                            dropped_event_like = dropped_event_like + %s,
                            kept_durable = kept_durable + %s,
                            trusted_bypass = trusted_bypass + %s,
                            status = CASE
                              WHEN status = 'ready' THEN 'processing'
                              ELSE status
                            END,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            processed_increment,
                            generated_increment,
                            dropped_event_like_increment,
                            kept_durable_increment,
                            trusted_bypass_increment,
                            batch_id,
                        ),
                    )
            else:
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

    def _backfill_batches_have_decision_counters(self, conn) -> bool:
        if self._backfill_batches_have_decision_counters_cache is not None:
            return self._backfill_batches_have_decision_counters_cache
        required = {"dropped_event_like", "kept_durable", "trusted_bypass"}
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'memory_backfill_batches'
                """
            )
            present = {str(row[0]) for row in cur.fetchall()}
        self._backfill_batches_have_decision_counters_cache = required.issubset(present)
        return self._backfill_batches_have_decision_counters_cache

    def _backfill_batches_have_reason_counters(self, conn) -> bool:
        if self._backfill_batches_have_reason_counters_cache is not None:
            return self._backfill_batches_have_reason_counters_cache
        required = {"drop_reason_counts", "keep_reason_counts"}
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'memory_backfill_batches'
                """
            )
            present = {str(row[0]) for row in cur.fetchall()}
        self._backfill_batches_have_reason_counters_cache = required.issubset(present)
        return self._backfill_batches_have_reason_counters_cache

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
        config = self._resolve_gatekeeper_config(conn, claim.project_id)
        routing_policy = self._normalize_gatekeeper_routing_policy(config.routing_policy)
        gate = self._gatekeeper_decide(conn, claim, fingerprint, config=config)
        self._record_gatekeeper_decision(conn, claim, gate)
        assertion_class = str((gate.features or {}).get("assertion_class") or "fact").strip().lower() or "fact"
        self._upsert_claim(
            conn,
            claim,
            gate_tier=gate.tier,
            assertion_class=assertion_class,
            valid_from=valid_from,
            valid_to=valid_to,
            temporal_source=temporal_source,
        )

        if gate.tier == "operational_memory":
            return

        page_candidates = self._load_pages(conn, claim.project_id)
        page_resolution = self._resolve_page(claim, page_candidates, conn=conn)

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

        emit_reinforcement_drafts = bool(routing_policy.get("emit_reinforcement_drafts", False))
        if decision in {"reinforcement", "duplicate_ignored"} and not emit_reinforcement_drafts:
            self._set_claim_status(
                conn,
                claim_id=claim.id,
                status="rejected",
                rejection_reason="reinforcement_suppressed",
                rejection_details={
                    "decision": decision,
                    "page_id": str(page.id),
                    "section_key": section_key,
                    "policy_key": "emit_reinforcement_drafts",
                    "policy_value": False,
                },
            )
            self._upsert_wiki_claim_link(
                conn,
                claim_id=claim.id,
                page_id=page.id,
                section_key=section_key,
                insertion_status=decision,
            )
            return

        if draft_status == "pending_review":
            flood_guard = self._evaluate_draft_flood_guard(
                conn,
                project_id=claim.project_id,
                page_id=page.id,
                entity_key=page.entity_key,
                routing_policy=routing_policy,
            )
            if bool(flood_guard.get("blocked")):
                self._set_claim_status(
                    conn,
                    claim_id=claim.id,
                    status="rejected",
                    rejection_reason=str(flood_guard.get("reason") or "draft_flood_guard"),
                    rejection_details=flood_guard,
                )
                self._upsert_wiki_claim_link(
                    conn,
                    claim_id=claim.id,
                    page_id=page.id,
                    section_key=section_key,
                    insertion_status="rejected",
                )
                return

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
        self._upsert_wiki_claim_link(
            conn,
            claim_id=claim.id,
            page_id=page.id,
            section_key=section_key,
            insertion_status=decision,
        )

    def _upsert_claim(
        self,
        conn,
        claim: ClaimInput,
        *,
        gate_tier: str,
        assertion_class: str,
        valid_from: datetime | None,
        valid_to: datetime | None,
        temporal_source: str,
    ) -> None:
        source_ids = self._extract_source_ids(claim.evidence)
        decision_context = self._extract_operator_decision_context(claim)
        metadata = {
            "source": "claim_proposal",
            "evidence_count": len(claim.evidence),
            "source_ids": source_ids,
            "gate_tier": gate_tier,
            "assertion_class": assertion_class,
            "temporal_source": temporal_source,
        }
        if claim.metadata:
            metadata["claim_metadata"] = dict(claim.metadata)
        if decision_context:
            metadata["operator_decision"] = decision_context
            ticket_ids = decision_context.get("ticket_ids")
            if isinstance(ticket_ids, list) and ticket_ids:
                metadata["linked_ticket_ids"] = ticket_ids
            outcome = str(decision_context.get("outcome") or "").strip().lower()
            if outcome:
                metadata["resolution_outcome"] = outcome
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

    def _gatekeeper_decide(
        self,
        conn,
        claim: ClaimInput,
        fingerprint: str,
        *,
        config: GatekeeperConfig | None = None,
    ) -> GatekeeperDecision:
        resolved_config = config or self._resolve_gatekeeper_config(conn, claim.project_id)
        repeated_count = self._count_existing_claims_by_fingerprint(conn, claim.project_id, fingerprint)
        historical_source_count = self._count_source_diversity_by_fingerprint(conn, claim.project_id, fingerprint)
        incoming_source_ids = self._extract_source_ids(claim.evidence)
        has_recent_open_conflict = self._has_recent_open_conflict_for_entity(
            conn,
            claim.project_id,
            claim.entity_key,
            days=resolved_config.conflict_free_days,
        )
        return self._gatekeeper_decide_from_inputs(
            claim=claim,
            config=resolved_config,
            repeated_count=repeated_count,
            historical_source_count=historical_source_count,
            incoming_source_ids=incoming_source_ids,
            has_recent_open_conflict=has_recent_open_conflict,
        )

    def _set_claim_status(
        self,
        conn,
        *,
        claim_id: uuid.UUID,
        status: str,
        rejection_reason: str | None = None,
        rejection_details: dict[str, Any] | None = None,
    ) -> None:
        metadata_patch: dict[str, Any] = {
            "synthesis_control": {
                "status": status,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        }
        if rejection_reason:
            metadata_patch["synthesis_control"]["reason"] = rejection_reason
        if isinstance(rejection_details, dict) and rejection_details:
            metadata_patch["synthesis_control"]["details"] = rejection_details
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE claims
                SET status = %s,
                    metadata = COALESCE(metadata, '{}'::jsonb) || %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (status, self._jsonb(metadata_patch), claim_id),
            )

    def _upsert_wiki_claim_link(
        self,
        conn,
        *,
        claim_id: uuid.UUID,
        page_id: uuid.UUID,
        section_key: str,
        insertion_status: str,
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO wiki_claim_links (claim_id, page_id, section_key, insertion_status)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (claim_id, page_id, section_key) DO UPDATE
                SET insertion_status = EXCLUDED.insertion_status,
                    created_at = NOW()
                """,
                (claim_id, page_id, section_key, insertion_status),
            )

    def _evaluate_draft_flood_guard(
        self,
        conn,
        *,
        project_id: str,
        page_id: uuid.UUID,
        entity_key: str,
        routing_policy: dict[str, Any],
    ) -> dict[str, Any]:
        max_open_per_page = int(routing_policy.get("draft_flood_max_open_per_page", 200) or 200)
        max_open_per_entity = int(routing_policy.get("draft_flood_max_open_per_entity", 400) or 400)
        max_open_total = int(routing_policy.get("queue_pressure_safe_mode_open_drafts_threshold", 5000) or 5000)

        with conn.cursor() as cur:
            cur.execute(
                """
                WITH queue_counts AS (
                  SELECT
                    COUNT(*)::bigint AS open_total,
                    COUNT(*) FILTER (WHERE page_id = %s)::bigint AS open_for_page
                  FROM wiki_draft_changes
                  WHERE project_id = %s
                    AND status IN ('pending_review', 'blocked_conflict')
                ),
                entity_counts AS (
                  SELECT COUNT(*)::bigint AS open_for_entity
                  FROM wiki_draft_changes d
                  JOIN wiki_pages p ON p.id = d.page_id
                  WHERE d.project_id = %s
                    AND d.status IN ('pending_review', 'blocked_conflict')
                    AND p.entity_key = %s
                )
                SELECT
                  qc.open_total,
                  qc.open_for_page,
                  ec.open_for_entity
                FROM queue_counts qc
                CROSS JOIN entity_counts ec
                """,
                (page_id, project_id, project_id, entity_key),
            )
            row = cur.fetchone() or (0, 0, 0)

        open_total = int(row[0] or 0)
        open_for_page = int(row[1] or 0)
        open_for_entity = int(row[2] or 0)
        blocked = (
            open_total >= max_open_total
            or open_for_page >= max_open_per_page
            or open_for_entity >= max_open_per_entity
        )
        if open_total >= max_open_total:
            reason = "draft_queue_pressure"
        elif open_for_page >= max_open_per_page:
            reason = "draft_flood_page_limit"
        elif open_for_entity >= max_open_per_entity:
            reason = "draft_flood_entity_limit"
        else:
            reason = "ok"
        return {
            "blocked": blocked,
            "reason": reason,
            "counts": {
                "open_total": open_total,
                "open_for_page": open_for_page,
                "open_for_entity": open_for_entity,
            },
            "thresholds": {
                "open_total": max_open_total,
                "open_for_page": max_open_per_page,
                "open_for_entity": max_open_per_entity,
            },
        }

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
        token_set = set(tokens)
        evidence_count = len(claim.evidence)
        is_short = len(text) < config.operational_short_text_len or len(tokens) < config.operational_short_token_len
        routing_policy = self._normalize_gatekeeper_routing_policy(config.routing_policy)
        event_stream_token_keywords = set(
            str(item).strip().lower() for item in routing_policy.get("event_stream_token_keywords", []) if str(item).strip()
        )
        blocked_category_keywords = list(routing_policy.get("blocked_category_keywords", []))
        blocked_source_system_keywords = list(routing_policy.get("blocked_source_system_keywords", []))
        blocked_source_type_keywords = list(routing_policy.get("blocked_source_type_keywords", []))
        blocked_entity_keywords = list(routing_policy.get("blocked_entity_keywords", []))
        blocked_source_id_keywords = list(routing_policy.get("blocked_source_id_keywords", []))
        durable_signal_keywords = list(routing_policy.get("durable_signal_keywords", []))
        operational_stream_keywords = list(routing_policy.get("operational_stream_keywords", []))
        pii_sensitive_keywords = list(routing_policy.get("pii_sensitive_keywords", []))
        ingestion_default_deny_classes = {
            str(item).strip().lower()
            for item in (routing_policy.get("ingestion_classification_default_deny_classes") or [])
            if str(item).strip()
        }
        event_stream_min_numeric_token_ratio = float(routing_policy.get("event_stream_min_numeric_token_ratio", 0.45))
        event_stream_min_token_hits = int(routing_policy.get("event_stream_min_token_hits", 2))
        event_stream_min_kv_hits = int(routing_policy.get("event_stream_min_kv_hits", 2))
        min_durable_signal_hits = int(routing_policy.get("min_durable_signal_hits", 1))
        min_durable_signal_hits_for_backfill = int(routing_policy.get("min_durable_signal_hits_for_backfill", 1))
        require_multi_source_for_wiki = bool(routing_policy.get("require_multi_source_for_wiki", True))
        min_sources_for_wiki_candidate = int(routing_policy.get("min_sources_for_wiki_candidate", 2))
        min_evidence_for_wiki_candidate = int(routing_policy.get("min_evidence_for_wiki_candidate", 2))
        allow_policy_or_incident_override = bool(routing_policy.get("allow_policy_or_incident_override", True))
        backfill_requires_policy_signal = bool(routing_policy.get("backfill_requires_policy_signal", True))
        publish_mode_by_assertion_class = self._normalize_publish_mode_map(
            routing_policy.get("publish_mode_by_assertion_class")
        )
        operational_verbs = {
            "sent",
            "send",
            "clicked",
            "click",
            "opened",
            "processed",
            "done",
            "ok",
            "called",
            "pinged",
            "updated",
            "logged",
            "assigned",
            "started",
            "finished",
            "отправил",
            "отправлено",
            "нажал",
            "обновил",
            "сделал",
            "готово",
            "позвонил",
        }
        has_operational_pattern = bool(token_set & operational_verbs)
        policy_words = {"must", "required", "only", "forbidden", "until", "closed", "open", "policy", "quarantine"}
        has_policy_signal = bool(token_set & policy_words)
        preference_words = {
            "prefer",
            "prefers",
            "preference",
            "contact",
            "customer",
            "client",
            "slack",
            "email",
            "call",
            "клиент",
            "предпочт",
            "контакт",
            "звонить",
        }
        has_preference_signal = bool(token_set & preference_words)
        process_words = {
            "process",
            "procedure",
            "workflow",
            "runbook",
            "playbook",
            "sop",
            "step",
            "steps",
            "checklist",
            "escalation",
            "handoff",
            "if",
            "when",
            "then",
            "процесс",
            "процедура",
            "регламент",
            "инструкция",
            "шаг",
            "эскалация",
        }
        has_process_signal = bool(token_set & process_words)
        high_priority_words = {
            "blocked",
            "outage",
            "incident",
            "hazard",
            "unsafe",
            "security",
            "breach",
            "critical",
            "failure",
            "broken",
            "авария",
            "инцидент",
            "опасно",
            "критично",
            "поломка",
            "сбой",
            "закрыт",
            "карантин",
        }
        has_high_priority_signal = bool(token_set & high_priority_words)
        category_hint = self._category_to_page_type(claim.category)
        normalized_category = self._normalize_text(claim.category)
        normalized_entity_key = self._normalize_text(claim.entity_key)
        incoming_source_systems = self._extract_source_systems(claim.evidence)
        incoming_source_types = self._extract_source_types(claim.evidence)
        incoming_tool_names = self._extract_tool_names(claim.evidence)
        incoming_ingest_lanes = self._extract_ingest_lanes(claim.evidence)
        is_knowledge_ingest = "knowledge" in incoming_ingest_lanes
        source_diversity = max(historical_source_count, len(incoming_source_ids))
        source_id_blob = " ".join(self._normalize_text(item) for item in incoming_source_ids)
        blocked_by_category = any(keyword in normalized_category for keyword in blocked_category_keywords if keyword)
        blocked_by_source_system = any(
            self._keyword_matches_identifier(system, keyword)
            for system in incoming_source_systems
            for keyword in blocked_source_system_keywords
            if keyword
        )
        blocked_by_source_type = any(
            self._keyword_matches_identifier(source_type, keyword)
            for source_type in incoming_source_types
            for keyword in blocked_source_type_keywords
            if keyword
        )
        if is_knowledge_ingest:
            blocked_by_source_system = False
            blocked_by_source_type = False
        blocked_by_entity = any(keyword in normalized_entity_key for keyword in blocked_entity_keywords if keyword)
        blocked_by_source_id = any(keyword in source_id_blob for keyword in blocked_source_id_keywords if keyword)
        numeric_token_count = sum(1 for token in tokens if any(ch.isdigit() for ch in token))
        numeric_token_ratio = float(numeric_token_count) / float(max(len(tokens), 1))
        event_stream_token_hits = sum(1 for token in token_set if token in event_stream_token_keywords)
        event_kv_hits = len(
            re.findall(
                r"\b(id|order_id|invoice_id|status|state|created_at|updated_at|customer_id|task_id|event_id)\s*[:=]",
                text,
            )
        )
        has_structured_event_blob = bool(
            (text.count("{") >= 1 and text.count("}") >= 1 and text.count(":") >= 3)
            or event_kv_hits >= event_stream_min_kv_hits
        )
        has_order_like_id_pattern = bool(
            re.search(
                r"\b(order|заказ|task|event|ticket|shipment|delivery)[\s_:#-]{0,12}[a-z0-9_-]{3,}\b",
                text,
            )
        )
        has_event_stream_shape = (
            event_stream_token_hits >= event_stream_min_token_hits
            and (numeric_token_ratio >= event_stream_min_numeric_token_ratio or has_order_like_id_pattern or has_structured_event_blob)
        )
        durable_signal_hits = self._count_keyword_hits(
            normalized_text=text,
            token_set=token_set,
            keywords=durable_signal_keywords,
        )
        has_backfill_evidence = (
            "external_event" in incoming_source_types
            or "memory_backfill" in incoming_tool_names
            or "backfill" in incoming_tool_names
        )
        has_override_signal = allow_policy_or_incident_override and (has_policy_signal or has_high_priority_signal)
        backfill_without_durable_signal = (
            backfill_requires_policy_signal
            and has_backfill_evidence
            and not has_override_signal
            and durable_signal_hits < min_durable_signal_hits_for_backfill
            and (category_hint == "general" or source_diversity <= 1)
        )
        routing_hard_block = (
            blocked_by_category
            or blocked_by_source_system
            or blocked_by_source_type
            or blocked_by_entity
            or blocked_by_source_id
            or has_event_stream_shape
            or backfill_without_durable_signal
        ) and not has_override_signal
        has_durable_signal = (
            has_policy_signal
            or has_process_signal
            or has_high_priority_signal
            or durable_signal_hits >= min_durable_signal_hits
        )
        assertion_class = self._infer_assertion_class(
            category_hint=category_hint,
            has_policy_signal=has_policy_signal,
            has_process_signal=has_process_signal,
            has_preference_signal=has_preference_signal,
            has_high_priority_signal=has_high_priority_signal,
            has_event_stream_shape=has_event_stream_shape,
            blocked_by_source_id=blocked_by_source_id,
            blocked_by_source_type=blocked_by_source_type,
        )
        runtime_source_systems = {
            "runtime_memory",
            "sdk_monitor",
            "openclaw_runtime",
            "agent_runtime",
            "tool_result",
            "chat_runtime",
        }
        all_runtime_sources = bool(incoming_source_systems) and set(incoming_source_systems).issubset(runtime_source_systems)
        looks_like_runtime_noise = (
            all_runtime_sources
            and repeated_count == 0
            and source_diversity <= 1
            and not has_durable_signal
            and (is_short or has_operational_pattern or category_hint == "general")
        )
        classification_haystack = " ".join(
            item
            for item in (
                text,
                normalized_category,
                normalized_entity_key,
                " ".join(incoming_source_systems),
                " ".join(incoming_source_types),
                " ".join(incoming_source_ids),
            )
            if item
        )
        operational_keyword_hits = [
            keyword
            for keyword in operational_stream_keywords
            if keyword and keyword in classification_haystack
        ][:20]
        pii_keyword_hits = [
            keyword
            for keyword in pii_sensitive_keywords
            if keyword and keyword in classification_haystack
        ][:20]
        pii_regex_hits = bool(
            re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", claim.claim_text or "")
            or re.search(
                r"(?<!\d)(?:\+\d{7,15}|\d{10,15}|\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{4})(?!\d)",
                claim.claim_text or "",
            )
        )
        ingestion_classification = "evergreen_knowledge"
        if pii_keyword_hits or pii_regex_hits:
            ingestion_classification = "pii_sensitive_stream"
        elif (
            looks_like_runtime_noise
            or has_event_stream_shape
            or blocked_by_source_system
            or blocked_by_source_type
            or blocked_by_source_id
            or blocked_by_entity
            or blocked_by_category
            or bool(operational_keyword_hits)
        ):
            ingestion_classification = "operational_stream"
        ingestion_default_deny_block = (
            ingestion_classification in ingestion_default_deny_classes
            and not has_override_signal
            and not is_knowledge_ingest
        )
        if ingestion_default_deny_block:
            routing_hard_block = True
        is_single_source_one_off = (
            not has_durable_signal
            and repeated_count == 0
            and source_diversity <= 1
            and evidence_count <= 2
        )

        score = 0.35
        if has_policy_signal:
            score += 0.2
        if has_durable_signal and not has_policy_signal:
            score += 0.12
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

        if routing_hard_block:
            tier = "operational_memory"
            rationale = "routing policy rejected event-stream style memory for wiki ingestion"
        elif looks_like_runtime_noise:
            tier = "operational_memory"
            rationale = "single-source runtime operational event without durable policy signal"
        elif is_single_source_one_off:
            tier = "operational_memory"
            rationale = "single-source one-off observation without durable knowledge signal"
        elif has_operational_pattern and is_short and repeated_count == 0:
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

        insufficient_support = (
            require_multi_source_for_wiki
            and source_diversity < min_sources_for_wiki_candidate
            and evidence_count < min_evidence_for_wiki_candidate
            and repeated_count <= 0
            and not has_override_signal
            and not has_durable_signal
        )
        if insufficient_support and tier != "operational_memory":
            tier = "operational_memory"
            rationale = "routing policy requires independent source/evidence support before wiki routing"

        llm_assessment: GatekeeperLLMAssessment
        if llm_assessment_override is not None:
            llm_assessment = llm_assessment_override
        elif routing_hard_block:
            llm_assessment = GatekeeperLLMAssessment(
                status="skipped",
                provider=config.llm_provider,
                model=config.llm_model,
                error="routing_policy_hard_block",
            )
        else:
            llm_assessment = self._run_gatekeeper_llm_assessment(
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
                    "has_process_signal": has_process_signal,
                    "has_preference_signal": has_preference_signal,
                    "has_recent_open_conflict": has_recent_open_conflict,
                    "heuristic_score": score,
                    "heuristic_tier": tier,
                    "assertion_class": assertion_class,
                    "routing_hard_block": routing_hard_block,
                    "insufficient_support": insufficient_support,
                    "blocked_by_category": blocked_by_category,
                    "blocked_by_source_system": blocked_by_source_system,
                    "blocked_by_source_type": blocked_by_source_type,
                    "blocked_by_entity": blocked_by_entity,
                    "blocked_by_source_id": blocked_by_source_id,
                    "has_event_stream_shape": has_event_stream_shape,
                    "has_backfill_evidence": has_backfill_evidence,
                    "incoming_ingest_lanes": incoming_ingest_lanes,
                    "is_knowledge_ingest": is_knowledge_ingest,
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
                if is_short and repeated_count == 0 and not has_durable_signal:
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
            "incoming_source_systems": incoming_source_systems,
            "incoming_source_types": incoming_source_types,
            "incoming_tool_names": incoming_tool_names,
            "incoming_ingest_lanes": incoming_ingest_lanes,
            "is_knowledge_ingest": is_knowledge_ingest,
            "all_runtime_sources": all_runtime_sources,
            "looks_like_runtime_noise": looks_like_runtime_noise,
            "ingestion_classification": ingestion_classification,
            "ingestion_classification_default_deny_classes": sorted(ingestion_default_deny_classes),
            "ingestion_default_deny_block": ingestion_default_deny_block,
            "ingestion_operational_keyword_hits": operational_keyword_hits,
            "ingestion_pii_keyword_hits": pii_keyword_hits,
            "ingestion_pii_regex_hits": pii_regex_hits,
            "routing_policy": routing_policy,
            "routing_hard_block": routing_hard_block,
            "blocked_by_category": blocked_by_category,
            "blocked_by_source_system": blocked_by_source_system,
            "blocked_by_source_type": blocked_by_source_type,
            "blocked_by_entity": blocked_by_entity,
            "blocked_by_source_id": blocked_by_source_id,
            "has_event_stream_shape": has_event_stream_shape,
            "has_structured_event_blob": has_structured_event_blob,
            "has_order_like_id_pattern": has_order_like_id_pattern,
            "event_stream_token_hits": event_stream_token_hits,
            "event_kv_hits": event_kv_hits,
            "numeric_token_count": numeric_token_count,
            "numeric_token_ratio": round(numeric_token_ratio, 4),
            "has_backfill_evidence": has_backfill_evidence,
            "backfill_without_durable_signal": backfill_without_durable_signal,
            "durable_signal_hits": durable_signal_hits,
            "has_durable_signal": has_durable_signal,
            "insufficient_support": insufficient_support,
            "is_short": is_short,
            "has_operational_pattern": has_operational_pattern,
            "has_policy_signal": has_policy_signal,
            "has_process_signal": has_process_signal,
            "has_preference_signal": has_preference_signal,
            "has_high_priority_signal": has_high_priority_signal,
            "has_override_signal": has_override_signal,
            "has_recent_open_conflict": has_recent_open_conflict,
            "assertion_class": assertion_class,
            "publish_mode_by_assertion_class": publish_mode_by_assertion_class,
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

    def _gatekeeper_config_has_publish_columns(self, conn) -> bool:
        if self._gatekeeper_config_has_publish_columns_cache is not None:
            return self._gatekeeper_config_has_publish_columns_cache
        required = {
            "publish_mode_default",
            "publish_mode_by_category",
            "auto_publish_min_score",
            "auto_publish_min_sources",
            "auto_publish_require_golden",
            "auto_publish_allow_conflicts",
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
        self._gatekeeper_config_has_publish_columns_cache = required.issubset(present)
        return self._gatekeeper_config_has_publish_columns_cache

    def _gatekeeper_config_has_routing_policy_column(self, conn) -> bool:
        if self._gatekeeper_config_has_routing_policy_column_cache is not None:
            return self._gatekeeper_config_has_routing_policy_column_cache
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'gatekeeper_project_configs'
                  AND column_name = 'routing_policy'
                LIMIT 1
                """
            )
            self._gatekeeper_config_has_routing_policy_column_cache = cur.fetchone() is not None
        return self._gatekeeper_config_has_routing_policy_column_cache

    def _normalize_publish_mode(self, value: Any) -> str:
        raw = str(value or "").strip().lower()
        if raw not in {"human_required", "conditional", "auto_publish"}:
            return "auto_publish"
        return raw

    def _normalize_publish_mode_map(self, value: Any) -> dict[str, str]:
        if not isinstance(value, dict):
            return {}
        out: dict[str, str] = {}
        for key, item in value.items():
            category = str(key or "").strip().lower()
            if not category:
                continue
            mode = self._normalize_publish_mode(item)
            out[category[:64]] = mode
        return out

    def _normalize_policy_keyword_list(self, value: Any, *, fallback: list[str], limit: int = 64) -> list[str]:
        if not isinstance(value, list):
            return list(fallback)
        out: list[str] = []
        seen: set[str] = set()
        for item in value:
            text = unicodedata.normalize("NFKC", str(item or "")).strip().lower()
            text = re.sub(r"\s+", " ", text)
            if not text:
                continue
            if len(text) > 96:
                text = text[:96]
            if text in seen:
                continue
            seen.add(text)
            out.append(text)
            if len(out) >= limit:
                break
        if not out:
            return list(fallback)
        return out

    def _normalize_gatekeeper_routing_policy(self, value: Any) -> dict[str, Any]:
        base = dict(DEFAULT_GATEKEEPER_ROUTING_POLICY)
        if not isinstance(value, dict):
            return base
        normalized = dict(base)
        normalized["blocked_category_keywords"] = self._normalize_policy_keyword_list(
            value.get("blocked_category_keywords"),
            fallback=list(base["blocked_category_keywords"]),
        )
        normalized["blocked_source_system_keywords"] = self._normalize_policy_keyword_list(
            value.get("blocked_source_system_keywords"),
            fallback=list(base["blocked_source_system_keywords"]),
        )
        normalized["blocked_source_type_keywords"] = self._normalize_policy_keyword_list(
            value.get("blocked_source_type_keywords"),
            fallback=list(base["blocked_source_type_keywords"]),
        )
        normalized["blocked_entity_keywords"] = self._normalize_policy_keyword_list(
            value.get("blocked_entity_keywords"),
            fallback=list(base["blocked_entity_keywords"]),
        )
        normalized["blocked_source_id_keywords"] = self._normalize_policy_keyword_list(
            value.get("blocked_source_id_keywords"),
            fallback=list(base["blocked_source_id_keywords"]),
        )
        normalized["event_stream_token_keywords"] = self._normalize_policy_keyword_list(
            value.get("event_stream_token_keywords"),
            fallback=list(base["event_stream_token_keywords"]),
        )
        normalized["durable_signal_keywords"] = self._normalize_policy_keyword_list(
            value.get("durable_signal_keywords"),
            fallback=list(base["durable_signal_keywords"]),
        )
        normalized["high_signal_route_keywords"] = self._normalize_policy_keyword_list(
            value.get("high_signal_route_keywords"),
            fallback=list(base["high_signal_route_keywords"]),
            limit=128,
        )
        normalized["ingestion_classification_default_deny_classes"] = self._normalize_policy_keyword_list(
            value.get("ingestion_classification_default_deny_classes"),
            fallback=list(base["ingestion_classification_default_deny_classes"]),
            limit=5,
        )
        normalized["operational_stream_keywords"] = self._normalize_policy_keyword_list(
            value.get("operational_stream_keywords"),
            fallback=list(base["operational_stream_keywords"]),
            limit=128,
        )
        normalized["pii_sensitive_keywords"] = self._normalize_policy_keyword_list(
            value.get("pii_sensitive_keywords"),
            fallback=list(base["pii_sensitive_keywords"]),
            limit=128,
        )
        normalized["auto_publish_risk_keywords_high"] = self._normalize_policy_keyword_list(
            value.get("auto_publish_risk_keywords_high"),
            fallback=list(base["auto_publish_risk_keywords_high"]),
        )
        normalized["auto_publish_risk_keywords_medium"] = self._normalize_policy_keyword_list(
            value.get("auto_publish_risk_keywords_medium"),
            fallback=list(base["auto_publish_risk_keywords_medium"]),
        )
        normalized["auto_publish_force_human_required_levels"] = self._normalize_policy_keyword_list(
            value.get("auto_publish_force_human_required_levels"),
            fallback=list(base["auto_publish_force_human_required_levels"]),
            limit=5,
        )
        normalized["process_simulation_require_for_page_types"] = self._normalize_policy_keyword_list(
            value.get("process_simulation_require_for_page_types"),
            fallback=list(base["process_simulation_require_for_page_types"]),
            limit=10,
        )
        normalized["process_simulation_block_levels"] = self._normalize_policy_keyword_list(
            value.get("process_simulation_block_levels"),
            fallback=list(base["process_simulation_block_levels"]),
            limit=5,
        )
        try:
            simulation_sample_limit = int(
                value.get("process_simulation_sample_limit", int(base["process_simulation_sample_limit"]))
            )
        except Exception:
            simulation_sample_limit = int(base["process_simulation_sample_limit"])
        normalized["process_simulation_sample_limit"] = max(1, min(50, simulation_sample_limit))
        normalized["publish_mode_by_assertion_class"] = self._normalize_publish_mode_map(
            value.get("publish_mode_by_assertion_class")
        )
        if not normalized["publish_mode_by_assertion_class"]:
            normalized["publish_mode_by_assertion_class"] = dict(base["publish_mode_by_assertion_class"])
        try:
            min_numeric_ratio = float(value.get("event_stream_min_numeric_token_ratio", 0.45))
        except Exception:
            min_numeric_ratio = 0.45
        normalized["event_stream_min_numeric_token_ratio"] = max(0.0, min(1.0, min_numeric_ratio))
        try:
            token_hits = int(value.get("event_stream_min_token_hits", 2))
        except Exception:
            token_hits = 2
        normalized["event_stream_min_token_hits"] = max(1, min(20, token_hits))
        try:
            kv_hits = int(value.get("event_stream_min_kv_hits", 2))
        except Exception:
            kv_hits = 2
        normalized["event_stream_min_kv_hits"] = max(1, min(20, kv_hits))
        try:
            min_durable_hits = int(value.get("min_durable_signal_hits", 1))
        except Exception:
            min_durable_hits = 1
        normalized["min_durable_signal_hits"] = max(0, min(20, min_durable_hits))
        try:
            min_backfill_durable_hits = int(value.get("min_durable_signal_hits_for_backfill", 1))
        except Exception:
            min_backfill_durable_hits = 1
        normalized["min_durable_signal_hits_for_backfill"] = max(0, min(20, min_backfill_durable_hits))
        try:
            high_signal_min_hits = int(value.get("high_signal_min_keyword_hits", int(base["high_signal_min_keyword_hits"])))
        except Exception:
            high_signal_min_hits = int(base["high_signal_min_keyword_hits"])
        normalized["high_signal_min_keyword_hits"] = max(1, min(20, high_signal_min_hits))
        try:
            claims_floor_min_events = int(value.get("claims_floor_min_events", int(base["claims_floor_min_events"])))
        except Exception:
            claims_floor_min_events = int(base["claims_floor_min_events"])
        normalized["claims_floor_min_events"] = max(1, min(100000, claims_floor_min_events))
        try:
            claims_floor_alert_after_minutes = int(
                value.get("claims_floor_alert_after_minutes", int(base["claims_floor_alert_after_minutes"]))
            )
        except Exception:
            claims_floor_alert_after_minutes = int(base["claims_floor_alert_after_minutes"])
        normalized["claims_floor_alert_after_minutes"] = max(1, min(1440, claims_floor_alert_after_minutes))
        try:
            claims_floor_min_conversion_ratio = float(
                value.get("claims_floor_min_conversion_ratio", float(base["claims_floor_min_conversion_ratio"]))
            )
        except Exception:
            claims_floor_min_conversion_ratio = float(base["claims_floor_min_conversion_ratio"])
        normalized["claims_floor_min_conversion_ratio"] = max(0.0, min(1.0, claims_floor_min_conversion_ratio))
        try:
            feedback_window_days = int(value.get("retrieval_feedback_window_days", 30))
        except Exception:
            feedback_window_days = 30
        normalized["retrieval_feedback_window_days"] = max(1, min(365, feedback_window_days))
        try:
            feedback_min_events = int(value.get("retrieval_feedback_min_events", 3))
        except Exception:
            feedback_min_events = 3
        normalized["retrieval_feedback_min_events"] = max(1, min(200, feedback_min_events))
        try:
            feedback_negative_ratio = float(value.get("retrieval_feedback_block_negative_ratio", 0.7))
        except Exception:
            feedback_negative_ratio = 0.7
        normalized["retrieval_feedback_block_negative_ratio"] = max(0.0, min(1.0, feedback_negative_ratio))
        try:
            feedback_balance = int(value.get("retrieval_feedback_block_balance", 2))
        except Exception:
            feedback_balance = 2
        normalized["retrieval_feedback_block_balance"] = max(1, min(500, feedback_balance))
        normalized["require_multi_source_for_wiki"] = bool(value.get("require_multi_source_for_wiki", True))
        try:
            min_sources = int(value.get("min_sources_for_wiki_candidate", 2))
        except Exception:
            min_sources = 2
        try:
            min_evidence = int(value.get("min_evidence_for_wiki_candidate", 2))
        except Exception:
            min_evidence = 2
        normalized["min_sources_for_wiki_candidate"] = max(1, min(20, min_sources))
        normalized["min_evidence_for_wiki_candidate"] = max(1, min(20, min_evidence))
        normalized["allow_policy_or_incident_override"] = bool(value.get("allow_policy_or_incident_override", True))
        normalized["backfill_requires_policy_signal"] = bool(value.get("backfill_requires_policy_signal", True))
        llm_mode_raw = str(value.get("backfill_llm_classifier_mode", base["backfill_llm_classifier_mode"]) or "").strip().lower()
        normalized["backfill_llm_classifier_mode"] = llm_mode_raw if llm_mode_raw in {"off", "assist", "enforce"} else str(
            base["backfill_llm_classifier_mode"]
        )
        try:
            backfill_llm_confidence = float(
                value.get(
                    "backfill_llm_classifier_min_confidence",
                    base["backfill_llm_classifier_min_confidence"],
                )
            )
        except Exception:
            backfill_llm_confidence = float(base["backfill_llm_classifier_min_confidence"])
        normalized["backfill_llm_classifier_min_confidence"] = max(0.0, min(1.0, backfill_llm_confidence))
        normalized["backfill_llm_classifier_ambiguous_only"] = bool(
            value.get(
                "backfill_llm_classifier_ambiguous_only",
                base["backfill_llm_classifier_ambiguous_only"],
            )
        )
        model_value = str(value.get("backfill_llm_classifier_model") or "").strip()
        normalized["backfill_llm_classifier_model"] = model_value[:128] if model_value else ""
        normalized["emit_reinforcement_drafts"] = bool(
            value.get("emit_reinforcement_drafts", base["emit_reinforcement_drafts"])
        )
        try:
            draft_flood_max_open_per_page = int(
                value.get("draft_flood_max_open_per_page", base["draft_flood_max_open_per_page"])
            )
        except Exception:
            draft_flood_max_open_per_page = int(base["draft_flood_max_open_per_page"])
        normalized["draft_flood_max_open_per_page"] = max(50, min(20000, draft_flood_max_open_per_page))
        try:
            draft_flood_max_open_per_entity = int(
                value.get("draft_flood_max_open_per_entity", base["draft_flood_max_open_per_entity"])
            )
        except Exception:
            draft_flood_max_open_per_entity = int(base["draft_flood_max_open_per_entity"])
        normalized["draft_flood_max_open_per_entity"] = max(50, min(40000, draft_flood_max_open_per_entity))
        try:
            queue_pressure_open_drafts = int(
                value.get(
                    "queue_pressure_safe_mode_open_drafts_threshold",
                    base["queue_pressure_safe_mode_open_drafts_threshold"],
                )
            )
        except Exception:
            queue_pressure_open_drafts = int(base["queue_pressure_safe_mode_open_drafts_threshold"])
        normalized["queue_pressure_safe_mode_open_drafts_threshold"] = max(100, min(200000, queue_pressure_open_drafts))
        try:
            queue_pressure_open_drafts_per_page = int(
                value.get(
                    "queue_pressure_safe_mode_open_drafts_per_page_threshold",
                    base["queue_pressure_safe_mode_open_drafts_per_page_threshold"],
                )
            )
        except Exception:
            queue_pressure_open_drafts_per_page = int(base["queue_pressure_safe_mode_open_drafts_per_page_threshold"])
        normalized["queue_pressure_safe_mode_open_drafts_per_page_threshold"] = max(
            50, min(20000, queue_pressure_open_drafts_per_page)
        )
        return normalized

    def _resolve_gatekeeper_config(self, conn, project_id: str) -> GatekeeperConfig:
        has_llm_columns = self._gatekeeper_config_has_llm_columns(conn)
        has_publish_columns = self._gatekeeper_config_has_publish_columns(conn)
        has_routing_policy_column = self._gatekeeper_config_has_routing_policy_column(conn)
        with conn.cursor() as cur:
            if has_llm_columns and has_publish_columns and has_routing_policy_column:
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
                      llm_timeout_ms,
                      publish_mode_default,
                      publish_mode_by_category,
                      auto_publish_min_score,
                      auto_publish_min_sources,
                      auto_publish_require_golden,
                      auto_publish_allow_conflicts,
                      routing_policy
                    FROM gatekeeper_project_configs
                    WHERE project_id = %s
                    LIMIT 1
                    """,
                    (project_id,),
                )
            elif has_llm_columns and has_publish_columns:
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
                      llm_timeout_ms,
                      publish_mode_default,
                      publish_mode_by_category,
                      auto_publish_min_score,
                      auto_publish_min_sources,
                      auto_publish_require_golden,
                      auto_publish_allow_conflicts
                    FROM gatekeeper_project_configs
                    WHERE project_id = %s
                    LIMIT 1
                    """,
                    (project_id,),
                )
            elif has_llm_columns:
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
                publish_mode_default="auto_publish",
                publish_mode_by_category={},
                routing_policy=self._normalize_gatekeeper_routing_policy(None),
                auto_publish_min_score=0.9,
                auto_publish_min_sources=3,
                auto_publish_require_golden=True,
                auto_publish_allow_conflicts=False,
            )
        else:
            if has_llm_columns and has_publish_columns and has_routing_policy_column:
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
                    publish_mode_default=self._normalize_publish_mode(row[11]),
                    publish_mode_by_category=self._normalize_publish_mode_map(row[12]),
                    auto_publish_min_score=max(0.0, min(1.0, float(row[13]))),
                    auto_publish_min_sources=max(1, int(row[14])),
                    auto_publish_require_golden=bool(row[15]),
                    auto_publish_allow_conflicts=bool(row[16]),
                    routing_policy=self._normalize_gatekeeper_routing_policy(row[17]),
                )
            elif has_llm_columns and has_publish_columns:
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
                    publish_mode_default=self._normalize_publish_mode(row[11]),
                    publish_mode_by_category=self._normalize_publish_mode_map(row[12]),
                    auto_publish_min_score=max(0.0, min(1.0, float(row[13]))),
                    auto_publish_min_sources=max(1, int(row[14])),
                    auto_publish_require_golden=bool(row[15]),
                    auto_publish_allow_conflicts=bool(row[16]),
                    routing_policy=self._normalize_gatekeeper_routing_policy(None),
                )
            elif has_llm_columns:
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
                    publish_mode_default="auto_publish",
                    publish_mode_by_category={},
                    routing_policy=self._normalize_gatekeeper_routing_policy(None),
                    auto_publish_min_score=0.9,
                    auto_publish_min_sources=3,
                    auto_publish_require_golden=True,
                    auto_publish_allow_conflicts=False,
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
                    publish_mode_default="auto_publish",
                    publish_mode_by_category={},
                    routing_policy=self._normalize_gatekeeper_routing_policy(None),
                    auto_publish_min_score=0.9,
                    auto_publish_min_sources=3,
                    auto_publish_require_golden=True,
                    auto_publish_allow_conflicts=False,
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

    def _resolve_page(
        self,
        claim: ClaimInput,
        candidates: list[PageRecord],
        *,
        conn=None,
    ) -> PageResolution:
        if not candidates:
            return PageResolution(mode="new_page", page=None, confidence=0.45, rationale="no page candidates found")

        active_candidates = [page for page in candidates if str(page.status).strip().lower() != "archived"]
        if not active_candidates:
            return PageResolution(
                mode="new_page",
                page=None,
                confidence=0.45,
                rationale="only archived page candidates found",
            )

        scored: list[tuple[float, PageRecord]] = []
        claim_tokens = set(self._tokens(claim.claim_text))
        entity_norm = self._normalize_text(claim.entity_key)
        entity_slug_norm = self._normalize_text(self._slugify(claim.entity_key))
        page_type = self._category_to_page_type(claim.category)
        route_policy: dict[str, Any] = {
            "threshold_high": float(self.threshold_high),
            "threshold_mid": float(self.threshold_mid),
            "new_page_margin": float(self.threshold_new_page_margin),
            "ambiguity_gap": float(self.threshold_route_ambiguity_gap),
            "new_page_false_positive_rate": 0.0,
            "conflict_rate": 0.0,
        }
        if conn is not None:
            route_policy = self._resolve_effective_route_policy(conn, claim.project_id)
        effective_threshold_high = float(route_policy["threshold_high"])
        effective_threshold_mid = float(route_policy["threshold_mid"])
        effective_margin = float(route_policy["new_page_margin"])
        effective_gap = float(route_policy["ambiguity_gap"])

        for page in active_candidates:
            score = 0.0
            page_entity_norm = self._normalize_text(page.entity_key)
            if entity_norm and entity_norm == page_entity_norm:
                score += 0.65
            if entity_norm and entity_norm == self._normalize_text(page.slug):
                score += 0.55
            identity_signals = self._page_identity_signals(page)
            if entity_norm and entity_norm in identity_signals:
                score += 0.2
            if entity_slug_norm and entity_slug_norm in identity_signals:
                score += 0.14
            if page.page_type == page_type:
                score += 0.15
            page_status = str(page.status).strip().lower()
            if page_status == "published":
                score += 0.05
            elif page_status == "draft":
                score += 0.01

            candidate_tokens = set(self._tokens(page.title + " " + page.entity_key + " " + " ".join(page.aliases)))
            if claim_tokens and candidate_tokens:
                overlap = len(claim_tokens & candidate_tokens) / max(len(claim_tokens), 1)
                score += min(overlap * 0.4, 0.2)

            title_similarity = self._text_similarity(claim.entity_key, page.title)
            score += min(title_similarity * 0.2, 0.1)
            score = min(score, 1.0)
            scored.append((score, page))

        if conn is not None:
            scored = self._rerank_page_candidates(conn, claim, scored, top_k=min(self.route_rerank_top_k, len(scored)))
        scored.sort(key=lambda item: item[0], reverse=True)
        top_score, top_page = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else 0.0
        gap = max(0.0, top_score - second_score)
        diagnostics = (
            f"top_score={top_score:.2f}, second_score={second_score:.2f}, gap={gap:.2f}, "
            f"threshold_high={effective_threshold_high:.2f}, threshold_mid={effective_threshold_mid:.2f}, "
            f"new_page_margin={effective_margin:.2f}, ambiguity_gap={effective_gap:.2f}, "
            f"new_page_false_positive_rate={float(route_policy['new_page_false_positive_rate']):.2f}, "
            f"conflict_rate={float(route_policy['conflict_rate']):.2f}"
        )

        if top_score >= effective_threshold_high:
            return PageResolution(
                mode="existing",
                page=top_page,
                confidence=top_score,
                rationale=f"matched existing page by entity/title similarity; {diagnostics}",
            )
        if top_score >= effective_threshold_mid:
            return PageResolution(
                mode="existing_low_confidence",
                page=top_page,
                confidence=top_score,
                rationale=f"weak page match, human validation required; {diagnostics}",
            )

        near_mid_threshold = max(0.0, effective_threshold_mid - effective_margin)
        if top_score >= near_mid_threshold and gap <= effective_gap:
            return PageResolution(
                mode="existing_low_confidence",
                page=top_page,
                confidence=top_score,
                rationale=(
                    "ambiguous route near new-page threshold, reusing best existing page for human validation; "
                    f"{diagnostics}"
                ),
            )
        return PageResolution(
            mode="new_page",
            page=None,
            confidence=top_score,
            rationale=f"no reliable active page match; {diagnostics}",
        )

    def _page_identity_signals(self, page: PageRecord) -> set[str]:
        signals: set[str] = set()
        for value in [page.entity_key, page.slug, page.title, *(page.aliases or [])]:
            if not value:
                continue
            normalized = self._normalize_text(str(value))
            if normalized:
                signals.add(normalized)
            slugified = self._normalize_text(self._slugify(str(value)))
            if slugified:
                signals.add(slugified)
        return signals

    def _load_page_routing_context(self, conn, page: PageRecord) -> str:
        cache_key = str(page.id)
        now = time.monotonic()
        cached = self._page_context_cache.get(cache_key)
        if cached is not None and (now - cached[0]) <= float(self.page_context_cache_ttl_sec):
            return cached[1]

        headings: list[str] = []
        statement_lines: list[str] = []
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT heading
                FROM wiki_sections
                WHERE page_id = %s
                ORDER BY order_index ASC, section_key ASC
                LIMIT 20
                """,
                (page.id,),
            )
            headings = [str(row[0]).strip() for row in cur.fetchall() if row and row[0]]
            cur.execute(
                """
                SELECT statement_text
                FROM wiki_statements
                WHERE page_id = %s
                  AND status = 'active'
                ORDER BY created_at DESC
                LIMIT 12
                """,
                (page.id,),
            )
            statement_lines = [str(row[0]).strip() for row in cur.fetchall() if row and row[0]]

        context_parts = [page.title, page.entity_key, page.slug, " ".join(page.aliases or []), " ".join(headings), " ".join(statement_lines)]
        context_text = " ".join(part for part in context_parts if isinstance(part, str) and part.strip())
        context_text = context_text[:6000]
        self._page_context_cache[cache_key] = (now, context_text)
        return context_text

    def _rerank_page_candidates(
        self,
        conn,
        claim: ClaimInput,
        scored: list[tuple[float, PageRecord]],
        *,
        top_k: int,
    ) -> list[tuple[float, PageRecord]]:
        if top_k <= 0 or not scored:
            return scored
        claim_context = f"{claim.entity_key} {claim.category} {claim.claim_text}"
        claim_tokens = set(self._tokens(claim_context))
        page_type = self._category_to_page_type(claim.category)
        reranked: list[tuple[float, PageRecord]] = []
        sorted_scored = sorted(scored, key=lambda item: item[0], reverse=True)
        for index, (base_score, page) in enumerate(sorted_scored):
            if index >= top_k:
                reranked.append((base_score, page))
                continue
            page_context = self._load_page_routing_context(conn, page)
            similarity = self._text_similarity(claim_context, page_context) if page_context else 0.0
            page_tokens = set(self._tokens(page_context))
            overlap_ratio = 0.0
            if claim_tokens and page_tokens:
                overlap_ratio = len(claim_tokens & page_tokens) / max(len(claim_tokens), 1)

            rerank_boost = min(similarity * 0.22, 0.18) + min(overlap_ratio * 0.16, 0.12)
            if page.page_type == page_type:
                rerank_boost += 0.02
            reranked_score = max(0.0, min(1.0, base_score + rerank_boost))
            reranked.append((reranked_score, page))
        return reranked

    def _resolve_effective_route_policy(self, conn, project_id: str) -> dict[str, Any]:
        now = time.monotonic()
        cached = self._routing_feedback_cache.get(project_id)
        if cached is not None and (now - cached[0]) <= float(self.routing_feedback_cache_ttl_sec):
            return cached[1]

        new_page_total = 0
        new_page_reassigned = 0
        draft_total = 0
        conflict_total = 0
        route_quality_total = 0
        ambiguous_total = 0
        weak_match_total = 0

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                      COUNT(*) FILTER (WHERE action_type = 'approve' AND decision_before = 'new_page')::bigint,
                      COUNT(*) FILTER (
                        WHERE action_type = 'approve'
                          AND decision_before = 'new_page'
                          AND COALESCE(decision_after, '') <> 'new_page'
                      )::bigint
                    FROM moderation_actions
                    WHERE project_id = %s
                      AND created_at >= NOW() - INTERVAL '30 days'
                    """,
                    (project_id,),
                )
                row = cur.fetchone() or (0, 0)
                new_page_total = int(row[0] or 0)
                new_page_reassigned = int(row[1] or 0)

                cur.execute(
                    """
                    SELECT
                      COUNT(*)::bigint,
                      COUNT(*) FILTER (WHERE decision = 'conflict')::bigint,
                      COUNT(*) FILTER (WHERE rationale ILIKE 'ambiguous route near new-page threshold%%')::bigint,
                      COUNT(*) FILTER (WHERE rationale ILIKE 'weak page match%%')::bigint
                    FROM wiki_draft_changes
                    WHERE project_id = %s
                      AND created_at >= NOW() - INTERVAL '30 days'
                    """,
                    (project_id,),
                )
                draft_row = cur.fetchone() or (0, 0, 0, 0)
                draft_total = int(draft_row[0] or 0)
                conflict_total = int(draft_row[1] or 0)
                ambiguous_total = int(draft_row[2] or 0)
                weak_match_total = int(draft_row[3] or 0)
                route_quality_total = draft_total
        except Exception:
            pass

        new_page_false_positive_rate = (
            float(new_page_reassigned) / float(new_page_total) if new_page_total > 0 else 0.0
        )
        conflict_rate = float(conflict_total) / float(draft_total) if draft_total > 0 else 0.0
        ambiguous_rate = float(ambiguous_total) / float(route_quality_total) if route_quality_total > 0 else 0.0

        threshold_mid = float(self.threshold_mid)
        new_page_margin = float(self.threshold_new_page_margin)
        ambiguity_gap = float(self.threshold_route_ambiguity_gap)

        if new_page_total >= 10:
            if new_page_false_positive_rate >= 0.2:
                new_page_margin += 0.03
            if new_page_false_positive_rate >= 0.35:
                new_page_margin += 0.03
        if draft_total >= 30 and conflict_rate >= 0.25:
            threshold_mid = min(0.95, threshold_mid + 0.01)
            new_page_margin = max(0.02, new_page_margin - 0.03)
            ambiguity_gap = max(0.01, ambiguity_gap - 0.01)
        if route_quality_total >= 30 and ambiguous_rate > 0.35 and conflict_rate < 0.12:
            new_page_margin = min(0.3, new_page_margin + 0.01)

        policy = {
            "threshold_high": float(self.threshold_high),
            "threshold_mid": max(0.0, min(0.99, threshold_mid)),
            "new_page_margin": max(0.0, min(0.3, new_page_margin)),
            "ambiguity_gap": max(0.0, min(1.0, ambiguity_gap)),
            "new_page_total": new_page_total,
            "new_page_reassigned": new_page_reassigned,
            "new_page_false_positive_rate": round(new_page_false_positive_rate, 4),
            "draft_total": draft_total,
            "conflict_total": conflict_total,
            "conflict_rate": round(conflict_rate, 4),
            "ambiguous_total": ambiguous_total,
            "ambiguous_rate": round(ambiguous_rate, 4),
            "weak_match_total": weak_match_total,
        }
        self._routing_feedback_cache[project_id] = (now, policy)
        return policy

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
        if page_type == "process":
            bootstrap_markdown = (
                f"# {title}\n\n"
                f"## Summary\n"
                f"- Draft process page generated from claim `{claim.id}`.\n"
                f"- Goal: capture trigger -> action -> outcome workflow.\n\n"
                f"## Triggers\n"
                f"- Pending approval.\n\n"
                f"## Steps\n"
                f"- Pending approval.\n\n"
                f"## Exceptions\n"
                f"- Pending approval.\n\n"
                f"## Escalation\n"
                f"- Pending approval.\n\n"
                f"## Outcome Verification\n"
                f"- Pending approval.\n"
            )
        else:
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
        process_triplet = self._extract_process_triplet_from_claim(claim)
        if process_triplet is not None and section_key in {"triggers", "steps", "exceptions", "escalation", "verification"}:
            line = self._format_process_triplet_line(process_triplet, section_key=section_key, evidence_suffix=evidence_suffix)

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

    def _format_process_triplet_line(
        self,
        process_triplet: dict[str, Any],
        *,
        section_key: str,
        evidence_suffix: str,
    ) -> str:
        trigger = str(process_triplet.get("trigger") or "").strip()
        action = str(process_triplet.get("action") or "").strip()
        outcome = str(process_triplet.get("outcome") or "").strip()

        if section_key == "triggers":
            body = trigger or action or outcome or "Pending trigger detail."
            return f"- Trigger: {body}{evidence_suffix}"
        if section_key == "exceptions":
            body = outcome or action or trigger or "Pending exception detail."
            return f"- Exception: {body}{evidence_suffix}"
        if section_key == "escalation":
            body = action or trigger or outcome or "Pending escalation rule."
            return f"- Escalation: {body}{evidence_suffix}"
        if section_key == "verification":
            body = outcome or action or trigger or "Pending verification criteria."
            return f"- Verification: {body}{evidence_suffix}"

        parts: list[str] = []
        if trigger:
            parts.append(f"Trigger: {trigger}")
        if action:
            parts.append(f"Action: {action}")
        if outcome:
            parts.append(f"Outcome: {outcome}")
        if not parts:
            parts.append("Action: Pending process step detail.")
        return f"- {' | '.join(parts)}{evidence_suffix}"

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
        if any(
            token in value
            for token in (
                "process",
                "procedure",
                "workflow",
                "runbook",
                "playbook",
                "sop",
                "процесс",
                "процедур",
                "регламент",
                "инструкц",
                "эскалац",
            )
        ):
            return "process"
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

    def _extract_process_triplet(self, text: str) -> dict[str, Any] | None:
        normalized = self._normalize_text(text)
        if not normalized:
            return None

        trigger = ""
        action = ""
        outcome = ""

        pattern_if_then = re.search(
            r"\b(?:if|when|если|когда)\b\s+(?P<trigger>[^.]{3,240}?)\s*(?:,|then|то)\s+(?P<action>[^.]{3,280})",
            normalized,
        )
        if pattern_if_then:
            trigger = str(pattern_if_then.group("trigger") or "").strip(" ,.;:")
            action = str(pattern_if_then.group("action") or "").strip(" ,.;:")
        else:
            pattern_steps = re.search(
                r"\b(?:process|workflow|procedure|runbook|playbook|sop|процесс|процедура|регламент|инструкция)\b[:\s-]*(?P<action>[^.]{6,320})",
                normalized,
            )
            if pattern_steps:
                action = str(pattern_steps.group("action") or "").strip(" ,.;:")

        pattern_outcome = re.search(
            r"\b(?:result|outcome|verify|sla|resolution|итог|результат|проверить|проверка)\b[:\s-]*(?P<outcome>[^.]{3,220})",
            normalized,
        )
        if pattern_outcome:
            outcome = str(pattern_outcome.group("outcome") or "").strip(" ,.;:")

        if not trigger and not action and not outcome:
            return None

        confidence = 0.55
        if action:
            confidence += 0.2
        if trigger:
            confidence += 0.15
        if outcome:
            confidence += 0.1
        confidence = max(0.0, min(1.0, round(confidence, 3)))
        return {
            "trigger": trigger,
            "action": action,
            "outcome": outcome,
            "confidence": confidence,
        }

    def _extract_process_triplet_from_claim(self, claim: ClaimInput) -> dict[str, Any] | None:
        metadata_triplet = claim.metadata.get("process_triplet") if isinstance(claim.metadata, dict) else None
        if isinstance(metadata_triplet, dict):
            trigger = str(metadata_triplet.get("trigger") or "").strip()
            action = str(metadata_triplet.get("action") or "").strip()
            outcome = str(metadata_triplet.get("outcome") or "").strip()
            if trigger or action or outcome:
                confidence = metadata_triplet.get("confidence")
                if not isinstance(confidence, (int, float)):
                    confidence = 0.85
                return {
                    "trigger": trigger,
                    "action": action,
                    "outcome": outcome,
                    "confidence": max(0.0, min(1.0, round(float(confidence), 3))),
                }

        for evidence in claim.evidence:
            if not isinstance(evidence, dict):
                continue
            evidence_triplet = evidence.get("process_triplet")
            if isinstance(evidence_triplet, dict):
                trigger = str(evidence_triplet.get("trigger") or "").strip()
                action = str(evidence_triplet.get("action") or "").strip()
                outcome = str(evidence_triplet.get("outcome") or "").strip()
                if trigger or action or outcome:
                    confidence = evidence_triplet.get("confidence")
                    if not isinstance(confidence, (int, float)):
                        confidence = 0.75
                    return {
                        "trigger": trigger,
                        "action": action,
                        "outcome": outcome,
                        "confidence": max(0.0, min(1.0, round(float(confidence), 3))),
                    }
        return self._extract_process_triplet(claim.claim_text)

    def _extract_ticket_ids_from_claim(self, claim: ClaimInput) -> list[str]:
        candidates: set[str] = set()

        def _collect(value: Any) -> None:
            text = str(value or "").strip()
            if not text:
                return
            text_upper = text.upper()
            if re.fullmatch(r"[A-Z]{2,10}-\d{1,10}", text_upper):
                candidates.add(text_upper[:64])
            elif re.fullmatch(r"\d{4,12}", text):
                candidates.add(text[:64])

        for pattern in (
            r"\b([A-Z]{2,10}-\d{1,10})\b",
            r"\b(?:ticket|case|incident|request|task)\s*(?:#|№|id)?\s*[:=-]?\s*([A-Z]{2,10}-\d{1,10}|\d{4,12})\b",
        ):
            for match in re.findall(pattern, claim.claim_text, flags=re.IGNORECASE):
                _collect(match)

        if isinstance(claim.metadata, dict):
            for key in ("ticket_id", "ticket", "case_id", "incident_id", "request_id", "task_id", "external_ticket_id"):
                _collect(claim.metadata.get(key))
            list_values = claim.metadata.get("ticket_ids")
            if isinstance(list_values, list):
                for item in list_values:
                    _collect(item)

        for evidence in claim.evidence:
            if not isinstance(evidence, dict):
                continue
            for key in ("ticket_id", "ticket", "case_id", "incident_id", "request_id", "task_id", "external_ticket_id"):
                _collect(evidence.get(key))
            meta = evidence.get("metadata")
            if isinstance(meta, dict):
                for key in ("ticket_id", "ticket", "case_id", "incident_id", "request_id", "task_id", "external_ticket_id"):
                    _collect(meta.get(key))
        return sorted(candidates)[:32]

    def _extract_outcome_from_claim(self, claim: ClaimInput) -> str | None:
        def _normalize(value: Any) -> str | None:
            text = str(value or "").strip().lower()
            return text if text else None

        if isinstance(claim.metadata, dict):
            for key in ("outcome", "resolution_outcome", "resolution", "status", "result"):
                outcome = _normalize(claim.metadata.get(key))
                if outcome:
                    return outcome[:64]

        for evidence in claim.evidence:
            if not isinstance(evidence, dict):
                continue
            for key in ("outcome", "resolution_outcome", "resolution", "status", "result"):
                outcome = _normalize(evidence.get(key))
                if outcome:
                    return outcome[:64]
            meta = evidence.get("metadata")
            if isinstance(meta, dict):
                for key in ("outcome", "resolution_outcome", "resolution", "status", "result"):
                    outcome = _normalize(meta.get(key))
                    if outcome:
                        return outcome[:64]

        tokens = set(self._tokens(claim.claim_text))
        if tokens & {"resolved", "fixed", "completed", "done", "restored", "решен", "закрыт"}:
            return "resolved"
        if tokens & {"escalated", "escalation", "handoff", "эскалация", "передан"}:
            return "escalated"
        if tokens & {"failed", "blocked", "error", "incident", "сбой", "ошибка", "неудача"}:
            return "failed"
        if tokens & {"pending", "waiting", "awaiting", "ожидание"}:
            return "pending"
        return None

    def _extract_operator_decision_context(self, claim: ClaimInput) -> dict[str, Any]:
        context: dict[str, Any] = {}
        process_triplet = self._extract_process_triplet_from_claim(claim)
        if process_triplet is not None:
            context["process_triplet"] = process_triplet
        ticket_ids = self._extract_ticket_ids_from_claim(claim)
        if ticket_ids:
            context["ticket_ids"] = ticket_ids
        outcome = self._extract_outcome_from_claim(claim)
        if outcome:
            context["outcome"] = outcome
        if context:
            context["capture_mode"] = "online_claim"
        return context

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

    def _extract_source_systems(self, evidence: list[dict[str, Any]]) -> list[str]:
        systems: set[str] = set()
        for item in evidence:
            if not isinstance(item, dict):
                continue
            candidate = item.get("source_system")
            if not candidate and isinstance(item.get("metadata"), dict):
                metadata = item.get("metadata") or {}
                candidate = metadata.get("source_system") or metadata.get("source")
            value = str(candidate or "").strip().lower()
            if not value:
                continue
            value = re.sub(r"[^a-z0-9_./:-]+", "_", value)
            value = re.sub(r"_+", "_", value).strip("_")
            if value:
                systems.add(value[:128])
        return sorted(systems)

    def _extract_source_types(self, evidence: list[dict[str, Any]]) -> list[str]:
        source_types: set[str] = set()
        for item in evidence:
            if not isinstance(item, dict):
                continue
            candidate = item.get("source_type")
            value = str(candidate or "").strip().lower()
            if not value:
                continue
            value = re.sub(r"[^a-z0-9_./:-]+", "_", value)
            value = re.sub(r"_+", "_", value).strip("_")
            if value:
                source_types.add(value[:128])
        return sorted(source_types)

    def _extract_tool_names(self, evidence: list[dict[str, Any]]) -> list[str]:
        tool_names: set[str] = set()
        for item in evidence:
            if not isinstance(item, dict):
                continue
            candidate = item.get("tool_name")
            value = str(candidate or "").strip().lower()
            if not value:
                continue
            value = re.sub(r"[^a-z0-9_./:-]+", "_", value)
            value = re.sub(r"_+", "_", value).strip("_")
            if value:
                tool_names.add(value[:128])
        return sorted(tool_names)

    def _extract_ingest_lanes(self, evidence: list[dict[str, Any]]) -> list[str]:
        ingest_lanes: set[str] = set()
        for item in evidence:
            if not isinstance(item, dict):
                continue
            lane = str(item.get("ingest_lane") or "").strip().lower()
            if lane in {"event", "knowledge"}:
                ingest_lanes.add(lane)
                continue
            metadata = item.get("metadata")
            if isinstance(metadata, dict):
                meta_lane = str(metadata.get("ingest_lane") or "").strip().lower()
                if meta_lane in {"event", "knowledge"}:
                    ingest_lanes.add(meta_lane)
        return sorted(ingest_lanes)

    def _count_keyword_hits(
        self,
        *,
        normalized_text: str,
        token_set: set[str],
        keywords: list[str],
    ) -> int:
        hits = 0
        seen: set[str] = set()
        for raw_keyword in keywords:
            keyword = str(raw_keyword or "").strip().lower()
            if not keyword or keyword in seen:
                continue
            seen.add(keyword)
            if " " in keyword:
                if keyword in normalized_text:
                    hits += 1
                continue
            if keyword in token_set:
                hits += 1
        return hits

    def _keyword_matches_identifier(self, identifier: str, keyword: str) -> bool:
        normalized_identifier = self._normalize_text(identifier)
        normalized_keyword = self._normalize_text(keyword)
        if not normalized_identifier or not normalized_keyword:
            return False
        if any(ch in normalized_keyword for ch in "_./:-"):
            return normalized_keyword in normalized_identifier
        return normalized_identifier == normalized_keyword

    def _infer_assertion_class(
        self,
        *,
        category_hint: str,
        has_policy_signal: bool,
        has_process_signal: bool,
        has_preference_signal: bool,
        has_high_priority_signal: bool,
        has_event_stream_shape: bool,
        blocked_by_source_id: bool,
        blocked_by_source_type: bool,
    ) -> str:
        if has_event_stream_shape or blocked_by_source_id or blocked_by_source_type:
            return "event"
        if has_high_priority_signal or category_hint == "incident":
            return "incident"
        if has_preference_signal or category_hint == "customer":
            return "preference"
        if has_process_signal or category_hint == "process":
            return "process"
        if has_policy_signal or category_hint in {"access", "operations"}:
            return "policy"
        return "fact"

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
