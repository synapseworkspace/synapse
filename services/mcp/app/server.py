from __future__ import annotations

import os
import sys
from typing import Any

from .runtime import SynapseKnowledgeRuntime, build_runtime_from_env


def create_mcp_server(runtime: SynapseKnowledgeRuntime | None = None) -> Any:
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception as exc:  # pragma: no cover - import guard for minimal environments
        raise RuntimeError(
            "Missing MCP runtime dependency. Install with `pip install -e services/mcp` (includes `mcp`)."
        ) from exc

    runtime_impl = runtime or build_runtime_from_env()
    server = FastMCP("synapse-mcp")

    @server.tool(
        name="search_knowledge",
        description=(
            "Semantic search over approved Synapse knowledge statements with project-level filters; "
            "returns explainability fields (`retrieval_reason`, `score_breakdown`, `retrieval_confidence`) per result. "
            "Supports intent-aware context injection (`retrieval_intent`, `max_context_snippets`) and "
            "context-policy controls (`context_policy_mode`, confidence/score thresholds)."
        ),
    )
    def search_knowledge(
        project_id: str,
        query: str,
        limit: int = 10,
        entity_key: str | None = None,
        category: str | None = None,
        page_type: str | None = None,
        related_entity_key: str | None = None,
        retrieval_intent: str | None = None,
        max_context_snippets: int | None = None,
        context_policy_mode: str | None = None,
        min_retrieval_confidence: float | None = None,
        min_total_score: float | None = None,
        min_lexical_score: float | None = None,
        min_token_overlap_ratio: float | None = None,
    ) -> dict[str, Any]:
        return runtime_impl.search_knowledge(
            project_id=project_id,
            query=query,
            limit=limit,
            entity_key=entity_key,
            category=category,
            page_type=page_type,
            related_entity_key=related_entity_key,
            retrieval_intent=retrieval_intent,
            max_context_snippets=max_context_snippets,
            context_policy_mode=context_policy_mode,
            min_retrieval_confidence=min_retrieval_confidence,
            min_total_score=min_total_score,
            min_lexical_score=min_lexical_score,
            min_token_overlap_ratio=min_token_overlap_ratio,
        )

    @server.tool(
        name="get_entity_facts",
        description="Return current facts for a specific entity from published Synapse pages.",
    )
    def get_entity_facts(
        project_id: str,
        entity_key: str,
        limit: int = 50,
        category: str | None = None,
        include_non_current: bool = False,
    ) -> dict[str, Any]:
        return runtime_impl.get_entity_facts(
            project_id=project_id,
            entity_key=entity_key,
            limit=limit,
            category=category,
            include_non_current=include_non_current,
        )

    @server.tool(
        name="get_recent_changes",
        description="List recent knowledge changes (moderation actions and published snapshots).",
    )
    def get_recent_changes(
        project_id: str,
        limit: int = 20,
        since_hours: int = 168,
    ) -> dict[str, Any]:
        return runtime_impl.get_recent_changes(
            project_id=project_id,
            limit=limit,
            since_hours=since_hours,
        )

    @server.tool(
        name="explain_conflicts",
        description="Explain conflict records with incoming claim vs conflicting statement context.",
    )
    def explain_conflicts(
        project_id: str,
        limit: int = 20,
        resolution_status: str | None = "open",
        entity_key: str | None = None,
    ) -> dict[str, Any]:
        return runtime_impl.explain_conflicts(
            project_id=project_id,
            limit=limit,
            resolution_status=resolution_status,
            entity_key=entity_key,
        )

    @server.tool(
        name="get_open_tasks",
        description="List active project tasks (`todo`, `in_progress`, `blocked`) for agent execution context.",
    )
    def get_open_tasks(
        project_id: str,
        limit: int = 20,
        assignee: str | None = None,
        entity_key: str | None = None,
    ) -> dict[str, Any]:
        return runtime_impl.get_open_tasks(
            project_id=project_id,
            limit=limit,
            assignee=assignee,
            entity_key=entity_key,
        )

    @server.tool(
        name="get_task_details",
        description="Return one task with timeline events and links to claims/drafts/pages.",
    )
    def get_task_details(
        project_id: str,
        task_id: str,
        events_limit: int = 50,
        links_limit: int = 50,
    ) -> dict[str, Any]:
        return runtime_impl.get_task_details(
            project_id=project_id,
            task_id=task_id,
            events_limit=events_limit,
            links_limit=links_limit,
        )

    @server.tool(
        name="get_onboarding_pack",
        description=(
            "Generate a day-0 onboarding pack from published wiki knowledge: "
            "critical playbooks, escalation rules, forbidden actions, and fresh changes."
        ),
    )
    def get_onboarding_pack(
        project_id: str,
        role: str | None = None,
        max_items_per_section: int = 5,
        freshness_days: int = 14,
    ) -> dict[str, Any]:
        return runtime_impl.get_onboarding_pack(
            project_id=project_id,
            role=role,
            max_items_per_section=max_items_per_section,
            freshness_days=freshness_days,
        )

    @server.tool(
        name="get_state_snapshot",
        description=(
            "Return the latest published Step-0 state snapshot page "
            "(compressed wiki state for fast runtime context priming)."
        ),
    )
    def get_state_snapshot(
        project_id: str,
        space_key: str | None = None,
    ) -> dict[str, Any]:
        return runtime_impl.get_state_snapshot(
            project_id=project_id,
            space_key=space_key,
        )

    @server.tool(
        name="get_space_policy_adoption_summary",
        description=(
            "Summarize governance adoption for one wiki space (who updates policy, cadence, checklist usage, "
            "and transition count) for retrieval-friendly operational context."
        ),
    )
    def get_space_policy_adoption_summary(
        project_id: str,
        space_key: str,
        limit: int = 200,
    ) -> dict[str, Any]:
        return runtime_impl.get_space_policy_adoption_summary(
            project_id=project_id,
            space_key=space_key,
            limit=limit,
        )

    return server


def run_mcp_server(*, transport: str | None = None) -> None:
    server = create_mcp_server()
    selected_transport = (transport or os.getenv("SYNAPSE_MCP_TRANSPORT", "stdio")).strip().lower()
    host = os.getenv("SYNAPSE_MCP_HOST", "0.0.0.0")
    port = int(os.getenv("SYNAPSE_MCP_PORT", "8091"))

    def _warn(message: str) -> None:
        print(f"[synapse-mcp] warning: {message}", file=sys.stderr)

    network_candidates: list[str] = []
    if selected_transport in {"streamable-http", "http"}:
        network_candidates = [selected_transport]
        if selected_transport == "http":
            network_candidates.append("streamable-http")
    else:
        if selected_transport not in {"stdio"}:
            _warn(f"unsupported transport `{selected_transport}` requested; trying streamable-http then stdio fallback")
        network_candidates = ["streamable-http"]

    for candidate in network_candidates:
        try:
            server.run(transport=candidate, host=host, port=port)
            return
        except (TypeError, ValueError) as exc:
            _warn(f"transport `{candidate}` not accepted by runtime ({type(exc).__name__}: {exc}); falling back")

    for candidate in (selected_transport, "stdio"):
        try:
            server.run(transport=candidate)
            return
        except (TypeError, ValueError):
            continue
    server.run()
