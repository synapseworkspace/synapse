#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _http_json(
    base_url: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout_s: float,
) -> dict[str, Any]:
    headers = {"content-type": "application/json"}
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib_request.Request(f"{base_url}{path}", data=body, headers=headers, method=method)
    try:
        with urllib_request.urlopen(request, timeout=timeout_s) as response:
            raw = response.read().decode("utf-8")
            parsed = json.loads(raw) if raw else {}
            return {
                "status": int(response.getcode()),
                "json": parsed if isinstance(parsed, dict) else {},
                "text": raw,
            }
    except urllib_error.HTTPError as err:
        raw = err.read().decode("utf-8") if err.fp is not None else ""
        parsed = json.loads(raw) if raw else {}
        return {
            "status": int(err.code),
            "json": parsed if isinstance(parsed, dict) else {},
            "text": raw,
        }


def _api_get(base_url: str, path: str, *, timeout_s: float) -> dict[str, Any]:
    response = _http_json(base_url, "GET", path, timeout_s=timeout_s)
    _assert(response["status"] == 200, f"GET {path} failed: {response['status']} {response['text']}")
    return response["json"]


def _api_post(base_url: str, path: str, payload: dict[str, Any], *, timeout_s: float) -> dict[str, Any]:
    response = _http_json(base_url, "POST", path, payload, timeout_s=timeout_s)
    _assert(response["status"] == 200, f"POST {path} failed: {response['status']} {response['text']}")
    return response["json"]


def _api_put(base_url: str, path: str, payload: dict[str, Any], *, timeout_s: float) -> dict[str, Any]:
    response = _http_json(base_url, "PUT", path, payload, timeout_s=timeout_s)
    _assert(response["status"] == 200, f"PUT {path} failed: {response['status']} {response['text']}")
    return response["json"]


def _wait_for_api(base_url: str, *, timeout_s: float, request_timeout_s: float) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        response = _http_json(base_url, "GET", "/health", timeout_s=request_timeout_s)
        status_value = str((response.get("json") or {}).get("status") or "").lower()
        if response["status"] == 200 and status_value in {"ok", "degraded"}:
            return
        time.sleep(1.0)
    raise RuntimeError(f"API at {base_url} did not become ready in time")


def _query(params: dict[str, Any]) -> str:
    filtered = {key: value for key, value in params.items() if value is not None}
    return urllib_parse.urlencode(filtered, doseq=True)


def _runs_for_source(runs: list[dict[str, Any]], source_id: str) -> list[dict[str, Any]]:
    return [item for item in runs if str(item.get("source_id") or "") == source_id]


