from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Iterable, Protocol, Sequence


@dataclass(slots=True)
class InsightContext:
    function_name: str
    integration: str
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    result: Any
    category_hint: str | None = None
    entity_hint: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    source_id: str | None = None


@dataclass(slots=True)
class ExtractedInsight:
    claim_text: str
    category: str | None = None
    entity_key: str | None = None
    confidence: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    valid_from: str | None = None
    valid_to: str | None = None


class Extractor(Protocol):
    name: str

    def extract(self, context: InsightContext) -> Sequence[ExtractedInsight]: ...


@dataclass(slots=True)
class StructuredResultExtractor:
    name: str = "structured_result"

    def extract(self, context: InsightContext) -> Sequence[ExtractedInsight]:
        result = context.result
        if not isinstance(result, dict):
            return []
        claim_text = str(result.get("claim_text") or result.get("fact") or "").strip()
        if not claim_text:
            return []
        category = str(result.get("category") or context.category_hint or "").strip() or None
        entity_key = str(result.get("entity_key") or context.entity_hint or "").strip() or None
        confidence = _coerce_confidence(result.get("confidence"))
        valid_from = _coerce_iso_or_none(result.get("valid_from"))
        valid_to = _coerce_iso_or_none(result.get("valid_to"))
        metadata = dict(result.get("metadata") or {})
        return [
            ExtractedInsight(
                claim_text=claim_text,
                category=category,
                entity_key=entity_key,
                confidence=confidence,
                metadata=metadata,
                valid_from=valid_from,
                valid_to=valid_to,
            )
        ]


@dataclass(slots=True)
class KeywordExtractor:
    name: str = "keyword"
    keywords: tuple[str, ...] = (
        "closed",
        "open",
        "required",
        "forbidden",
        "only",
        "policy",
        "quarantine",
        "gate",
        "card",
        "access",
    )
    min_text_len: int = 12

    def extract(self, context: InsightContext) -> Sequence[ExtractedInsight]:
        texts = _coerce_texts(context.result)
        out: list[ExtractedInsight] = []
        for text in texts:
            normalized = text.lower()
            if len(normalized) < self.min_text_len:
                continue
            if not any(keyword in normalized for keyword in self.keywords):
                continue
            out.append(
                ExtractedInsight(
                    claim_text=text.strip(),
                    category=context.category_hint,
                    entity_key=context.entity_hint,
                    confidence=0.7,
                    metadata={"extractor": self.name, "keywords": [k for k in self.keywords if k in normalized][:5]},
                )
            )
        return out


def default_extractors() -> list[Extractor]:
    return [StructuredResultExtractor(), KeywordExtractor()]


def _coerce_texts(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    if isinstance(value, dict):
        texts: list[str] = []
        for key in ("claim_text", "fact", "message", "text", "result", "summary"):
            raw = value.get(key)
            if isinstance(raw, str) and raw.strip():
                texts.append(raw.strip())
        if texts:
            return texts
        return [repr(value)]
    if isinstance(value, (list, tuple, set, frozenset)):
        return [item for item in (_coerce_scalar_text(x) for x in value) if item]
    return [repr(value)]


def _coerce_scalar_text(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        return _coerce_scalar_text(value.get("text") or value.get("message") or value.get("result"))
    return None


def _coerce_confidence(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, number))


def _coerce_iso_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}", text):
        return text
    return None
