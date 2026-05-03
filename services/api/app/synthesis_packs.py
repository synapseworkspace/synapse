from __future__ import annotations

import re
from typing import Any, Callable, Protocol


NormalizeItemsFn = Callable[[Any], list[str]]
ExtractRuntimeItemsFn = Callable[[list[Any], tuple[str, ...], int], list[str]]
NormalizeStatementTextFn = Callable[[str], str]
NormalizeSpaceKeyFn = Callable[[Any], str]
SpaceSlugFn = Callable[[str, str], str]
BuildDecisionsLogSeedPageFn = Callable[[str], dict[str, str]]


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

    def refine_process_playbook(
        self,
        *,
        playbook: dict[str, Any],
        source_kind: str,
        normalize_statement_text: NormalizeStatementTextFn,
    ) -> dict[str, Any]: ...

    def build_company_context_extensions(
        self,
        *,
        matrix_rows: list[dict[str, Any]] | None,
        source_counts: list[tuple[str, int]] | None,
        claims_rollup: list[tuple[str, int]] | None,
        normalize_statement_text: NormalizeStatementTextFn,
    ) -> dict[str, Any]: ...

    def build_capability_profile_extensions(
        self,
        *,
        matrix_rows: list[dict[str, Any]] | None,
    ) -> dict[str, Any]: ...

    def build_tooling_map_extensions(
        self,
        *,
        matrix_rows: list[dict[str, Any]] | None,
    ) -> dict[str, Any]: ...

    def default_space_for_starter_profile(self, profile: str) -> str: ...

    def wiki_space_template_catalog(self) -> list[dict[str, Any]]: ...

    def build_first_run_starter_pages(
        self,
        profile: str,
        *,
        space_key: str | None,
        include_decisions_log: bool,
        normalize_space_key: NormalizeSpaceKeyFn,
        space_slug: SpaceSlugFn,
        build_decisions_log_seed_page: BuildDecisionsLogSeedPageFn,
    ) -> list[dict[str, str]]: ...

    def build_role_template_pages(
        self,
        template_key: str,
        *,
        space_key: str | None,
        normalize_space_key: NormalizeSpaceKeyFn,
        space_slug: SpaceSlugFn,
    ) -> list[dict[str, str]]: ...

    def business_profiles_catalog(self) -> list[dict[str, Any]]: ...

    def resolve_business_profile(self, key: str | None) -> dict[str, Any] | None: ...

    def canonical_page_classes(self) -> list[dict[str, Any]]: ...

    def build_company_knowledge_seed_pages(
        self,
        profile: str,
        *,
        space_key: str | None,
        normalize_space_key: NormalizeSpaceKeyFn,
        space_slug: SpaceSlugFn,
    ) -> list[dict[str, str]]: ...


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

_STARTER_PROFILE_DEFAULT_SPACES = {
    "standard": "operations",
    "support_ops": "support",
    "logistics_ops": "logistics",
    "sales_ops": "sales",
    "compliance_ops": "compliance",
    "ai_employee_org": "operations",
}

_WIKI_SPACE_TEMPLATE_CATALOG = [
    {
        "template_key": "support_ops",
        "label": "Support Ops",
        "default_space_key": "support",
        "description": "Triage, escalation, and customer communication playbooks.",
        "policy": {"write_mode": "owners_only", "comment_mode": "open", "review_assignment_required": True},
    },
    {
        "template_key": "logistics_ops",
        "label": "Logistics Ops",
        "default_space_key": "logistics",
        "description": "Dispatch rules, access procedures, and incident handling.",
        "policy": {"write_mode": "owners_only", "comment_mode": "open", "review_assignment_required": True},
    },
    {
        "template_key": "sales_ops",
        "label": "Sales Ops",
        "default_space_key": "sales",
        "description": "Qualification rules, stage playbooks, and handoff contracts.",
        "policy": {"write_mode": "open", "comment_mode": "open", "review_assignment_required": False},
    },
    {
        "template_key": "compliance_ops",
        "label": "Compliance Ops",
        "default_space_key": "compliance",
        "description": "Control catalog, evidence workflow, and audit readiness.",
        "policy": {"write_mode": "owners_only", "comment_mode": "owners_only", "review_assignment_required": True},
    },
    {
        "template_key": "ai_employee_org",
        "label": "AI Employee Org",
        "default_space_key": "operations",
        "description": "Opinionated bootstrap for agent-driven organizations: profiles, tools, tasks, HITL, and integrations.",
        "policy": {"write_mode": "owners_only", "comment_mode": "open", "review_assignment_required": True},
    },
]

_BUSINESS_PROFILES_CATALOG = [
    {
        "key": "generic_service_ops",
        "label": "Generic Service Ops",
        "description": "Neutral default for service organizations that want a clean wiki-first operating baseline.",
        "synthesis_pack": "generic_ops",
        "starter_profile": "standard",
        "role_template_key": None,
        "default_space_key": "operations",
        "bundle_promotion_space_key": "operations",
        "recommended_noise_preset": "enterprise_wiki_bootstrap",
        "focus": ["agent profile", "data map", "operational runbook", "decisions log"],
        "company_knowledge_pack": "generic_company",
    },
    {
        "key": "logistics_operator",
        "label": "Logistics Operator",
        "description": "Dispatch, routing, warehouse, incident, and recurring transport workflow heavy deployments.",
        "synthesis_pack": "logistics_ops",
        "starter_profile": "logistics_ops",
        "role_template_key": "logistics_ops",
        "default_space_key": "logistics",
        "bundle_promotion_space_key": "logistics",
        "recommended_noise_preset": "enterprise_wiki_bootstrap",
        "focus": ["process playbooks", "data sources catalog", "incident runbooks", "scheduled task SOPs"],
        "company_knowledge_pack": "logistics_company",
    },
    {
        "key": "support_center",
        "label": "Support Center",
        "description": "Triage, escalation, customer communication, and incident response heavy support organizations.",
        "synthesis_pack": "support_ops",
        "starter_profile": "support_ops",
        "role_template_key": "support_ops",
        "default_space_key": "support",
        "bundle_promotion_space_key": "support",
        "recommended_noise_preset": "enterprise_wiki_bootstrap",
        "focus": ["ticket triage", "escalation rules", "customer communication", "decision log"],
        "company_knowledge_pack": "support_company",
    },
    {
        "key": "sales_revenue_ops",
        "label": "Sales / Revenue Ops",
        "description": "Qualification, stage management, and sales-to-success handoff driven teams.",
        "synthesis_pack": "sales_ops",
        "starter_profile": "sales_ops",
        "role_template_key": "sales_ops",
        "default_space_key": "sales",
        "bundle_promotion_space_key": "sales",
        "recommended_noise_preset": "enterprise_wiki_bootstrap",
        "focus": ["deal stage playbooks", "handoff contracts", "tooling map", "company operating context"],
        "company_knowledge_pack": "sales_company",
    },
    {
        "key": "compliance_program",
        "label": "Compliance Program",
        "description": "Control catalogs, audit evidence, review workflows, and policy-heavy environments.",
        "synthesis_pack": "compliance_ops",
        "starter_profile": "compliance_ops",
        "role_template_key": "compliance_ops",
        "default_space_key": "compliance",
        "bundle_promotion_space_key": "compliance",
        "recommended_noise_preset": "enterprise_wiki_bootstrap",
        "focus": ["control maps", "audit evidence", "policy pages", "decisions log"],
        "company_knowledge_pack": "compliance_company",
    },
    {
        "key": "ai_employee_org",
        "label": "AI Employee Org",
        "description": "Agent-driven org with strong control-plane metadata, scheduled tasks, approvals, and integrations.",
        "synthesis_pack": "generic_ops",
        "starter_profile": "ai_employee_org",
        "role_template_key": "ai_employee_org",
        "default_space_key": "operations",
        "bundle_promotion_space_key": "operations",
        "recommended_noise_preset": "enterprise_wiki_bootstrap",
        "focus": ["tool catalog", "scheduled tasks", "HITL rules", "integrations map", "agent directory"],
        "company_knowledge_pack": "generic_company",
    },
]

