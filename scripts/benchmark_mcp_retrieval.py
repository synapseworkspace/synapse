#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
import hashlib
import json
import random
import statistics
import time
from typing import Any
from uuid import uuid4


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark Synapse MCP retrieval latency/quality on seeded snapshot.")
    parser.add_argument("--project-id", default="mcp_bench", help="Project id used for benchmark seed and retrieval.")
    parser.add_argument("--database-url", default=None, help="Override DATABASE_URL.")
    parser.add_argument("--skip-seed", action="store_true", help="Do not seed benchmark dataset.")
    parser.add_argument("--replace", action="store_true", help="Delete existing benchmark project rows before seed.")
    parser.add_argument("--seed-pages", type=int, default=800, help="Number of wiki pages to seed.")
    parser.add_argument("--statements-per-page", type=int, default=3, help="Statements per seeded page.")
    parser.add_argument("--edge-fanout", type=int, default=1, help="Related entities per page (graph degree fanout).")
    parser.add_argument("--seed-random", type=int, default=42, help="Deterministic random seed.")
    parser.add_argument("--limit", type=int, default=10, help="search_knowledge limit per benchmark call.")
    parser.add_argument("--warmup", type=int, default=20, help="Warmup calls per case (not measured).")
    parser.add_argument("--iterations", type=int, default=200, help="Measured calls per case.")
    parser.add_argument("--max-graph-hops", type=int, default=3, help="Graph traversal max hops.")
    parser.add_argument("--graph-boost-hop1", type=float, default=0.20, help="Score boost for 1-hop neighbor.")
    parser.add_argument("--graph-boost-hop2", type=float, default=0.12, help="Score boost for 2-hop neighbor.")
    parser.add_argument("--graph-boost-hop3", type=float, default=0.06, help="Score boost for 3-hop neighbor.")
    parser.add_argument("--graph-boost-other", type=float, default=0.03, help="Score boost for >3 hops.")
    return parser.parse_args()


def _percentile_ms(samples_ns: list[int], pct: float) -> float:
    if not samples_ns:
        return 0.0
    rank = min(len(samples_ns) - 1, max(0, int(round((pct / 100.0) * (len(samples_ns) - 1)))))
    sorted_vals = sorted(samples_ns)
    return round(sorted_vals[rank] / 1_000_000.0, 3)


