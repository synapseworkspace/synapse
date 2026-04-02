#!/usr/bin/env python3
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any

from app.legacy_import import LegacySeedOrchestrator


def _safe_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _record_view(record: dict[str, Any]) -> dict[str, Any]:
    metadata = _safe_dict(record.get("metadata"))
    plan = _safe_dict(metadata.get("synapse_seed_plan"))
    return {
        "entity_key": record.get("entity_key"),
        "category": record.get("category"),
        "space_key": plan.get("space_key"),
        "page_slug": plan.get("page_slug"),
        "section_key": plan.get("section_key"),
        "section_heading": plan.get("section_heading"),
        "group_mode": plan.get("group_mode"),
        "page_title": plan.get("page_title"),
    }


def _records_by_source_id(records: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    out: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []
    for record in records:
        source_id = str(record.get("source_id") or "").strip()
        if not source_id:
            continue
        if source_id in out:
            duplicates.append(source_id)
            continue
        out[source_id] = record
    return out, duplicates


def _normalize_top_pages(summary: dict[str, Any]) -> list[dict[str, Any]]:
    raw = summary.get("top_pages")
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "page_slug": str(item.get("page_slug") or ""),
                "records": int(item.get("records") or 0),
                "categories": sorted(str(x) for x in (item.get("categories") or []) if str(x).strip()),
                "section_keys": sorted(str(x) for x in (item.get("section_keys") or []) if str(x).strip()),
            }
        )
    return out


def _deterministic_signature(records: list[dict[str, Any]]) -> list[tuple[str, str, str, str, str, str]]:
    out: list[tuple[str, str, str, str, str, str]] = []
    for record in records:
        source_id = str(record.get("source_id") or "").strip()
        if not source_id:
            continue
        view = _record_view(record)
        out.append(
            (
                source_id,
                str(view.get("entity_key") or ""),
                str(view.get("category") or ""),
                str(view.get("page_slug") or ""),
                str(view.get("section_key") or ""),
                str(view.get("group_mode") or ""),
            )
        )
    out.sort(key=lambda item: item[0])
    return out


def _run_case(case: dict[str, Any]) -> tuple[bool, str]:
    case_id = str(case.get("id") or "unknown_case")
    source_type = str(case.get("source_type") or "local_dir")
    source_ref = str(case.get("source_ref") or "/tmp/legacy")
    config = _safe_dict(case.get("config"))
    records_raw = case.get("records")
    expected = _safe_dict(case.get("expected"))
    records = [item for item in (records_raw if isinstance(records_raw, list) else []) if isinstance(item, dict)]

    orchestrator = LegacySeedOrchestrator()
    run_a = orchestrator.apply(
        records=deepcopy(records),
        source_type=source_type,
        source_ref=source_ref,
        project_id="eval_project",
        source_id=f"{case_id}:source",
        run_id=f"{case_id}:run_a",
        config=config,
    )

    # Determinism check: page targeting must stay stable even if input order changes.
    run_b = orchestrator.apply(
        records=list(reversed(deepcopy(records))),
        source_type=source_type,
        source_ref=source_ref,
        project_id="eval_project",
        source_id=f"{case_id}:source",
        run_id=f"{case_id}:run_b",
        config=config,
    )

    signature_a = _deterministic_signature(run_a.records)
    signature_b = _deterministic_signature(run_b.records)
    if signature_a != signature_b:
        return False, f"{case_id}: non-deterministic seed targeting across input order"

    by_source_id, duplicates = _records_by_source_id(run_a.records)
    if duplicates:
        return False, f"{case_id}: duplicate source_id in output: {sorted(set(duplicates))}"

    expected_summary = _safe_dict(expected.get("summary"))
    for key, expected_value in expected_summary.items():
        actual_value = run_a.summary.get(key)
        if actual_value != expected_value:
            return False, f"{case_id}: summary.{key} expected={expected_value!r} got={actual_value!r}"

    expected_records = _safe_dict(expected.get("by_source_id"))
    for source_id, spec in expected_records.items():
        if source_id not in by_source_id:
            return False, f"{case_id}: expected source_id={source_id!r} not found in output"
        view = _record_view(by_source_id[source_id])
        for field, expected_value in _safe_dict(spec).items():
            actual_value = view.get(field)
            if actual_value != expected_value:
                return (
                    False,
                    f"{case_id}: {source_id}.{field} expected={expected_value!r} got={actual_value!r}",
                )

    expected_top_pages_raw = expected.get("top_pages")
    if isinstance(expected_top_pages_raw, list):
        expected_top_pages: list[dict[str, Any]] = []
        for item in expected_top_pages_raw:
            if not isinstance(item, dict):
                continue
            expected_top_pages.append(
                {
                    "page_slug": str(item.get("page_slug") or ""),
                    "records": int(item.get("records") or 0),
                    "categories": sorted(str(x) for x in (item.get("categories") or []) if str(x).strip()),
                    "section_keys": sorted(str(x) for x in (item.get("section_keys") or []) if str(x).strip()),
                }
            )
        actual_top_pages = _normalize_top_pages(run_a.summary)
        if actual_top_pages != expected_top_pages:
            return (
                False,
                f"{case_id}: top_pages mismatch expected={expected_top_pages!r} got={actual_top_pages!r}",
            )

    return True, f"{case_id}: ok"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic Legacy seed-planning regression dataset.")
    parser.add_argument(
        "--dataset",
        default="eval/legacy_seed_cases.json",
        help="Path to legacy seed regression dataset JSON file.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print compact summary without per-case messages.",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(json.dumps({"status": "error", "error": "dataset_not_found", "dataset": str(dataset_path)}))
        sys.exit(2)

    try:
        raw = json.loads(dataset_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": "dataset_parse_failed",
                    "dataset": str(dataset_path),
                    "message": str(exc),
                }
            )
        )
        sys.exit(2)

    cases = raw.get("cases")
    if not isinstance(cases, list):
        print(json.dumps({"status": "error", "error": "invalid_dataset_cases", "dataset": str(dataset_path)}))
        sys.exit(2)

    results: list[dict[str, Any]] = []
    passed = 0
    failed = 0
    for case in cases:
        if not isinstance(case, dict):
            failed += 1
            results.append({"id": "invalid_case", "ok": False, "message": "case is not an object"})
            continue
        ok, message = _run_case(case)
        if ok:
            passed += 1
        else:
            failed += 1
        results.append({"id": str(case.get("id") or "unknown_case"), "ok": ok, "message": message})

    output: dict[str, Any] = {
        "status": "ok" if failed == 0 else "failed",
        "dataset": str(dataset_path),
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "failed_case_ids": [item["id"] for item in results if not item["ok"]],
    }
    if not args.summary_only:
        output["results"] = results

    print(json.dumps(output, ensure_ascii=False, indent=2))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
