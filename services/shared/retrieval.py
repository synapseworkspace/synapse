from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class RetrievalGraphConfig:
    max_graph_hops: int = 3
    boost_hop1: float = 0.20
    boost_hop2: float = 0.12
    boost_hop3: float = 0.06
    boost_other: float = 0.03


@dataclass(frozen=True, slots=True)
class RetrievalContextPolicyConfig:
    mode: str = "advisory"  # off | advisory | enforced
    min_confidence: float = 0.45
    min_total_score: float = 0.20
    min_lexical_score: float = 0.08
    min_token_overlap_ratio: float = 0.15


@dataclass(frozen=True, slots=True)
class RetrievalSearchPlan:
    sql: str
    params: tuple[Any, ...]
    query: str
    limit: int
    query_tokens: tuple[str, ...]
    entity_key: str | None
    category: str | None
    page_type: str | None
    related_entity_key: str | None


def serialize_graph_config(config: RetrievalGraphConfig) -> dict[str, float | int]:
    return {
        "max_graph_hops": int(config.max_graph_hops),
        "boost_hop1": round(float(config.boost_hop1), 4),
        "boost_hop2": round(float(config.boost_hop2), 4),
        "boost_hop3": round(float(config.boost_hop3), 4),
        "boost_other": round(float(config.boost_other), 4),
    }


def build_graph_config_headers(config: RetrievalGraphConfig) -> dict[str, str]:
    payload = serialize_graph_config(config)
    return {
        "X-Synapse-Retrieval-Graph-Max-Hops": str(payload["max_graph_hops"]),
        "X-Synapse-Retrieval-Graph-Boost-Hop1": f"{payload['boost_hop1']:.4f}",
        "X-Synapse-Retrieval-Graph-Boost-Hop2": f"{payload['boost_hop2']:.4f}",
        "X-Synapse-Retrieval-Graph-Boost-Hop3": f"{payload['boost_hop3']:.4f}",
        "X-Synapse-Retrieval-Graph-Boost-Other": f"{payload['boost_other']:.4f}",
    }


def normalize_context_policy_mode(value: Any, *, default: str = "advisory") -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"off", "advisory", "enforced"}:
        return normalized
    fallback = str(default or "advisory").strip().lower()
    return fallback if fallback in {"off", "advisory", "enforced"} else "advisory"


def serialize_context_policy_config(config: RetrievalContextPolicyConfig) -> dict[str, float | str]:
    return {
        "mode": normalize_context_policy_mode(config.mode),
        "min_confidence": round(float(config.min_confidence), 4),
        "min_total_score": round(float(config.min_total_score), 4),
        "min_lexical_score": round(float(config.min_lexical_score), 4),
        "min_token_overlap_ratio": round(float(config.min_token_overlap_ratio), 4),
    }


def build_context_policy_headers(config: RetrievalContextPolicyConfig) -> dict[str, str]:
    payload = serialize_context_policy_config(config)
    return {
        "X-Synapse-Retrieval-Context-Policy-Mode": str(payload["mode"]),
        "X-Synapse-Retrieval-Context-Min-Confidence": f"{float(payload['min_confidence']):.4f}",
        "X-Synapse-Retrieval-Context-Min-Total-Score": f"{float(payload['min_total_score']):.4f}",
        "X-Synapse-Retrieval-Context-Min-Lexical-Score": f"{float(payload['min_lexical_score']):.4f}",
        "X-Synapse-Retrieval-Context-Min-Token-Overlap-Ratio": f"{float(payload['min_token_overlap_ratio']):.4f}",
    }


