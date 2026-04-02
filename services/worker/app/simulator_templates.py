from __future__ import annotations

from typing import Any


TEMPLATE_CATALOG: dict[str, str] = {
    "gate_access_card_only": "Tighten gate access for a location/entity to physical card-only mode.",
    "warehouse_quarantine": "Mark warehouse operations as quarantined (temporarily restricted).",
    "prepaid_only_dispatch": "Switch dispatch policy to prepaid-only before shipment.",
}


def list_templates() -> dict[str, str]:
    return dict(TEMPLATE_CATALOG)


def build_policy_changes(template_id: str, *, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    normalized_id = str(template_id or "").strip().lower()
    if normalized_id not in TEMPLATE_CATALOG:
        allowed = ", ".join(sorted(TEMPLATE_CATALOG.keys()))
        raise ValueError(f"unsupported template_id='{template_id}'. supported: {allowed}")

    payload = dict(params or {})
    if normalized_id == "gate_access_card_only":
        return _gate_access_card_only(payload)
    if normalized_id == "warehouse_quarantine":
        return _warehouse_quarantine(payload)
    if normalized_id == "prepaid_only_dispatch":
        return _prepaid_only_dispatch(payload)
    raise ValueError(f"unsupported template_id='{template_id}'")


def _require_non_empty_string(params: dict[str, Any], key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"template parameter '{key}' is required")
    return value.strip()


def _optional_string(params: dict[str, Any], key: str) -> str | None:
    value = params.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _gate_access_card_only(params: dict[str, Any]) -> list[dict[str, Any]]:
    entity_key = _require_non_empty_string(params, "entity_key").lower()
    location_name = _optional_string(params, "location_name") or entity_key.replace("_", " ").title()
    old_statement = _optional_string(params, "old_statement") or f"{location_name}: gate is open for deliveries."
    new_statement = _optional_string(params, "new_statement") or f"{location_name}: gate access requires a physical key card."
    return [
        {
            "policy_id": f"{entity_key}_gate_card_only",
            "entity_key": entity_key,
            "category": "access",
            "old_statement": old_statement,
            "new_statement": new_statement,
        }
    ]


def _warehouse_quarantine(params: dict[str, Any]) -> list[dict[str, Any]]:
    entity_key = _require_non_empty_string(params, "entity_key").lower()
    warehouse_name = _optional_string(params, "warehouse_name") or entity_key.replace("_", " ").title()
    until_date = _optional_string(params, "until_date")
    old_statement = _optional_string(params, "old_statement") or f"{warehouse_name}: normal loading/unloading operations."
    quarantine_tail = f" until {until_date}" if until_date else ""
    new_statement = _optional_string(params, "new_statement") or (
        f"{warehouse_name}: operations are restricted due to quarantine{quarantine_tail}."
    )
    return [
        {
            "policy_id": f"{entity_key}_quarantine",
            "entity_key": entity_key,
            "category": "operations",
            "old_statement": old_statement,
            "new_statement": new_statement,
        }
    ]


def _prepaid_only_dispatch(params: dict[str, Any]) -> list[dict[str, Any]]:
    entity_key = (_optional_string(params, "entity_key") or "billing_policy").lower()
    policy_scope = _optional_string(params, "scope_name") or "Dispatch Policy"
    old_statement = _optional_string(params, "old_statement") or f"{policy_scope}: orders may be shipped before payment."
    new_statement = _optional_string(params, "new_statement") or (
        f"{policy_scope}: orders must be prepaid before shipment dispatch."
    )
    return [
        {
            "policy_id": f"{entity_key}_prepaid_only",
            "entity_key": entity_key,
            "category": "billing",
            "old_statement": old_statement,
            "new_statement": new_statement,
        }
    ]
