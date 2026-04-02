from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Protocol


class MCPToolCaller(Protocol):
    def __call__(self, tool_name: str, arguments: dict[str, Any]) -> Any: ...


MCP_CONTEXT_POLICY_PROFILES: dict[str, dict[str, Any]] = {
    "off": {
        "context_policy_mode": "off",
        "description": "Disable context policy filtering and rely on baseline ranking only.",
    },
    "advisory": {
        "context_policy_mode": "advisory",
        "description": "Keep full retrieval set but attach policy/confidence diagnostics.",
    },
    "enforced": {
        "context_policy_mode": "enforced",
        "min_retrieval_confidence": 0.45,
        "min_total_score": 0.20,
        "min_lexical_score": 0.08,
        "min_token_overlap_ratio": 0.15,
        "description": "Filter low-confidence rows for production-safe prompt injection.",
    },
    "strict_enforced": {
        "context_policy_mode": "enforced",
        "min_retrieval_confidence": 0.60,
        "min_total_score": 0.30,
        "min_lexical_score": 0.10,
        "min_token_overlap_ratio": 0.20,
        "description": "Use stricter filtering for high-risk or high-precision workflows.",
    },
}


def _coerce_payload(response: Any) -> Any:
    if isinstance(response, dict):
        if "structuredContent" in response and isinstance(response["structuredContent"], dict):
            return response["structuredContent"]
        if "result" in response and isinstance(response["result"], dict):
            return response["result"]
        return response
    if isinstance(response, list):
        return response
    if hasattr(response, "structuredContent"):
        structured = getattr(response, "structuredContent")
        if isinstance(structured, dict):
            return structured
    if hasattr(response, "content"):
        content = getattr(response, "content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    try:
                        return json.loads(item["text"])
                    except Exception:
                        continue
    return {"raw": response}


def _normalize_context_policy_mode(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"off", "advisory", "enforced"}:
        return normalized
    return "advisory"


def _normalize_context_policy_profile(value: str | None) -> str | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    if normalized in MCP_CONTEXT_POLICY_PROFILES:
        return normalized
    allowed = ", ".join(sorted(MCP_CONTEXT_POLICY_PROFILES.keys()))
    raise ValueError(f"unsupported context policy profile `{value}` (allowed: {allowed})")


def _resolve_context_policy_profile(value: str | None) -> dict[str, Any]:
    profile_name = _normalize_context_policy_profile(value)
    if profile_name is None:
        return {}
    profile = MCP_CONTEXT_POLICY_PROFILES.get(profile_name) or {}
    return {
        "context_policy_profile": profile_name,
        "context_policy_mode": profile.get("context_policy_mode"),
        "min_retrieval_confidence": profile.get("min_retrieval_confidence"),
        "min_total_score": profile.get("min_total_score"),
        "min_lexical_score": profile.get("min_lexical_score"),
        "min_token_overlap_ratio": profile.get("min_token_overlap_ratio"),
    }


def list_context_policy_profiles() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name in sorted(MCP_CONTEXT_POLICY_PROFILES.keys()):
        profile = dict(MCP_CONTEXT_POLICY_PROFILES.get(name) or {})
        profile["profile"] = name
        out.append(profile)
    return out


def _clamp_float(value: Any, *, minimum: float, maximum: float, default: float) -> float:
    try:
        parsed = float(value)
    except Exception:
        return float(default)
    return max(minimum, min(maximum, parsed))


def _coerce_context_policy_payload(search_payload: dict[str, Any], *, resolved_mode: str) -> dict[str, Any]:
    explainability = search_payload.get("explainability")
    if isinstance(explainability, dict):
        context_policy = explainability.get("context_policy")
        if isinstance(context_policy, dict):
            return context_policy
    payload_policy = search_payload.get("context_policy")
    if isinstance(payload_policy, dict):
        return payload_policy
    return {"mode": resolved_mode}


def _filter_context_results(
    results: list[Any],
    *,
    mode: str,
    min_retrieval_confidence: float | None,
) -> tuple[list[Any], int]:
    if mode != "enforced":
        return list(results), 0
    threshold = (
        _clamp_float(min_retrieval_confidence, minimum=0.0, maximum=1.0, default=0.45)
        if min_retrieval_confidence is not None
        else None
    )
    kept: list[Any] = []
    filtered_out = 0
    for item in results:
        if not isinstance(item, dict):
            kept.append(item)
            continue
        context_policy = item.get("context_policy")
        if isinstance(context_policy, dict) and "eligible" in context_policy:
            if bool(context_policy.get("eligible")):
                kept.append(item)
            else:
                filtered_out += 1
            continue
        confidence_raw = item.get("retrieval_confidence")
        if threshold is not None and isinstance(confidence_raw, (int, float)) and float(confidence_raw) < threshold:
            filtered_out += 1
            continue
        kept.append(item)
    return kept, filtered_out


@dataclass
class MCPContextHelper:
    project_id: str
    call_tool: MCPToolCaller
    default_search_limit: int = 6
    default_fact_limit: int = 20
    default_context_policy_profile: str | None = None
    default_context_policy_mode: str = "advisory"
    default_min_retrieval_confidence: float | None = None
    default_min_total_score: float | None = None
    default_min_lexical_score: float | None = None
    default_min_token_overlap_ratio: float | None = None

    def search_knowledge(
        self,
        query: str,
        *,
        limit: int | None = None,
        filters: dict[str, Any] | None = None,
        context_policy_profile: str | None = None,
        context_policy_mode: str | None = None,
        min_retrieval_confidence: float | None = None,
        min_total_score: float | None = None,
        min_lexical_score: float | None = None,
        min_token_overlap_ratio: float | None = None,
    ) -> dict[str, Any]:
        requested_limit = int(limit if limit is not None else self.default_search_limit)
        payload = {
            "project_id": self.project_id,
            "query": query,
            "limit": max(1, min(100, requested_limit)),
        }
        profile_overrides = _resolve_context_policy_profile(context_policy_profile or self.default_context_policy_profile)
        resolved_mode = _normalize_context_policy_mode(
            context_policy_mode or profile_overrides.get("context_policy_mode") or self.default_context_policy_mode
        )
        if resolved_mode != "advisory":
            payload["context_policy_mode"] = resolved_mode

        resolved_min_confidence = (
            min_retrieval_confidence
            if min_retrieval_confidence is not None
            else (
                profile_overrides.get("min_retrieval_confidence")
                if profile_overrides.get("min_retrieval_confidence") is not None
                else self.default_min_retrieval_confidence
            )
        )
        if resolved_min_confidence is not None:
            payload["min_retrieval_confidence"] = _clamp_float(
                resolved_min_confidence,
                minimum=0.0,
                maximum=1.0,
                default=0.45,
            )
        resolved_min_total = (
            min_total_score
            if min_total_score is not None
            else (
                profile_overrides.get("min_total_score")
                if profile_overrides.get("min_total_score") is not None
                else self.default_min_total_score
            )
        )
        if resolved_min_total is not None:
            payload["min_total_score"] = _clamp_float(
                resolved_min_total,
                minimum=0.0,
                maximum=2.0,
                default=0.20,
            )
        resolved_min_lexical = (
            min_lexical_score
            if min_lexical_score is not None
            else (
                profile_overrides.get("min_lexical_score")
                if profile_overrides.get("min_lexical_score") is not None
                else self.default_min_lexical_score
            )
        )
        if resolved_min_lexical is not None:
            payload["min_lexical_score"] = _clamp_float(
                resolved_min_lexical,
                minimum=0.0,
                maximum=2.0,
                default=0.08,
            )
        resolved_min_overlap = (
            min_token_overlap_ratio
            if min_token_overlap_ratio is not None
            else (
                profile_overrides.get("min_token_overlap_ratio")
                if profile_overrides.get("min_token_overlap_ratio") is not None
                else self.default_min_token_overlap_ratio
            )
        )
        if resolved_min_overlap is not None:
            payload["min_token_overlap_ratio"] = _clamp_float(
                resolved_min_overlap,
                minimum=0.0,
                maximum=1.0,
                default=0.15,
            )

        payload.update(dict(filters or {}))
        response = self.call_tool("search_knowledge", payload)
        normalized = _coerce_payload(response)
        if isinstance(normalized, dict):
            return normalized
        return {"results": normalized}

    def get_entity_facts(
        self,
        entity_key: str,
        *,
        limit: int | None = None,
        category: str | None = None,
        include_non_current: bool = False,
    ) -> dict[str, Any]:
        requested_limit = int(limit if limit is not None else self.default_fact_limit)
        payload = {
            "project_id": self.project_id,
            "entity_key": entity_key,
            "limit": max(1, min(500, requested_limit)),
            "include_non_current": bool(include_non_current),
        }
        if category:
            payload["category"] = category
        response = self.call_tool("get_entity_facts", payload)
        normalized = _coerce_payload(response)
        if isinstance(normalized, dict):
            return normalized
        return {"facts": normalized}

    def get_recent_changes(self, *, limit: int = 20, since_hours: int = 168) -> dict[str, Any]:
        payload = {
            "project_id": self.project_id,
            "limit": max(1, min(200, int(limit))),
            "since_hours": max(1, min(24 * 90, int(since_hours))),
        }
        response = self.call_tool("get_recent_changes", payload)
        normalized = _coerce_payload(response)
        if isinstance(normalized, dict):
            return normalized
        return {"changes": normalized}

    def explain_conflicts(
        self,
        *,
        limit: int = 20,
        resolution_status: str = "open",
        entity_key: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "project_id": self.project_id,
            "limit": max(1, min(200, int(limit))),
            "resolution_status": resolution_status,
        }
        if entity_key:
            payload["entity_key"] = entity_key
        response = self.call_tool("explain_conflicts", payload)
        normalized = _coerce_payload(response)
        if isinstance(normalized, dict):
            return normalized
        return {"conflicts": normalized}

    def build_context(
        self,
        *,
        query: str,
        entity_key: str | None = None,
        include_recent_changes: bool = False,
        recent_since_hours: int = 24,
        context_policy_profile: str | None = None,
        context_policy_mode: str = "enforced",
        min_retrieval_confidence: float | None = None,
        min_total_score: float | None = None,
        min_lexical_score: float | None = None,
        min_token_overlap_ratio: float | None = None,
    ) -> dict[str, Any]:
        resolved_mode = _normalize_context_policy_mode(context_policy_mode)
        search_payload = self.search_knowledge(
            query=query,
            context_policy_profile=context_policy_profile,
            context_policy_mode=resolved_mode,
            min_retrieval_confidence=min_retrieval_confidence,
            min_total_score=min_total_score,
            min_lexical_score=min_lexical_score,
            min_token_overlap_ratio=min_token_overlap_ratio,
        )
        raw_results = list(search_payload.get("results", []))
        search_results, filtered_out_local = _filter_context_results(
            raw_results,
            mode=resolved_mode,
            min_retrieval_confidence=min_retrieval_confidence,
        )
        policy_filtered_out = int(search_payload.get("policy_filtered_out") or 0)
        if policy_filtered_out <= 0 and filtered_out_local > 0:
            policy_filtered_out = filtered_out_local
        context: dict[str, Any] = {
            "query": query,
            "search_results": search_results,
            "revision": search_payload.get("revision"),
            "policy_filtered_out": policy_filtered_out,
            "context_policy": _coerce_context_policy_payload(search_payload, resolved_mode=resolved_mode),
        }
        if entity_key:
            facts_payload = self.get_entity_facts(entity_key)
            context["entity_key"] = entity_key
            context["entity_facts"] = list(facts_payload.get("facts", []))
            context["facts_revision"] = facts_payload.get("revision")
        else:
            context["entity_facts"] = []

        if include_recent_changes:
            changes_payload = self.get_recent_changes(since_hours=recent_since_hours)
            context["recent_changes"] = list(changes_payload.get("changes", []))
        else:
            context["recent_changes"] = []
        return context

    def build_context_markdown(
        self,
        *,
        query: str,
        entity_key: str | None = None,
        include_recent_changes: bool = False,
        context_policy_profile: str | None = None,
        max_search_results: int = 5,
        max_entity_facts: int = 8,
        max_recent_changes: int = 4,
    ) -> str:
        context = self.build_context(
            query=query,
            entity_key=entity_key,
            include_recent_changes=include_recent_changes,
            context_policy_profile=context_policy_profile,
        )
        lines: list[str] = ["## Synapse Context Injection"]
        lines.append(f"- query: {query}")
        if entity_key:
            lines.append(f"- entity_key: {entity_key}")

        results = context.get("search_results", [])
        if results:
            lines.append("### Relevant Knowledge")
            for item in results[: max(1, int(max_search_results))]:
                page = item.get("page") if isinstance(item, dict) else {}
                page_slug = page.get("slug") if isinstance(page, dict) else None
                statement = item.get("statement_text") if isinstance(item, dict) else None
                if statement:
                    lines.append(f"- {statement}" + (f" (`{page_slug}`)" if page_slug else ""))

        facts = context.get("entity_facts", [])
        if facts:
            lines.append("### Entity Facts")
            for item in facts[: max(1, int(max_entity_facts))]:
                statement = item.get("statement_text") if isinstance(item, dict) else None
                if statement:
                    lines.append(f"- {statement}")

        changes = context.get("recent_changes", [])
        if changes:
            lines.append("### Recent Changes")
            for item in changes[: max(1, int(max_recent_changes))]:
                action = item.get("action") if isinstance(item, dict) else None
                created_at = item.get("created_at") if isinstance(item, dict) else None
                page = item.get("page") if isinstance(item, dict) else {}
                page_slug = page.get("slug") if isinstance(page, dict) else None
                label = " ".join(part for part in [action, page_slug] if part)
                if label:
                    lines.append(f"- {label}" + (f" ({created_at})" if created_at else ""))

        return "\n".join(lines).strip() + "\n"

    def make_openclaw_search_callback(
        self,
        *,
        default_filters: dict[str, Any] | None = None,
        context_policy_profile: str | None = None,
        context_policy_mode: str | None = None,
        min_retrieval_confidence: float | None = None,
        min_total_score: float | None = None,
        min_lexical_score: float | None = None,
        min_token_overlap_ratio: float | None = None,
    ) -> Callable[..., Any]:
        def _callback(query: str, limit: int = 5, filters: dict[str, Any] | None = None) -> Any:
            merged_filters: dict[str, Any] = {}
            merged_filters.update(default_filters or {})
            merged_filters.update(filters or {})
            payload = self.search_knowledge(
                query=query,
                limit=limit,
                filters=merged_filters,
                context_policy_profile=context_policy_profile,
                context_policy_mode=context_policy_mode,
                min_retrieval_confidence=min_retrieval_confidence,
                min_total_score=min_total_score,
                min_lexical_score=min_lexical_score,
                min_token_overlap_ratio=min_token_overlap_ratio,
            )
            return payload.get("results", payload)

        return _callback