def load_context_policy_config_from_env(
    env: Mapping[str, str] | None = None,
) -> RetrievalContextPolicyConfig:
    source = os.environ if env is None else env
    return RetrievalContextPolicyConfig(
        mode=normalize_context_policy_mode(source.get("SYNAPSE_MCP_CONTEXT_POLICY_MODE"), default="advisory"),
        min_confidence=normalize_float_value(
            source.get("SYNAPSE_MCP_CONTEXT_MIN_CONFIDENCE", "0.45"),
            default=0.45,
            minimum=0.0,
            maximum=1.0,
        ),
        min_total_score=normalize_float_value(
            source.get("SYNAPSE_MCP_CONTEXT_MIN_TOTAL_SCORE", "0.20"),
            default=0.20,
            minimum=0.0,
            maximum=2.0,
        ),
        min_lexical_score=normalize_float_value(
            source.get("SYNAPSE_MCP_CONTEXT_MIN_LEXICAL_SCORE", "0.08"),
            default=0.08,
            minimum=0.0,
            maximum=2.0,
        ),
        min_token_overlap_ratio=normalize_float_value(
            source.get("SYNAPSE_MCP_CONTEXT_MIN_TOKEN_OVERLAP_RATIO", "0.15"),
            default=0.15,
            minimum=0.0,
            maximum=1.0,
        ),
    )


def resolve_context_policy_config(
    *,
    base: RetrievalContextPolicyConfig,
    mode: str | None = None,
    min_confidence: float | None = None,
    min_total_score: float | None = None,
    min_lexical_score: float | None = None,
    min_token_overlap_ratio: float | None = None,
) -> RetrievalContextPolicyConfig:
    return RetrievalContextPolicyConfig(
        mode=normalize_context_policy_mode(mode, default=base.mode),
        min_confidence=normalize_float_value(
            min_confidence if min_confidence is not None else base.min_confidence,
            default=base.min_confidence,
            minimum=0.0,
            maximum=1.0,
        ),
        min_total_score=normalize_float_value(
            min_total_score if min_total_score is not None else base.min_total_score,
            default=base.min_total_score,
            minimum=0.0,
            maximum=2.0,
        ),
        min_lexical_score=normalize_float_value(
            min_lexical_score if min_lexical_score is not None else base.min_lexical_score,
            default=base.min_lexical_score,
            minimum=0.0,
            maximum=2.0,
        ),
        min_token_overlap_ratio=normalize_float_value(
            min_token_overlap_ratio if min_token_overlap_ratio is not None else base.min_token_overlap_ratio,
            default=base.min_token_overlap_ratio,
            minimum=0.0,
            maximum=1.0,
        ),
    )


