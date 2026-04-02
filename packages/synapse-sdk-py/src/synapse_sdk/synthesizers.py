from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence

from synapse_sdk.extractors import ExtractedInsight

SYNTHESIZER_CONTRACT_VERSION = "v1"


@dataclass(slots=True)
class SynthesisContext:
    function_name: str
    integration: str
    extracted_insights: tuple[ExtractedInsight, ...]
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    result: Any
    category_hint: str | None = None
    entity_hint: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    source_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Synthesizer(Protocol):
    name: str
    contract_version: str

    def synthesize(self, context: SynthesisContext) -> Sequence[ExtractedInsight]: ...


@dataclass(slots=True)
class ConfidenceClampSynthesizer:
    name: str = "confidence_clamp"
    contract_version: str = SYNTHESIZER_CONTRACT_VERSION

    def synthesize(self, context: SynthesisContext) -> Sequence[ExtractedInsight]:
        out: list[ExtractedInsight] = []
        for item in context.extracted_insights:
            confidence = item.confidence
            if confidence is not None:
                confidence = max(0.0, min(1.0, float(confidence)))
            metadata = dict(item.metadata)
            metadata.setdefault("synthesizer", self.name)
            out.append(
                ExtractedInsight(
                    claim_text=item.claim_text,
                    category=item.category,
                    entity_key=item.entity_key,
                    confidence=confidence,
                    metadata=metadata,
                    valid_from=item.valid_from,
                    valid_to=item.valid_to,
                )
            )
        return out


def default_synthesizers() -> list[Synthesizer]:
    return [ConfidenceClampSynthesizer()]