_CANONICAL_PAGE_CLASS_CATALOG = [
    {
        "page_type": "entity",
        "label": "Entity",
        "purpose": "Canonical page for a business entity, its states, identifiers, linked systems, and related processes.",
        "sections": ["Definition", "Key Fields", "States", "Systems", "Related Processes", "Exceptions"],
    },
    {
        "page_type": "process",
        "label": "Process",
        "purpose": "Human-readable SOP describing purpose, owner, trigger, inputs, outputs, exceptions, and escalation.",
        "sections": ["Purpose", "Owner", "Trigger", "Inputs", "Outputs", "Exceptions", "Escalation"],
    },
    {
        "page_type": "policy",
        "label": "Policy",
        "purpose": "Stable rule or approval boundary with authority, scope, and override guidance.",
        "sections": ["Rule", "Scope", "Authority", "Exceptions", "Override Rules", "Review Cadence"],
    },
    {
        "page_type": "source_of_truth",
        "label": "Source of Truth",
        "purpose": "Explains which system or table is authoritative for a question and how to trust freshness/derived data.",
        "sections": ["Canonical Source", "Derived Signals", "Freshness", "Conflict Resolution", "Owners"],
    },
    {
        "page_type": "glossary_term",
        "label": "Glossary Term",
        "purpose": "Company term with definition, aliases, and linked entities/processes.",
        "sections": ["Definition", "Aliases", "Used In", "Common Confusions"],
    },
    {
        "page_type": "known_exception",
        "label": "Known Exception",
        "purpose": "Documented non-ideal but recurring exception pattern, when it applies, and what to do.",
        "sections": ["Exception Pattern", "Applies When", "Risk", "Mitigation", "Expiry/Review"],
    },
    {
        "page_type": "escalation_rule",
        "label": "Escalation Rule",
        "purpose": "Defines when work stops being autonomous and who must be involved next.",
        "sections": ["Trigger", "Owner", "Channel", "SLA", "Resolution Expectations"],
    },
]

