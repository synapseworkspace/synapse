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
        space_key: str | None,
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
    "support_company": [
        {
            "title": "How the Support Operation Works",
            "slug_leaf": "how-the-support-operation-works",
            "page_type": "process",
            "markdown": (
                "# How the Support Operation Works\n\n"
                "## Purpose\n"
                "- Explain the support operation in business language: queue ownership, escalation paths, customer communication, and success criteria.\n\n"
                "## Core Roles\n"
                "- Frontline support, specialists, incident managers, reviewers, and AI agents.\n\n"
                "## Core Loops\n"
                "- Queue triage, escalation handling, customer updates, and recurring support reporting.\n\n"
                "## Failure Modes\n"
                "- Hidden ownership, SLA drift, weak customer context, and unresolved escalations.\n"
            ),
        },
        {
            "title": "Support Glossary",
            "slug_leaf": "support-glossary",
            "page_type": "glossary_term",
            "markdown": (
                "# Support Glossary\n\n"
                "## Canonical Terms\n"
                "- Define queue, escalation, incident, SLA risk, resolution note, and customer-impact in company language.\n\n"
                "## Common Confusions\n"
                "- Record terms that frequently drift between ticket systems, internal notes, and operator chat.\n"
            ),
        },
        {
            "title": "Queue Ownership and Escalation",
            "slug_leaf": "queue-ownership-and-escalation",
            "page_type": "escalation_rule",
            "markdown": (
                "# Queue Ownership and Escalation\n\n"
                "## Queue Ownership\n"
                "- Which team owns which queue and what signals move work between them.\n\n"
                "## Escalation Rules\n"
                "- When frontline support can resolve, when specialists take over, and when a manager must intervene.\n"
            ),
        },
        {
            "title": "Customer Incidents and Communication",
            "slug_leaf": "customer-incidents-and-communication",
            "page_type": "process",
            "markdown": (
                "# Customer Incidents and Communication\n\n"
                "## Incident Rhythm\n"
                "- How support identifies a customer-impacting incident, updates customers, and closes the loop.\n\n"
                "## Communication Rules\n"
                "- What should always be recorded before handoff or escalation.\n"
            ),
        },
        {
            "title": "Systems and Sources of Truth for Support",
            "slug_leaf": "systems-and-sources-of-truth-for-support",
            "page_type": "source_of_truth",
            "markdown": (
                "# Systems and Sources of Truth for Support\n\n"
                "## System Roles\n"
                "- Which ticketing, incident, CRM, and knowledge systems answer which support questions.\n\n"
                "## Trust Rules\n"
                "- Which source wins when ticket state, incident state, or customer notes disagree.\n"
            ),
        },
        {
            "title": "Known Support Pitfalls and Heuristics",
            "slug_leaf": "known-support-pitfalls-and-heuristics",
            "page_type": "known_exception",
            "markdown": (
                "# Known Support Pitfalls and Heuristics\n\n"
                "## Common Pitfalls\n"
                "- Typical routing mistakes, stale incident context, and customer-update gaps.\n\n"
                "## Working Heuristics\n"
                "- Practical rules experienced support operators keep reusing under pressure.\n"
            ),
        },
    ],
    "sales_company": [
        {
            "title": "How Revenue Operations Works",
            "slug_leaf": "how-revenue-operations-works",
            "page_type": "process",
            "markdown": (
                "# How Revenue Operations Works\n\n"
                "## Purpose\n"
                "- Explain the revenue operation in business language: qualification, stage management, ownership transfer, and reporting.\n\n"
                "## Core Roles\n"
                "- AEs, SDRs, rev-ops, success, reviewers, and AI agents.\n\n"
                "## Core Loops\n"
                "- Qualification checks, stage progression, handoff readiness, and pipeline reporting.\n\n"
                "## Failure Modes\n"
                "- Hidden blockers, weak handoff context, stage drift, and unowned deals.\n"
            ),
        },
        {
            "title": "Revenue Glossary",
            "slug_leaf": "revenue-glossary",
            "page_type": "glossary_term",
            "markdown": (
                "# Revenue Glossary\n\n"
                "## Canonical Terms\n"
                "- Define qualification, stage, handoff, opportunity health, and revenue-risk in company language.\n\n"
                "## Common Confusions\n"
                "- Record pipeline terms that drift across CRM, sheets, and operator notes.\n"
            ),
        },
        {
            "title": "Roles and Handoff Ownership",
            "slug_leaf": "roles-and-handoff-ownership",
            "page_type": "entity",
            "markdown": (
                "# Roles and Handoff Ownership\n\n"
                "## Revenue Roles\n"
                "- Which team owns qualification, stage progression, handoff preparation, and downstream follow-through.\n\n"
                "## Agent Boundaries\n"
                "- What revenue agents can update autonomously and where human approval or override starts.\n"
            ),
        },
        {
            "title": "Qualification and Stage Progression",
            "slug_leaf": "qualification-and-stage-progression",
            "page_type": "process",
            "markdown": (
                "# Qualification and Stage Progression\n\n"
                "## Entry Criteria\n"
                "- What must be true before a deal can move forward.\n\n"
                "## Handoff Readiness\n"
                "- Which context, owner, and blocker fields must be explicit before downstream teams inherit the work.\n"
            ),
        },
        {
            "title": "CRM and Revenue Source of Truth",
            "slug_leaf": "crm-and-revenue-source-of-truth",
            "page_type": "source_of_truth",
            "markdown": (
                "# CRM and Revenue Source of Truth\n\n"
                "## System Roles\n"
                "- Which CRM, warehouse, sheet, and handoff systems answer which revenue questions.\n\n"
                "## Trust Rules\n"
                "- What wins when pipeline state, owner notes, and downstream handoff views disagree.\n"
            ),
        },
        {
            "title": "Revenue Exceptions and Handoff Heuristics",
            "slug_leaf": "revenue-exceptions-and-handoff-heuristics",
            "page_type": "known_exception",
            "markdown": (
                "# Revenue Exceptions and Handoff Heuristics\n\n"
                "## Common Exceptions\n"
                "- Typical qualification gaps, stage mismatches, and handoff failures that need explicit handling.\n\n"
                "## Working Heuristics\n"
                "- Stable operator rules for protecting downstream teams from weak deal context.\n"
            ),
        },
    ],
    "compliance_company": [
        {
            "title": "How the Compliance Program Operates",
            "slug_leaf": "how-the-compliance-program-operates",
            "page_type": "process",
            "markdown": (
                "# How the Compliance Program Operates\n\n"
                "## Purpose\n"
                "- Explain the compliance program in business language: control ownership, evidence collection, review cadence, and escalation.\n\n"
                "## Core Roles\n"
                "- Control owners, reviewers, approvers, auditors, and AI agents.\n\n"
                "## Core Loops\n"
                "- Evidence collection, control review, policy follow-up, and audit preparation.\n\n"
                "## Failure Modes\n"
                "- Missing evidence, unclear ownership, policy drift, and unresolved approval gaps.\n"
            ),
        },
        {
            "title": "Compliance Glossary",
            "slug_leaf": "compliance-glossary",
            "page_type": "glossary_term",
            "markdown": (
                "# Compliance Glossary\n\n"
                "## Canonical Terms\n"
                "- Define control, evidence, exception, review obligation, and approval boundary in company language.\n\n"
                "## Common Confusions\n"
                "- Record terms that drift between policy docs, evidence systems, and operator notes.\n"
            ),
        },
        {
            "title": "Control Ownership and Review Cadence",
            "slug_leaf": "control-ownership-and-review-cadence",
            "page_type": "entity",
            "markdown": (
                "# Control Ownership and Review Cadence\n\n"
                "## Ownership\n"
                "- Which teams own control execution, evidence freshness, and review obligations.\n\n"
                "## Review Rhythm\n"
                "- Which controls are checked daily, periodically, or only during incident/audit windows.\n"
            ),
        },
        {
            "title": "Evidence and Source of Truth",
            "slug_leaf": "evidence-and-source-of-truth",
            "page_type": "source_of_truth",
            "markdown": (
                "# Evidence and Source of Truth\n\n"
                "## Canonical Evidence\n"
                "- Which system is authoritative for each control or policy question.\n\n"
                "## Trust Rules\n"
                "- What to do when evidence snapshots, policy notes, and operator-maintained views disagree.\n"
            ),
        },
        {
            "title": "Escalations and Approval Boundaries",
            "slug_leaf": "escalations-and-approval-boundaries",
            "page_type": "escalation_rule",
            "markdown": (
                "# Escalations and Approval Boundaries\n\n"
                "## Approval Triggers\n"
                "- Which control or policy states require a reviewer, approver, or audit owner.\n\n"
                "## Escalation Rules\n"
                "- When missing evidence or policy drift must stop autonomous progress.\n"
            ),
        },
        {
            "title": "Known Control Exceptions and Audit Heuristics",
            "slug_leaf": "known-control-exceptions-and-audit-heuristics",
            "page_type": "known_exception",
            "markdown": (
                "# Known Control Exceptions and Audit Heuristics\n\n"
                "## Common Exceptions\n"
                "- Typical evidence gaps, stale review states, and policy mismatches that operators keep encountering.\n\n"
                "## Working Heuristics\n"
                "- Stable rules teams use to keep the review loop clean before audit pressure appears.\n"
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


def _company_domain_key(value: Any) -> str:
    normalized = re.sub(r"[^a-z0-9_/-]+", "-", str(value or "").strip().lower()).strip("-")
    if not normalized:
        return "generic"
    token = normalized.split("/")[0]
    if token in {"logistics", "support", "sales", "compliance"}:
        return token
    return "generic"


def _humanize_company_process_label(
    value: Any,
    *,
    normalize_statement_text: NormalizeStatementTextFn,
    domain_key: str,
) -> str:
    raw_text = str(value or "").strip()
    normalized = normalize_statement_text(raw_text)
    if not normalized:
        return ""
    lowered = f" {normalized} "
    label_map: list[tuple[tuple[str, ...], str]] = [
        (("documents", "shift", "readiness"), "shift readiness checks"),
        (("incident", "monitor"), "incident monitoring"),
        (("daily", "report"), "daily operating report"),
        (("erp", "sync"), "ERP state refresh"),
        (("fleet", "sync"), "fleet availability refresh"),
        (("comment", "signal"), "operator comment learning"),
        (("ticket", "escalat"), "ticket escalation review"),
        (("queue", "triage"), "queue triage"),
        (("customer", "update"), "customer update follow-through"),
        (("deal", "handoff"), "deal handoff review"),
        (("qualification",), "qualification checks"),
        (("stage", "progress"), "stage progression review"),
        (("control", "evidence"), "control evidence review"),
        (("policy", "review"), "policy review"),
        (("audit", "readiness"), "audit readiness review"),
    ]
    for keywords, label in label_map:
        if all(keyword in lowered for keyword in keywords):
            if domain_key == "support" and label == "daily operating report":
                return "daily support digest"
            if domain_key == "sales" and label == "daily operating report":
                return "daily pipeline digest"
            if domain_key == "compliance" and label == "daily operating report":
                return "daily control digest"
            return label
    cleaned = raw_text
    cleaned = cleaned.replace(".", " ").replace("/", " ").replace("_", " ").replace("-", " ")
    cleaned = re.sub(r"\b(queryspec|virtual|builtin|cron|scheduled|workflow|task|program|v2)\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bstanding\s+order\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned or normalized.replace("  ", " ")
    return cleaned.lower()


def _build_company_cycle_outline(processes: list[str], *, domain_key: str) -> list[str]:
    cleaned = [str(item).strip().rstrip(".") for item in processes if str(item).strip()]
    if not cleaned:
        if domain_key == "support":
            return [
                "Start by checking queue pressure, incoming incidents, and any SLA-risk work.",
                "Work through routing, customer communication, and specialist escalation in that order.",
                "Close the loop with an explicit owner, customer-visible next step, and follow-up checkpoint.",
            ]
        if domain_key == "sales":
            return [
                "Start by checking deal stage movement, qualification gaps, and pending handoffs.",
                "Work through ownership transitions and missing context before advancing revenue workflow state.",
                "Close the loop with a clear next stage, owner, and downstream handoff expectation.",
            ]
        if domain_key == "compliance":
            return [
                "Start by checking current control posture, evidence freshness, and pending review obligations.",
                "Work through evidence validation, policy checks, and approval gaps before closure.",
                "Close the loop with the current control state, missing evidence, and next review date.",
            ]
        return [
            "Start by checking the current operating context and any new exceptions.",
            "Work through the core operating checks before changing state or escalating.",
            "Close the loop with explicit outputs, follow-up actions, and handoff notes.",
        ]
    outline = [f"Start by checking {cleaned[0]}."]
    if len(cleaned) >= 2:
        outline.append(f"Then confirm {cleaned[1]} before the workflow advances.")
    if len(cleaned) >= 3:
        outline.append(f"Close the loop with {cleaned[2]} and a clear handoff or reporting update.")
    else:
        outline.append("Close the loop with an explicit handoff, reporting update, or escalation note.")
    return outline


def _company_block_fallback_title(block_type: str, target_page_slug: str | None, target_page_type: str | None) -> str:
    slug_leaf = str(target_page_slug or "").strip().split("/")[-1]
    if slug_leaf:
        return _humanize_signal_label(slug_leaf.replace("-", " "))
    label = str(target_page_type or block_type or "company knowledge").replace("_", " ").replace("-", " ")
    return _humanize_signal_label(label)


def _company_block_why_it_matters(block_type: str, target_page_type: str | None) -> str:
    normalized = str(block_type or target_page_type or "").strip().lower()
    if normalized in {"entity_overview", "entity"}:
        return "Operators and agents need a shared picture of the main business objects before they can trust downstream SOPs and reports."
    if normalized in {"process_sop_candidate", "process"}:
        return "A repeatable operating cycle should read like a human SOP, not like scattered scheduled-task metadata."
    if normalized in {"source_of_truth_rule", "source_of_truth"}:
        return "When systems disagree, the company needs one explicit trust rule instead of silent guesswork."
    if normalized in {"known_exception", "working_heuristic"}:
        return "A mature org wiki should preserve the practical shortcuts and recurring pitfalls that operators actually use."
    if normalized in {"contradiction_watch"}:
        return "Conflicts should be made explicit so people and agents know what still needs resolution before broad reuse."
    return "This candidate looks important enough to mature into durable company knowledge."


def _build_company_candidate_page_markdown(block: dict[str, Any]) -> str:
    block_type = str(block.get("block_type") or "").strip().lower()
    title = str(block.get("human_title") or "").strip() or _company_block_fallback_title(
        block_type,
        str(block.get("target_page_slug") or ""),
        str(block.get("target_page_type") or ""),
    )
    human_summary = str(block.get("human_summary") or block.get("summary") or "").strip() or "Pending company-facing summary."
    evidence_basis = str(block.get("evidence_basis") or "").strip() or "Evidence basis pending."
    why_it_matters = str(block.get("why_it_matters") or "").strip() or _company_block_why_it_matters(
        str(block.get("block_type") or ""),
        str(block.get("target_page_type") or ""),
    )
    knowledge_state = str(block.get("knowledge_state") or "candidate").strip().lower() or "candidate"
    confidence = str(block.get("confidence") or "unknown").strip().lower() or "unknown"
    promotion_path = str(block.get("promotion_path") or "").strip() or "Promotion path pending explicit owner review."
    contradiction_topic = str(block.get("contradiction_topic") or "").strip()
    resolution_rule = str(block.get("resolution_rule") or "").strip()
    canonical_target = str(block.get("target_page_slug") or "").strip()
    lines = [
        f"# {title}",
        "",
        human_summary,
        "",
        "## Why This Matters",
        f"- {why_it_matters}",
        "",
        "## Current Knowledge State",
        f"- State: {knowledge_state}",
        f"- Confidence: {confidence}",
        f"- Candidate ID: `{str(block.get('block_id') or '').strip()}`",
    ]
    if canonical_target:
        lines.append(f"- Intended canon page: `{canonical_target}`")
    if block_type == "process_sop_candidate":
        owner_hint = str(block.get("owner_hint") or "operations team").strip()
        trigger_hint = str(block.get("trigger_hint") or "start of the operating cycle").strip()
        inputs_hint = [str(item).strip() for item in (block.get("inputs_hint") or []) if str(item).strip()]
        outputs_hint = [str(item).strip() for item in (block.get("outputs_hint") or []) if str(item).strip()]
        failure_modes_hint = [str(item).strip() for item in (block.get("failure_modes_hint") or []) if str(item).strip()]
        escalation_hint = str(block.get("escalation_hint") or "Escalate when the cycle leaves approved operating scope.").strip()
        cycle_outline = [str(item).strip() for item in (block.get("cycle_outline") or []) if str(item).strip()]
        lines.extend(
            [
                "",
                "## Goal",
                f"- {human_summary}",
                "",
                "## Who Owns This Cycle",
                f"- {owner_hint}",
                "",
                "## Trigger",
                f"- {trigger_hint}",
                "",
                "## Typical Rhythm",
                *[f"- {item}" for item in (cycle_outline or ["Start with the current operating context.", "Work through the recurring checks and decisions.", "Close the loop with explicit outputs and a handoff note."])],
                "",
                "## Inputs To Check",
                *[f"- {item}" for item in (inputs_hint or ["current operational systems", "latest team context"])],
                "",
                "## Expected Outputs",
                *[f"- {item}" for item in (outputs_hint or ["workflow completed and documented"])],
                "",
                "## Common Failure Modes",
                *[f"- {item}" for item in (failure_modes_hint or ["missing evidence", "stale source context"])],
                "",
                "## Escalation",
                f"- {escalation_hint}",
                "",
                "## Evidence We Are Using",
                f"- {evidence_basis}",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "## Current Working Rule",
                f"- {human_summary}",
                "",
                "## Evidence We Are Using",
                f"- {evidence_basis}",
            ]
        )
    if contradiction_topic:
        lines.extend(["", "## Conflict To Resolve", f"- Topic: {contradiction_topic}"])
    if resolution_rule:
        heading = "## Canonical Ruling" if block_type in {"contradiction_watch", "source_of_truth_rule"} else "## Preferred Resolution"
        lines.extend(["", heading, f"- {resolution_rule}"])
    lines.extend(["", "## Before Promotion To Canon", f"- {promotion_path}", ""])
    return "\n".join(lines)


def _build_company_candidate_humanization(block: dict[str, Any]) -> dict[str, Any]:
    block_type = str(block.get("block_type") or "").strip().lower()
    target_page_type = str(block.get("target_page_type") or "").strip().lower() or None
    target_page_slug = str(block.get("target_page_slug") or "").strip() or None
    summary = str(block.get("summary") or "").strip()
    domain_key = _company_domain_key(block.get("domain_label") or target_page_slug or block.get("block_id"))
    domain_titles = {
        "logistics": {
            "entity_overview": "Core business entities in the logistics operation",
            "process_sop_candidate": "Daily logistics operating cycle",
            "source_of_truth_rule": "Which systems to trust for live logistics state",
            "known_exception": "Recurring logistics pitfalls and exception patterns",
            "working_heuristic": "Working heuristics the team keeps reusing",
            "contradiction_watch": "Source-of-truth conflicts that still need resolution",
        },
        "support": {
            "entity_overview": "Core business entities in the support operation",
            "process_sop_candidate": "Daily support operating cycle",
            "source_of_truth_rule": "Which systems to trust for live support state",
            "known_exception": "Recurring support pitfalls and exception patterns",
            "working_heuristic": "Support heuristics the team keeps reusing",
            "contradiction_watch": "Support source conflicts that still need resolution",
        },
        "sales": {
            "entity_overview": "Core business entities in the revenue operation",
            "process_sop_candidate": "Daily revenue operating cycle",
            "source_of_truth_rule": "Which systems to trust for live revenue state",
            "known_exception": "Recurring revenue pitfalls and exception patterns",
            "working_heuristic": "Revenue heuristics the team keeps reusing",
            "contradiction_watch": "Revenue source conflicts that still need resolution",
        },
        "compliance": {
            "entity_overview": "Core business entities in the compliance program",
            "process_sop_candidate": "Daily compliance operating cycle",
            "source_of_truth_rule": "Which systems to trust for compliance evidence state",
            "known_exception": "Recurring compliance pitfalls and exception patterns",
            "working_heuristic": "Compliance heuristics the team keeps reusing",
            "contradiction_watch": "Compliance source conflicts that still need resolution",
        },
    }
    title_map = domain_titles.get(domain_key, {})
    human_title = _company_block_fallback_title(block_type, target_page_slug, target_page_type)
    human_summary = summary
    if block_type in title_map:
        human_title = title_map[block_type]
    if block_type == "entity_overview":
        entity_focus = [str(item).strip() for item in (block.get("entity_focus") or []) if str(item).strip()]
        if entity_focus:
            human_summary = f"The operation currently appears to revolve around {', '.join(entity_focus[:3])}, and those entities should anchor the rest of the company wiki."
        else:
            human_summary = summary.replace("Current", "Right now the operation appears to center on")
    elif block_type == "process_sop_candidate":
        cadence_label = str(block.get("cadence_label") or "operating cycle").strip()
        process_focus = [str(item).strip() for item in (block.get("process_focus") or []) if str(item).strip()]
        if process_focus:
            human_summary = (
                f"This {cadence_label} appears to run through {', '.join(process_focus[:3])}, with explicit checks, handoffs, and escalation points."
            )
        else:
            human_summary = summary.replace("The current", "The current team rhythm suggests that the operation")
    elif block_type == "source_of_truth_rule":
        human_summary = summary.replace("Trust rule candidate:", "Working trust rule:").replace("Current company knowledge suggests", "Current evidence suggests")
    elif block_type == "known_exception":
        human_summary = summary.replace("Recurring operational exceptions likely include", "Operators are repeatedly running into")
    elif block_type == "working_heuristic":
        human_summary = summary.replace("Company memory is repeatedly surfacing heuristics around", "The team keeps leaning on heuristics around")
    elif block_type == "contradiction_watch":
        human_summary = summary.replace("Current company knowledge shows", "Current evidence shows").replace(
            "Current company knowledge appears exposed to",
            "Current evidence still appears exposed to",
        )
    human_summary = human_summary.strip().rstrip(".")
    if human_summary:
        human_summary = f"{human_summary}."
    why_it_matters = _company_block_why_it_matters(block_type, target_page_type)
    page_markdown = _build_company_candidate_page_markdown(
        {
            **block,
            "human_title": human_title,
            "human_summary": human_summary,
            "why_it_matters": why_it_matters,
        }
    )
    return {
        "human_title": human_title,
        "human_summary": human_summary,
        "why_it_matters": why_it_matters,
        "page_markdown": page_markdown,
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
        space_key: str | None,
        matrix_rows: list[dict[str, Any]] | None,
        source_counts: list[tuple[str, int]] | None,
        claims_rollup: list[tuple[str, int]] | None,
        normalize_statement_text: NormalizeStatementTextFn,
    ) -> dict[str, Any]:
        del space_key, matrix_rows, source_counts, claims_rollup, normalize_statement_text
        return {
            "snapshot_notes": [],
            "workflow_signals": [],
            "entity_signals": [],
            "process_signals": [],
            "trust_signals": [],
            "exception_signals": [],
            "candidate_canon_blocks": [],
            "knowledge_lifecycle_summary": [],
            "contradiction_summaries": [],
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
        elif normalized_profile == "support_ops":
            pack_key = "support_company"
        elif normalized_profile == "sales_ops":
            pack_key = "sales_company"
        elif normalized_profile == "compliance_ops":
            pack_key = "compliance_company"
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


def _build_domain_company_context_extensions(
    *,
    space_key: str | None,
    matrix_rows: list[dict[str, Any]] | None,
    source_counts: list[tuple[str, int]] | None,
    claims_rollup: list[tuple[str, int]] | None,
    normalize_statement_text: NormalizeStatementTextFn,
    domain_key: str,
    operation_label: str,
    entity_buckets: dict[str, tuple[str, ...]],
    exception_buckets: dict[str, tuple[str, ...]],
    process_slug_leaf: str,
    overview_slug_leaf: str,
    trust_slug_leaf: str,
    heuristics_slug_leaf: str,
    owner_hint: str,
    outputs_hint: list[str],
    escalation_hint: str,
    principles: list[str],
) -> dict[str, Any]:
    normalized_space = re.sub(r"[^a-z0-9_/-]+", "-", str(space_key or "").strip().lower()).strip("-") or domain_key
    workflow_counts: dict[str, int] = {}
    entity_counts: dict[str, int] = {key: 0 for key in entity_buckets}
    exception_counts: dict[str, int] = {key: 0 for key in exception_buckets}

    def _target_slug(leaf: str) -> str:
        normalized_leaf = re.sub(r"[^a-z0-9_/-]+", "-", str(leaf or "").strip().lower()).strip("-") or "company-knowledge"
        return f"{normalized_space}/{normalized_leaf}"

    def _bump_signals(value: Any, *, weight: int = 1) -> None:
        text = normalize_statement_text(str(value or ""))
        if not text:
            return
        for label, keywords in entity_buckets.items():
            if any(keyword in text for keyword in keywords):
                entity_counts[label] = int(entity_counts.get(label, 0)) + int(weight)
        for label, keywords in exception_buckets.items():
            if any(keyword in text for keyword in keywords):
                exception_counts[label] = int(exception_counts.get(label, 0)) + int(weight)

    for item in matrix_rows or []:
        if not isinstance(item, dict):
            continue
        for value in [*(item.get("standing_orders") or []), *(item.get("scheduled_tasks") or [])]:
            label = _humanize_company_process_label(
                value,
                normalize_statement_text=normalize_statement_text,
                domain_key=domain_key,
            )
            if not label:
                continue
            workflow_counts[label] = int(workflow_counts.get(label, 0)) + 1
            _bump_signals(label, weight=2)
        for value in [
            *(item.get("responsibilities") or []),
            *(item.get("scenario_examples") or []),
            *(item.get("source_bindings") or []),
            *(item.get("data_sources") or []),
            *(item.get("approval_rules") or []),
            *(item.get("escalation_rules") or []),
        ]:
            _bump_signals(value)
    for category, total in claims_rollup or []:
        _bump_signals(category, weight=max(1, int(total or 0)))

    workflow_signals = [
        {"label": name, "count": total}
        for name, total in sorted(workflow_counts.items(), key=lambda item: (-item[1], item[0].lower()))[:6]
    ]
    entity_signals = [
        {"label": label, "count": total}
        for label, total in sorted(entity_counts.items(), key=lambda item: (-item[1], item[0].lower()))
        if int(total) > 0
    ][:8]
    process_signals = [
        {
            "label": str(item.get("label") or ""),
            "count": int(item.get("count") or 0),
            "why": "Recurring workflow observed in scheduled tasks, standing orders, or operating routines.",
        }
        for item in workflow_signals[:6]
    ]
    trust_signals: list[dict[str, Any]] = []
    for source_type, total in source_counts or []:
        normalized_source = normalize_statement_text(str(source_type or ""))
        label = _humanize_signal_label(str(source_type or "unknown"))
        trust_note = "Operational source stream."
        if "postgres" in normalized_source or "crm" in normalized_source or "erp" in normalized_source or "ticket" in normalized_source:
            trust_note = "Likely canonical operational record; prefer when live ownership or workflow state matters."
        elif "sheet" in normalized_source:
            trust_note = "Often a derived or operator-maintained view; validate against canonical systems when conflicts appear."
        elif "memory" in normalized_source or "kb" in normalized_source:
            trust_note = "Knowledge or summary layer; useful for context, but should not silently override live state."
        elif "api" in normalized_source or "provider" in normalized_source or "incident" in normalized_source:
            trust_note = "Provider or service feed; make freshness and outage handling explicit."
        trust_signals.append({"label": label, "count": int(total or 0), "trust_note": trust_note})
    trust_signals = sorted(trust_signals, key=lambda item: (-int(item.get("count") or 0), str(item.get("label") or "").lower()))[:6]
    exception_signals = [
        {"label": label, "count": total}
        for label, total in sorted(exception_counts.items(), key=lambda item: (-item[1], item[0].lower()))
        if int(total) > 0
    ][:6]

    candidate_canon_blocks: list[dict[str, Any]] = []
    knowledge_state_counts: dict[str, int] = {}
    contradiction_summaries: list[dict[str, Any]] = []

    def _append_canon_block(block: dict[str, Any]) -> None:
        state = str(block.get("knowledge_state") or "candidate").strip().lower() or "candidate"
        block["knowledge_state"] = state
        knowledge_state_counts[state] = int(knowledge_state_counts.get(state, 0)) + 1
        if not str(block.get("block_id") or "").strip():
            block["block_id"] = f"{normalized_space}:{str(block.get('block_type') or 'candidate').strip().lower()}"
        block.setdefault("domain_label", domain_key)
        block.setdefault("operation_label", operation_label)
        block.update(_build_company_candidate_humanization(block))
        candidate_canon_blocks.append(block)

    top_entities = [str(item.get("label") or "").strip() for item in entity_signals[:3] if str(item.get("label") or "").strip()]
    top_processes = [str(item.get("label") or "").strip() for item in process_signals[:3] if str(item.get("label") or "").strip()]
    top_exceptions = [str(item.get("label") or "").strip() for item in exception_signals[:3] if str(item.get("label") or "").strip()]

    if top_entities:
        strongest_entity_count = max(int(item.get("count") or 0) for item in entity_signals[:3]) if entity_signals else 0
        _append_canon_block(
            {
                "block_type": "entity_overview",
                "target_page_type": "entity",
                "target_page_slug": _target_slug(overview_slug_leaf),
                "promotion_path": f"Promote into the {operation_label.lower()} overview after owner review confirms the entity framing.",
                "knowledge_state": "reviewed" if strongest_entity_count >= 3 else "candidate",
                "confidence": "medium",
                "summary": f"Current {domain_key} memory centers on {', '.join(top_entities)} as the main business entities.",
                "evidence_basis": "Repeated mentions across workflows, responsibilities, and claim rollups.",
                "entity_focus": top_entities,
            }
        )
    if top_processes:
        cadence_label = "daily operating cycle" if any("daily" in normalize_statement_text(item) for item in top_processes) else "recurring operating cycle"
        strongest_process_count = max(int(item.get("count") or 0) for item in process_signals[:3]) if process_signals else 0
        process_inputs = [str(item.get("label") or "").strip() for item in trust_signals[:2] if str(item.get("label") or "").strip()]
        if not process_inputs:
            process_inputs = ["current operating systems", "latest operator context"]
        _append_canon_block(
            {
                "block_type": "process_sop_candidate",
                "target_page_type": "process",
                "target_page_slug": _target_slug(process_slug_leaf),
                "promotion_path": "Promote into the main SOP page once owner, trigger, outputs, and escalation steps read clearly to operators.",
                "knowledge_state": "reviewed" if strongest_process_count >= 2 else "candidate",
                "confidence": "medium",
                "summary": f"The current {cadence_label} appears to revolve around {', '.join(top_processes)}.",
                "evidence_basis": "Observed in standing orders, scheduled tasks, and recurring operational routines.",
                "owner_hint": owner_hint,
                "trigger_hint": f"Start of the {cadence_label} and any handoff or incident that changes {operation_label.lower()} state.",
                "inputs_hint": process_inputs,
                "outputs_hint": outputs_hint,
                "failure_modes_hint": top_exceptions or ["stale source context", "missing handoff evidence"],
                "escalation_hint": escalation_hint,
                "process_focus": top_processes,
                "cadence_label": cadence_label,
                "cycle_outline": _build_company_cycle_outline(top_processes, domain_key=domain_key),
            }
        )
    canonical_sources = [str(item.get("label") or "").strip() for item in trust_signals if "canonical operational record" in normalize_statement_text(str(item.get("trust_note") or ""))]
    derived_sources = [str(item.get("label") or "").strip() for item in trust_signals if "derived" in normalize_statement_text(str(item.get("trust_note") or ""))]
    if canonical_sources or derived_sources:
        summary_parts: list[str] = []
        if canonical_sources:
            summary_parts.append(f"prefer {', '.join(canonical_sources[:2])} when live ownership or workflow state matters")
        if derived_sources:
            summary_parts.append(f"treat {', '.join(derived_sources[:2])} as secondary or operator-maintained context during conflicts")
        source_state = "reviewed" if canonical_sources else "stale"
        _append_canon_block(
            {
                "block_type": "source_of_truth_rule",
                "target_page_type": "source_of_truth",
                "target_page_slug": _target_slug(trust_slug_leaf),
                "promotion_path": "Promote into trust rules after source precedence and freshness language are reviewed by operators.",
                "knowledge_state": source_state,
                "confidence": "medium",
                "summary": f"Trust rule candidate: {'; '.join(summary_parts)}.",
                "evidence_basis": "Inferred from connected source classes and source-trust heuristics.",
            }
        )
    if top_exceptions:
        strongest_exception_count = max(int(item.get("count") or 0) for item in exception_signals[:3]) if exception_signals else 0
        _append_canon_block(
            {
                "block_type": "known_exception",
                "target_page_type": "known_exception",
                "target_page_slug": _target_slug(heuristics_slug_leaf),
                "promotion_path": "Promote into the pitfalls page after confirming that the exception pattern recurs in live operations.",
                "knowledge_state": "reviewed" if strongest_exception_count >= 2 else "candidate",
                "confidence": "low",
                "summary": f"Recurring operational exceptions likely include {', '.join(top_exceptions)}.",
                "evidence_basis": "Pattern counts derived from workflow, responsibility, and claim language.",
            }
        )
    if claims_rollup:
        top_claims = [str(category or "").strip().replace("_", " ") for category, _ in claims_rollup[:3] if str(category or "").strip()]
        if top_claims:
            strongest_claim_count = max(int(total or 0) for _, total in claims_rollup[:3]) if claims_rollup else 0
            _append_canon_block(
                {
                    "block_type": "working_heuristic",
                    "target_page_type": "known_exception",
                    "target_page_slug": _target_slug(heuristics_slug_leaf),
                    "promotion_path": "Promote into the heuristics page once the pattern is stable enough to guide future operators.",
                    "knowledge_state": "reviewed" if strongest_claim_count >= 3 else "candidate",
                    "confidence": "low",
                    "summary": f"Company memory is repeatedly surfacing heuristics around {', '.join(top_claims)}.",
                    "evidence_basis": "Repeated claim categories observed in current knowledge rollups.",
                }
            )
    stale_conflict_total = sum(
        int(item.get("count") or 0)
        for item in exception_signals
        if "stale" in normalize_statement_text(str(item.get("label") or "")) or "conflict" in normalize_statement_text(str(item.get("label") or ""))
    )
    if stale_conflict_total > 0:
        contradiction_state = "contradicted" if canonical_sources and derived_sources else "stale"
        contradiction_summary = (
            "Current company knowledge shows source disagreement between canonical records and derived/operator-maintained views."
            if contradiction_state == "contradicted"
            else "Current company knowledge still appears exposed to stale or weakly grounded source views that need refresh or validation."
        )
        resolution_rule = (
            f"Prefer {', '.join(canonical_sources[:2])} for live state; use {', '.join(derived_sources[:2])} as secondary context until the mismatch is resolved."
            if contradiction_state == "contradicted" and canonical_sources and derived_sources
            else "Refresh or validate the weaker source before promoting it into canonical company knowledge."
        )
        _append_canon_block(
            {
                "block_type": "contradiction_watch",
                "target_page_type": "source_of_truth",
                "target_page_slug": _target_slug(trust_slug_leaf),
                "promotion_path": "Keep in reviewed trust rules until the conflict is resolved or documented as an explicit override rule.",
                "knowledge_state": contradiction_state,
                "confidence": "medium" if contradiction_state == "contradicted" else "low",
                "summary": contradiction_summary,
                "evidence_basis": "Exception patterns mention stale/conflicting data and source-trust signals show mixed evidence posture.",
                "contradiction_topic": "source_of_truth_conflict",
                "resolution_rule": resolution_rule,
            }
        )
        contradiction_summaries.append(
            {
                "topic": "source_of_truth_conflict",
                "knowledge_state": contradiction_state,
                "summary": contradiction_summary,
                "resolution_rule": resolution_rule,
                "evidence_basis": "Built from source trust signals plus stale/conflict exception patterns.",
            }
        )

    knowledge_lifecycle_summary = [
        {"state": state, "count": total}
        for state, total in sorted(
            knowledge_state_counts.items(),
            key=lambda item: (-int(item[1]), ["candidate", "reviewed", "canonical", "stale", "contradicted", "superseded"].index(item[0]) if item[0] in ["candidate", "reviewed", "canonical", "stale", "contradicted", "superseded"] else 99),
        )
    ]
    snapshot_notes = [
        f"Recurring workflows observed: {len(workflow_signals)}.",
        f"Connected source streams contributing to {domain_key} knowledge: {sum(int(total or 0) for _, total in (source_counts or []))}.",
        f"Operational domain signals currently tracked: {sum(int(total or 0) for _, total in (claims_rollup or []))}.",
    ]
    return {
        "snapshot_notes": snapshot_notes,
        "workflow_signals": workflow_signals,
        "entity_signals": entity_signals,
        "process_signals": process_signals,
        "trust_signals": trust_signals,
        "exception_signals": exception_signals,
        "candidate_canon_blocks": candidate_canon_blocks,
        "knowledge_lifecycle_summary": knowledge_lifecycle_summary,
        "contradiction_summaries": contradiction_summaries,
        "principles": principles,
    }


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
        space_key: str | None,
        matrix_rows: list[dict[str, Any]] | None,
        source_counts: list[tuple[str, int]] | None,
        claims_rollup: list[tuple[str, int]] | None,
        normalize_statement_text: NormalizeStatementTextFn,
    ) -> dict[str, Any]:
        normalized_space = re.sub(r"[^a-z0-9_/-]+", "-", str(space_key or "").strip().lower()).strip("-") or "company"
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
                label = _humanize_company_process_label(
                    text,
                    normalize_statement_text=normalize_statement_text,
                    domain_key="logistics",
                )
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
        knowledge_state_counts: dict[str, int] = {}
        contradiction_summaries: list[dict[str, Any]] = []

        def _target_slug(leaf: str) -> str:
            normalized_leaf = re.sub(r"[^a-z0-9_/-]+", "-", str(leaf or "").strip().lower()).strip("-") or "company-knowledge"
            return f"{normalized_space}/{normalized_leaf}"

        def _append_canon_block(block: dict[str, Any]) -> None:
            state = str(block.get("knowledge_state") or "candidate").strip().lower() or "candidate"
            block["knowledge_state"] = state
            knowledge_state_counts[state] = int(knowledge_state_counts.get(state, 0)) + 1
            if not str(block.get("block_id") or "").strip():
                block["block_id"] = f"{normalized_space}:{str(block.get('block_type') or 'candidate').strip().lower()}"
            block.update(_build_company_candidate_humanization(block))
            candidate_canon_blocks.append(block)

        top_entities = [str(item.get("label") or "").strip() for item in entity_signals[:3] if str(item.get("label") or "").strip()]
        top_exceptions = [
            label
            for label, total in sorted(exception_counts.items(), key=lambda item: (-item[1], item[0].lower()))
            if int(total) > 0
        ][:3]
        if top_entities:
            strongest_entity_count = max(int(item.get("count") or 0) for item in entity_signals[:3]) if entity_signals else 0
            _append_canon_block(
                {
                    "block_type": "entity_overview",
                    "target_page_type": "entity",
                    "target_page_slug": _target_slug("how-the-logistics-operation-works"),
                    "promotion_path": "Promote into the logistics operation overview after owner review confirms the entity framing.",
                    "knowledge_state": "reviewed" if strongest_entity_count >= 3 else "candidate",
                    "confidence": "medium",
                    "summary": f"Current logistics memory centers on {', '.join(top_entities)} as the main business entities.",
                    "evidence_basis": "Repeated mentions across scheduled workflows, responsibilities, and claim rollups.",
                    "domain_label": "logistics",
                    "entity_focus": top_entities,
                }
            )

        top_processes = [str(item.get("label") or "").strip() for item in process_signals[:3] if str(item.get("label") or "").strip()]
        if top_processes:
            cadence = "daily operating cadence" if any("daily" in normalize_statement_text(item) for item in top_processes) else "recurring operational workflow"
            strongest_process_count = max(int(item.get("count") or 0) for item in process_signals[:3]) if process_signals else 0
            process_inputs = [str(item.get("label") or "").strip() for item in trust_signals[:2] if str(item.get("label") or "").strip()]
            if not process_inputs:
                process_inputs = ["current operational systems", "latest operator context"]
            process_outputs = ["shift readiness confirmed", "exceptions escalated", "daily reporting updated"]
            process_failure_modes = top_exceptions[:3] if top_exceptions else ["source mismatch", "missing readiness evidence"]
            _append_canon_block(
                {
                    "block_type": "process_sop_candidate",
                    "target_page_type": "process",
                    "target_page_slug": _target_slug("daily-logistics-operating-cycle"),
                    "promotion_path": "Promote into the daily operating cycle or a dedicated SOP page once trigger, owner, and exception path are explicit.",
                    "knowledge_state": "reviewed" if strongest_process_count >= 2 else "candidate",
                    "confidence": "medium",
                    "summary": f"The current {cadence} appears to revolve around {', '.join(top_processes)}.",
                    "evidence_basis": "Observed in standing orders and scheduled tasks across the runtime matrix.",
                    "owner_hint": "logistics operations / dispatch team",
                    "trigger_hint": f"Start of the {cadence} and any new operator handoff that changes route, readiness, or incident posture.",
                    "inputs_hint": process_inputs,
                    "outputs_hint": process_outputs,
                    "failure_modes_hint": process_failure_modes,
                    "escalation_hint": "Escalate to the human operations lead whenever readiness is incomplete, source trust breaks down, or incidents affect customer/service commitments.",
                    "domain_label": "logistics",
                    "process_focus": top_processes,
                    "cadence_label": cadence,
                    "cycle_outline": _build_company_cycle_outline(top_processes, domain_key="logistics"),
                }
            )

        canonical_sources: list[str] = []
        derived_sources: list[str] = []
        if trust_signals:
            canonical_sources = [str(item.get("label") or "").strip() for item in trust_signals if "canonical operational record" in normalize_statement_text(str(item.get("trust_note") or ""))]
            derived_sources = [str(item.get("label") or "").strip() for item in trust_signals if "derived" in normalize_statement_text(str(item.get("trust_note") or ""))]
            if canonical_sources or derived_sources:
                summary_parts: list[str] = []
                if canonical_sources:
                    summary_parts.append(f"prefer {', '.join(canonical_sources[:2])} for live operational state")
                if derived_sources:
                    summary_parts.append(f"treat {', '.join(derived_sources[:2])} as derived/operator-maintained views during conflicts")
                source_truth_state = "reviewed"
                if not canonical_sources and derived_sources:
                    source_truth_state = "stale"
                _append_canon_block(
                    {
                        "block_type": "source_of_truth_rule",
                        "target_page_type": "source_of_truth",
                        "target_page_slug": _target_slug("trust-rules-for-logistics-data"),
                        "promotion_path": "Promote into trust rules once source precedence and freshness language are reviewed by operators.",
                        "knowledge_state": source_truth_state,
                        "confidence": "medium",
                        "summary": f"Trust rule candidate: {'; '.join(summary_parts)}.",
                        "evidence_basis": "Inferred from connected source classes and source-trust heuristics.",
                        "domain_label": "logistics",
                    }
                )

        top_exceptions = [str(item.get("label") or "").strip() for item in exception_signals[:3] if str(item.get("label") or "").strip()]
        if top_exceptions:
            strongest_exception_count = max(int(item.get("count") or 0) for item in exception_signals[:3]) if exception_signals else 0
            _append_canon_block(
                {
                    "block_type": "known_exception",
                    "target_page_type": "known_exception",
                    "target_page_slug": _target_slug("known-pitfalls-and-working-heuristics"),
                    "promotion_path": "Promote into the pitfalls/exception page after confirming that the pattern recurs in live operations.",
                    "knowledge_state": "reviewed" if strongest_exception_count >= 2 else "candidate",
                    "confidence": "low",
                    "summary": f"Recurring operational exceptions likely include {', '.join(top_exceptions)}.",
                    "evidence_basis": "Pattern counts derived from workflow, responsibility, and claim language.",
                    "domain_label": "logistics",
                }
            )

        if claims_rollup:
            top_claims = [str(category or "").strip().replace("_", " ") for category, _ in claims_rollup[:3] if str(category or "").strip()]
            if top_claims:
                strongest_claim_count = max(int(total or 0) for _, total in claims_rollup[:3]) if claims_rollup else 0
                _append_canon_block(
                    {
                        "block_type": "working_heuristic",
                        "target_page_type": "known_exception",
                        "target_page_slug": _target_slug("known-pitfalls-and-working-heuristics"),
                        "promotion_path": "Promote into the working heuristics page once the pattern is stable enough to guide future operators.",
                        "knowledge_state": "reviewed" if strongest_claim_count >= 3 else "candidate",
                        "confidence": "low",
                        "summary": f"Company memory is repeatedly surfacing heuristics around {', '.join(top_claims)}.",
                        "evidence_basis": "Repeated claim categories observed in current knowledge rollups.",
                        "domain_label": "logistics",
                    }
                )
        stale_conflict_total = int(exception_counts.get("Stale or conflicting source data") or 0)
        if stale_conflict_total > 0:
            contradiction_state = "contradicted" if canonical_sources and derived_sources else "stale"
            contradiction_summary = (
                "Current company knowledge shows source disagreement between canonical operational records and derived/operator-maintained views."
                if contradiction_state == "contradicted"
                else "Current company knowledge appears exposed to stale or weakly grounded source views that need refresh or validation."
            )
            resolution_rule = (
                f"Prefer {', '.join(canonical_sources[:2])} for live state; use {', '.join(derived_sources[:2])} as secondary/operator context until the mismatch is resolved."
                if contradiction_state == "contradicted" and canonical_sources and derived_sources
                else "Refresh or validate the weaker source before promoting it into canonical company knowledge."
            )
            _append_canon_block(
                {
                    "block_type": "contradiction_watch",
                    "target_page_type": "source_of_truth",
                    "target_page_slug": _target_slug("trust-rules-for-logistics-data"),
                    "promotion_path": "Keep in reviewed trust rules until the conflict is resolved or documented as an explicit override rule.",
                    "knowledge_state": contradiction_state,
                    "confidence": "medium" if contradiction_state == "contradicted" else "low",
                    "summary": contradiction_summary,
                    "evidence_basis": "Exception patterns mention stale/conflicting data and source-trust signals show mixed evidence posture.",
                    "contradiction_topic": "source_of_truth_conflict",
                    "resolution_rule": resolution_rule,
                    "domain_label": "logistics",
                }
            )
            contradiction_summaries.append(
                {
                    "topic": "source_of_truth_conflict",
                    "knowledge_state": contradiction_state,
                    "summary": contradiction_summary,
                    "resolution_rule": resolution_rule,
                    "evidence_basis": "Built from source trust signals plus stale/conflict exception patterns.",
                }
            )
        knowledge_lifecycle_summary = [
            {"state": state, "count": total}
            for state, total in sorted(
                knowledge_state_counts.items(),
                key=lambda item: (-int(item[1]), ["candidate", "reviewed", "canonical", "stale", "contradicted", "superseded"].index(item[0]) if item[0] in ["candidate", "reviewed", "canonical", "stale", "contradicted", "superseded"] else 99),
            )
        ]
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
            "knowledge_lifecycle_summary": knowledge_lifecycle_summary,
            "contradiction_summaries": contradiction_summaries,
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
        space_key: str | None,
        matrix_rows: list[dict[str, Any]] | None,
        source_counts: list[tuple[str, int]] | None,
        claims_rollup: list[tuple[str, int]] | None,
        normalize_statement_text: NormalizeStatementTextFn,
    ) -> dict[str, Any]:
        return _build_domain_company_context_extensions(
            space_key=space_key,
            matrix_rows=matrix_rows,
            source_counts=source_counts,
            claims_rollup=claims_rollup,
            normalize_statement_text=normalize_statement_text,
            domain_key="support",
            operation_label="support operation",
            entity_buckets={
                "Customer Case": ("ticket", "case", "customer"),
                "Queue": ("queue", "routing", "triage"),
                "Incident": ("incident", "sev", "outage"),
                "Escalation": ("escalat", "handoff"),
                "SLA": ("sla", "breach"),
                "Knowledge Article": ("kb", "knowledge", "macro"),
            },
            exception_buckets={
                "Queue ownership drift": ("queue", "owner"),
                "Customer update gap": ("customer", "update"),
                "Escalation delay": ("escalat", "delay"),
                "Stale or conflicting source data": ("stale", "conflict", "derived"),
            },
            process_slug_leaf="daily-support-operating-cycle",
            overview_slug_leaf="how-the-support-operation-works",
            trust_slug_leaf="systems-and-sources-of-truth-for-support",
            heuristics_slug_leaf="known-support-pitfalls-and-heuristics",
            owner_hint="support operations / queue owner",
            outputs_hint=["queue state updated", "customer next step recorded", "escalations routed cleanly"],
            escalation_hint="Escalate to the incident manager or support lead whenever SLA risk, customer-impact uncertainty, or unclear ownership appears.",
            principles=[
                "Customer-facing escalations should stay explicit, time-bounded, and tied to queue ownership.",
                "Support workflows should prefer reusable routing rules over one-off operator memory.",
                "Resolution notes should be written so the next human or agent can resume without hidden context.",
            ],
        )

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
        space_key: str | None,
        matrix_rows: list[dict[str, Any]] | None,
        source_counts: list[tuple[str, int]] | None,
        claims_rollup: list[tuple[str, int]] | None,
        normalize_statement_text: NormalizeStatementTextFn,
    ) -> dict[str, Any]:
        return _build_domain_company_context_extensions(
            space_key=space_key,
            matrix_rows=matrix_rows,
            source_counts=source_counts,
            claims_rollup=claims_rollup,
            normalize_statement_text=normalize_statement_text,
            domain_key="sales",
            operation_label="revenue operation",
            entity_buckets={
                "Deal": ("deal", "opportunity", "pipeline"),
                "Stage": ("stage", "qualification"),
                "Handoff": ("handoff", "transfer"),
                "Account Owner": ("owner", "account executive", "sdr"),
                "Forecast / Report": ("forecast", "report", "revenue"),
                "Customer Context": ("customer", "context", "notes"),
            },
            exception_buckets={
                "Qualification gap": ("qualification", "missing"),
                "Handoff risk": ("handoff", "risk", "blocker"),
                "Stage drift": ("stage", "drift"),
                "Stale or conflicting source data": ("stale", "conflict", "derived"),
            },
            process_slug_leaf="daily-revenue-operating-cycle",
            overview_slug_leaf="how-revenue-operations-works",
            trust_slug_leaf="crm-and-revenue-source-of-truth",
            heuristics_slug_leaf="revenue-exceptions-and-handoff-heuristics",
            owner_hint="revenue operations / pipeline owner",
            outputs_hint=["pipeline state updated", "handoff package prepared", "risk follow-ups assigned"],
            escalation_hint="Escalate to the revenue-ops lead whenever qualification is incomplete, ownership is unclear, or downstream teams would inherit weak context.",
            principles=[
                "Qualification and stage changes should be explicit enough that downstream teams inherit clean context.",
                "Revenue handoffs should capture commitments, blockers, and owner transitions without hidden operator knowledge.",
                "Pipeline summaries should surface risk and missing context before they become customer-facing failures.",
            ],
        )

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
        space_key: str | None,
        matrix_rows: list[dict[str, Any]] | None,
        source_counts: list[tuple[str, int]] | None,
        claims_rollup: list[tuple[str, int]] | None,
        normalize_statement_text: NormalizeStatementTextFn,
    ) -> dict[str, Any]:
        return _build_domain_company_context_extensions(
            space_key=space_key,
            matrix_rows=matrix_rows,
            source_counts=source_counts,
            claims_rollup=claims_rollup,
            normalize_statement_text=normalize_statement_text,
            domain_key="compliance",
            operation_label="compliance program",
            entity_buckets={
                "Control": ("control", "policy"),
                "Evidence": ("evidence", "artifact"),
                "Review Obligation": ("review", "cadence"),
                "Approval Boundary": ("approval", "approver"),
                "Exception": ("exception", "override"),
                "Audit Item": ("audit", "finding"),
            },
            exception_buckets={
                "Missing evidence": ("missing", "evidence"),
                "Approval gap": ("approval", "gap"),
                "Policy drift": ("policy", "drift"),
                "Stale or conflicting source data": ("stale", "conflict", "derived"),
            },
            process_slug_leaf="daily-compliance-operating-cycle",
            overview_slug_leaf="how-the-compliance-program-operates",
            trust_slug_leaf="evidence-and-source-of-truth",
            heuristics_slug_leaf="known-control-exceptions-and-audit-heuristics",
            owner_hint="control owner / compliance reviewer",
            outputs_hint=["control posture updated", "evidence gaps flagged", "next review obligation recorded"],
            escalation_hint="Escalate to the compliance lead or approver whenever evidence is missing, policy drift appears, or an approval boundary blocks autonomous closure.",
            principles=[
                "Control evidence and policy execution should remain attributable, reviewable, and easy to audit.",
                "Compliance workflows should escalate missing approvals or evidence rather than silently marking success.",
                "Shared operating context should make review cadence and control ownership explicit for the next operator or auditor.",
            ],
        )

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
