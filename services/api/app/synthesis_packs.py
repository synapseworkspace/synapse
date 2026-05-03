from __future__ import annotations

import re
from typing import Any, Callable, Protocol


NormalizeItemsFn = Callable[[Any], list[str]]
ExtractRuntimeItemsFn = Callable[[list[Any], tuple[str, ...], int], list[str]]
NormalizeStatementTextFn = Callable[[str], str]
NormalizeSpaceKeyFn = Callable[[Any], str]


class SynthesisPack(Protocol):
    key: str

    def derive_task_semantics(
        self,
        task_contract: dict[str, Any],
        *,
        normalize_items: NormalizeItemsFn,
        extract_runtime_items: ExtractRuntimeItemsFn,
        normalize_statement_text: NormalizeStatementTextFn,
    ) -> dict[str, Any]: ...

    def infer_core_space_keys(
        self,
        *,
        surfaces: list[Any] | None,
        profiles: list[dict[str, Any]] | None,
        normalize_space_key: NormalizeSpaceKeyFn,
    ) -> list[str]: ...

    def infer_source_usage_from_matrix(
        self,
        *,
        matrix_rows: list[dict[str, Any]] | None,
        source_ref: str,
        source_type: str,
        config: dict[str, Any],
        normalize_statement_text: NormalizeStatementTextFn,
    ) -> dict[str, Any]: ...


_RUNTIME_SURFACE_SPACE_STOPWORDS = {
    "action",
    "agent",
    "ai",
    "approval",
    "assistant",
    "authority",
    "automation",
    "binding",
    "builtin",
    "cargo",
    "code",
    "contract",
    "control",
    "cron",
    "daily",
    "data",
    "day",
    "decision",
    "default",
    "document",
    "documents",
    "driver",
    "economy",
    "entity",
    "erp",
    "exec",
    "flow",
    "for",
    "graph",
    "hint",
    "incident",
    "integration",
    "kb",
    "knowledge",
    "latest",
    "manifest",
    "memory",
    "model",
    "monitor",
    "notes",
    "ops",
    "order",
    "orders",
    "outbound",
    "polling",
    "postgres",
    "process",
    "program",
    "readiness",
    "registry",
    "report",
    "request",
    "reschedule",
    "route",
    "runtime",
    "scheduler",
    "scenario",
    "search",
    "service",
    "shift",
    "sheet",
    "source",
    "standing",
    "state",
    "surface",
    "sync",
    "system",
    "task",
    "tool",
    "tools",
    "usage",
    "v1",
    "workflow",
    "world",
}

_RUNTIME_SURFACE_SPACE_GENERIC = {"general", "operations", "runtime", "agents"}
_RUNTIME_SURFACE_PREFERRED_SPACE_TOKENS = {
    "billing",
    "compliance",
    "dispatch",
    "finance",
    "hr",
    "legal",
    "logistics",
    "marketing",
    "procurement",
    "sales",
    "security",
    "support",
    "warehouse",
}