_COMPANY_KNOWLEDGE_PACKS: dict[str, list[dict[str, str]]] = {
    "generic_company": [
        {
            "title": "How the Operation Works",
            "slug_leaf": "how-the-operation-works",
            "page_type": "process",
            "markdown": (
                "# How the Operation Works\n\n"
                "## Purpose\n"
                "- Describe the operating model in human language: who participates, what success looks like, and where the main workflow loops live.\n\n"
                "## Core Roles\n"
                "- Team leads, operators, agents, reviewers, and escalation owners.\n\n"
                "## Core Loops\n"
                "- Daily operating cadence, exception handling, reporting, and approvals.\n\n"
                "## Failure Modes\n"
                "- Common breakdown points and the first place to look when outcomes drift.\n"
            ),
        },
        {
            "title": "Company Glossary",
            "slug_leaf": "company-glossary",
            "page_type": "glossary_term",
            "markdown": (
                "# Company Glossary\n\n"
                "## Canonical Terms\n"
                "- Define the words people actually use, not just table names or tool labels.\n\n"
                "## Aliases\n"
                "- Common shorthand, internal synonyms, and terms that frequently get confused.\n"
            ),
        },
        {
            "title": "Roles and Responsibilities",
            "slug_leaf": "roles-and-responsibilities",
            "page_type": "entity",
            "markdown": (
                "# Roles and Responsibilities\n\n"
                "## Human Roles\n"
                "- What each operator, manager, and reviewer owns.\n\n"
                "## Agent Roles\n"
                "- What agents do autonomously, what they propose, and when they escalate.\n"
            ),
        },
        {
            "title": "Sources of Truth",
            "slug_leaf": "sources-of-truth",
            "page_type": "source_of_truth",
            "markdown": (
                "# Sources of Truth\n\n"
                "## Canonical Systems\n"
                "- Which system answers which business question.\n\n"
                "## Trust Rules\n"
                "- What to do when operational, derived, and canonical sources disagree.\n"
            ),
        },
        {
            "title": "Known Exceptions and Heuristics",
            "slug_leaf": "known-exceptions-and-heuristics",
            "page_type": "known_exception",
            "markdown": (
                "# Known Exceptions and Heuristics\n\n"
                "## Common Exceptions\n"
                "- Situations where the ideal process is not what experienced operators actually do.\n\n"
                "## Heuristics\n"
                "- Stable working rules that are learned from repeated practice.\n"
            ),
        },
    ],
    "logistics_company": [
        {
            "title": "How the Logistics Operation Works",
            "slug_leaf": "how-the-logistics-operation-works",
            "page_type": "process",
            "markdown": (
                "# How the Logistics Operation Works\n\n"
                "## Purpose\n"
                "- Explain the logistics operation in business language: roles, operating loops, critical workflows, and common failure points.\n\n"
                "## Core Roles\n"
                "- Dispatch, operators, drivers, managers, and AI agents.\n\n"
                "## Success Criteria\n"
                "- On-time execution, shift readiness, safe escalations, and accurate reporting.\n\n"
                "## Common Failure Modes\n"
                "- Readiness gaps, route drift, provider outages, stale ERP data, and unresolved incidents.\n"
            ),
        },
        {
            "title": "Logistics Glossary",
            "slug_leaf": "logistics-glossary",
            "page_type": "glossary_term",
            "markdown": (
                "# Logistics Glossary\n\n"
                "## Canonical Terms\n"
                "- Define shift, route, order, tech task, readiness, incident, and source of truth in company language.\n\n"
                "## Common Confusions\n"
                "- Record terms that often get mixed up across ERP, sheets, and operational conversations.\n"
            ),
        },
        {
            "title": "Roles and Responsibility Zones",
            "slug_leaf": "roles-and-responsibility-zones",
            "page_type": "entity",
            "markdown": (
                "# Roles and Responsibility Zones\n\n"
                "## Human Operators\n"
                "- What dispatch, operations leads, and reviewers own.\n\n"
                "## Agent Responsibility\n"
                "- What the logistics assistant can do autonomously, what it proposes, and when it must escalate.\n"
            ),
        },
        {
            "title": "Documents and Shift Readiness",
            "slug_leaf": "documents-and-shift-readiness",
            "page_type": "entity",
            "markdown": (
                "# Documents and Shift Readiness\n\n"
                "## Required Documents\n"
                "- Which documents matter before shift execution and why.\n\n"
                "## Readiness States\n"
                "- Ready, blocked, incomplete, and exception states.\n\n"
                "## Source of Truth\n"
                "- Which systems or projections should be trusted for document/readiness checks.\n"
            ),
        },
        {
            "title": "Daily Logistics Operating Cycle",
            "slug_leaf": "daily-logistics-operating-cycle",
            "page_type": "process",
            "markdown": (
                "# Daily Logistics Operating Cycle\n\n"
                "## Morning Checks\n"
                "- Readiness, provider state, route status, and critical incidents.\n\n"
                "## Daytime Monitoring\n"
                "- Fleet status, delivery failures, escalation handling, and exception review.\n\n"
                "## Reporting Cadence\n"
                "- Daily reports, economics slices, and end-of-day review outputs.\n"
            ),
        },
        {
            "title": "Incidents and Escalations",
            "slug_leaf": "incidents-and-escalations",
            "page_type": "escalation_rule",
            "markdown": (
                "# Incidents and Escalations\n\n"
                "## What Counts as an Incident\n"
                "- Define severity, business impact, and operational triggers.\n\n"
                "## Escalation Rules\n"
                "- Who is notified, through which channel, and with what SLA.\n\n"
                "## Agent Boundaries\n"
                "- Where the agent can act automatically and where a human must take over.\n"
            ),
        },
        {
            "title": "Driver Economics and Reporting",
            "slug_leaf": "driver-economics-and-reporting",
            "page_type": "entity",
            "markdown": (
                "# Driver Economics and Reporting\n\n"
                "## What Is Measured\n"
                "- Which economics slices matter for drivers and why they are reviewed.\n\n"
                "## Consumers\n"
                "- Who reads the report and what decisions it supports.\n\n"
                "## Anomaly Patterns\n"
                "- Which outliers and drifts deserve operational attention.\n"
            ),
        },
        {
            "title": "ERP and Operational Systems",
            "slug_leaf": "erp-and-operational-systems",
            "page_type": "source_of_truth",
            "markdown": (
                "# ERP and Operational Systems\n\n"
                "## System Roles\n"
                "- ERP, sheets, provider feeds, memory/KB, and internal projections.\n\n"
                "## System of Record\n"
                "- Which system is authoritative for routes, tasks, docs, and reporting.\n"
            ),
        },
        {
            "title": "Trust Rules for Logistics Data",
            "slug_leaf": "trust-rules-for-logistics-data",
            "page_type": "source_of_truth",
            "markdown": (
                "# Trust Rules for Logistics Data\n\n"
                "## Priority Rules\n"
                "- If systems disagree, record what should win for each business question.\n\n"
                "## Freshness Windows\n"
                "- When data is considered stale and when a refresh or escalation is required.\n\n"
                "## Canonical vs Derived\n"
                "- Distinguish source-of-truth values from operational projections and summaries.\n"
            ),
        },
        {
            "title": "Known Pitfalls and Working Heuristics",
            "slug_leaf": "known-pitfalls-and-working-heuristics",
            "page_type": "known_exception",
            "markdown": (
                "# Known Pitfalls and Working Heuristics\n\n"
                "## Common Pitfalls\n"
                "- Typical false signals, stale feeds, and process mismatches that experienced operators watch for.\n\n"
                "## Stable Heuristics\n"
                "- What usually works in real operations when the formal process is not enough.\n"
            ),
        },
    ],
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


def _humanize_signal_label(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").replace("_", " ")).strip()
    return text[:1].upper() + text[1:] if text else ""


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

    def refine_process_playbook(
        self,
        *,
        playbook: dict[str, Any],
        source_kind: str,
        normalize_statement_text: NormalizeStatementTextFn,
    ) -> dict[str, Any]:
        del source_kind, normalize_statement_text
        return dict(playbook)

    def build_company_context_extensions(
        self,
        *,
        matrix_rows: list[dict[str, Any]] | None,
        source_counts: list[tuple[str, int]] | None,
        claims_rollup: list[tuple[str, int]] | None,
        normalize_statement_text: NormalizeStatementTextFn,
    ) -> dict[str, Any]:
        del matrix_rows, source_counts, claims_rollup, normalize_statement_text
        return {
            "snapshot_notes": [],
            "workflow_signals": [],
            "entity_signals": [],
            "process_signals": [],
            "trust_signals": [],
            "exception_signals": [],
            "candidate_canon_blocks": [],
            "principles": [
                "Durable policy/process knowledge should be published to wiki; event payload streams stay in operational lane.",
                "Escalation is mandatory when SLA/compliance/customer-impact risks are detected.",
                "Agent actions should be constrained by tool guardrails and approval rules.",
            ],
        }

    def build_capability_profile_extensions(
        self,
        *,
        matrix_rows: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        del matrix_rows
        return {
            "signal_bullets": [
                "Runtime intents observed in sessions/tasks and converted into reusable actions.",
                "Tool invocations and handoff contracts between agents.",
                "Data-source access patterns, policy limits, and escalation pathways.",
            ],
            "sparse_hint": "Capability discovery is still sparse; add explicit profile metadata or debrief signals to enrich this agent page.",
        }

    def build_tooling_map_extensions(
        self,
        *,
        matrix_rows: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        del matrix_rows
        return {
            "governance_bullets": [
                "Any tool touching finance/compliance/customer identity should require approval or reviewer assignment.",
                "Prefer policy/process backed actions over direct payload-driven decisions.",
                "Use this map to document which tool drives which workflow and where human approval boundaries start.",
            ],
            "empty_hint": "Runtime tool discovery pending",
        }

    def default_space_for_starter_profile(self, profile: str) -> str:
        return _STARTER_PROFILE_DEFAULT_SPACES.get(str(profile or "").strip().lower(), "operations")

    def wiki_space_template_catalog(self) -> list[dict[str, Any]]:
        return [dict(item) for item in _WIKI_SPACE_TEMPLATE_CATALOG]

    def canonical_page_classes(self) -> list[dict[str, Any]]:
        return [dict(item) for item in _CANONICAL_PAGE_CLASS_CATALOG]

    def build_company_knowledge_seed_pages(
        self,
        profile: str,
        *,
        space_key: str | None,
        normalize_space_key: NormalizeSpaceKeyFn,
        space_slug: SpaceSlugFn,
    ) -> list[dict[str, str]]:
        normalized_profile = str(profile or "").strip().lower() or "standard"
        space = normalize_space_key(space_key or "") or self.default_space_for_starter_profile(normalized_profile)
        pack_key = "generic_company"
        if normalized_profile == "logistics_ops":
            pack_key = "logistics_company"
        pages = _COMPANY_KNOWLEDGE_PACKS.get(pack_key) or _COMPANY_KNOWLEDGE_PACKS["generic_company"]
        return [
            {
                "title": str(item["title"]),
                "slug": space_slug(space, str(item["slug_leaf"])),
                "page_type": str(item["page_type"]),
                "markdown": str(item["markdown"]),
            }
            for item in pages
        ]

    def build_first_run_starter_pages(
        self,
        profile: str,
        *,
        space_key: str | None,
        include_decisions_log: bool,
        normalize_space_key: NormalizeSpaceKeyFn,
        space_slug: SpaceSlugFn,
        build_decisions_log_seed_page: BuildDecisionsLogSeedPageFn,
    ) -> list[dict[str, str]]:
        normalized_profile = str(profile or "").strip().lower() or "standard"
        space = normalize_space_key(space_key or "") or self.default_space_for_starter_profile(normalized_profile)
        pages: list[dict[str, str]] = [
            {
                "title": "Agent Profile",
                "slug": space_slug(space, "agent-profile"),
                "page_type": "agent_profile",
                "markdown": (
                    "# Agent Profile\n\n"
                    "## Mission\n"
                    "- What this agent is responsible for.\n\n"
                    "## Inputs\n"
                    "- Systems, queues, or channels the agent reads.\n\n"
                    "## Tools\n"
                    "- Tools/API integrations used in execution.\n\n"
                    "## Escalation\n"
                    "- Conditions that require human review.\n"
                ),
            },
            {
                "title": "Data Map",
                "slug": space_slug(space, "data-map"),
                "page_type": "data_map",
                "markdown": (
                    "# Data Map\n\n"
                    "## Sources of Truth\n"
                    "- Core systems and ownership.\n\n"
                    "## Operational Signals\n"
                    "- Which signals are durable knowledge vs runtime noise.\n\n"
                    "## Sync Contracts\n"
                    "- Connector cadence, cursor strategy, and replay guarantees.\n"
                ),
            },
            {
                "title": "Operational Runbook",
                "slug": space_slug(space, "operational-runbook"),
                "page_type": "runbook",
                "markdown": (
                    "# Operational Runbook\n\n"
                    "## If/Then Procedures\n"
                    "- If condition X happens, do action Y.\n\n"
                    "## Incident Escalation\n"
                    "- Owner, SLA, and communication channel.\n\n"
                    "## Known Exceptions\n"
                    "- Approved exceptions and expiration dates.\n"
                ),
            },
        ]
        if normalized_profile == "support_ops":
            pages.append(
                {
                    "title": "Support Escalation Matrix",
                    "slug": space_slug(space, "support-escalation-matrix"),
                    "page_type": "runbook",
                    "markdown": (
                        "# Support Escalation Matrix\n\n"
                        "## Triage Levels\n"
                        "- P1/P2/P3 definitions and handling windows.\n\n"
                        "## Routing Rules\n"
                        "- Which queue and owner for each issue type.\n\n"
                        "## Customer Communication\n"
                        "- Message templates and update cadence.\n"
                    ),
                }
            )
        if normalized_profile == "logistics_ops":
            pages.append(
                {
                    "title": "Dispatch Escalation Policy",
                    "slug": space_slug(space, "dispatch-escalation-policy"),
                    "page_type": "policy",
                    "markdown": (
                        "# Dispatch Escalation Policy\n\n"
                        "## Trigger Conditions\n"
                        "- Late pickup, access failure, or route dead-end.\n\n"
                        "## Required Actions\n"
                        "- Notify dispatch channel, update ETA, and create incident task.\n"
                    ),
                }
            )
        if normalized_profile == "sales_ops":
            pages.append(
                {
                    "title": "Deal Stage Playbook",
                    "slug": space_slug(space, "deal-stage-playbook"),
                    "page_type": "runbook",
                    "markdown": (
                        "# Deal Stage Playbook\n\n"
                        "## Qualification\n"
                        "- Mandatory checks before stage transition.\n\n"
                        "## Handoff\n"
                        "- Required context for support/onboarding transfer.\n"
                    ),
                }
            )
        if normalized_profile == "compliance_ops":
            pages.append(
                {
                    "title": "Compliance Control Map",
                    "slug": space_slug(space, "compliance-control-map"),
                    "page_type": "policy",
                    "markdown": (
                        "# Compliance Control Map\n\n"
                        "## Control Catalog\n"
                        "- Controls, owners, and evidence sources.\n\n"
                        "## Audit Trail\n"
                        "- Review cadence and exception workflow.\n"
                    ),
                }
            )
        if normalized_profile in {"logistics_ops", "ai_employee_org"}:
            pages.extend(
                self.build_company_knowledge_seed_pages(
                    normalized_profile,
                    space_key=space,
                    normalize_space_key=normalize_space_key,
                    space_slug=space_slug,
                )
            )
        if normalized_profile == "ai_employee_org":
            pages.extend(
                [
                    {
                        "title": "Tool Catalog",
                        "slug": space_slug(space, "tool-catalog"),
                        "page_type": "operations",
                        "markdown": (
                            "# Tool Catalog\n\n"
                            "## Registered Tools\n"
                            "- Tool name, purpose, and owning agent.\n\n"
                            "## Guardrails\n"
                            "- Approval boundaries, rate limits, and unsafe actions.\n\n"
                            "## Failure Modes\n"
                            "- Known failure cases and recovery workflow.\n"
                        ),
                    },
                    {
                        "title": "Scheduled Tasks",
                        "slug": space_slug(space, "scheduled-tasks"),
                        "page_type": "operations",
                        "markdown": (
                            "# Scheduled Tasks\n\n"
                            "## Cron / Automations\n"
                            "- Recurring jobs, trigger cadence, and owning agent.\n\n"
                            "## Output Contracts\n"
                            "- Which pages, tasks, or systems each automation updates.\n\n"
                            "## Escalation\n"
                            "- What to do if the scheduled task misses SLA.\n"
                        ),
                    },
                    {
                        "title": "Human-in-the-Loop Rules",
                        "slug": space_slug(space, "human-in-the-loop-rules"),
                        "page_type": "policy",
                        "markdown": (
                            "# Human-in-the-Loop Rules\n\n"
                            "## Approval Boundaries\n"
                            "- Which actions require explicit human approval.\n\n"
                            "## Escalation Triggers\n"
                            "- Risk, ambiguity, or policy conditions that force handoff.\n\n"
                            "## Override Logging\n"
                            "- How human overrides are recorded and reused.\n"
                        ),
                    },
                    {
                        "title": "Integrations Map",
                        "slug": space_slug(space, "integrations-map"),
                        "page_type": "operations",
                        "markdown": (
                            "# Integrations Map\n\n"
                            "## Connected Systems\n"
                            "- APIs, queues, docs, databases, and external services.\n\n"
                            "## Data Flow\n"
                            "- Which agent reads/writes each integration.\n\n"
                            "## Reliability Notes\n"
                            "- Freshness, fallback, and outage behavior.\n"
                        ),
                    },
                    {
                        "title": "Escalation Rules",
                        "slug": space_slug(space, "escalation-rules"),
                        "page_type": "policy",
                        "markdown": (
                            "# Escalation Rules\n\n"
                            "## Trigger Conditions\n"
                            "- When agents must escalate instead of acting autonomously.\n\n"
                            "## Owners & Channels\n"
                            "- Who gets paged and where.\n\n"
                            "## Resolution Expectations\n"
                            "- SLA, rollback, and follow-up capture requirements.\n"
                        ),
                    },
                ]
            )
        if include_decisions_log:
            pages.append(build_decisions_log_seed_page(space))
        deduped: list[dict[str, str]] = []
        seen_slugs: set[str] = set()
        for item in pages:
            slug = str(item.get("slug") or "").strip().lower()
            if not slug or slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            deduped.append(item)
        return deduped

    def build_role_template_pages(
        self,
        template_key: str,
        *,
        space_key: str | None,
        normalize_space_key: NormalizeSpaceKeyFn,
        space_slug: SpaceSlugFn,
    ) -> list[dict[str, str]]:
        normalized_key = str(template_key or "").strip().lower()
        template = next((item for item in _WIKI_SPACE_TEMPLATE_CATALOG if str(item.get("template_key") or "").strip().lower() == normalized_key), {})
        space = normalize_space_key(space_key or "") or normalize_space_key(template.get("default_space_key") or "") or "operations"
        if normalized_key == "support_ops":
            return [
                {
                    "title": "Ticket Triage Playbook",
                    "slug": space_slug(space, "ticket-triage-playbook"),
                    "page_type": "runbook",
                    "markdown": "# Ticket Triage Playbook\n\n## Intake\n- Capture issue class, severity, and impact.\n\n## Decision\n- Route by SLA and ownership matrix.\n",
                },
                {
                    "title": "Support Escalation Rules",
                    "slug": space_slug(space, "support-escalation-rules"),
                    "page_type": "policy",
                    "markdown": "# Support Escalation Rules\n\n## Escalate When\n- SLA risk or repeated customer impact.\n\n## Notify\n- On-call + owner channel with incident reference.\n",
                },
                {
                    "title": "Customer Communication Standard",
                    "slug": space_slug(space, "customer-communication-standard"),
                    "page_type": "policy",
                    "markdown": "# Customer Communication Standard\n\n## Cadence\n- Provide periodic updates by severity level.\n\n## Message Quality\n- Include impact, ETA, and next checkpoint.\n",
                },
            ]
        if normalized_key == "logistics_ops":
            return [
                {
                    "title": "Dispatch Decision Runbook",
                    "slug": space_slug(space, "dispatch-decision-runbook"),
                    "page_type": "runbook",
                    "markdown": "# Dispatch Decision Runbook\n\n## Route Validation\n- Validate access constraints and fallback routes.\n\n## Escalation\n- Open incident when route safety or SLA is at risk.\n",
                },
                {
                    "title": "Warehouse Exception Flow",
                    "slug": space_slug(space, "warehouse-exception-flow"),
                    "page_type": "runbook",
                    "markdown": "# Warehouse Exception Flow\n\n## Exceptions\n- Quarantine, ramp outage, stock mismatch.\n\n## Required Actions\n- Re-route, notify, and record mitigation.\n",
                },
                {
                    "title": "Delivery SLA Escalation",
                    "slug": space_slug(space, "delivery-sla-escalation"),
                    "page_type": "policy",
                    "markdown": "# Delivery SLA Escalation\n\n## Trigger\n- ETA drift above agreed threshold.\n\n## Action\n- Notify owner, customer, and dispatch channel.\n",
                },
            ]
        if normalized_key == "sales_ops":
            return [
                {
                    "title": "Lead Qualification Policy",
                    "slug": space_slug(space, "lead-qualification-policy"),
                    "page_type": "policy",
                    "markdown": "# Lead Qualification Policy\n\n## Required Signals\n- Budget, timeline, stakeholder readiness.\n",
                },
                {
                    "title": "Deal Stage Playbook",
                    "slug": space_slug(space, "deal-stage-playbook"),
                    "page_type": "runbook",
                    "markdown": "# Deal Stage Playbook\n\n## Stage Gates\n- Exit criteria and next action for each stage.\n",
                },
                {
                    "title": "Sales-to-Support Handoff",
                    "slug": space_slug(space, "sales-to-support-handoff"),
                    "page_type": "runbook",
                    "markdown": "# Sales-to-Support Handoff\n\n## Required Context\n- Contract scope, commitments, and success criteria.\n",
                },
            ]
        if normalized_key == "ai_employee_org":
            return [
                {
                    "title": "Agent Directory Index",
                    "slug": space_slug(space, "agent-directory-index"),
                    "page_type": "agent_profile",
                    "markdown": (
                        "# Agent Directory Index\n\n"
                        "## Agent Roster\n"
                        "- Each connected agent, role, status, and owning team.\n\n"
                        "## Capability Coverage\n"
                        "- Which workstreams are automated, assisted, or human-only.\n\n"
                        "## Handoff Topology\n"
                        "- Where agents hand off to other agents or humans.\n"
                    ),
                },
                {
                    "title": "Tool Catalog",
                    "slug": space_slug(space, "tool-catalog"),
                    "page_type": "operations",
                    "markdown": (
                        "# Tool Catalog\n\n"
                        "## Registered Tools\n"
                        "- Tool, owner, purpose, and safety boundary.\n\n"
                        "## Guardrails\n"
                        "- Rate limits, approval rules, and rollback path.\n"
                    ),
                },
                {
                    "title": "Scheduled Tasks",
                    "slug": space_slug(space, "scheduled-tasks"),
                    "page_type": "operations",
                    "markdown": (
                        "# Scheduled Tasks\n\n"
                        "## Automation Calendar\n"
                        "- Recurring jobs, cadence, and owning agent.\n\n"
                        "## Failure Handling\n"
                        "- SLA, retry, and escalation path.\n"
                    ),
                },
                {
                    "title": "Human-in-the-Loop Rules",
                    "slug": space_slug(space, "human-in-the-loop-rules"),
                    "page_type": "policy",
                    "markdown": (
                        "# Human-in-the-Loop Rules\n\n"
                        "## Approval Boundaries\n"
                        "- Which actions require human sign-off.\n\n"
                        "## Override Logging\n"
                        "- How overrides are captured and fed back into Synapse.\n"
                    ),
                },
                {
                    "title": "Integrations Map",
                    "slug": space_slug(space, "integrations-map"),
                    "page_type": "operations",
                    "markdown": (
                        "# Integrations Map\n\n"
                        "## Systems\n"
                        "- APIs, DBs, docs, queues, and external SaaS.\n\n"
                        "## Data Flow\n"
                        "- Which agents consume or mutate which integration.\n"
                    ),
                },
            ]
        return [
            {
                "title": "Compliance Control Catalog",
                "slug": space_slug(space, "compliance-control-catalog"),
                "page_type": "policy",
                "markdown": "# Compliance Control Catalog\n\n## Controls\n- Control owner, objective, and evidence source.\n",
            },
            {
                "title": "Incident Reporting Procedure",
                "slug": space_slug(space, "incident-reporting-procedure"),
                "page_type": "runbook",
                "markdown": "# Incident Reporting Procedure\n\n## Report Timeline\n- Initial report and update cadence by severity.\n",
            },
            {
                "title": "Audit Evidence Checklist",
                "slug": space_slug(space, "audit-evidence-checklist"),
                "page_type": "runbook",
                "markdown": "# Audit Evidence Checklist\n\n## Evidence Readiness\n- Owner, retention, and validation cadence.\n",
            },
        ]

    def business_profiles_catalog(self) -> list[dict[str, Any]]:
        return [dict(item) for item in _BUSINESS_PROFILES_CATALOG]

    def resolve_business_profile(self, key: str | None) -> dict[str, Any] | None:
        normalized = str(key or "").strip().lower()
        if not normalized:
            return None
        for item in _BUSINESS_PROFILES_CATALOG:
            if str(item.get("key") or "").strip().lower() == normalized:
                return dict(item)
        return None


class LogisticsOpsSynthesisPack(GenericOpsSynthesisPack):
    key = "logistics_ops"

    def _process_playbook_tokens(
        self,
        playbook: dict[str, Any],
        *,
        normalize_statement_text: NormalizeStatementTextFn,
    ) -> str:
        return normalize_statement_text(
            " ".join(
                [
                    str(playbook.get("title") or ""),
                    str(playbook.get("trigger") or ""),
                    str(playbook.get("action") or ""),
                    str(playbook.get("output") or ""),
                ]
            )
        )

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
        elif "fleet" in tokens and "sync" in tokens:
            semantics.update(
                {
                    "purpose": "Synchronize fleet state from the external provider so operations can act on current vehicle availability and status.",
                    "trigger": f"Recurring fleet sync runs on `{semantics['schedule_text']}` and refreshes the current fleet picture.",
                    "inputs": list(dict.fromkeys([*source_hints, "fleet status feed", "provider state", "vehicle availability"]))[:6],
                    "steps": [
                        "Load the latest fleet-provider state and current operational fleet snapshot.",
                        "Apply the synchronization routine for vehicle status, availability, or metadata changes.",
                        "Detect mismatches, stale provider data, or failed writes before declaring the sync complete.",
                        "Record synchronization outcome and unresolved deltas for operator follow-up.",
                    ],
                    "outputs": "Fleet state synchronized with provider changes and mismatches explicitly recorded.",
                    "verification": [
                        "Confirm the synchronized fleet view matches the current provider state.",
                        "Verify stale or failed fleet updates were surfaced instead of silently ignored.",
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

    def refine_process_playbook(
        self,
        *,
        playbook: dict[str, Any],
        source_kind: str,
        normalize_statement_text: NormalizeStatementTextFn,
    ) -> dict[str, Any]:
        del source_kind
        refined = dict(playbook)
        tokens = self._process_playbook_tokens(refined, normalize_statement_text=normalize_statement_text)
        inputs = [str(v).strip() for v in (refined.get("inputs") or []) if str(v).strip()]
        tools = [str(v).strip() for v in (refined.get("tools") or []) if str(v).strip()]
        artifacts = [str(v).strip() for v in (refined.get("artifacts") or []) if str(v).strip()]
        evidence = [str(v).strip() for v in (refined.get("evidence") or []) if str(v).strip()]

        if "incident" in tokens and "monitor" in tokens:
            refined.update(
                {
                    "purpose": "Continuously watch live logistics risk signals and escalate emerging incidents before they affect dispatch, SLA, or customer communication.",
                    "steps": [
                        "Load the latest incident-like signals, unresolved blockers, and active logistics alerts.",
                        "Check whether any active incident crossed recurrence, severity, or response thresholds.",
                        "Notify the configured authority and update the incident state when escalation is required.",
                        "Record unresolved blockers and the explicit next owner before the next monitor cycle.",
                    ],
                    "output": "Updated incident state with explicit escalation notes, next owner, and remaining blockers.",
                    "verification": [
                        "Confirm whether incident status changed, stayed stable, or intentionally remained under watch.",
                        "Verify escalation routing matches the configured authority and standing-order mode.",
                    ],
                }
            )
        elif "driver" in tokens and "economy" in tokens:
            refined.update(
                {
                    "purpose": "Refresh the recurring driver economy workflow so operations can review cost and performance drift on a stable cadence.",
                    "inputs": list(dict.fromkeys([*inputs, "driver economy metrics", "shift performance context"]))[:6],
                    "steps": [
                        "Collect the latest driver economy metrics and supporting shift context for the reporting window.",
                        "Rebuild or refresh the target report or sheet used by operations.",
                        "Highlight anomalies, missing inputs, or unusual cost drift before downstream use.",
                        "Publish the refreshed report and log any exception that needs follow-up.",
                    ],
                    "output": "Updated driver economy report or sheet ready for operations or finance review.",
                    "verification": [
                        "Confirm the report window and source freshness match the intended daily or shift cycle.",
                        "Verify anomalies and missing inputs were surfaced explicitly instead of buried in generic output.",
                    ],
                }
            )
        elif "daily" in tokens and "report" in tokens:
            refined.update(
                {
                    "purpose": "Produce the recurring logistics operating digest with blockers, escalations, and current-day movement.",
                    "steps": [
                        "Collect the latest activity metrics, blockers, escalations, and durable changes for the reporting window.",
                        "Assemble the report in the expected operational format or destination system.",
                        "Highlight missed thresholds, open incidents, and human follow-ups that still need action.",
                        "Publish the report and link follow-up tasks or wiki updates where needed.",
                    ],
                    "output": "Published daily report with current blockers, escalations, and activity summary.",
                    "verification": [
                        "Confirm the report covers the intended audience and reporting window.",
                        "Verify important blockers and escalations were surfaced directly, not diluted into generic prose.",
                    ],
                }
            )
        elif "fleet" in tokens and "sync" in tokens:
            refined.update(
                {
                    "purpose": "Synchronize fleet-provider state so dispatch and operations use current vehicle availability, readiness, and status.",
                    "inputs": list(dict.fromkeys([*inputs, "fleet status feed", "provider state", "vehicle availability"]))[:6],
                    "steps": [
                        "Load the latest fleet-provider snapshot and the current internal fleet state.",
                        "Apply the synchronization routine for vehicle availability, status, and metadata changes.",
                        "Detect mismatches, stale provider state, or failed writes before closing the workflow.",
                        "Record synchronization outcome and unresolved deltas for operator follow-up.",
                    ],
                    "output": "Fleet state synchronized with provider changes and mismatches explicitly recorded.",
                    "verification": [
                        "Confirm the synchronized fleet view matches the latest provider state.",
                        "Verify failed or stale fleet updates were surfaced instead of silently ignored.",
                    ],
                }
            )
        elif ("cargo" in tokens and "sync" in tokens) or ("erp" in tokens and "sync" in tokens):
            refined.update(
                {
                    "purpose": "Synchronize ERP or cargo-facing notes so downstream logistics decisions run on current operational state.",
                    "inputs": list(dict.fromkeys([*inputs, "ERP notes", "cargo state", "dispatch context"]))[:6],
                    "steps": [
                        "Load the latest cargo, ERP-facing, and dispatch-side state for the workflow window.",
                        "Apply the synchronization routine for notes, status, or derived fields.",
                        "Detect mismatches or failed writes before declaring the sync complete.",
                        "Record synchronization outcome and unresolved deltas for follow-up.",
                    ],
                    "output": "ERP and cargo notes synchronized with mismatches explicitly recorded.",
                    "verification": [
                        "Confirm the target ERP or cargo system reflects the newly synchronized state.",
                        "Check that failed or partial updates were escalated instead of silently ignored.",
                    ],
                }
            )
        elif "document" in tokens and ("shift" in tokens or "readiness" in tokens):
            refined.update(
                {
                    "purpose": "Check driver or shift document readiness before dispatch or operational handoff starts.",
                    "inputs": list(dict.fromkeys([*inputs, "driver documents", "shift roster", "readiness checklist"]))[:6],
                    "steps": [
                        "Load the latest driver or shift document set and the readiness checklist.",
                        "Detect missing, expired, or inconsistent documents before the shift proceeds.",
                        "Escalate unresolved readiness blockers to the configured authority.",
                        "Record the final readiness state and any missing artifacts for the next operator.",
                    ],
                    "output": "Document readiness state updated with explicit blockers and escalation notes.",
                    "verification": [
                        "Confirm every required document is either present or escalated.",
                        "Verify the final readiness note is visible to the next operator or agent.",
                    ],
                }
            )
        elif "comment" in tokens and ("signal" in tokens or "learning" in tokens):
            refined.update(
                {
                    "purpose": "Distill recurring logistics comments into reusable signals that improve future playbooks and durable knowledge.",
                    "steps": [
                        "Review fresh operational comments and isolate recurring patterns from one-off chatter.",
                        "Separate reusable logistics signals from transactional or ephemeral updates.",
                        "Link high-signal findings to the affected process, source, or decision surface.",
                        "Write back the synthesized findings for wiki promotion or human review.",
                    ],
                    "output": "Structured learning signals ready for knowledge promotion and follow-up review.",
                }
            )
        refined["tools"] = list(dict.fromkeys([*tools]))[:6]
        refined["artifacts"] = list(dict.fromkeys([*artifacts]))[:6]
        refined["evidence"] = list(dict.fromkeys([*evidence]))[:6]
        return refined

    def build_company_context_extensions(
        self,
        *,
        matrix_rows: list[dict[str, Any]] | None,
        source_counts: list[tuple[str, int]] | None,
        claims_rollup: list[tuple[str, int]] | None,
        normalize_statement_text: NormalizeStatementTextFn,
    ) -> dict[str, Any]:
        workflow_counts: dict[str, int] = {}
        entity_buckets = {
            "Driver": ("driver",),
            "Route": ("route", "routing"),
            "Shift": ("shift", "readiness"),
            "Order / Task": ("order", "task", "assignment", "snapshot"),
            "Document": ("document", "docs"),
            "Incident": ("incident", "failure", "escalat", "access"),
            "Fleet Provider": ("fleet", "provider", "delimobil"),
            "ERP Object": ("erp",),
            "Economics Report": ("econom", "report"),
        }
        entity_counts: dict[str, int] = {key: 0 for key in entity_buckets}
        exception_counts: dict[str, int] = {
            "Readiness gap": 0,
            "Delivery failure": 0,
            "Access / route dead-end": 0,
            "Stale or conflicting source data": 0,
        }

        def _bump_entity_signals(value: Any, weight: int = 1) -> None:
            text = normalize_statement_text(str(value or ""))
            if not text:
                return
            for label, keywords in entity_buckets.items():
                if any(keyword in text for keyword in keywords):
                    entity_counts[label] = int(entity_counts.get(label, 0)) + int(weight)

            if "readiness" in text or ("shift" in text and "ready" in text):
                exception_counts["Readiness gap"] = int(exception_counts["Readiness gap"]) + int(weight)
            if "failure" in text or "incident" in text:
                exception_counts["Delivery failure"] = int(exception_counts["Delivery failure"]) + int(weight)
            if "access" in text or ("route" in text and "dead" in text):
                exception_counts["Access / route dead-end"] = int(exception_counts["Access / route dead-end"]) + int(weight)
            if "stale" in text or "conflict" in text or "derived" in text:
                exception_counts["Stale or conflicting source data"] = int(exception_counts["Stale or conflicting source data"]) + int(weight)

        for item in matrix_rows or []:
            if not isinstance(item, dict):
                continue
            for value in [*(item.get("standing_orders") or []), *(item.get("scheduled_tasks") or [])]:
                text = str(value or "").strip()
                if not text:
                    continue
                normalized = normalize_statement_text(text)
                label = re.sub(r"\s+", " ", text.replace("_", " ")).strip()
                if not normalized or not label:
                    continue
                workflow_counts[label] = int(workflow_counts.get(label, 0)) + 1
                _bump_entity_signals(label, weight=2)
            for value in [
                *(item.get("responsibilities") or []),
                *(item.get("scenario_examples") or []),
                *(item.get("source_bindings") or []),
                *(item.get("data_sources") or []),
            ]:
                _bump_entity_signals(value)
        workflow_signals = [
            {"label": name, "count": total}
            for name, total in sorted(workflow_counts.items(), key=lambda item: (-item[1], item[0].lower()))[:6]
        ]
        for category, total in claims_rollup or []:
            _bump_entity_signals(category, weight=max(1, int(total or 0)))

        entity_signals = [
            {"label": label, "count": total}
            for label, total in sorted(entity_counts.items(), key=lambda item: (-item[1], item[0].lower()))
            if int(total) > 0
        ][:8]
        process_signals = [
            {
                "label": str(item.get("label") or ""),
                "count": int(item.get("count") or 0),
                "why": "Recurring workflow observed in scheduled tasks or standing orders.",
            }
            for item in workflow_signals[:6]
        ]

        source_total = sum(int(total or 0) for _, total in (source_counts or []))
        domain_total = sum(int(total or 0) for _, total in (claims_rollup or []))
        trust_signals: list[dict[str, Any]] = []
        for source_type, total in source_counts or []:
            normalized_source = normalize_statement_text(str(source_type or ""))
            label = _humanize_signal_label(str(source_type or "unknown"))
            trust_note = "Operational source stream."
            if "postgres" in normalized_source or "erp" in normalized_source:
                trust_note = "Likely canonical operational record; prefer for routes, tasks, and current state."
            elif "sheet" in normalized_source:
                trust_note = "Often a derived or operator-maintained view; validate against canonical systems when conflicts appear."
            elif "memory" in normalized_source or "kb" in normalized_source:
                trust_note = "Knowledge or summary layer; useful for context, but should not silently override live operational state."
            elif "api" in normalized_source or "provider" in normalized_source:
                trust_note = "Provider or service feed; treat freshness and outage handling explicitly."
            trust_signals.append({"label": label, "count": int(total or 0), "trust_note": trust_note})
        trust_signals = sorted(trust_signals, key=lambda item: (-int(item.get("count") or 0), str(item.get("label") or "").lower()))[:6]

        exception_signals = [
            {"label": label, "count": total}
            for label, total in sorted(exception_counts.items(), key=lambda item: (-item[1], item[0].lower()))
            if int(total) > 0
        ][:6]
        candidate_canon_blocks: list[dict[str, Any]] = []

        top_entities = [str(item.get("label") or "").strip() for item in entity_signals[:3] if str(item.get("label") or "").strip()]
        if top_entities:
            candidate_canon_blocks.append(
                {
                    "block_type": "entity_overview",
                    "knowledge_state": "candidate",
                    "confidence": "medium",
                    "summary": f"Current logistics memory centers on {', '.join(top_entities)} as the main business entities.",
                    "evidence_basis": "Repeated mentions across scheduled workflows, responsibilities, and claim rollups.",
                }
            )

        top_processes = [str(item.get("label") or "").strip() for item in process_signals[:3] if str(item.get("label") or "").strip()]
        if top_processes:
            cadence = "daily operating cadence" if any("daily" in normalize_statement_text(item) for item in top_processes) else "recurring operational workflow"
            candidate_canon_blocks.append(
                {
                    "block_type": "process_sop_candidate",
                    "knowledge_state": "candidate",
                    "confidence": "medium",
                    "summary": f"The current {cadence} appears to revolve around {', '.join(top_processes)}.",
                    "evidence_basis": "Observed in standing orders and scheduled tasks across the runtime matrix.",
                }
            )

        if trust_signals:
            canonical_sources = [str(item.get("label") or "").strip() for item in trust_signals if "canonical operational record" in normalize_statement_text(str(item.get("trust_note") or ""))]
            derived_sources = [str(item.get("label") or "").strip() for item in trust_signals if "derived" in normalize_statement_text(str(item.get("trust_note") or ""))]
            if canonical_sources or derived_sources:
                summary_parts: list[str] = []
                if canonical_sources:
                    summary_parts.append(f"prefer {', '.join(canonical_sources[:2])} for live operational state")
                if derived_sources:
                    summary_parts.append(f"treat {', '.join(derived_sources[:2])} as derived/operator-maintained views during conflicts")
                candidate_canon_blocks.append(
                    {
                        "block_type": "source_of_truth_rule",
                        "knowledge_state": "candidate",
                        "confidence": "medium",
                        "summary": f"Trust rule candidate: {'; '.join(summary_parts)}.",
                        "evidence_basis": "Inferred from connected source classes and source-trust heuristics.",
                    }
                )

        top_exceptions = [str(item.get("label") or "").strip() for item in exception_signals[:3] if str(item.get("label") or "").strip()]
        if top_exceptions:
            candidate_canon_blocks.append(
                {
                    "block_type": "known_exception",
                    "knowledge_state": "candidate",
                    "confidence": "low",
                    "summary": f"Recurring operational exceptions likely include {', '.join(top_exceptions)}.",
                    "evidence_basis": "Pattern counts derived from workflow, responsibility, and claim language.",
                }
            )

        if claims_rollup:
            top_claims = [str(category or "").strip().replace("_", " ") for category, _ in claims_rollup[:3] if str(category or "").strip()]
            if top_claims:
                candidate_canon_blocks.append(
                    {
                        "block_type": "working_heuristic",
                        "knowledge_state": "candidate",
                        "confidence": "low",
                        "summary": f"Company memory is repeatedly surfacing heuristics around {', '.join(top_claims)}.",
                        "evidence_basis": "Repeated claim categories observed in current knowledge rollups.",
                    }
                )
        snapshot_notes = [
            f"Recurring workflows observed: {len(workflow_signals)}.",
            f"Connected source streams contributing to logistics knowledge: {source_total}.",
            f"Operational domain signals currently tracked: {domain_total}.",
        ]
        return {
            "snapshot_notes": snapshot_notes,
            "workflow_signals": workflow_signals,
            "entity_signals": entity_signals,
            "process_signals": process_signals,
            "trust_signals": trust_signals,
            "exception_signals": exception_signals,
            "candidate_canon_blocks": candidate_canon_blocks,
            "principles": [
                "Recurring dispatch, incident, and reporting workflows should be captured as reusable SOPs instead of staying trapped inside runtime chatter.",
                "Source freshness and authority matter: logistics actions should prefer the latest operational source of truth before acting.",
                "Escalation should remain explicit whenever route, SLA, access, or customer-impact risk crosses the approved boundary.",
            ],
        }


class SupportOpsSynthesisPack(GenericOpsSynthesisPack):
    key = "support_ops"

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
        if "ticket" in tokens or "incident" in tokens or "escalat" in tokens:
            semantics.update(
                {
                    "purpose": "Run a recurring support workflow that keeps queue routing, escalation, and customer communication consistent.",
                    "trigger": f"Recurring support workflow runs on `{semantics['schedule_text']}` and reviews open queue or incident signals.",
                    "steps": [
                        "Load the latest ticket, queue, or escalation context for the workflow window.",
                        "Route or escalate work according to the declared support policy and queue ownership.",
                        "Record customer-visible next action, blocking dependency, or required handoff.",
                        "Write back the updated support state for the next operator or automation cycle.",
                    ],
                    "outputs": "Support workflow state refreshed with owner, escalation path, and customer-visible next step.",
                }
            )
        return semantics

    def refine_process_playbook(
        self,
        *,
        playbook: dict[str, Any],
        source_kind: str,
        normalize_statement_text: NormalizeStatementTextFn,
    ) -> dict[str, Any]:
        del source_kind
        refined = dict(playbook)
        tokens = normalize_statement_text(
            " ".join(
                [
                    str(refined.get("title") or ""),
                    str(refined.get("trigger") or ""),
                    str(refined.get("action") or ""),
                    str(refined.get("output") or ""),
                ]
            )
        )
        if "ticket" in tokens or "incident" in tokens or "escalat" in tokens:
            refined.update(
                {
                    "purpose": "Turn recurring ticket or escalation patterns into reusable support operating procedures.",
                    "steps": [
                        "Capture the incoming issue, severity, affected customer scope, and current SLA posture.",
                        "Route the work to the right queue, owner, or escalation path based on the declared support rules.",
                        "Record the customer-visible next step and any blocking dependencies before handoff.",
                        "Close the loop with an explicit resolution or escalation note for the next operator.",
                    ],
                    "output": "Ticket or escalation state updated with owner, SLA posture, and customer-visible next action.",
                    "verification": [
                        "Confirm routing matched the intended queue or escalation policy.",
                        "Verify the customer-visible status and next checkpoint were recorded clearly.",
                    ],
                }
            )
        elif "daily" in tokens and "report" in tokens:
            refined.update(
                {
                    "purpose": "Produce a recurring support operations digest with queue pressure, blockers, escalations, and customer-impact signals.",
                    "steps": [
                        "Collect queue metrics, blocker counts, escalation summaries, and unresolved customer-impact signals.",
                        "Assemble the support operating digest for the intended review audience.",
                        "Highlight SLA breaches, at-risk tickets, and repeated failure patterns that need human action.",
                        "Publish the digest and attach the expected follow-up path.",
                    ],
                    "output": "Published support operations digest with queue health, escalations, and follow-up actions.",
                }
            )
        return refined

    def build_company_context_extensions(
        self,
        *,
        matrix_rows: list[dict[str, Any]] | None,
        source_counts: list[tuple[str, int]] | None,
        claims_rollup: list[tuple[str, int]] | None,
        normalize_statement_text: NormalizeStatementTextFn,
    ) -> dict[str, Any]:
        del normalize_statement_text
        queue_signals = 0
        escalation_signals = 0
        for item in matrix_rows or []:
            if not isinstance(item, dict):
                continue
            queue_signals += len([str(v).strip() for v in (item.get("standing_orders") or []) if str(v).strip()])
            escalation_signals += len([str(v).strip() for v in (item.get("escalation_rules") or []) if str(v).strip()])
        return {
            "snapshot_notes": [
                f"Queue-oriented recurring workflows observed: {queue_signals}.",
                f"Explicit escalation boundaries observed: {escalation_signals}.",
            ],
            "workflow_signals": [],
            "principles": [
                "Customer-facing escalations should stay explicit, time-bounded, and tied to queue ownership.",
                "Support workflows should prefer reusable routing rules over one-off operator memory.",
                "Resolution notes should be written so the next human or agent can resume without hidden context.",
            ],
        }

    def build_capability_profile_extensions(
        self,
        *,
        matrix_rows: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        del matrix_rows
        return {
            "signal_bullets": [
                "Queue-routing, escalation, and customer communication patterns observed in recurring support workflows.",
                "Tool usage and handoff paths between frontline support, specialists, and human approvers.",
                "Data-source and SLA signals that decide when a case can stay autonomous vs must escalate.",
            ],
            "sparse_hint": "Support capability discovery is still sparse; sync queue ownership, escalation rules, and customer communication contracts to enrich this page.",
        }

    def build_tooling_map_extensions(
        self,
        *,
        matrix_rows: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        del matrix_rows
        return {
            "governance_bullets": [
                "Support tools should make queue ownership, SLA posture, and customer-visible next steps explicit.",
                "Escalation and customer messaging tools should respect approval or override boundaries when risk is high.",
                "Use this map to show which tool drives triage, escalation, and customer communication workflows.",
            ],
            "empty_hint": "Runtime support tool discovery pending",
        }


class SalesOpsSynthesisPack(GenericOpsSynthesisPack):
    key = "sales_ops"

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
        if "deal" in tokens or "qualification" in tokens or "handoff" in tokens or "revenue" in tokens:
            semantics.update(
                {
                    "purpose": "Run a recurring revenue-ops workflow that keeps qualification, stage movement, and handoffs explicit.",
                    "trigger": f"Recurring revenue-ops workflow runs on `{semantics['schedule_text']}` and reviews the current deal or handoff state.",
                    "steps": [
                        "Load the latest qualification, stage, or handoff context for the workflow window.",
                        "Check required criteria before changing ownership, stage, or downstream handoff status.",
                        "Surface blockers, missing context, or revenue-risk exceptions before advancing the workflow.",
                        "Write back the next stage decision or handoff package for the next owner.",
                    ],
                    "outputs": "Revenue workflow updated with explicit owner, next stage, and missing context signals.",
                }
            )
        return semantics

    def refine_process_playbook(
        self,
        *,
        playbook: dict[str, Any],
        source_kind: str,
        normalize_statement_text: NormalizeStatementTextFn,
    ) -> dict[str, Any]:
        del source_kind
        refined = dict(playbook)
        tokens = normalize_statement_text(
            " ".join(
                [
                    str(refined.get("title") or ""),
                    str(refined.get("trigger") or ""),
                    str(refined.get("action") or ""),
                    str(refined.get("output") or ""),
                ]
            )
        )
        if "deal" in tokens or "handoff" in tokens or "qualification" in tokens or "revenue" in tokens:
            refined.update(
                {
                    "purpose": "Convert recurring qualification, stage-management, and handoff work into reusable revenue operations SOPs.",
                    "steps": [
                        "Capture the current deal stage, owner, and any missing qualification signal.",
                        "Validate that the required stage criteria or handoff inputs are present before advancing.",
                        "Escalate exceptions such as missing stakeholders, unclear scope, or revenue-risk blockers.",
                        "Record the next stage decision or handoff package in a reusable way for the next operator.",
                    ],
                    "output": "Deal or handoff state updated with explicit next step, owner, and missing qualification gaps.",
                    "verification": [
                        "Confirm the stage transition or handoff matched the declared revenue-ops policy.",
                        "Verify missing context was surfaced before downstream teams inherited the workflow.",
                    ],
                }
            )
        elif "daily" in tokens and "report" in tokens:
            refined.update(
                {
                    "purpose": "Produce a recurring revenue-ops digest with pipeline movement, blockers, and handoff risk.",
                    "steps": [
                        "Collect the latest pipeline movement, qualification gaps, and pending handoff blockers.",
                        "Assemble the digest for sales, revenue operations, or success stakeholders.",
                        "Highlight stalled deals, at-risk handoffs, and missing data needed for stage progression.",
                        "Publish the digest and attach the next follow-up expectations.",
                    ],
                    "output": "Published revenue-ops digest with pipeline movement, handoff blockers, and next actions.",
                }
            )
        return refined

    def build_company_context_extensions(
        self,
        *,
        matrix_rows: list[dict[str, Any]] | None,
        source_counts: list[tuple[str, int]] | None,
        claims_rollup: list[tuple[str, int]] | None,
        normalize_statement_text: NormalizeStatementTextFn,
    ) -> dict[str, Any]:
        del source_counts, claims_rollup, normalize_statement_text
        handoff_signals = 0
        qualification_signals = 0
        for item in matrix_rows or []:
            if not isinstance(item, dict):
                continue
            handoff_signals += len([str(v).strip() for v in (item.get("standing_orders") or []) if "handoff" in str(v).lower()])
            qualification_signals += len([str(v).strip() for v in (item.get("responsibilities") or []) if str(v).strip()])
        return {
            "snapshot_notes": [
                f"Revenue handoff workflows observed: {handoff_signals}.",
                f"Qualification/capability signals observed: {qualification_signals}.",
            ],
            "workflow_signals": [],
            "principles": [
                "Qualification and stage changes should be explicit enough that downstream teams inherit clean context.",
                "Revenue handoffs should capture commitments, blockers, and owner transitions without hidden operator knowledge.",
                "Pipeline summaries should surface risk and missing context before they become customer-facing failures.",
            ],
        }

    def build_capability_profile_extensions(
        self,
        *,
        matrix_rows: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        del matrix_rows
        return {
            "signal_bullets": [
                "Qualification, stage progression, and handoff patterns observed in recurring revenue workflows.",
                "Tool usage across pipeline updates, handoff preparation, and downstream customer-success coordination.",
                "Data-source and approval signals that control when stage movement or ownership transfer is allowed.",
            ],
            "sparse_hint": "Revenue capability discovery is still sparse; sync stage policy, handoff contracts, and qualification rules to deepen this page.",
        }

    def build_tooling_map_extensions(
        self,
        *,
        matrix_rows: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        del matrix_rows
        return {
            "governance_bullets": [
                "Revenue tools should preserve clear ownership, stage criteria, and handoff readiness before advancing work.",
                "Qualification or pricing-sensitive actions should respect explicit approval or override boundaries.",
                "Use this map to show which tool drives qualification, pipeline movement, and customer handoff workflows.",
            ],
            "empty_hint": "Runtime revenue tool discovery pending",
        }


class ComplianceOpsSynthesisPack(GenericOpsSynthesisPack):
    key = "compliance_ops"

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
        if any(token in tokens for token in ("audit", "control", "evidence", "review", "policy", "compliance")):
            semantics.update(
                {
                    "purpose": "Run a recurring compliance workflow that keeps control evidence, review posture, and policy execution explicit.",
                    "trigger": f"Recurring compliance workflow runs on `{semantics['schedule_text']}` and reviews control or evidence state.",
                    "steps": [
                        "Load the latest control, review, or evidence state for the workflow window.",
                        "Validate that required artifacts, approvals, and control checks are present and current.",
                        "Escalate missing evidence, policy drift, or approval gaps before marking the workflow complete.",
                        "Record the resulting compliance state and next review obligation for the next operator or audit cycle.",
                    ],
                    "outputs": "Compliance workflow updated with explicit evidence posture, approval status, and next review checkpoint.",
                }
            )
        return semantics

    def refine_process_playbook(
        self,
        *,
        playbook: dict[str, Any],
        source_kind: str,
        normalize_statement_text: NormalizeStatementTextFn,
    ) -> dict[str, Any]:
        del source_kind
        refined = dict(playbook)
        tokens = normalize_statement_text(
            " ".join(
                [
                    str(refined.get("title") or ""),
                    str(refined.get("trigger") or ""),
                    str(refined.get("action") or ""),
                    str(refined.get("output") or ""),
                ]
            )
        )
        if any(token in tokens for token in ("audit", "control", "evidence", "review", "policy", "compliance")):
            refined.update(
                {
                    "purpose": "Convert recurring control, evidence, and policy-review work into reusable compliance operating procedures.",
                    "steps": [
                        "Capture the current control, evidence, or review state and identify the required artifact set.",
                        "Validate that policy expectations, approvals, and control checkpoints are satisfied before closure.",
                        "Escalate any missing evidence, policy drift, or unresolved review exception.",
                        "Record the resulting control posture and next review obligation for the next operator or auditor.",
                    ],
                    "output": "Compliance state updated with explicit evidence posture, approval status, and next review checkpoint.",
                    "verification": [
                        "Confirm the required evidence set is present, current, and attributable.",
                        "Verify that unresolved policy or approval gaps were escalated instead of silently accepted.",
                    ],
                }
            )
        return refined

    def build_company_context_extensions(
        self,
        *,
        matrix_rows: list[dict[str, Any]] | None,
        source_counts: list[tuple[str, int]] | None,
        claims_rollup: list[tuple[str, int]] | None,
        normalize_statement_text: NormalizeStatementTextFn,
    ) -> dict[str, Any]:
        del source_counts, claims_rollup, normalize_statement_text
        control_signals = 0
        review_signals = 0
        for item in matrix_rows or []:
            if not isinstance(item, dict):
                continue
            control_signals += len([str(v).strip() for v in (item.get("standing_orders") or []) if str(v).strip()])
            review_signals += len([str(v).strip() for v in (item.get("approval_rules") or []) if str(v).strip()])
        return {
            "snapshot_notes": [
                f"Control-oriented recurring workflows observed: {control_signals}.",
                f"Explicit approval/review boundaries observed: {review_signals}.",
            ],
            "workflow_signals": [],
            "principles": [
                "Control evidence and policy execution should remain attributable, reviewable, and easy to audit.",
                "Compliance workflows should escalate missing approvals or evidence rather than silently marking success.",
                "Shared operating context should make review cadence and control ownership explicit for the next operator or auditor.",
            ],
        }

    def build_capability_profile_extensions(
        self,
        *,
        matrix_rows: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        del matrix_rows
        return {
            "signal_bullets": [
                "Control, evidence, and policy-review workflows observed in recurring compliance operations.",
                "Tool usage across audit evidence collection, control execution, and approval routing.",
                "Approval and data-source signals that define when compliance actions can proceed autonomously vs require review.",
            ],
            "sparse_hint": "Compliance capability discovery is still sparse; sync control ownership, approval rules, and evidence contracts to deepen this page.",
        }

    def build_tooling_map_extensions(
        self,
        *,
        matrix_rows: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        del matrix_rows
        return {
            "governance_bullets": [
                "Compliance tools should preserve attributable evidence, approval state, and control ownership.",
                "Policy, review, or audit-sensitive actions should require explicit approval boundaries where appropriate.",
                "Use this map to show which tool drives evidence collection, control execution, and review workflows.",
            ],
            "empty_hint": "Runtime compliance tool discovery pending",
        }


_PACKS: dict[str, SynthesisPack] = {
    "generic_ops": GenericOpsSynthesisPack(),
    "logistics_ops": LogisticsOpsSynthesisPack(),
    "support_ops": SupportOpsSynthesisPack(),
    "sales_ops": SalesOpsSynthesisPack(),
    "compliance_ops": ComplianceOpsSynthesisPack(),
}


def get_synthesis_pack(key: str | None) -> SynthesisPack:
    normalized = str(key or "").strip().lower()
    return _PACKS.get(normalized) or _PACKS["generic_ops"]