def main() -> int:
    parser = argparse.ArgumentParser(description="E2E: connector -> queued legacy sync run -> processed -> pipeline visibility.")
    parser.add_argument("--api-url", default="http://127.0.0.1:8080")
    parser.add_argument("--project-id", default=None)
    parser.add_argument(
        "--legacy-sql-dsn",
        default="postgresql://synapse:synapse@postgres:5432/synapse",
        help="DSN used by worker for postgres_sql connector source.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--poll-interval-seconds", type=float, default=2.0)
    parser.add_argument("--request-timeout-seconds", type=float, default=15.0)
    args = parser.parse_args()

    api_url = str(args.api_url).rstrip("/")
    project_id = str(args.project_id or f"legacy_sync_e2e_{int(time.time())}")
    timeout_s = max(30.0, float(args.timeout_seconds))
    poll_interval_s = max(0.5, float(args.poll_interval_seconds))
    request_timeout_s = max(2.0, float(args.request_timeout_seconds))
    legacy_sql_dsn = str(args.legacy_sql_dsn).strip()

    _wait_for_api(api_url, timeout_s=timeout_s, request_timeout_s=request_timeout_s)

    # Seed one memory record so events table has deterministic rows for connector query.
    seed_record_id = f"legacy-sync-seed-{uuid.uuid4()}"
    _api_post(
        api_url,
        "/v1/backfill/memory",
        {
            "batch": {
                "project_id": project_id,
                "source_system": "legacy_sync_e2e_seed",
                "created_by": "integration_legacy_sync",
                "finalize": True,
                "records": [
                    {
                        "source_id": seed_record_id,
                        "content": "Customer Omega requires gate key-card access after 18:00.",
                        "entity_key": "customer_omega",
                        "category": "access_policy",
                        "observed_at": datetime.now(UTC).isoformat(),
                        "metadata": {"namespace": "ops.memory", "seed": True},
                    }
                ],
            }
        },
        timeout_s=request_timeout_s,
    )

    source_response = _api_put(
        api_url,
        "/v1/legacy-import/sources",
        {
            "project_id": project_id,
            "source_type": "postgres_sql",
            "source_ref": "events_connector_e2e",
            "enabled": True,
            "sync_interval_minutes": 5,
            "config": {
                "sql_dsn": legacy_sql_dsn,
                "sql_query": (
                    "SELECT "
                    "id::text AS source_id, "
                    "('event_type=' || event_type || '; payload=' || payload::text) AS content, "
                    "observed_at, "
                    "COALESCE(NULLIF(session_id, ''), NULLIF(agent_id, ''), 'legacy_sync_e2e') AS entity_key, "
                    "'operations' AS category, "
                    "jsonb_build_object('from_events_table', true, 'event_type', event_type) AS metadata "
                    "FROM events "
                    "WHERE project_id = %(project_id)s "
                    "ORDER BY observed_at DESC "
                    "LIMIT 200"
                ),
                "sql_query_params": {"project_id": project_id},
                "sql_source_id_prefix": "legacy_sync_e2e",
                "source_system": "legacy_sync:postgres_sql:e2e",
                "curated_import": {
                    "enabled": True,
                    "source_systems": ["legacy_sync:postgres_sql:e2e"],
                    "noise_preset": "off",
                    "drop_event_like": False,
                },
            },
            "updated_by": "integration_legacy_sync",
        },
        timeout_s=request_timeout_s,
    )
    source = source_response.get("source") if isinstance(source_response.get("source"), dict) else {}
    source_id = str(source.get("id") or "")
    _assert(source_id, "legacy source upsert returned empty source id")

    # Ensure starter pages are published so pages stage is always represented in pipeline visibility.
    _api_post(
        api_url,
        "/v1/adoption/first-run/bootstrap",
        {
            "project_id": project_id,
            "created_by": "integration_legacy_sync",
            "profile": "support_ops",
            "publish": True,
        },
        timeout_s=request_timeout_s,
    )

    sync_response = _api_post(
        api_url,
        "/v1/adoption/sync-presets/execute",
        {
            "project_id": project_id,
            "confirm_project_id": project_id,
            "updated_by": "integration_legacy_sync",
            "reviewed_by": "integration_legacy_sync",
            "dry_run": False,
            "queue_enabled_sources": True,
            "run_bootstrap_approve": False,
            "include_starter_pages": False,
            "apply_bootstrap_profile": False,
            "sync_processor_lookback_minutes": 30,
            "fail_on_sync_processor_unavailable": False,
        },
        timeout_s=request_timeout_s,
    )
    sync_queue = sync_response.get("sync_queue") if isinstance(sync_response.get("sync_queue"), dict) else {}
    processor_state = sync_response.get("sync_queue_processor") if isinstance(sync_response.get("sync_queue_processor"), dict) else {}
    warnings = sync_response.get("warnings") if isinstance(sync_response.get("warnings"), list) else []
    explainability = sync_response.get("explainability") if isinstance(sync_response.get("explainability"), dict) else {}
    reason_buckets = explainability.get("reason_buckets") if isinstance(explainability.get("reason_buckets"), dict) else {}
    _assert(bool(reason_buckets), f"sync preset explainability reason_buckets missing: {json.dumps(sync_response, ensure_ascii=False)}")
    _assert(
        isinstance(sync_response.get("pipeline_visibility"), dict),
        f"sync preset pipeline_visibility missing: {json.dumps(sync_response, ensure_ascii=False)}",
    )
    _assert(
        isinstance(sync_response.get("rejection_diagnostics"), dict),
        f"sync preset rejection_diagnostics missing: {json.dumps(sync_response, ensure_ascii=False)}",
    )
    queued_now = int(sync_queue.get("queued") or 0)
    already_queued = int(sync_queue.get("already_queued") or 0)
    _assert(
        queued_now + already_queued > 0,
        f"sync preset did not queue legacy source run: {json.dumps(sync_response, ensure_ascii=False)}",
    )
    if str(processor_state.get("status") or "") == "unavailable":
        has_processor_warning = any(
            isinstance(item, dict) and str(item.get("code") or "") == "legacy_sync_processor_unavailable"
            for item in warnings
        )
        _assert(has_processor_warning, f"expected hard warning for unavailable sync processor: {json.dumps(sync_response, ensure_ascii=False)}")

    deadline = time.time() + timeout_s
    run_status: dict[str, Any] | None = None
    while time.time() < deadline:
        params = _query({"project_id": project_id, "limit": 100})
        runs_response = _api_get(api_url, f"/v1/legacy-import/runs?{params}", timeout_s=request_timeout_s)
        runs = runs_response.get("runs") if isinstance(runs_response.get("runs"), list) else []
        source_runs = _runs_for_source([item for item in runs if isinstance(item, dict)], source_id)
        if source_runs:
            completed = next((item for item in source_runs if str(item.get("status") or "") == "completed"), None)
            if completed is not None:
                run_status = completed
                break
            running_or_queued = any(str(item.get("status") or "") in {"queued", "running"} for item in source_runs)
            failed = next((item for item in source_runs if str(item.get("status") or "") == "failed"), None)
            if failed is not None and not running_or_queued:
                raise RuntimeError(f"legacy sync run failed: {json.dumps(failed, ensure_ascii=False)}")
            skipped = next((item for item in source_runs if str(item.get("status") or "") == "skipped"), None)
            if skipped is not None and not running_or_queued:
                run_status = skipped
                break
        time.sleep(poll_interval_s)

    _assert(run_status is not None, "legacy sync run did not reach completed status before timeout")
    if str(run_status.get("status") or "") == "completed":
        _assert(int(run_status.get("records_uploaded") or 0) > 0, f"legacy sync uploaded 0 records: {json.dumps(run_status, ensure_ascii=False)}")

    # Ensure claims stage has at least one deterministic item (worker extracts this queued claim).
    _api_post(
        api_url,
        "/v1/facts/proposals",
        {
            "claim": {
                "id": str(uuid.uuid4()),
                "schema_version": "v1",
                "project_id": project_id,
                "entity_key": "customer_omega",
                "category": "access_policy",
                "claim_text": "Gate access policy changed: key-card required after 18:00.",
                "status": "draft",
                "evidence": [
                    {
                        "source_system": "integration_legacy_sync",
                        "snippet": "Imported from legacy connector e2e.",
                    }
                ],
            }
        },
        timeout_s=request_timeout_s,
    )

    pipeline_snapshot: dict[str, Any] | None = None
    while time.time() < deadline:
        params = _query({"project_id": project_id, "days": 7})
        visibility = _api_get(api_url, f"/v1/adoption/pipeline/visibility?{params}", timeout_s=request_timeout_s)
        pipeline = visibility.get("pipeline") if isinstance(visibility.get("pipeline"), dict) else {}
        events_count = int(pipeline.get("events") or 0)
        claims_count = int(pipeline.get("claims") or 0)
        pages_count = int(pipeline.get("pages") or 0)
        pipeline_snapshot = visibility
        if events_count > 0 and claims_count > 0 and pages_count > 0:
            break
        time.sleep(poll_interval_s)

    _assert(pipeline_snapshot is not None, "pipeline visibility polling returned no snapshots")
    pipeline = pipeline_snapshot.get("pipeline") if isinstance(pipeline_snapshot.get("pipeline"), dict) else {}
    _assert(int(pipeline.get("events") or 0) > 0, f"pipeline events stayed at 0: {json.dumps(pipeline_snapshot, ensure_ascii=False)}")
    _assert(int(pipeline.get("claims") or 0) > 0, f"pipeline claims stayed at 0: {json.dumps(pipeline_snapshot, ensure_ascii=False)}")
    _assert(int(pipeline.get("pages") or 0) > 0, f"pipeline pages stayed at 0: {json.dumps(pipeline_snapshot, ensure_ascii=False)}")

    # Regression guard #55: adoption KPI endpoint should not fail on fresh self-host.
    kpi_params = _query({"project_id": project_id, "days": 30})
    kpi_payload = _api_get(api_url, f"/v1/adoption/kpi?{kpi_params}", timeout_s=request_timeout_s)
    kpi_metrics = kpi_payload.get("kpi") if isinstance(kpi_payload.get("kpi"), dict) else {}
    _assert(kpi_payload.get("project_id") == project_id, f"adoption KPI returned unexpected project id: {json.dumps(kpi_payload, ensure_ascii=False)}")
    _assert(
        isinstance(kpi_metrics.get("draft_noise_ratio"), (int, float)),
        f"adoption KPI missing draft_noise_ratio metric: {json.dumps(kpi_payload, ensure_ascii=False)}",
    )

    # Regression guard #56: fallback space reroute must not leave broken wiki links in Data Sources Catalog.
    _api_put(
        api_url,
        "/v1/wiki/spaces/operations/policy",
        {
            "project_id": project_id,
            "space_key": "operations",
            "updated_by": "integration_legacy_sync",
            "write_mode": "owners_only",
            "comment_mode": "open",
            "review_assignment_required": False,
        },
        timeout_s=request_timeout_s,
    )
    _api_put(
        api_url,
        "/v1/wiki/spaces/logistics/policy",
        {
            "project_id": project_id,
            "space_key": "logistics",
            "updated_by": "integration_legacy_sync",
            "write_mode": "open",
            "comment_mode": "open",
            "review_assignment_required": False,
        },
        timeout_s=request_timeout_s,
    )
    bootstrap_payload = _api_post(
        api_url,
        "/v1/adoption/agent-wiki-bootstrap",
        {
            "project_id": project_id,
            "updated_by": "integration_legacy_sync",
            "dry_run": False,
            "confirm_project_id": project_id,
            "publish": True,
            "space_key": "operations",
            "include_data_sources_catalog": True,
            "include_agent_capability_profile": False,
            "include_operational_logic": False,
            "include_first_run_starter": False,
            "max_sources": 25,
            "max_agents": 10,
            "max_signals": 10,
        },
        timeout_s=request_timeout_s,
    )
    fallback_info = bootstrap_payload.get("policy_space_fallback") if isinstance(bootstrap_payload.get("policy_space_fallback"), dict) else {}
    applied_fallbacks = fallback_info.get("applied") if isinstance(fallback_info.get("applied"), list) else []
    _assert(
        any(
            str(item.get("from_slug") or "").startswith("operations/")
            and str(item.get("to_slug") or "").startswith("logistics/")
            for item in applied_fallbacks
            if isinstance(item, dict)
        ),
        f"expected operations -> logistics fallback entries in bootstrap response: {json.dumps(bootstrap_payload, ensure_ascii=False)}",
    )
    catalog_params = _query({"project_id": project_id})
    catalog_page = _api_get(
        api_url,
        f"/v1/wiki/pages/logistics/data-sources-catalog?{catalog_params}",
        timeout_s=request_timeout_s,
    )
    latest_version = catalog_page.get("latest_version") if isinstance(catalog_page.get("latest_version"), dict) else {}
    catalog_markdown = str(latest_version.get("markdown") or "")
    _assert(
        "/wiki/operations/source-" not in catalog_markdown,
        f"catalog markdown still contains broken operations links after fallback: {catalog_markdown}",
    )
    _assert(
        "/wiki/logistics/source-" in catalog_markdown,
        f"catalog markdown missing rewritten logistics source links: {catalog_markdown}",
    )

    output = {
        "status": "ok",
        "project_id": project_id,
        "legacy_source_id": source_id,
        "legacy_sync_run": {
            "id": run_status.get("id"),
            "status": run_status.get("status"),
            "records_collected": int(run_status.get("records_collected") or 0),
            "records_uploaded": int(run_status.get("records_uploaded") or 0),
        },
        "pipeline": pipeline,
        "adoption_kpi": {
            "time_to_first_draft_sec": kpi_metrics.get("time_to_first_draft_sec"),
            "time_to_first_publish_sec": kpi_metrics.get("time_to_first_publish_sec"),
            "draft_noise_ratio": kpi_metrics.get("draft_noise_ratio"),
            "publish_revert_rate": kpi_metrics.get("publish_revert_rate"),
        },
        "bootstrap_fallback_applied_count": len(applied_fallbacks),
        "generated_at": datetime.now(UTC).isoformat(),
    }
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