def _extract_runtime_surface_space_candidates(*values: Any, normalize_space_key: NormalizeSpaceKeyFn) -> list[str]:
    weighted: dict[str, int] = {}

    def _bump(token: str, weight: int) -> None:
        normalized = normalize_space_key(token)
        if not normalized or normalized in _RUNTIME_SURFACE_SPACE_STOPWORDS:
            return
        if len(normalized) < 3:
            return
        weighted[normalized] = int(weighted.get(normalized, 0)) + int(weight)

    def _scan(value: Any, *, preferred_weight: int = 3, general_weight: int = 1) -> None:
        if isinstance(value, list):
            for item in value:
                _scan(item, preferred_weight=preferred_weight, general_weight=general_weight)
            return
        if isinstance(value, dict):
            for field in (
                "space_key",
                "wiki_space_key",
                "domain",
                "team",
                "task_code",
                "builtin_task",
                "standing_order_program",
                "name",
                "capability",
                "process",
                "source",
            ):
                if field in value:
                    _scan(value.get(field), preferred_weight=preferred_weight, general_weight=general_weight)
            for field in ("capabilities", "processes", "tools", "sources", "source_hints"):
                if field in value:
                    _scan(value.get(field), preferred_weight=preferred_weight, general_weight=general_weight)
            return
        text = str(value or "").strip().lower()
        if not text:
            return
        explicit = normalize_space_key(text)
        explicit_ok = explicit and "." not in text and ":" not in text and len([part for part in re.split(r"[^a-z0-9]+", text) if part]) <= 2
        if explicit_ok and explicit not in _RUNTIME_SURFACE_SPACE_GENERIC and explicit not in _RUNTIME_SURFACE_SPACE_STOPWORDS:
            _bump(explicit, preferred_weight + 1)
        chunks = re.split(r"[^a-z0-9]+", text)
        for idx, chunk in enumerate(chunks):
            token = normalize_space_key(chunk)
            if not token:
                continue
            if token in {"standing", "order", "scheduled", "builtin", "task"} and idx + 1 < len(chunks):
                next_token = normalize_space_key(chunks[idx + 1])
                if next_token:
                    _bump(next_token, preferred_weight + 2)
                continue
            weight = preferred_weight if token in _RUNTIME_SURFACE_PREFERRED_SPACE_TOKENS else general_weight
            _bump(token, weight)

    for value in values:
        _scan(value)
    ranked = sorted(weighted.items(), key=lambda item: (-item[1], item[0]))
    return [token for token, _ in ranked[:6]]


def _build_generic_task_semantics(
    task_contract: dict[str, Any],
    *,
    normalize_items: NormalizeItemsFn,
    extract_runtime_items: ExtractRuntimeItemsFn,
) -> dict[str, Any]:
    task_code = str(task_contract.get("task_code") or task_contract.get("name") or "").strip()
    builtin_task = str(task_contract.get("builtin_task") or "").strip()
    program = str(task_contract.get("standing_order_program") or "").strip()
    schedule_kind = str(task_contract.get("schedule_kind") or "").strip()
    cron_expr = str(task_contract.get("cron_expr") or "").strip()
    interval_seconds = str(task_contract.get("interval_seconds") or "").strip()
    schedule_text = cron_expr or (f"every {interval_seconds}s" if interval_seconds else schedule_kind or "scheduled")
    authority = normalize_items(task_contract.get("standing_order_authority") or [])[:6]
    approval_mode = str(task_contract.get("standing_order_approval_mode") or "").strip()
    escalation = (
        task_contract.get("standing_order_escalation")
        if isinstance(task_contract.get("standing_order_escalation"), dict)
        else {}
    )
    escalation_mode = str(escalation.get("mode") or "").strip()
    source_hints = extract_runtime_items(
        task_contract.get("source_hints") if isinstance(task_contract.get("source_hints"), list) else [],
        fields=("source", "name", "binding", "id", "table"),
        limit=8,
    )

    artifacts = list(source_hints)
    if program:
        artifacts = list(dict.fromkeys([*artifacts, program]))[:6]
    if not artifacts:
        artifacts = ["runtime task context", "bound sources"]

    verification = [
        "Confirm the run completed without leaving approved authority or policy scope.",
        "Check that downstream artifacts were updated and reflect the latest durable state.",
    ]
    if authority:
        verification.append(f"Authority check: {', '.join(authority[:3])}.")
    if approval_mode and approval_mode.lower() not in {"", "none"}:
        verification.append(f"Approval boundary: `{approval_mode}`.")

    return {
        "title": builtin_task or task_code or "scheduled_task",
        "purpose": "Execute a recurring operational workflow and keep the result traceable for wiki/debrief reuse.",
        "trigger": f"Scheduled execution for `{task_code or builtin_task or 'task'}` on `{schedule_text}`.",
        "inputs": list(source_hints),
        "steps": [
            f"Wait for schedule trigger ({schedule_text}).",
            f"Run `{builtin_task or task_code or 'task'}` inside the approved standing-order scope.",
            "Validate the resulting state against current policy/process expectations.",
            "Record outcome, exceptions, and follow-up evidence back into the wiki/debrief loop.",
        ],
        "outputs": f"Recurring workflow `{builtin_task or task_code or 'task'}` completed and traceable.",
        "verification": verification[:4],
        "artifacts": artifacts[:6],
        "authority": authority,
        "approval_mode": approval_mode,
        "escalation_mode": escalation_mode,
        "schedule_text": schedule_text,
    }


