from __future__ import annotations

import json
import os
import sys
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Protocol

if TYPE_CHECKING:  # pragma: no cover
    import psycopg

try:
    from shared.retrieval import (
        RetrievalContextPolicyConfig,
        RetrievalGraphConfig,
        build_retrieval_explain_fields,
        build_retrieval_search_plan,
        clean_optional_filter as _clean_optional,
        load_context_policy_config_from_env,
        load_graph_config_from_env,
        normalize_context_policy_mode,
        normalize_float_value as _normalize_float,
        normalize_limit_value as _normalize_limit,
        query_tokens as _query_tokens,
        resolve_context_policy_config,
        serialize_context_policy_config,
    )
except ModuleNotFoundError:
    services_root = Path(__file__).resolve().parents[2]
    if str(services_root) not in sys.path:
        sys.path.append(str(services_root))
    from shared.retrieval import (
        RetrievalContextPolicyConfig,
        RetrievalGraphConfig,
        build_retrieval_explain_fields,
        build_retrieval_search_plan,
        clean_optional_filter as _clean_optional,
        load_context_policy_config_from_env,
        load_graph_config_from_env,
        normalize_context_policy_mode,
        normalize_float_value as _normalize_float,
        normalize_limit_value as _normalize_limit,
        query_tokens as _query_tokens,
        resolve_context_policy_config,
        serialize_context_policy_config,
    )


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(UTC).isoformat()


@dataclass(slots=True)
class CacheEntry:
    revision: str
    expires_at: datetime
    value: dict[str, Any]


class KnowledgeStore(Protocol):
    def get_project_revision(self, project_id: str) -> str: ...

    def search_knowledge(
        self,
        *,
        project_id: str,
        query: str,
        limit: int,
        entity_key: str | None,
        category: str | None,
        page_type: str | None,
        related_entity_key: str | None,
    ) -> list[dict[str, Any]]: ...

    def get_entity_facts(
        self,
        *,
        project_id: str,
        entity_key: str,
        limit: int,
        category: str | None,
        include_non_current: bool,
    ) -> list[dict[str, Any]]: ...

    def get_recent_changes(
        self,
        *,
        project_id: str,
        limit: int,
        since_hours: int,
    ) -> list[dict[str, Any]]: ...

    def explain_conflicts(
        self,
        *,
        project_id: str,
        limit: int,
        resolution_status: str | None,
        entity_key: str | None,
    ) -> list[dict[str, Any]]: ...

    def get_open_tasks(
        self,
        *,
        project_id: str,
        limit: int,
        assignee: str | None,
        entity_key: str | None,
    ) -> list[dict[str, Any]]: ...

    def get_task_details(
        self,
        *,
        project_id: str,
        task_id: str,
        events_limit: int,
        links_limit: int,
    ) -> dict[str, Any] | None: ...


