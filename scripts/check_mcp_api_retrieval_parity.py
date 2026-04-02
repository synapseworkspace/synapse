#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SERVICES_ROOT = ROOT / "services"
API_MAIN_PATH = SERVICES_ROOT / "api" / "app" / "main.py"
MCP_RUNTIME_PATH = SERVICES_ROOT / "mcp" / "app" / "runtime.py"

if str(SERVICES_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICES_ROOT))

from shared.retrieval import (
    RetrievalContextPolicyConfig,
    RetrievalGraphConfig,
    build_retrieval_explain_fields,
    build_retrieval_search_plan,
)


def _load_mcp_runtime_module():
    spec = importlib.util.spec_from_file_location("synapse_mcp_runtime_parity", MCP_RUNTIME_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load MCP runtime module from {MCP_RUNTIME_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _FakeCursor:
    def __init__(self, *, rows: list[tuple[Any, ...]], capture: dict[str, Any]) -> None:
        self._rows = rows
        self._capture = capture

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        self._capture["sql"] = sql
        self._capture["params"] = params

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._rows)


class _FakeConn:
    def __init__(self, *, rows: list[tuple[Any, ...]], capture: dict[str, Any]) -> None:
        self._rows = rows
        self._capture = capture

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return _FakeCursor(rows=self._rows, capture=self._capture)


def _assert_api_uses_shared_retrieval_contract() -> None:
    source = API_MAIN_PATH.read_text(encoding="utf-8")
    required = (
        "from shared.retrieval import",
        "build_retrieval_search_plan(",
        "build_retrieval_explain_fields(",
        "load_graph_config_from_env(",
    )
    forbidden = (
        "def _build_retrieval_explain_fields(",
        "def _query_tokens(",
        "def _token_overlap(",
    )
    for fragment in required:
        assert fragment in source, f"missing API retrieval parity fragment: {fragment}"
    for fragment in forbidden:
        assert fragment not in source, f"API still carries duplicated retrieval helper: {fragment}"


def main() -> int:
    _assert_api_uses_shared_retrieval_contract()
    runtime_module = _load_mcp_runtime_module()
    PostgresKnowledgeStore = runtime_module.PostgresKnowledgeStore
    SynapseKnowledgeRuntime = runtime_module.SynapseKnowledgeRuntime

    graph_config = RetrievalGraphConfig(
        max_graph_hops=4,
        boost_hop1=0.31,
        boost_hop2=0.19,
        boost_hop3=0.11,
        boost_other=0.05,
    )
    query_args = {
        "project_id": "omega_demo",
        "query": "omega gate card",
        "limit": 7,
        "entity_key": "bc_omega",
        "category": "delivery_rules",
        "page_type": "location",
        "related_entity_key": "warehouse_1",
    }

    expected_plan = build_retrieval_search_plan(
        graph_config=graph_config,
        **query_args,
    )
    assert expected_plan is not None

    sample_rows = [
        (
            "st-1",
            "BC Omega gate requires physical card after 10:00.",
            "Access",
            datetime(2026, 4, 2, 12, 0, tzinfo=UTC),
            None,
            datetime(2026, 4, 2, 12, 5, tzinfo=UTC),
            "page-1",
            "BC Omega",
            "regions/bc-omega",
            "bc_omega",
            "location",
            "delivery_rules",
            1.42,
            1,
            0.31,
        )
    ]

    mcp_capture: dict[str, Any] = {}
    mcp_store = PostgresKnowledgeStore(
        database_url="postgresql://unused",
        max_graph_hops=graph_config.max_graph_hops,
        graph_boost_hop1=graph_config.boost_hop1,
        graph_boost_hop2=graph_config.boost_hop2,
        graph_boost_hop3=graph_config.boost_hop3,
        graph_boost_other=graph_config.boost_other,
    )
    mcp_store._conn = lambda: _FakeConn(rows=sample_rows, capture=mcp_capture)
    mcp_rows = mcp_store.search_knowledge(**query_args)
    assert mcp_capture.get("sql", "").strip() == expected_plan.sql.strip()
    assert mcp_capture.get("params") == expected_plan.params
    assert len(mcp_rows) == 1, mcp_rows

    class _RuntimeFakeStore:
        def get_project_revision(self, project_id: str) -> str:
            return "snapshot:r1"

        def search_knowledge(self, **kwargs):
            return list(mcp_rows)

        def get_entity_facts(self, **kwargs):
            return []

        def get_recent_changes(self, **kwargs):
            return []

        def explain_conflicts(self, **kwargs):
            return []

        def get_open_tasks(self, **kwargs):
            return []

        def get_task_details(self, **kwargs):
            return None

    policy = RetrievalContextPolicyConfig(mode="advisory")
    runtime = SynapseKnowledgeRuntime(
        _RuntimeFakeStore(),
        cache_ttl_seconds=30,
        max_cache_entries=128,
        context_policy=policy,
    )
    mcp_payload = runtime.search_knowledge(**query_args)
    mcp_result = mcp_payload["results"][0]
    expected_runtime_result = build_retrieval_explain_fields(
        query=query_args["query"],
        related_entity_key=query_args["related_entity_key"],
        result=mcp_rows[0],
        query_tokens_override=expected_plan.query_tokens,
        context_policy=policy,
    )
    assert expected_runtime_result["score_breakdown"] == mcp_result["score_breakdown"]
    assert expected_runtime_result["retrieval_reason"] == mcp_result["retrieval_reason"]
    assert expected_runtime_result["retrieval_confidence"] == mcp_result["retrieval_confidence"]
    assert expected_runtime_result["context_policy"] == mcp_result["context_policy"]

    print("mcp/api retrieval parity smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