class GenericOpsSynthesisPack:
    key = "generic_ops"

    def derive_task_semantics(
        self,
        task_contract: dict[str, Any],
        *,
        normalize_items: NormalizeItemsFn,
        extract_runtime_items: ExtractRuntimeItemsFn,
        normalize_statement_text: NormalizeStatementTextFn,
    ) -> dict[str, Any]:
        del normalize_statement_text
        return _build_generic_task_semantics(
            task_contract,
            normalize_items=normalize_items,
            extract_runtime_items=extract_runtime_items,
        )

    def infer_core_space_keys(
        self,
        *,
        surfaces: list[Any] | None,
        profiles: list[dict[str, Any]] | None,
        normalize_space_key: NormalizeSpaceKeyFn,
    ) -> list[str]:
        explicit_spaces: list[str] = []
        inferred_candidates: list[str] = []

        def _append_explicit(value: Any) -> None:
            normalized = normalize_space_key(value)
            if not normalized or normalized in _RUNTIME_SURFACE_SPACE_GENERIC:
                return
            explicit_spaces.append(normalized)

        for surface in surfaces or []:
            if surface is None:
                continue
            runtime_overview = (
                surface.runtime_overview
                if hasattr(surface, "runtime_overview") and isinstance(surface.runtime_overview, dict)
                else {}
            )
            metadata = surface.metadata if hasattr(surface, "metadata") and isinstance(surface.metadata, dict) else {}
            _append_explicit(metadata.get("space_key"))
            _append_explicit(metadata.get("wiki_space_key"))
            _append_explicit(runtime_overview.get("domain"))
            inferred_candidates.extend(
                _extract_runtime_surface_space_candidates(
                    runtime_overview.get("org_code"),
                    runtime_overview.get("domain"),
                    getattr(surface, "scheduled_tasks", None),
                    normalize_space_key=normalize_space_key,
                )
            )
        for profile in profiles or []:
            if not isinstance(profile, dict):
                continue
            metadata = profile.get("metadata") if isinstance(profile.get("metadata"), dict) else {}
            _append_explicit(metadata.get("space_key"))
            _append_explicit(metadata.get("wiki_space_key"))
            runtime_overview = metadata.get("runtime_overview") if isinstance(metadata.get("runtime_overview"), dict) else {}
            _append_explicit(runtime_overview.get("domain"))
            inferred_candidates.extend(
                _extract_runtime_surface_space_candidates(
                    metadata.get("scheduled_task_contracts"),
                    runtime_overview.get("org_code"),
                    runtime_overview.get("domain"),
                    normalize_space_key=normalize_space_key,
                )
            )

        deduped: list[str] = []
        seen: set[str] = set()
        for item in explicit_spaces:
            normalized = normalize_space_key(item)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        if deduped:
            return deduped
        for item in inferred_candidates:
            normalized = normalize_space_key(item)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped[:1] or ["operations"]

    def infer_source_usage_from_matrix(
        self,
        *,
        matrix_rows: list[dict[str, Any]] | None,
        source_ref: str,
        source_type: str,
        config: dict[str, Any],
        normalize_statement_text: NormalizeStatementTextFn,
    ) -> dict[str, Any]:
        def _safe_items(value: Any) -> list[Any]:
            if value is None:
                return []
            if isinstance(value, list):
                return value
            if isinstance(value, tuple):
                return list(value)
            if isinstance(value, set):
                return list(value)
            if isinstance(value, dict):
                return [value]
            text = str(value or "").strip()
            return [text] if text else []

        def _looks_like_knowledge_plane_source() -> bool:
            haystack = " ".join(
                [
                    str(source_type or ""),
                    str(source_ref or ""),
                    str(config.get("sql_profile") or ""),
                    str(config.get("sql_profile_table") or ""),
                    str(config.get("sql_profile_resolved_table") or ""),
                    str(config.get("sql_table") or ""),
                ]
            ).lower()
            return any(token in haystack for token in ("memory", "ops_kb", "knowledge", "policy", "wiki", "runbook"))

        inferred = {
            "agents": set(),
            "scenarios": set(),
            "capabilities": set(),
            "actions": set(),
            "processes": set(),
            "tools": set(),
            "contracts": [],
        }
        usage_tokens = {
            normalize_statement_text(str(source_ref or "")),
            normalize_statement_text(str(source_type or "")),
            normalize_statement_text(str(config.get("sql_profile") or "")),
            normalize_statement_text(str(config.get("sql_profile_table") or "")),
            normalize_statement_text(str(config.get("sql_profile_resolved_table") or "")),
            normalize_statement_text(str(config.get("sql_table") or "")),
        }
        usage_tokens = {token for token in usage_tokens if token}
        for item in matrix_rows or []:
            if not isinstance(item, dict):
                continue
            agent_id = str(item.get("agent_id") or "").strip()
            if not agent_id:
                continue
            item_sources = {
                normalize_statement_text(str(value or ""))
                for value in [*_safe_items(item.get("data_sources")), *_safe_items(item.get("source_bindings"))]
                if str(value or "").strip()
            }
            contract_sources = {
                normalize_statement_text(str(value or ""))
                for contract in _safe_items(item.get("tool_contracts"))
                if isinstance(contract, dict)
                for value in _safe_items(contract.get("sources"))
                if str(value or "").strip()
            }
            binding_contracts = [contract for contract in _safe_items(item.get("source_binding_contracts")) if isinstance(contract, dict)]
            binding_sources = {
                normalize_statement_text(str(contract.get("source") or ""))
                for contract in binding_contracts
                if str(contract.get("source") or "").strip()
            }
            if usage_tokens.intersection(item_sources.union(contract_sources).union(binding_sources)):
                inferred["agents"].add(agent_id)
                inferred["scenarios"].update({str(v).strip() for v in _safe_items(item.get("scenario_examples")) if str(v).strip()})
                inferred["capabilities"].update({str(v).strip() for v in _safe_items(item.get("responsibilities")) if str(v).strip()})
                inferred["actions"].update({str(v).strip() for v in _safe_items(item.get("allowed_actions")) if str(v).strip()})
                inferred["actions"].update({str(v).strip() for v in _safe_items(item.get("observed_actions")) if str(v).strip()})
                inferred["processes"].update({str(v).strip() for v in _safe_items(item.get("standing_orders")) if str(v).strip()})
                inferred["processes"].update({str(v).strip() for v in _safe_items(item.get("scheduled_tasks")) if str(v).strip()})
                inferred["tools"].update({str(v).strip() for v in _safe_items(item.get("tools")) if str(v).strip()})
                for contract in binding_contracts:
                    normalized_source = normalize_statement_text(str(contract.get("source") or ""))
                    if normalized_source and normalized_source in usage_tokens:
                        inferred["contracts"].append(contract)
                continue
            if _looks_like_knowledge_plane_source():
                runtime_active = bool(item.get("running_instances")) or str(item.get("status") or "").strip().lower() == "active"
                if runtime_active:
                    inferred["agents"].add(agent_id)
                    inferred["capabilities"].update({str(v).strip() for v in _safe_items(item.get("responsibilities")) if str(v).strip()})
                    inferred["processes"].update({str(v).strip() for v in _safe_items(item.get("standing_orders")) if str(v).strip()})
                    inferred["processes"].update({str(v).strip() for v in _safe_items(item.get("scheduled_tasks")) if str(v).strip()})
                    inferred["actions"].update({str(v).strip() for v in _safe_items(item.get("allowed_actions")) if str(v).strip()})
                    inferred["tools"].update({str(v).strip() for v in _safe_items(item.get("tools")) if str(v).strip()})
                    inferred["scenarios"].update({str(v).strip() for v in _safe_items(item.get("scenario_examples")) if str(v).strip()})
                    inferred["contracts"].extend(binding_contracts[:4])
        return inferred