class PostgresKnowledgeStore:
    def __init__(
        self,
        *,
        database_url: str,
        max_graph_hops: int = 3,
        graph_boost_hop1: float = 0.20,
        graph_boost_hop2: float = 0.12,
        graph_boost_hop3: float = 0.06,
        graph_boost_other: float = 0.03,
    ) -> None:
        self._database_url = database_url
        self._graph_config = RetrievalGraphConfig(
            max_graph_hops=max(1, int(max_graph_hops)),
            boost_hop1=float(graph_boost_hop1),
            boost_hop2=float(graph_boost_hop2),
            boost_hop3=float(graph_boost_hop3),
            boost_other=float(graph_boost_other),
        )

    def get_project_revision(self, project_id: str) -> str:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT MAX(updated_at)
                    FROM synapse_tasks
                    WHERE project_id = %s
                    """,
                    (project_id,),
                )
                task_row = cur.fetchone()
                task_revision = (
                    task_row[0].isoformat()
                    if task_row is not None and task_row[0] is not None
                    else "none"
                )

                cur.execute(
                    """
                    SELECT id::text, published_at
                    FROM knowledge_snapshots
                    WHERE project_id = %s
                    ORDER BY published_at DESC
                    LIMIT 1
                    """,
                    (project_id,),
                )
                row = cur.fetchone()
                if row is not None:
                    return f"snapshot:{row[0]}:{row[1].isoformat()}:tasks:{task_revision}"

                cur.execute(
                    """
                    SELECT MAX(updated_at)
                    FROM wiki_pages
                    WHERE project_id = %s
                      AND status = 'published'
                    """,
                    (project_id,),
                )
                page_row = cur.fetchone()
                if page_row is not None and page_row[0] is not None:
                    return f"pages:{page_row[0].isoformat()}:tasks:{task_revision}"
                if task_revision != "none":
                    return f"tasks:{task_revision}"
        return "empty"

    def search_knowledge(
        self,
        *,
        project_id: str,
        query: str,
        limit: int,
        entity_key: str | None,
        category: str | None,
        page_type: str | None,
        related_entity_key: str | None,
    ) -> list[dict[str, Any]]:
        plan = build_retrieval_search_plan(
            project_id=project_id,
            query=query,
            limit=limit,
            entity_key=entity_key,
            category=category,
            page_type=page_type,
            related_entity_key=related_entity_key,
            graph_config=self._graph_config,
        )
        if plan is None:
            return []
        results: list[dict[str, Any]] = []

        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(plan.sql, plan.params)
                for row in cur.fetchall():
                    results.append(
                        {
                            "statement_id": row[0],
                            "statement_text": row[1],
                            "section_key": row[2],
                            "valid_from": _iso(row[3]),
                            "valid_to": _iso(row[4]),
                            "created_at": _iso(row[5]),
                            "page": {
                                "id": row[6],
                                "title": row[7],
                                "slug": row[8],
                                "entity_key": row[9],
                                "page_type": row[10],
                            },
                            "category": row[11] or None,
                            "score": round(float(row[12]), 4),
                            "graph_hops": int(row[13]) if row[13] is not None else None,
                            "graph_boost": round(float(row[14]), 4),
                        }
                    )
        return results

    def get_entity_facts(
        self,
        *,
        project_id: str,
        entity_key: str,
        limit: int,
        category: str | None,
        include_non_current: bool,
    ) -> list[dict[str, Any]]:
        normalized_entity = entity_key.strip().lower()
        category_filter = _clean_optional(category)
        results: list[dict[str, Any]] = []

        validity_clause = ""
        if not include_non_current:
            validity_clause = """
              AND (st.valid_from IS NULL OR st.valid_from <= NOW())
              AND (st.valid_to IS NULL OR st.valid_to >= NOW())
            """

        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                      st.id::text,
                      st.statement_text,
                      st.section_key,
                      st.status,
                      st.valid_from,
                      st.valid_to,
                      st.created_at,
                      p.id::text,
                      p.title,
                      p.slug,
                      p.entity_key,
                      p.page_type,
                      COALESCE(claim_meta.category, '')
                    FROM wiki_pages p
                    JOIN wiki_statements st ON st.page_id = p.id
                    LEFT JOIN LATERAL (
                      SELECT c.category
                      FROM claims c
                      WHERE c.project_id = st.project_id
                        AND c.claim_fingerprint = st.claim_fingerprint
                      ORDER BY c.updated_at DESC
                      LIMIT 1
                    ) claim_meta ON TRUE
                    WHERE p.project_id = %s
                      AND p.status = 'published'
                      AND lower(p.entity_key) = %s
                      AND st.status = 'active'
                      {validity_clause}
                      AND (%s::text IS NULL OR lower(COALESCE(claim_meta.category, '')) = %s::text)
                    ORDER BY st.created_at DESC
                    LIMIT %s
                    """,
                    (project_id, normalized_entity, category_filter, category_filter, limit),
                )
                for row in cur.fetchall():
                    results.append(
                        {
                            "statement_id": row[0],
                            "statement_text": row[1],
                            "section_key": row[2],
                            "status": row[3],
                            "valid_from": _iso(row[4]),
                            "valid_to": _iso(row[5]),
                            "created_at": _iso(row[6]),
                            "page": {
                                "id": row[7],
                                "title": row[8],
                                "slug": row[9],
                                "entity_key": row[10],
                                "page_type": row[11],
                            },
                            "category": row[12] or None,
                        }
                    )
        return results

    def get_recent_changes(
        self,
        *,
        project_id: str,
        limit: int,
        since_hours: int,
    ) -> list[dict[str, Any]]:
        cutoff = _now_utc() - timedelta(hours=since_hours)
        events: list[dict[str, Any]] = []
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                      ma.id::text,
                      ma.action_type,
                      ma.reviewed_by,
                      ma.created_at,
                      ma.draft_id::text,
                      ma.claim_id::text,
                      ma.page_id::text,
                      ma.note,
                      ma.reason,
                      COALESCE(ma.result, '{}'::jsonb),
                      p.title,
                      p.slug
                    FROM moderation_actions ma
                    LEFT JOIN wiki_pages p ON p.id = ma.page_id
                    WHERE ma.project_id = %s
                      AND ma.created_at >= %s
                    ORDER BY ma.created_at DESC
                    LIMIT %s
                    """,
                    (project_id, cutoff, limit),
                )
                for row in cur.fetchall():
                    events.append(
                        {
                            "change_type": "moderation",
                            "id": row[0],
                            "action": row[1],
                            "actor": row[2],
                            "created_at": _iso(row[3]),
                            "draft_id": row[4],
                            "claim_id": row[5],
                            "page_id": row[6],
                            "note": row[7],
                            "reason": row[8],
                            "result": row[9] if isinstance(row[9], dict) else {},
                            "page": {"title": row[10], "slug": row[11]},
                        }
                    )

                cur.execute(
                    """
                    SELECT
                      ks.id::text,
                      ks.created_by,
                      ks.note,
                      ks.published_at,
                      COUNT(ksp.page_id)::integer
                    FROM knowledge_snapshots ks
                    LEFT JOIN knowledge_snapshot_pages ksp ON ksp.snapshot_id = ks.id
                    WHERE ks.project_id = %s
                      AND ks.published_at >= %s
                    GROUP BY ks.id, ks.created_by, ks.note, ks.published_at
                    ORDER BY ks.published_at DESC
                    LIMIT %s
                    """,
                    (project_id, cutoff, limit),
                )
                for row in cur.fetchall():
                    events.append(
                        {
                            "change_type": "snapshot",
                            "id": row[0],
                            "action": "publish",
                            "actor": row[1],
                            "created_at": _iso(row[3]),
                            "note": row[2],
                            "page_count": int(row[4]),
                        }
                    )

        events.sort(key=lambda item: item.get("created_at") or "", reverse=True)
        return events[:limit]

    def explain_conflicts(
        self,
        *,
        project_id: str,
        limit: int,
        resolution_status: str | None,
        entity_key: str | None,
    ) -> list[dict[str, Any]]:
        status_filter = _clean_optional(resolution_status)
        entity_filter = _clean_optional(entity_key)
        results: list[dict[str, Any]] = []
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                      wc.id::text,
                      wc.conflict_type,
                      wc.resolution_status,
                      wc.created_at,
                      wc.resolved_at,
                      wc.resolved_by,
                      COALESCE(wc.details, '{}'::jsonb),
                      p.id::text,
                      p.title,
                      p.slug,
                      p.entity_key,
                      c.id::text,
                      c.entity_key,
                      c.category,
                      c.claim_text,
                      c.valid_from,
                      c.valid_to,
                      ws.id::text,
                      ws.section_key,
                      ws.statement_text,
                      ws.valid_from,
                      ws.valid_to
                    FROM wiki_conflicts wc
                    LEFT JOIN wiki_pages p ON p.id = wc.page_id
                    LEFT JOIN claims c ON c.id = wc.claim_id
                    LEFT JOIN wiki_statements ws ON ws.id = wc.conflicting_statement_id
                    WHERE wc.project_id = %s
                      AND (%s IS NULL OR wc.resolution_status = %s)
                      AND (
                        %s IS NULL
                        OR lower(COALESCE(p.entity_key, '')) = %s
                        OR lower(COALESCE(c.entity_key, '')) = %s
                      )
                    ORDER BY
                      CASE wc.resolution_status
                        WHEN 'open' THEN 0
                        WHEN 'resolved' THEN 1
                        ELSE 2
                      END,
                      wc.created_at DESC
                    LIMIT %s
                    """,
                    (
                        project_id,
                        status_filter,
                        status_filter,
                        entity_filter,
                        entity_filter,
                        entity_filter,
                        limit,
                    ),
                )
                for row in cur.fetchall():
                    results.append(
                        {
                            "conflict_id": row[0],
                            "conflict_type": row[1],
                            "resolution_status": row[2],
                            "created_at": _iso(row[3]),
                            "resolved_at": _iso(row[4]),
                            "resolved_by": row[5],
                            "details": row[6] if isinstance(row[6], dict) else {},
                            "page": {
                                "id": row[7],
                                "title": row[8],
                                "slug": row[9],
                                "entity_key": row[10],
                            },
                            "incoming_claim": {
                                "id": row[11],
                                "entity_key": row[12],
                                "category": row[13],
                                "claim_text": row[14],
                                "valid_from": _iso(row[15]),
                                "valid_to": _iso(row[16]),
                            },
                            "conflicting_statement": {
                                "id": row[17],
                                "section_key": row[18],
                                "statement_text": row[19],
                                "valid_from": _iso(row[20]),
                                "valid_to": _iso(row[21]),
                            },
                        }
                    )
        return results

    def get_open_tasks(
        self,
        *,
        project_id: str,
        limit: int,
        assignee: str | None,
        entity_key: str | None,
    ) -> list[dict[str, Any]]:
        normalized_assignee = assignee.strip() if isinstance(assignee, str) and assignee.strip() else None
        normalized_entity = entity_key.strip().lower() if isinstance(entity_key, str) and entity_key.strip() else None
        rows: list[dict[str, Any]] = []
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                      t.id::text,
                      t.title,
                      t.description,
                      t.status,
                      t.priority,
                      t.source,
                      t.assignee,
                      t.entity_key,
                      t.category,
                      t.due_at,
                      t.created_at,
                      t.updated_at,
                      COALESCE(t.metadata, '{}'::jsonb),
                      COALESCE(link_counts.total_links, 0)::int
                    FROM synapse_tasks t
                    LEFT JOIN LATERAL (
                      SELECT COUNT(*) AS total_links
                      FROM synapse_task_links l
                      WHERE l.task_id = t.id
                    ) link_counts ON TRUE
                    WHERE t.project_id = %s
                      AND t.status IN ('todo', 'in_progress', 'blocked')
                      AND (%s::text IS NULL OR t.assignee = %s)
                      AND (%s::text IS NULL OR lower(COALESCE(t.entity_key, '')) = %s)
                    ORDER BY
                      CASE t.status
                        WHEN 'in_progress' THEN 0
                        WHEN 'blocked' THEN 1
                        WHEN 'todo' THEN 2
                        ELSE 3
                      END,
                      CASE t.priority
                        WHEN 'critical' THEN 0
                        WHEN 'high' THEN 1
                        WHEN 'normal' THEN 2
                        ELSE 3
                      END,
                      t.updated_at DESC
                    LIMIT %s
                    """,
                    (
                        project_id,
                        normalized_assignee,
                        normalized_assignee,
                        normalized_entity,
                        normalized_entity,
                        limit,
                    ),
                )
                for row in cur.fetchall():
                    rows.append(
                        {
                            "id": row[0],
                            "title": row[1],
                            "description": row[2],
                            "status": row[3],
                            "priority": row[4],
                            "source": row[5],
                            "assignee": row[6],
                            "entity_key": row[7],
                            "category": row[8],
                            "due_at": _iso(row[9]),
                            "created_at": _iso(row[10]),
                            "updated_at": _iso(row[11]),
                            "metadata": row[12] if isinstance(row[12], dict) else {},
                            "link_count": int(row[13]),
                        }
                    )
        return rows

    def get_task_details(
        self,
        *,
        project_id: str,
        task_id: str,
        events_limit: int,
        links_limit: int,
    ) -> dict[str, Any] | None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                      id::text,
                      title,
                      description,
                      status,
                      priority,
                      source,
                      assignee,
                      entity_key,
                      category,
                      due_at,
                      created_by,
                      updated_by,
                      created_at,
                      updated_at,
                      COALESCE(metadata, '{}'::jsonb)
                    FROM synapse_tasks
                    WHERE project_id = %s
                      AND id::text = %s
                    LIMIT 1
                    """,
                    (project_id, task_id),
                )
                task_row = cur.fetchone()
                if task_row is None:
                    return None

                events: list[dict[str, Any]] = []
                if events_limit > 0:
                    cur.execute(
                        """
                        SELECT
                          id::text,
                          event_type,
                          actor,
                          payload,
                          created_at
                        FROM synapse_task_events
                        WHERE project_id = %s
                          AND task_id::text = %s
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        (project_id, task_id, events_limit),
                    )
                    events = [
                        {
                            "id": row[0],
                            "event_type": row[1],
                            "actor": row[2],
                            "payload": row[3] if isinstance(row[3], dict) else {},
                            "created_at": _iso(row[4]),
                        }
                        for row in cur.fetchall()
                    ]

                links: list[dict[str, Any]] = []
                if links_limit > 0:
                    cur.execute(
                        """
                        SELECT
                          id::text,
                          link_type,
                          link_ref,
                          note,
                          metadata,
                          created_by,
                          created_at
                        FROM synapse_task_links
                        WHERE project_id = %s
                          AND task_id::text = %s
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        (project_id, task_id, links_limit),
                    )
                    links = [
                        {
                            "id": row[0],
                            "link_type": row[1],
                            "link_ref": row[2],
                            "note": row[3],
                            "metadata": row[4] if isinstance(row[4], dict) else {},
                            "created_by": row[5],
                            "created_at": _iso(row[6]),
                        }
                        for row in cur.fetchall()
                    ]

        return {
            "id": task_row[0],
            "title": task_row[1],
            "description": task_row[2],
            "status": task_row[3],
            "priority": task_row[4],
            "source": task_row[5],
            "assignee": task_row[6],
            "entity_key": task_row[7],
            "category": task_row[8],
            "due_at": _iso(task_row[9]),
            "created_by": task_row[10],
            "updated_by": task_row[11],
            "created_at": _iso(task_row[12]),
            "updated_at": _iso(task_row[13]),
            "metadata": task_row[14] if isinstance(task_row[14], dict) else {},
            "events": events,
            "links": links,
        }

    def _conn(self):
        try:
            import psycopg
        except Exception as exc:  # pragma: no cover - optional dependency in offline tests
            raise RuntimeError(
                "psycopg is required for PostgresKnowledgeStore. Install `psycopg[binary]` in services/mcp."
            ) from exc
        return psycopg.connect(self._database_url, autocommit=True)