def _cleanup_project(conn, *, project_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM knowledge_snapshot_pages
            WHERE snapshot_id IN (SELECT id FROM knowledge_snapshots WHERE project_id = %s)
            """,
            (project_id,),
        )
        cur.execute("DELETE FROM knowledge_snapshots WHERE project_id = %s", (project_id,))
        cur.execute("DELETE FROM moderation_actions WHERE project_id = %s", (project_id,))
        cur.execute("DELETE FROM wiki_conflicts WHERE project_id = %s", (project_id,))
        cur.execute("DELETE FROM wiki_draft_changes WHERE project_id = %s", (project_id,))
        cur.execute(
            """
            DELETE FROM wiki_claim_links
            WHERE claim_id IN (SELECT id FROM claims WHERE project_id = %s)
               OR page_id IN (SELECT id FROM wiki_pages WHERE project_id = %s)
            """,
            (project_id, project_id),
        )
        cur.execute("DELETE FROM wiki_statements WHERE project_id = %s", (project_id,))
        cur.execute("DELETE FROM claims WHERE project_id = %s", (project_id,))
        cur.execute("DELETE FROM wiki_pages WHERE project_id = %s", (project_id,))


def _seed_project(
    conn,
    *,
    project_id: str,
    seed_pages: int,
    statements_per_page: int,
    edge_fanout: int,
    seed_random: int,
) -> dict[str, Any]:
    rng = random.Random(seed_random)
    page_count = max(10, int(seed_pages))
    statements_count = max(1, int(statements_per_page))
    fanout = max(1, int(edge_fanout))
    base = datetime(2026, 3, 31, 8, 0, 0, tzinfo=UTC)

    entity_keys = [f"entity_{idx:04d}" for idx in range(1, page_count + 1)]
    one_hop_entity = entity_keys[1]
    two_hop_entity = entity_keys[2]
    far_entity = entity_keys[min(page_count - 1, max(9, page_count // 2))]

    with conn.cursor() as cur:
        for idx, entity_key in enumerate(entity_keys):
            page_id = uuid4()
            title = f"Benchmark {entity_key.replace('_', ' ').title()}"
            slug = entity_key.replace("_", "-")
            page_type = "policy" if idx % 7 == 0 else "entity"

            related_entities: list[str] = []
            for hop in range(1, fanout + 1):
                related_entities.append(entity_keys[(idx + hop) % page_count])
            metadata = {"related_entities": related_entities}

            created_at = base + timedelta(seconds=idx)
            cur.execute(
                """
                INSERT INTO wiki_pages (
                  id, project_id, page_type, title, slug, entity_key, status, current_version, metadata, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'published', 1, %s, %s, %s)
                """,
                (page_id, project_id, page_type, title, slug, entity_key, json.dumps(metadata), created_at, created_at),
            )
            cur.execute(
                """
                INSERT INTO wiki_page_aliases (page_id, alias_text, created_at)
                VALUES (%s, %s, %s)
                """,
                (page_id, entity_key.replace("_", " "), created_at),
            )

            for stmt_idx in range(statements_count):
                statement_text = f"{entity_key} operational note {stmt_idx}: standard routing and dispatch."
                category = "operations"
                section_key = "operations"

                if entity_key == one_hop_entity and stmt_idx == 0:
                    statement_text = "benchmark_anchor card required handoff policy"
                    category = "access"
                    section_key = "access_rules"
                    page_type = "policy"
                elif entity_key == two_hop_entity and stmt_idx == 0:
                    statement_text = "benchmark_anchor card required handoff policy"
                    category = "operations"
                    section_key = "handoff_rules"
                    page_type = "policy"
                elif entity_key == far_entity and stmt_idx == 0:
                    statement_text = "benchmark_anchor card required handoff policy"
                    category = "operations"
                    section_key = "handoff_rules"
                    page_type = "policy"
                elif rng.random() < 0.12:
                    statement_text = f"{entity_key} card required for checkpoint #{stmt_idx}"
                    category = "access"
                    section_key = "access_rules"

                fingerprint = hashlib.sha1(
                    f"{project_id}|{entity_key}|{stmt_idx}|{statement_text}".encode("utf-8")
                ).hexdigest()
                claim_id = uuid4()
                statement_id = uuid4()
                created_stmt = created_at + timedelta(milliseconds=stmt_idx)

                cur.execute(
                    """
                    INSERT INTO claims (
                      id, project_id, entity_key, category, claim_text, confidence, status, metadata, claim_fingerprint, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, 'active', '{}'::jsonb, %s, %s, %s)
                    """,
                    (
                        claim_id,
                        project_id,
                        entity_key,
                        category,
                        statement_text,
                        0.9,
                        fingerprint,
                        created_stmt,
                        created_stmt,
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO wiki_statements (
                      id, project_id, page_id, section_key, statement_text, normalized_text, claim_fingerprint, status, metadata, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'active', '{}'::jsonb, %s, %s)
                    """,
                    (
                        statement_id,
                        project_id,
                        page_id,
                        section_key,
                        statement_text,
                        statement_text.strip().lower(),
                        fingerprint,
                        created_stmt,
                        created_stmt,
                    ),
                )

            if entity_key in {one_hop_entity, two_hop_entity, far_entity}:
                cur.execute(
                    """
                    UPDATE wiki_pages
                    SET page_type = 'policy', updated_at = NOW()
                    WHERE id = %s
                    """,
                    (page_id,),
                )

    return {
        "project_id": project_id,
        "pages_seeded": page_count,
        "statements_seeded": page_count * statements_count,
        "edge_fanout": fanout,
        "anchors": {
            "root_entity": entity_keys[0],
            "one_hop_entity": one_hop_entity,
            "two_hop_entity": two_hop_entity,
            "far_entity": far_entity,
        },
    }


def _run_case(
    *,
    store,
    project_id: str,
    case: dict[str, Any],
    warmup: int,
    iterations: int,
    limit: int,
) -> dict[str, Any]:
    args = {
        "project_id": project_id,
        "query": str(case["query"]),
        "limit": int(limit),
        "entity_key": case.get("entity_key"),
        "category": case.get("category"),
        "page_type": case.get("page_type"),
        "related_entity_key": case.get("related_entity_key"),
    }
    for _ in range(max(0, int(warmup))):
        store.search_knowledge(**args)

    samples_ns: list[int] = []
    top_entities: list[str | None] = []
    for _ in range(max(1, int(iterations))):
        started = time.perf_counter_ns()
        rows = store.search_knowledge(**args)
        elapsed = time.perf_counter_ns() - started
        samples_ns.append(elapsed)
        top = rows[0] if rows else {}
        page = top.get("page") if isinstance(top, dict) else {}
        top_entities.append(page.get("entity_key") if isinstance(page, dict) else None)

    expected = case.get("expected_top_entity")
    if expected is None:
        quality = None
    else:
        quality = round(sum(1 for entity in top_entities if entity == expected) / len(top_entities), 4)

    avg_ms = round((sum(samples_ns) / max(1, len(samples_ns))) / 1_000_000.0, 3)
    p50_ms = _percentile_ms(samples_ns, 50)
    p95_ms = _percentile_ms(samples_ns, 95)
    p99_ms = _percentile_ms(samples_ns, 99)
    throughput_qps = round(len(samples_ns) / (sum(samples_ns) / 1_000_000_000.0), 2) if samples_ns else 0.0
    return {
        "id": case.get("id"),
        "query": case.get("query"),
        "related_entity_key": case.get("related_entity_key"),
        "category": case.get("category"),
        "page_type": case.get("page_type"),
        "expected_top_entity": expected,
        "quality_top1_accuracy": quality,
        "latency_ms": {
            "avg": avg_ms,
            "p50": p50_ms,
            "p95": p95_ms,
            "p99": p99_ms,
        },
        "throughput_qps": throughput_qps,
        "observed_top_entities_sample": top_entities[:5],
    }