RETRIEVAL_SEARCH_SQL = """
WITH RECURSIVE relation_edges AS (
  SELECT
    lower(p.entity_key) AS from_entity,
    lower(rel.entity_value) AS to_entity
  FROM wiki_pages p
  CROSS JOIN LATERAL jsonb_array_elements_text(
    COALESCE(p.metadata->'related_entities', '[]'::jsonb)
  ) AS rel(entity_value)
  WHERE p.project_id = %s
    AND p.status = 'published'
),
graph_edges AS (
  SELECT from_entity, to_entity FROM relation_edges
  UNION
  SELECT to_entity AS from_entity, from_entity AS to_entity FROM relation_edges
),
graph_walk AS (
  SELECT %s::text AS entity_key, 0::int AS hop_count
  WHERE %s::text IS NOT NULL
  UNION ALL
  SELECT ge.to_entity, gw.hop_count + 1
  FROM graph_walk gw
  JOIN graph_edges ge ON ge.from_entity = gw.entity_key
  WHERE gw.hop_count < %s
),
graph_hops AS (
  SELECT
    entity_key,
    MIN(hop_count)::int AS hop_count
  FROM graph_walk
  WHERE hop_count > 0
  GROUP BY entity_key
)
SELECT
  st.id::text,
  st.statement_text,
  st.section_key,
  st.valid_from,
  st.valid_to,
  st.created_at,
  p.id::text,
  p.title,
  p.slug,
  p.entity_key,
  p.page_type,
  COALESCE(claim_meta.category, ''),
  (
    GREATEST(
      CASE WHEN lower(p.entity_key) = %s THEN 1.00 ELSE 0.00 END,
      CASE WHEN lower(p.slug) = %s THEN 0.95 ELSE 0.00 END,
      CASE WHEN lower(p.title) LIKE %s THEN 0.86 ELSE 0.00 END,
      similarity(st.normalized_text, %s),
      similarity(lower(p.title), %s),
      COALESCE((
        SELECT MAX(similarity(lower(a.alias_text), %s))
        FROM wiki_page_aliases a
        WHERE a.page_id = p.id
      ), 0.0)
    )
    + CASE
        WHEN %s::text IS NULL OR graph_hops.hop_count IS NULL THEN 0.00
        WHEN graph_hops.hop_count = 1 THEN %s
        WHEN graph_hops.hop_count = 2 THEN %s
        WHEN graph_hops.hop_count = 3 THEN %s
        ELSE %s
      END
  ) AS score
  ,
  graph_hops.hop_count,
  CASE
    WHEN %s::text IS NULL OR graph_hops.hop_count IS NULL THEN 0.00
    WHEN graph_hops.hop_count = 1 THEN %s
    WHEN graph_hops.hop_count = 2 THEN %s
    WHEN graph_hops.hop_count = 3 THEN %s
    ELSE %s
  END AS graph_boost
FROM wiki_statements st
JOIN wiki_pages p ON p.id = st.page_id
LEFT JOIN graph_hops ON lower(p.entity_key) = graph_hops.entity_key
LEFT JOIN LATERAL (
  SELECT c.category
  FROM claims c
  WHERE c.project_id = st.project_id
    AND c.claim_fingerprint = st.claim_fingerprint
  ORDER BY c.updated_at DESC
  LIMIT 1
) claim_meta ON TRUE
WHERE st.project_id = %s
  AND p.status = 'published'
  AND st.status = 'active'
  AND (st.valid_from IS NULL OR st.valid_from <= NOW())
  AND (st.valid_to IS NULL OR st.valid_to >= NOW())
  AND (%s::text IS NULL OR lower(p.entity_key) = %s)
  AND (%s::text IS NULL OR lower(p.page_type) = %s)
  AND (%s::text IS NULL OR lower(COALESCE(claim_meta.category, '')) = %s)
  AND (
    lower(st.statement_text) LIKE %s
    OR st.normalized_text LIKE %s
    OR lower(p.title) LIKE %s
    OR lower(p.slug) LIKE %s
    OR lower(p.entity_key) = %s
    OR similarity(st.normalized_text, %s) >= 0.15
    OR similarity(lower(p.title), %s) >= 0.25
    OR EXISTS (
      SELECT 1
      FROM wiki_page_aliases a
      WHERE a.page_id = p.id
        AND lower(a.alias_text) LIKE %s
    )
    OR (%s::text IS NOT NULL AND graph_hops.hop_count IS NOT NULL)
  )
ORDER BY score DESC, st.created_at DESC
LIMIT %s
"""