class SynapseKnowledgeRuntime:
    def __init__(
        self,
        store: KnowledgeStore,
        *,
        cache_ttl_seconds: int = 5,
        max_cache_entries: int = 5000,
        context_policy: RetrievalContextPolicyConfig | None = None,
    ) -> None:
        self._store = store
        self._cache_ttl = max(1, int(cache_ttl_seconds))
        self._max_cache_entries = max(100, int(max_cache_entries))
        self._context_policy = context_policy or load_context_policy_config_from_env()
        self._project_revisions: dict[str, str] = {}
        self._cache: dict[str, CacheEntry] = {}
        self._lock = threading.RLock()

    def search_knowledge(
        self,
        *,
        project_id: str,
        query: str,
        limit: int = 10,
        entity_key: str | None = None,
        category: str | None = None,
        page_type: str | None = None,
        related_entity_key: str | None = None,
        context_policy_mode: str | None = None,
        min_retrieval_confidence: float | None = None,
        min_total_score: float | None = None,
        min_lexical_score: float | None = None,
        min_token_overlap_ratio: float | None = None,
    ) -> dict[str, Any]:
        normalized_limit = _normalize_limit(limit, default=10, minimum=1, maximum=100)
        normalized_query = query.strip()
        resolved_query_tokens = _query_tokens(normalized_query)
        normalized_related = _clean_optional(related_entity_key)
        effective_context_policy = resolve_context_policy_config(
            base=self._context_policy,
            mode=context_policy_mode,
            min_confidence=min_retrieval_confidence,
            min_total_score=min_total_score,
            min_lexical_score=min_lexical_score,
            min_token_overlap_ratio=min_token_overlap_ratio,
        )
        context_policy_payload = serialize_context_policy_config(effective_context_policy)
        if not normalized_query:
            return {
                "project_id": project_id,
                "query": "",
                "results": [],
                "policy_filtered_out": 0,
                "cached": False,
                "revision": self._current_revision(project_id),
                "explainability": {
                    "version": "v1",
                    "query_tokens": [],
                    "related_entity_key": normalized_related,
                    "context_policy": context_policy_payload,
                },
            }

        return self._cached_tool_call(
            project_id=project_id,
            tool_name="search_knowledge",
            args={
                "query": normalized_query,
                "limit": normalized_limit,
                "entity_key": _clean_optional(entity_key),
                "category": _clean_optional(category),
                "page_type": _clean_optional(page_type),
                "related_entity_key": _clean_optional(related_entity_key),
                "context_policy_mode": normalize_context_policy_mode(effective_context_policy.mode),
                "min_retrieval_confidence": _normalize_float(
                    effective_context_policy.min_confidence,
                    default=effective_context_policy.min_confidence,
                    minimum=0.0,
                    maximum=1.0,
                ),
                "min_total_score": _normalize_float(
                    effective_context_policy.min_total_score,
                    default=effective_context_policy.min_total_score,
                    minimum=0.0,
                    maximum=2.0,
                ),
                "min_lexical_score": _normalize_float(
                    effective_context_policy.min_lexical_score,
                    default=effective_context_policy.min_lexical_score,
                    minimum=0.0,
                    maximum=2.0,
                ),
                "min_token_overlap_ratio": _normalize_float(
                    effective_context_policy.min_token_overlap_ratio,
                    default=effective_context_policy.min_token_overlap_ratio,
                    minimum=0.0,
                    maximum=1.0,
                ),
            },
            compute=lambda: self._compute_search_payload(
                project_id=project_id,
                normalized_query=normalized_query,
                normalized_limit=normalized_limit,
                entity_key=entity_key,
                category=category,
                page_type=page_type,
                related_entity_key=related_entity_key,
                normalized_related=normalized_related,
                resolved_query_tokens=resolved_query_tokens,
                effective_context_policy=effective_context_policy,
                context_policy_payload=context_policy_payload,
            ),
        )

    def get_entity_facts(
        self,
        *,
        project_id: str,
        entity_key: str,
        limit: int = 50,
        category: str | None = None,
        include_non_current: bool = False,
    ) -> dict[str, Any]:
        normalized_limit = _normalize_limit(limit, default=50, minimum=1, maximum=500)
        normalized_entity = entity_key.strip()
        if not normalized_entity:
            return {
                "project_id": project_id,
                "entity_key": "",
                "facts": [],
                "cached": False,
                "revision": self._current_revision(project_id),
            }
        normalized_include = bool(include_non_current)

        return self._cached_tool_call(
            project_id=project_id,
            tool_name="get_entity_facts",
            args={
                "entity_key": normalized_entity.lower(),
                "limit": normalized_limit,
                "category": _clean_optional(category),
                "include_non_current": normalized_include,
            },
            compute=lambda: {
                "project_id": project_id,
                "entity_key": normalized_entity,
                "facts": self._store.get_entity_facts(
                    project_id=project_id,
                    entity_key=normalized_entity,
                    limit=normalized_limit,
                    category=category,
                    include_non_current=normalized_include,
                ),
            },
        )

    def _compute_search_payload(
        self,
        *,
        project_id: str,
        normalized_query: str,
        normalized_limit: int,
        entity_key: str | None,
        category: str | None,
        page_type: str | None,
        related_entity_key: str | None,
        normalized_related: str | None,
        resolved_query_tokens: list[str],
        effective_context_policy: RetrievalContextPolicyConfig,
        context_policy_payload: dict[str, Any],
    ) -> dict[str, Any]:
        results = [
            build_retrieval_explain_fields(
                query=normalized_query,
                related_entity_key=normalized_related,
                result=row,
                query_tokens_override=resolved_query_tokens,
                context_policy=effective_context_policy,
            )
            for row in self._store.search_knowledge(
                project_id=project_id,
                query=normalized_query,
                limit=normalized_limit,
                entity_key=entity_key,
                category=category,
                page_type=page_type,
                related_entity_key=related_entity_key,
            )
        ]
        filtered_out = 0
        if normalize_context_policy_mode(effective_context_policy.mode) == "enforced":
            total_before = len(results)
            results = [
                row
                for row in results
                if isinstance(row.get("context_policy"), dict) and bool(row["context_policy"].get("eligible"))
            ]
            filtered_out = max(0, total_before - len(results))
        return {
            "project_id": project_id,
            "query": normalized_query,
            "results": results,
            "policy_filtered_out": filtered_out,
            "explainability": {
                "version": "v1",
                "query_tokens": resolved_query_tokens,
                "related_entity_key": normalized_related,
                "context_policy": context_policy_payload,
            },
        }

    def get_recent_changes(
        self,
        *,
        project_id: str,
        limit: int = 20,
        since_hours: int = 168,
    ) -> dict[str, Any]:
        normalized_limit = _normalize_limit(limit, default=20, minimum=1, maximum=200)
        normalized_since_hours = _normalize_limit(since_hours, default=168, minimum=1, maximum=24 * 90)
        return self._cached_tool_call(
            project_id=project_id,
            tool_name="get_recent_changes",
            args={"limit": normalized_limit, "since_hours": normalized_since_hours},
            compute=lambda: {
                "project_id": project_id,
                "since_hours": normalized_since_hours,
                "changes": self._store.get_recent_changes(
                    project_id=project_id,
                    limit=normalized_limit,
                    since_hours=normalized_since_hours,
                ),
            },
        )

    def explain_conflicts(
        self,
        *,
        project_id: str,
        limit: int = 20,
        resolution_status: str | None = "open",
        entity_key: str | None = None,
    ) -> dict[str, Any]:
        normalized_limit = _normalize_limit(limit, default=20, minimum=1, maximum=200)
        normalized_status = _clean_optional(resolution_status)
        if normalized_status not in {None, "open", "resolved", "dismissed"}:
            normalized_status = "open"
        normalized_entity_key = _clean_optional(entity_key)

        return self._cached_tool_call(
            project_id=project_id,
            tool_name="explain_conflicts",
            args={
                "limit": normalized_limit,
                "resolution_status": normalized_status,
                "entity_key": normalized_entity_key,
            },
            compute=lambda: {
                "project_id": project_id,
                "resolution_status": normalized_status,
                "conflicts": self._store.explain_conflicts(
                    project_id=project_id,
                    limit=normalized_limit,
                    resolution_status=normalized_status,
                    entity_key=normalized_entity_key,
                ),
            },
        )

    def get_open_tasks(
        self,
        *,
        project_id: str,
        limit: int = 20,
        assignee: str | None = None,
        entity_key: str | None = None,
    ) -> dict[str, Any]:
        normalized_limit = _normalize_limit(limit, default=20, minimum=1, maximum=200)
        normalized_assignee = assignee.strip() if isinstance(assignee, str) and assignee.strip() else None
        normalized_entity_key = _clean_optional(entity_key)
        return self._cached_tool_call(
            project_id=project_id,
            tool_name="get_open_tasks",
            args={
                "limit": normalized_limit,
                "assignee": normalized_assignee,
                "entity_key": normalized_entity_key,
            },
            compute=lambda: {
                "project_id": project_id,
                "tasks": self._store.get_open_tasks(
                    project_id=project_id,
                    limit=normalized_limit,
                    assignee=normalized_assignee,
                    entity_key=normalized_entity_key,
                ),
            },
        )

    def get_task_details(
        self,
        *,
        project_id: str,
        task_id: str,
        events_limit: int = 50,
        links_limit: int = 50,
    ) -> dict[str, Any]:
        normalized_task_id = task_id.strip()
        if not normalized_task_id:
            return {
                "project_id": project_id,
                "task": None,
                "cached": False,
                "revision": self._current_revision(project_id),
            }
        normalized_events = _normalize_limit(events_limit, default=50, minimum=0, maximum=500)
        normalized_links = _normalize_limit(links_limit, default=50, minimum=0, maximum=500)
        return self._cached_tool_call(
            project_id=project_id,
            tool_name="get_task_details",
            args={
                "task_id": normalized_task_id,
                "events_limit": normalized_events,
                "links_limit": normalized_links,
            },
            compute=lambda: {
                "project_id": project_id,
                "task": self._store.get_task_details(
                    project_id=project_id,
                    task_id=normalized_task_id,
                    events_limit=normalized_events,
                    links_limit=normalized_links,
                ),
            },
        )

    def _cached_tool_call(
        self,
        *,
        project_id: str,
        tool_name: str,
        args: dict[str, Any],
        compute: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        revision = self._refresh_project_revision(project_id)
        cache_key = self._cache_key(project_id=project_id, tool_name=tool_name, args=args)
        now = _now_utc()

        with self._lock:
            cached = self._cache.get(cache_key)
            if cached is not None and cached.revision == revision and cached.expires_at > now:
                cached_payload = dict(cached.value)
                cached_payload["cached"] = True
                cached_payload["revision"] = revision
                return cached_payload

        payload = compute()
        result = dict(payload)
        result["cached"] = False
        result["revision"] = revision

        with self._lock:
            if len(self._cache) >= self._max_cache_entries:
                self._evict_expired_or_oldest(now=now)
            self._cache[cache_key] = CacheEntry(
                revision=revision,
                expires_at=now + timedelta(seconds=self._cache_ttl),
                value=result,
            )
        return result

    def _current_revision(self, project_id: str) -> str:
        with self._lock:
            return self._project_revisions.get(project_id, "unknown")

    def _refresh_project_revision(self, project_id: str) -> str:
        revision = self._store.get_project_revision(project_id)
        with self._lock:
            previous = self._project_revisions.get(project_id)
            if previous != revision:
                self._project_revisions[project_id] = revision
                prefix = f"{project_id}:"
                for key in [item for item in self._cache.keys() if item.startswith(prefix)]:
                    self._cache.pop(key, None)
        return revision

    def _cache_key(self, *, project_id: str, tool_name: str, args: dict[str, Any]) -> str:
        payload = json.dumps(args, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
        return f"{project_id}:{tool_name}:{payload}"

    def _evict_expired_or_oldest(self, *, now: datetime) -> None:
        expired = [key for key, entry in self._cache.items() if entry.expires_at <= now]
        for key in expired:
            self._cache.pop(key, None)
        if len(self._cache) < self._max_cache_entries:
            return
        oldest = min(self._cache.items(), key=lambda item: item[1].expires_at)[0]
        self._cache.pop(oldest, None)


def build_runtime_from_env() -> SynapseKnowledgeRuntime:
    database_url = os.getenv("DATABASE_URL", "postgresql://synapse:synapse@localhost:55432/synapse")
    cache_ttl = _normalize_limit(
        os.getenv("SYNAPSE_MCP_CACHE_TTL_SEC", "5"),
        default=5,
        minimum=1,
        maximum=600,
    )
    cache_size = _normalize_limit(
        os.getenv("SYNAPSE_MCP_CACHE_MAX_ENTRIES", "5000"),
        default=5000,
        minimum=100,
        maximum=100_000,
    )
    graph_config = load_graph_config_from_env()
    store = PostgresKnowledgeStore(
        database_url=database_url,
        max_graph_hops=graph_config.max_graph_hops,
        graph_boost_hop1=graph_config.boost_hop1,
        graph_boost_hop2=graph_config.boost_hop2,
        graph_boost_hop3=graph_config.boost_hop3,
        graph_boost_other=graph_config.boost_other,
    )
    return SynapseKnowledgeRuntime(store, cache_ttl_seconds=cache_ttl, max_cache_entries=cache_size)