def main() -> None:
    args = parse_args()
    database_url = args.database_url or "postgresql://synapse:synapse@localhost:55432/synapse"

    try:
        import psycopg
    except Exception as exc:  # pragma: no cover
        raise SystemExit("Install psycopg[binary] to run benchmark script.") from exc
    try:
        from app.runtime import PostgresKnowledgeStore
    except Exception as exc:  # pragma: no cover
        raise SystemExit("Run with PYTHONPATH=services/mcp to import app.runtime.") from exc

    with psycopg.connect(database_url, autocommit=True) as conn:
        seed_summary: dict[str, Any] = {"status": "skipped"}
        if not args.skip_seed:
            if args.replace:
                _cleanup_project(conn, project_id=args.project_id)
            seed_summary = _seed_project(
                conn,
                project_id=args.project_id,
                seed_pages=args.seed_pages,
                statements_per_page=args.statements_per_page,
                edge_fanout=args.edge_fanout,
                seed_random=args.seed_random,
            )
            seed_summary["status"] = "seeded"

    store = PostgresKnowledgeStore(
        database_url=database_url,
        max_graph_hops=int(args.max_graph_hops),
        graph_boost_hop1=float(args.graph_boost_hop1),
        graph_boost_hop2=float(args.graph_boost_hop2),
        graph_boost_hop3=float(args.graph_boost_hop3),
        graph_boost_other=float(args.graph_boost_other),
    )

    anchors = seed_summary.get("anchors") or {}
    root_entity = anchors.get("root_entity", "entity_0001")
    one_hop_entity = anchors.get("one_hop_entity", "entity_0002")
    two_hop_entity = anchors.get("two_hop_entity", "entity_0003")

    benchmark_cases = [
        {
            "id": "baseline_no_graph_hint_ops",
            "query": "benchmark_anchor card required handoff policy",
            "category": "operations",
            "page_type": "policy",
        },
        {
            "id": "graph_hint_one_hop_access",
            "query": "benchmark_anchor card required handoff policy",
            "related_entity_key": root_entity,
            "category": "access",
            "page_type": "policy",
            "expected_top_entity": one_hop_entity,
        },
        {
            "id": "graph_hint_two_hop_ops",
            "query": "benchmark_anchor card required handoff policy",
            "related_entity_key": root_entity,
            "category": "operations",
            "page_type": "policy",
            "expected_top_entity": two_hop_entity,
        },
    ]

    cases = [
        _run_case(
            store=store,
            project_id=args.project_id,
            case=case,
            warmup=args.warmup,
            iterations=args.iterations,
            limit=args.limit,
        )
        for case in benchmark_cases
    ]

    avg_p95 = round(statistics.mean([case["latency_ms"]["p95"] for case in cases]), 3)
    quality_cases = [case for case in cases if case["quality_top1_accuracy"] is not None]
    quality_avg = round(statistics.mean([case["quality_top1_accuracy"] for case in quality_cases]), 4) if quality_cases else None
    output = {
        "status": "ok",
        "timestamp": datetime.now(UTC).isoformat(),
        "database_url_redacted": database_url.split("@")[-1],
        "project_id": args.project_id,
        "seed": seed_summary,
        "config": {
            "warmup": args.warmup,
            "iterations": args.iterations,
            "limit": args.limit,
            "max_graph_hops": args.max_graph_hops,
            "graph_boost_hop1": args.graph_boost_hop1,
            "graph_boost_hop2": args.graph_boost_hop2,
            "graph_boost_hop3": args.graph_boost_hop3,
            "graph_boost_other": args.graph_boost_other,
        },
        "summary": {
            "average_case_p95_ms": avg_p95,
            "average_quality_top1_accuracy": quality_avg,
        },
        "cases": cases,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
