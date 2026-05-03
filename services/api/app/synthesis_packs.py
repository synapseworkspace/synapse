from __future__ import annotations

from typing import Any, Callable, Protocol


NormalizeItemsFn = Callable[[Any], list[str]]
ExtractRuntimeItemsFn = Callable[[list[Any], tuple[str, ...], int], list[str]]
NormalizeStatementTextFn = Callable[[str], str]


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