class LogisticsOpsSynthesisPack(GenericOpsSynthesisPack):
    key = "logistics_ops"

    def derive_task_semantics(
        self,
        task_contract: dict[str, Any],
        *,
        normalize_items: NormalizeItemsFn,
        extract_runtime_items: ExtractRuntimeItemsFn,
        normalize_statement_text: NormalizeStatementTextFn,
    ) -> dict[str, Any]:
        semantics = _build_generic_task_semantics(
            task_contract,
            normalize_items=normalize_items,
            extract_runtime_items=extract_runtime_items,
        )
        task_code = str(task_contract.get("task_code") or task_contract.get("name") or "").strip()
        builtin_task = str(task_contract.get("builtin_task") or "").strip()
        program = str(task_contract.get("standing_order_program") or "").strip()
        tokens = normalize_statement_text(" ".join([task_code, builtin_task, program]))
        source_hints = list(semantics.get("inputs") or [])

        if "incident" in tokens and "monitor" in tokens:
            semantics.update(
                {
                    "purpose": "Continuously watch for logistics incidents and escalate emerging risk before it affects SLA or customer operations.",
                    "trigger": f"Recurring incident monitor runs on `{semantics['schedule_text']}` and checks active logistics risk signals.",
                    "inputs": list(dict.fromkeys([*source_hints, "incident feed", "logistics world model"]))[:6],
                    "steps": [
                        "Load the latest incident-like signals and open operational alerts.",
                        "Check whether any active incident crosses escalation or recurrence thresholds.",
                        "Notify the responsible authority and write back the incident state if escalation is required.",
                        "Capture resolution status or unresolved blockers for the next monitor cycle.",
                    ],
                    "outputs": "Updated incident status with explicit escalation notes and next action owner.",
                    "verification": [
                        "Verify whether an incident was opened, updated, or intentionally left unchanged.",
                        "Confirm escalation routing matches the configured authority and escalation mode.",
                    ],
                }
            )
        elif "driver" in tokens and "economy" in tokens:
            semantics.update(
                {
                    "purpose": "Refresh the driver economy reporting workflow so operations can review cost/performance drift on a stable schedule.",
                    "trigger": f"Recurring economy reporting task runs on `{semantics['schedule_text']}` and prepares the latest driver economy view.",
                    "inputs": list(dict.fromkeys([*source_hints, "driver economy metrics", "shift performance context"]))[:6],
                    "steps": [
                        "Collect the latest driver economy metrics and supporting shift context.",
                        "Recalculate or refresh the target report/sheet for the scheduled reporting window.",
                        "Highlight anomalies or changes that may require operational review before downstream use.",
                        "Publish or save the refreshed report and note any exceptions for follow-up.",
                    ],
                    "outputs": "Updated driver economy report/sheet ready for operations or finance review.",
                    "verification": [
                        "Confirm the reporting window and source freshness match the expected daily/shift cycle.",
                        "Verify that anomalies and missing inputs are explicitly called out in the output.",
                    ],
                }
            )
        elif "document" in tokens and ("shift" in tokens or "readiness" in tokens):
            semantics.update(
                {
                    "purpose": "Check document readiness before a driver shift or dispatch window starts.",
                    "trigger": f"Readiness control runs on `{semantics['schedule_text']}` before operational handoff points.",
                    "inputs": list(dict.fromkeys([*source_hints, "driver documents", "shift roster", "readiness checklist"]))[:6],
                    "steps": [
                        "Load the latest driver/shift document set and readiness checklist.",
                        "Detect missing, expired, or inconsistent documents before shift execution.",
                        "Escalate unresolved readiness blockers to the configured authority.",
                        "Record the final readiness state and any missing artifacts.",
                    ],
                    "outputs": "Document readiness state updated with explicit blockers and escalation notes.",
                    "verification": [
                        "Confirm every required document is either present or escalated.",
                        "Verify the final readiness note is written back for the next operator/agent.",
                    ],
                }
            )
        elif ("cargo" in tokens and "sync" in tokens) or ("erp" in tokens and "sync" in tokens):
            semantics.update(
                {
                    "purpose": "Synchronize cargo or ERP-facing notes so downstream logistics decisions rely on current operational data.",
                    "trigger": f"Recurring sync job runs on `{semantics['schedule_text']}` to refresh ERP/cargo-facing state.",
                    "inputs": list(dict.fromkeys([*source_hints, "ERP notes", "cargo state", "dispatch context"]))[:6],
                    "steps": [
                        "Read the latest cargo/ERP-facing inputs and current dispatch state.",
                        "Apply the synchronization/update routine for notes, status, or derived fields.",
                        "Detect mismatches or write failures before declaring the sync complete.",
                        "Record synchronization outcome and unresolved deltas for follow-up.",
                    ],
                    "outputs": "ERP/cargo notes synchronized and any mismatches explicitly recorded.",
                    "verification": [
                        "Confirm the target system reflects the newly synchronized state.",
                        "Check that any failed or partial updates were escalated instead of silently ignored.",
                    ],
                }
            )
        elif "daily" in tokens and "report" in tokens:
            semantics.update(
                {
                    "purpose": "Produce a recurring daily operating digest from the latest durable and operational signals.",
                    "trigger": f"Daily reporting task runs on `{semantics['schedule_text']}` to assemble the latest operational summary.",
                    "inputs": list(dict.fromkeys([*source_hints, "daily activity metrics", "open blockers", "escalation summary"]))[:6],
                    "steps": [
                        "Collect the latest daily metrics, blockers, escalations, and durable changes.",
                        "Assemble the report in the expected operational format or destination system.",
                        "Highlight exceptions, missed thresholds, or open risks that require human attention.",
                        "Publish the daily report and link follow-up actions where needed.",
                    ],
                    "outputs": "Published daily report with current blockers, escalations, and activity summary.",
                    "verification": [
                        "Confirm the report covers the intended reporting window and audience.",
                        "Verify important blockers/escalations were surfaced, not hidden in generic summary text.",
                    ],
                }
            )
        elif "comment" in tokens and ("signal" in tokens or "learning" in tokens):
            semantics.update(
                {
                    "purpose": "Distill recurring operational comments into reusable signals that can improve future playbooks or knowledge pages.",
                    "trigger": f"Comment-signal learning task runs on `{semantics['schedule_text']}` to review fresh operational feedback.",
                    "inputs": list(dict.fromkeys([*source_hints, "recent comments", "operator notes", "existing knowledge patterns"]))[:6],
                    "steps": [
                        "Review fresh operational comments and extract recurring or durable patterns.",
                        "Separate actionable signals from one-off noise or transactional chatter.",
                        "Link high-signal findings to affected processes, data sources, or decisions.",
                        "Write back the synthesized findings for wiki/debrief promotion.",
                    ],
                    "outputs": "Structured learning signals ready for knowledge promotion or human review.",
                    "verification": [
                        "Check that extracted signals are durable and reusable rather than raw chatter.",
                        "Confirm promoted learnings are linked to the affected workflow or decision area.",
                    ],
                }
            )

        return semantics


_PACKS: dict[str, SynthesisPack] = {
    "generic_ops": GenericOpsSynthesisPack(),
    "logistics_ops": LogisticsOpsSynthesisPack(),
}


def get_synthesis_pack(key: str | None) -> SynthesisPack:
    normalized = str(key or "").strip().lower()
    return _PACKS.get(normalized) or _PACKS["generic_ops"]
