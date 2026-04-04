from __future__ import annotations

from copy import deepcopy
import re
from typing import Any


POSTGRES_SQL_PROFILE_PRESETS: dict[str, dict[str, Any]] = {
    "ops_kb_items": {
        "label": "Ops KB Items",
        "description": "Operational KB table used in many agent stacks.",
        "default_table": "ops_kb_items",
        "table_candidates": ["ops_kb_items", "public.ops_kb_items"],
        "default_source_id_prefix": "ops_kb",
        "source_id_fields": ["source_id", "id", "memory_id"],
        "content_fields": ["content", "note", "text", "summary", "message", "value"],
        "entity_key_fields": ["entity_key", "entity", "entity_id", "customer_id", "subject_id"],
        "category_fields": ["category", "kind", "type", "topic"],
        "observed_at_fields": ["updated_at", "observed_at", "created_at", "timestamp", "ts"],
        "metadata_fields": ["metadata", "meta", "attributes", "context", "extra", "tags"],
    },
    "memory_items": {
        "label": "Memory Items",
        "description": "Generic runtime memory table (`memory_items`).",
        "default_table": "memory_items",
        "table_candidates": ["memory_items", "public.memory_items"],
        "default_source_id_prefix": "memory",
        "source_id_fields": ["source_id", "id", "memory_id"],
        "content_fields": ["content", "text", "value", "note", "summary", "message", "payload"],
        "entity_key_fields": ["entity_key", "entity", "entity_id", "agent_id", "subject_id"],
        "category_fields": ["category", "kind", "type", "memory_type"],
        "observed_at_fields": ["updated_at", "observed_at", "created_at", "timestamp", "ts"],
        "metadata_fields": ["metadata", "meta", "attributes", "context", "extra", "tags"],
    },
}

_PROFILE_ALIASES = {
    "ops_kb": "ops_kb_items",
    "opskb": "ops_kb_items",
    "ops-kb-items": "ops_kb_items",
    "memory": "memory_items",
    "memory-item": "memory_items",
    "memory-item-table": "memory_items",
}


def list_postgres_sql_profiles() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for profile in sorted(POSTGRES_SQL_PROFILE_PRESETS.keys()):
        preset = deepcopy(POSTGRES_SQL_PROFILE_PRESETS[profile])
        preset["profile"] = profile
        out.append(preset)
    return out


def get_postgres_sql_profile_preset(profile: str | None) -> dict[str, Any] | None:
    normalized = normalize_postgres_sql_profile(profile)
    if not normalized:
        return None
    preset = POSTGRES_SQL_PROFILE_PRESETS.get(normalized)
    return deepcopy(preset) if isinstance(preset, dict) else None


def normalize_postgres_sql_profile(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _normalize_simple_key(value)
    if not normalized:
        return None
    if normalized == "auto":
        return "auto"
    if normalized in POSTGRES_SQL_PROFILE_PRESETS:
        return normalized
    alias = _PROFILE_ALIASES.get(normalized)
    if alias:
        return alias
    return None


def infer_postgres_sql_profile(source_ref: str, *, config: dict[str, Any] | None = None) -> str | None:
    payload = dict(config or {})
    explicit = normalize_postgres_sql_profile(
        _first_non_empty(
            payload.get("sql_profile"),
            payload.get("profile"),
        )
    )
    if explicit and explicit != "auto":
        return explicit

    source_ref_text = str(source_ref or "").strip().lower()
    table_hint = str(payload.get("sql_profile_table") or payload.get("table") or "").strip().lower()
    combined = f"{source_ref_text} {table_hint}".strip()
    if not combined:
        return None

    if _contains_any(combined, ("ops_kb_items", "opskb", "ops_kb", "ops-kb")):
        return "ops_kb_items"
    if _contains_any(combined, ("memory_items", "memoryitems", "memory_item", "memory-item")):
        return "memory_items"
    return None


def apply_postgres_sql_profile_defaults(
    config: dict[str, Any] | None,
    *,
    source_ref: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized = dict(config or {})
    metadata: dict[str, Any] = {
        "profile": None,
        "profile_inferred": False,
        "profile_auto_mode": False,
    }

    raw_profile = _first_non_empty(normalized.get("sql_profile"), normalized.get("profile"))
    profile = normalize_postgres_sql_profile(raw_profile)
    if profile == "auto":
        metadata["profile_auto_mode"] = True
        profile = infer_postgres_sql_profile(source_ref, config=normalized)
        metadata["profile_inferred"] = bool(profile)
    elif not profile:
        has_query = bool(str(normalized.get("sql_query") or "").strip()) or bool(
            str(normalized.get("sql_query_file") or "").strip()
        )
        if not has_query:
            profile = infer_postgres_sql_profile(source_ref, config=normalized)
            metadata["profile_inferred"] = bool(profile)

    if not profile:
        return normalized, metadata

    preset = get_postgres_sql_profile_preset(profile)
    if not preset:
        return normalized, metadata

    normalized["sql_profile"] = profile
    if "profile" in normalized and not str(normalized.get("profile") or "").strip():
        normalized["profile"] = profile
    normalized.setdefault("sql_sync_mode", "polling")
    normalized.setdefault("sql_profile_table", str(preset.get("default_table") or "").strip())
    normalized.setdefault("sql_source_id_prefix", str(preset.get("default_source_id_prefix") or "").strip())

    mapping = normalized.get("sql_mapping") if isinstance(normalized.get("sql_mapping"), dict) else {}
    merged_mapping = dict(mapping)
    _set_default_field(merged_mapping, "source_id_field", preset.get("source_id_fields"))
    _set_default_field(merged_mapping, "entity_key_field", preset.get("entity_key_fields"))
    _set_default_field(merged_mapping, "category_field", preset.get("category_fields"))
    _set_default_field(merged_mapping, "observed_at_field", preset.get("observed_at_fields"))
    _set_default_field_list(merged_mapping, "content_fields", preset.get("content_fields"))
    _set_default_field_list(merged_mapping, "metadata_fields", preset.get("metadata_fields"))
    normalized["sql_mapping"] = merged_mapping

    metadata["profile"] = profile
    return normalized, metadata


def _set_default_field(mapping: dict[str, Any], key: str, candidates: Any) -> None:
    if str(mapping.get(key) or "").strip():
        return
    if not isinstance(candidates, list):
        return
    for item in candidates:
        text = str(item or "").strip()
        if text:
            mapping[key] = text
            return


def _set_default_field_list(mapping: dict[str, Any], key: str, candidates: Any) -> None:
    if isinstance(mapping.get(key), list) and mapping.get(key):
        return
    if not isinstance(candidates, list):
        return
    normalized: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        text = str(item or "").strip()
        if not text:
            continue
        token = text.lower()
        if token in seen:
            continue
        seen.add(token)
        normalized.append(text)
    if normalized:
        mapping[key] = normalized


def _first_non_empty(*values: Any) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


def _normalize_simple_key(value: str | None) -> str:
    if value is None:
        return ""
    token = str(value).strip().lower()
    token = token.replace(" ", "_")
    token = re.sub(r"[^a-z0-9_]+", "_", token)
    token = re.sub(r"_+", "_", token).strip("_")
    return token


def _contains_any(value: str, tokens: tuple[str, ...]) -> bool:
    payload = value.lower()
    for token in tokens:
        if token in payload:
            return True
    return False