def clean_optional_filter(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    return normalized


def normalize_limit_value(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return max(minimum, min(maximum, parsed))


def normalize_float_value(value: Any, *, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except Exception:
        return float(default)
    return float(max(minimum, min(maximum, parsed)))


def normalize_search_text(value: Any) -> str:
    return str(value or "").strip().lower()


def query_tokens(query: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9_]+", query.lower()) if token]


def token_overlap(tokens: Sequence[str], text: str) -> tuple[int, float]:
    if not tokens:
        return (0, 0.0)
    haystack = normalize_search_text(text)
    if not haystack:
        return (0, 0.0)
    hits = sum(1 for token in tokens if token in haystack)
    return (hits, hits / max(1, len(tokens)))


def load_graph_config_from_env(
    env: Mapping[str, str] | None = None,
) -> RetrievalGraphConfig:
    source = os.environ if env is None else env
    return RetrievalGraphConfig(
        max_graph_hops=normalize_limit_value(
            source.get("SYNAPSE_MCP_GRAPH_MAX_HOPS", "3"),
            default=3,
            minimum=1,
            maximum=6,
        ),
        boost_hop1=normalize_float_value(
            source.get("SYNAPSE_MCP_GRAPH_BOOST_HOP1", "0.20"),
            default=0.20,
            minimum=0.0,
            maximum=2.0,
        ),
        boost_hop2=normalize_float_value(
            source.get("SYNAPSE_MCP_GRAPH_BOOST_HOP2", "0.12"),
            default=0.12,
            minimum=0.0,
            maximum=2.0,
        ),
        boost_hop3=normalize_float_value(
            source.get("SYNAPSE_MCP_GRAPH_BOOST_HOP3", "0.06"),
            default=0.06,
            minimum=0.0,
            maximum=2.0,
        ),
        boost_other=normalize_float_value(
            source.get("SYNAPSE_MCP_GRAPH_BOOST_OTHER", "0.03"),
            default=0.03,
            minimum=0.0,
            maximum=2.0,
        ),
    )


def build_retrieval_search_plan(
    *,
    project_id: str,
    query: str,
    limit: int,
    entity_key: str | None,
    category: str | None,
    page_type: str | None,
    related_entity_key: str | None,
    graph_config: RetrievalGraphConfig,
) -> RetrievalSearchPlan | None:
    normalized_query = str(query or "").strip()
    if not normalized_query:
        return None
    needle = normalize_search_text(normalized_query)
    like = f"%{needle}%"
    needle_slug = needle.replace(" ", "-")
    normalized_limit = normalize_limit_value(limit, default=10, minimum=1, maximum=100)
    entity_filter = clean_optional_filter(entity_key)
    category_filter = clean_optional_filter(category)
    page_type_filter = clean_optional_filter(page_type)
    related_filter = clean_optional_filter(related_entity_key)
    params = (
        project_id,
        related_filter,
        related_filter,
        graph_config.max_graph_hops,
        needle,
        needle_slug,
        like,
        needle,
        needle,
        needle,
        related_filter,
        graph_config.boost_hop1,
        graph_config.boost_hop2,
        graph_config.boost_hop3,
        graph_config.boost_other,
        related_filter,
        graph_config.boost_hop1,
        graph_config.boost_hop2,
        graph_config.boost_hop3,
        graph_config.boost_other,
        project_id,
        entity_filter,
        entity_filter,
        page_type_filter,
        page_type_filter,
        category_filter,
        category_filter,
        like,
        like,
        like,
        like,
        needle,
        needle,
        needle,
        like,
        related_filter,
        normalized_limit,
    )
    return RetrievalSearchPlan(
        sql=RETRIEVAL_SEARCH_SQL,
        params=params,
        query=normalized_query,
        limit=normalized_limit,
        query_tokens=tuple(query_tokens(normalized_query)),
        entity_key=entity_filter,
        category=category_filter,
        page_type=page_type_filter,
        related_entity_key=related_filter,
    )


def build_retrieval_explain_fields(
    *,
    query: str,
    related_entity_key: str | None,
    result: dict[str, Any],
    query_tokens_override: Sequence[str] | None = None,
    context_policy: RetrievalContextPolicyConfig | None = None,
) -> dict[str, Any]:
    query_norm = normalize_search_text(query)
    query_slug = query_norm.replace(" ", "-")
    resolved_query_tokens = list(query_tokens_override) if query_tokens_override is not None else query_tokens(query_norm)

    payload = dict(result)
    page = payload.get("page")
    page_obj = page if isinstance(page, dict) else {}
    statement_text = str(payload.get("statement_text") or "")
    page_title = str(page_obj.get("title") or "")
    page_slug = str(page_obj.get("slug") or "")
    page_entity = str(page_obj.get("entity_key") or "")

    statement_hits, statement_ratio = token_overlap(resolved_query_tokens, statement_text)
    title_hits, title_ratio = token_overlap(resolved_query_tokens, page_title)
    slug_hits, slug_ratio = token_overlap(resolved_query_tokens, page_slug)
    combined_hits, combined_ratio = token_overlap(
        resolved_query_tokens,
        f"{statement_text} {page_title} {page_slug} {page_entity}",
    )

    entity_exact_match = bool(page_entity and normalize_search_text(page_entity) == query_norm)
    slug_exact_match = bool(page_slug and normalize_search_text(page_slug) == query_slug)
    title_phrase_match = bool(query_norm and query_norm in normalize_search_text(page_title))
    phrase_match = bool(
        query_norm
        and query_norm in normalize_search_text(f"{statement_text} {page_title} {page_slug} {page_entity}")
    )

    score = round(float(payload.get("score") or 0.0), 4)
    graph_boost = round(float(payload.get("graph_boost") or 0.0), 4)
    lexical_score = round(max(0.0, score - graph_boost), 4)
    graph_hops = payload.get("graph_hops")

    reason_parts: list[str] = []
    if entity_exact_match:
        reason_parts.append("exact entity match")
    elif slug_exact_match:
        reason_parts.append("exact slug match")
    elif title_phrase_match:
        reason_parts.append("title phrase match")
    if resolved_query_tokens:
        reason_parts.append(f"token overlap {combined_hits}/{len(resolved_query_tokens)}")
    if related_entity_key and graph_hops is not None:
        reason_parts.append(
            f"graph relation from `{related_entity_key}` in {int(graph_hops)} hop(s) (+{graph_boost:.2f})"
        )
    if not reason_parts:
        reason_parts.append("lexical similarity above retrieval floor")

    payload["score_breakdown"] = {
        "total": score,
        "lexical": lexical_score,
        "graph": graph_boost,
        "lexical_components": {
            "query_tokens_total": len(resolved_query_tokens),
            "token_overlap_hits": combined_hits,
            "token_overlap_ratio": round(combined_ratio, 4),
            "statement_token_hits": statement_hits,
            "statement_token_ratio": round(statement_ratio, 4),
            "title_token_hits": title_hits,
            "title_token_ratio": round(title_ratio, 4),
            "slug_token_hits": slug_hits,
            "slug_token_ratio": round(slug_ratio, 4),
            "entity_exact_match": entity_exact_match,
            "slug_exact_match": slug_exact_match,
            "title_phrase_match": title_phrase_match,
            "phrase_match": phrase_match,
        },
    }

    exact_match_signal = 0.0
    if entity_exact_match:
        exact_match_signal = 1.0
    elif slug_exact_match:
        exact_match_signal = 0.9
    elif title_phrase_match:
        exact_match_signal = 0.7
    elif phrase_match:
        exact_match_signal = 0.5

    graph_support = 0.0
    if related_entity_key and graph_hops is not None:
        hop_score = {1: 1.0, 2: 0.78, 3: 0.56}.get(int(graph_hops), 0.38)
        boost_score = max(0.0, min(1.0, graph_boost / 0.35))
        graph_support = max(0.0, min(1.0, 0.65 * hop_score + 0.35 * boost_score))

    lexical_score_norm = max(0.0, min(1.0, lexical_score / 1.10))
    confidence = (
        0.06
        + (0.50 * combined_ratio)
        + (0.22 * lexical_score_norm)
        + (0.15 * exact_match_signal)
        + (0.04 if phrase_match else 0.0)
        + (0.07 * graph_support)
    )
    confidence = max(0.0, min(1.0, confidence))
    confidence = round(confidence, 4)
    payload["retrieval_confidence"] = confidence
    payload["confidence_breakdown"] = {
        "overall": confidence,
        "lexical_overlap": round(combined_ratio, 4),
        "lexical_score_norm": round(lexical_score_norm, 4),
        "exact_match_signal": round(exact_match_signal, 4),
        "phrase_signal": 1.0 if phrase_match else 0.0,
        "graph_support": round(graph_support, 4),
    }

    effective_policy = context_policy or RetrievalContextPolicyConfig()
    policy_mode = normalize_context_policy_mode(effective_policy.mode)
    blockers: list[str] = []
    if policy_mode != "off":
        if score < float(effective_policy.min_total_score):
            blockers.append("min_total_score")
        if lexical_score < float(effective_policy.min_lexical_score):
            blockers.append("min_lexical_score")
        if (
            combined_ratio < float(effective_policy.min_token_overlap_ratio)
            and not entity_exact_match
            and not slug_exact_match
            and not title_phrase_match
        ):
            blockers.append("min_token_overlap_ratio")
        if confidence < float(effective_policy.min_confidence):
            blockers.append("min_confidence")

    eligible = not blockers
    payload["context_policy"] = {
        "mode": policy_mode,
        "eligible": bool(eligible),
        "blocked_by": blockers,
        "thresholds": serialize_context_policy_config(effective_policy),
    }
    payload["retrieval_reason"] = "; ".join(reason_parts)
    return payload
