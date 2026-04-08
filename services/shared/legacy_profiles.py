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

_SYNC_RUNNER_CONTRACTS: dict[str, dict[str, Any]] = {
    "polling": {
        "contract_key": "postgres_sql.polling",
        "source_type": "postgres_sql",
        "sync_mode": "polling",
        "sync_mode_aliases": ["query"],
        "label": "Incremental SQL Polling",
        "description": (
            "Runs parameterized SQL query on schedule, tracks cursor in source config, "
            "and uploads only incremental rows."
        ),
        "required_config": ["sql_dsn or sql_dsn_env"],
        "optional_config": [
            "sql_profile",
            "sql_profile_table",
            "sql_query",
            "sql_query_file",
            "sql_query_params",
            "sql_cursor_state_key",
            "sql_cursor_param",
            "sql_cursor_column",
            "sql_source_id_prefix",
            "chunk_size",
            "max_records",
        ],
        "state_keys": [
            "sql_last_cursor",
            "sql_last_synced_at",
            "sql_profile_resolved_table",
            "sql_profile_resolved_at",
        ],
        "runner": {
            "scheduler_script": "python services/worker/scripts/run_legacy_sync_scheduler.py --all-projects",
            "recommended_interval_minutes": 5,
            "supports_cron": True,
            "supports_continuous": False,
            "run_modes": ["manual", "scheduled"],
        },
        "cursor_semantics": {
            "default_state_key": "sql_last_cursor",
            "cursor_param": "cursor",
            "order": "ascending",
        },
    },
    "wal_cdc": {
        "contract_key": "postgres_sql.wal_cdc",
        "source_type": "postgres_sql",
        "sync_mode": "wal_cdc",
        "sync_mode_aliases": ["wal", "cdc"],
        "label": "Postgres WAL CDC",
        "description": (
            "Reads changes from logical replication slot, converts rows into backfill records, "
            "and tracks LSN cursor for near-real-time sync."
        ),
        "required_config": ["sql_dsn or sql_dsn_env", "wal_slot"],
        "optional_config": [
            "wal_publication",
            "wal_tables",
            "wal_start_lsn",
            "wal_cursor_state_key",
            "wal_timeout_seconds",
            "wal_max_changes",
            "sql_source_id_prefix",
            "chunk_size",
            "max_records",
        ],
        "state_keys": [
            "sql_last_lsn",
            "wal_last_lsn",
            "sql_last_synced_at",
        ],
        "runner": {
            "scheduler_script": "python services/worker/scripts/run_legacy_sync_scheduler.py --all-projects",
            "recommended_interval_minutes": 1,
            "supports_cron": True,
            "supports_continuous": True,
            "run_modes": ["manual", "scheduled"],
        },
        "cursor_semantics": {
            "default_state_key": "sql_last_lsn",
            "cursor_param": "wal_lsn",
            "order": "lsn_ascending",
        },
    },
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


def list_legacy_mapper_templates(
    *,
    source_type: str = "postgres_sql",
    profile: str | None = None,
) -> list[dict[str, Any]]:
    if _normalize_simple_key(source_type) != "postgres_sql":
        return []

    selected_profile = normalize_postgres_sql_profile(profile)
    out: list[dict[str, Any]] = []
    for profile_name, preset in sorted(POSTGRES_SQL_PROFILE_PRESETS.items()):
        if selected_profile and selected_profile not in {"auto", profile_name}:
            continue
        out.append(_build_postgres_sql_mapper_template(profile_name, preset, sync_mode="polling"))
        out.append(_build_postgres_sql_mapper_template(profile_name, preset, sync_mode="wal_cdc"))
    return out


def list_legacy_sync_runner_contracts(
    *,
    source_type: str = "postgres_sql",
    profile: str | None = None,
) -> list[dict[str, Any]]:
    if _normalize_simple_key(source_type) != "postgres_sql":
        return []
    normalized_profile = normalize_postgres_sql_profile(profile)
    profile_hints: list[str] = []
    if normalized_profile and normalized_profile != "auto":
        profile_hints = [normalized_profile]
    else:
        profile_hints = sorted(POSTGRES_SQL_PROFILE_PRESETS.keys())

    out: list[dict[str, Any]] = []
    for sync_mode in ("polling", "wal_cdc"):
        base = deepcopy(_SYNC_RUNNER_CONTRACTS[sync_mode])
        base["profile_hints"] = profile_hints
        base["recommended_profiles"] = profile_hints
        out.append(base)
    return out


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


def _build_postgres_sql_mapper_template(profile: str, preset: dict[str, Any], *, sync_mode: str) -> dict[str, Any]:
    default_table = str(preset.get("default_table") or "").strip()
    observed_candidates = preset.get("observed_at_fields") if isinstance(preset.get("observed_at_fields"), list) else []
    observed_field = str(observed_candidates[0]).strip() if observed_candidates else ""
    source_prefix = str(preset.get("default_source_id_prefix") or profile).strip() or profile
    mapping = {
        "source_id_field": _first_non_empty_list_item(preset.get("source_id_fields")),
        "entity_key_field": _first_non_empty_list_item(preset.get("entity_key_fields")),
        "category_field": _first_non_empty_list_item(preset.get("category_fields")),
        "observed_at_field": observed_field,
        "content_fields": list(preset.get("content_fields") or []),
        "metadata_fields": list(preset.get("metadata_fields") or []),
    }
    if sync_mode == "polling":
        config_patch: dict[str, Any] = {
            "sql_profile": profile,
            "sql_sync_mode": "polling",
            "sql_profile_table": default_table,
            "sql_source_id_prefix": source_prefix,
            "sql_cursor_state_key": "sql_last_cursor",
            "sql_cursor_param": "cursor",
            "max_records": 5000,
            "chunk_size": 100,
            "curated_import": {
                "enabled": True,
                "noise_preset": "balanced",
                "drop_event_like": True,
            },
            "sql_mapping": mapping,
        }
        if observed_field:
            config_patch["sql_cursor_column"] = observed_field
        template_key = f"postgres_sql.{profile}.polling"
        label_suffix = "Polling"
    else:
        config_patch = {
            "sql_profile": profile,
            "sql_sync_mode": "wal_cdc",
            "wal_slot": f"synapse_{profile}_slot",
            "wal_publication": f"synapse_{profile}_publication",
            "wal_tables": [default_table] if default_table else [],
            "wal_cursor_state_key": "sql_last_lsn",
            "sql_source_id_prefix": source_prefix,
            "max_records": 5000,
            "chunk_size": 100,
            "curated_import": {
                "enabled": True,
                "noise_preset": "balanced",
                "drop_event_like": True,
            },
            "sql_mapping": mapping,
        }
        template_key = f"postgres_sql.{profile}.wal_cdc"
        label_suffix = "WAL CDC"

    return {
        "template_key": template_key,
        "source_type": "postgres_sql",
        "profile": profile,
        "sync_mode": sync_mode,
        "label": f"{preset.get('label') or profile} ({label_suffix})",
        "description": str(preset.get("description") or "").strip(),
        "config_patch": config_patch,
        "runner_contract_key": f"postgres_sql.{sync_mode}",
    }


def _first_non_empty_list_item(values: Any) -> str:
    if not isinstance(values, list):
        return ""
    for item in values:
        text = str(item or "").strip()
        if text:
            return text
    return ""


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
