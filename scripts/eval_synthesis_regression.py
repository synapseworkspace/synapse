#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.wiki_engine import (
    ClaimInput,
    PageRecord,
    SectionRecord,
    StatementRecord,
    WikiSynthesisEngine,
)


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _build_claim(payload: dict[str, Any]) -> ClaimInput:
    claim_payload = {
        "id": payload.get("id") or str(uuid.uuid4()),
        "project_id": payload.get("project_id") or "eval_project",
        "entity_key": payload.get("entity_key") or "unknown_entity",
        "category": payload.get("category") or "general",
        "claim_text": payload.get("claim_text") or "",
        "evidence": payload.get("evidence") or [],
        "observed_at": payload.get("observed_at"),
        "valid_from": payload.get("valid_from"),
        "valid_to": payload.get("valid_to"),
    }
    return ClaimInput.from_payload(claim_payload)


def _build_statements(engine: WikiSynthesisEngine, raw: list[dict[str, Any]]) -> list[StatementRecord]:
    rows: list[StatementRecord] = []
    for idx, item in enumerate(raw):
        statement_text = str(item.get("statement_text") or "").strip()
        statement_id = item.get("id")
        try:
            parsed_id = uuid.UUID(str(statement_id)) if statement_id else uuid.uuid4()
        except ValueError:
            parsed_id = uuid.uuid4()
        rows.append(
            StatementRecord(
                id=parsed_id,
                section_key=str(item.get("section_key") or "facts"),
                statement_text=statement_text,
                normalized_text=engine._normalize_text(statement_text),
                claim_fingerprint=str(item.get("claim_fingerprint") or f"fp_{idx}"),
                valid_from=_parse_dt(item.get("valid_from")),
                valid_to=_parse_dt(item.get("valid_to")),
            )
        )
    return rows


def _build_page_candidates(raw: list[dict[str, Any]]) -> list[PageRecord]:
    out: list[PageRecord] = []
    for idx, item in enumerate(raw):
        page_id = item.get("id")
        try:
            parsed_id = uuid.UUID(str(page_id)) if page_id else uuid.uuid5(uuid.NAMESPACE_URL, f"eval:page:{idx}")
        except ValueError:
            parsed_id = uuid.uuid5(uuid.NAMESPACE_URL, f"eval:page:{idx}")
        out.append(
            PageRecord(
                id=parsed_id,
                project_id=str(item.get("project_id") or "eval_project"),
                page_type=str(item.get("page_type") or "general"),
                title=str(item.get("title") or "Untitled"),
                slug=str(item.get("slug") or f"page-{idx}"),
                entity_key=str(item.get("entity_key") or ""),
                status=str(item.get("status") or "published"),
                aliases=[str(alias) for alias in item.get("aliases") or []],
            )
        )
    return out


def _build_sections(raw: list[dict[str, Any]]) -> list[SectionRecord]:
    return [
        SectionRecord(
            section_key=str(item.get("section_key") or "facts"),
            heading=str(item.get("heading") or "Facts"),
            order_index=int(item.get("order_index") or 0),
        )
        for item in raw
    ]


def _run_case(engine: WikiSynthesisEngine, case: dict[str, Any]) -> tuple[bool, str]:
    kind = str(case.get("kind") or "").strip()
    expected = case.get("expected") or {}
    case_id = str(case.get("id") or "unknown_case")

    if kind == "conflict":
        statements = _build_statements(engine, case.get("existing_statements") or [])
        conflict = engine._detect_conflict(
            str(case.get("incoming_text") or ""),
            statements,
            incoming_valid_from=_parse_dt(case.get("incoming_valid_from")),
            incoming_valid_to=_parse_dt(case.get("incoming_valid_to")),
        )
        has_conflict = conflict is not None
        if bool(expected.get("has_conflict")) != has_conflict:
            return False, f"{case_id}: expected has_conflict={expected.get('has_conflict')} got {has_conflict}"
        expected_type = expected.get("conflict_type")
        if expected_type is not None and conflict is not None and str(conflict[1]) != str(expected_type):
            return False, f"{case_id}: expected conflict_type={expected_type} got {conflict[1]}"
        return True, f"{case_id}: ok"

    if kind == "dedup":
        statements = _build_statements(engine, case.get("existing_statements") or [])
        decision = engine._deduplicate(
            claim_text=str(case.get("incoming_text") or ""),
            fingerprint=str(case.get("incoming_fingerprint") or "fp_unknown"),
            statements=statements,
            incoming_valid_from=_parse_dt(case.get("incoming_valid_from")),
            incoming_valid_to=_parse_dt(case.get("incoming_valid_to")),
        ).decision
        expected_decision = str(expected.get("decision"))
        if decision != expected_decision:
            return False, f"{case_id}: expected dedup decision={expected_decision} got {decision}"
        return True, f"{case_id}: ok"

    if kind == "page_resolution":
        claim = _build_claim(case.get("claim") or {})
        candidates = _build_page_candidates(case.get("candidates") or [])
        resolution = engine._resolve_page(claim, candidates)
        if resolution.mode != str(expected.get("mode")):
            return False, f"{case_id}: expected mode={expected.get('mode')} got {resolution.mode}"
        return True, f"{case_id}: ok"

    if kind == "section_resolution":
        sections = _build_sections(case.get("existing_sections") or [])
        section_key, _section_heading, created_new = engine._resolve_section(
            page_type=str(case.get("page_type") or "general"),
            category=str(case.get("category") or "general"),
            claim_text=str(case.get("claim_text") or ""),
            existing_sections=sections,
        )
        if section_key != str(expected.get("section_key")):
            return False, f"{case_id}: expected section_key={expected.get('section_key')} got {section_key}"
        if bool(expected.get("created_new")) != created_new:
            return False, f"{case_id}: expected created_new={expected.get('created_new')} got {created_new}"
        return True, f"{case_id}: ok"

    if kind == "temporal_parse":
        claim = _build_claim(case.get("claim") or {})
        valid_from, valid_to, source = engine._resolve_claim_valid_window(claim)
        expected_source = expected.get("source")
        if expected_source is not None and source != str(expected_source):
            return False, f"{case_id}: expected source={expected_source} got {source}"

        expected_from_prefix = expected.get("valid_from_prefix")
        if expected_from_prefix is None:
            if valid_from is not None:
                return False, f"{case_id}: expected valid_from=None got {valid_from.isoformat()}"
        else:
            actual = valid_from.isoformat() if valid_from is not None else None
            if actual is None or not actual.startswith(str(expected_from_prefix)):
                return False, f"{case_id}: expected valid_from prefix={expected_from_prefix} got {actual}"

        expected_to_prefix = expected.get("valid_to_prefix")
        if expected_to_prefix is None:
            if valid_to is not None:
                return False, f"{case_id}: expected valid_to=None got {valid_to.isoformat()}"
        else:
            actual = valid_to.isoformat() if valid_to is not None else None
            if actual is None or not actual.startswith(str(expected_to_prefix)):
                return False, f"{case_id}: expected valid_to prefix={expected_to_prefix} got {actual}"

        return True, f"{case_id}: ok"

    if kind == "backfill_inference":
        payload = case.get("payload") or {}
        event_id_raw = case.get("event_id")
        try:
            event_id = uuid.UUID(str(event_id_raw)) if event_id_raw else uuid.uuid4()
        except ValueError:
            event_id = uuid.uuid4()
        claim_payload = engine._claim_payload_from_backfill_event(
            event_id=event_id,
            project_id=str(case.get("project_id") or "eval_project"),
            agent_id=case.get("agent_id"),
            session_id=case.get("session_id"),
            payload=payload if isinstance(payload, dict) else {},
            observed_at=_parse_dt(case.get("observed_at")),
        )
        should_generate = bool(expected.get("should_generate", True))
        if should_generate and claim_payload is None:
            return False, f"{case_id}: expected generated payload, got None"
        if not should_generate and claim_payload is not None:
            return False, f"{case_id}: expected None payload, got generated claim"
        if claim_payload is None:
            return True, f"{case_id}: ok"

        expected_entity = expected.get("entity_key")
        if expected_entity is not None and str(claim_payload.get("entity_key")) != str(expected_entity):
            return (
                False,
                f"{case_id}: expected entity_key={expected_entity} got {claim_payload.get('entity_key')}",
            )
        expected_category = expected.get("category")
        if expected_category is not None and str(claim_payload.get("category")) != str(expected_category):
            return (
                False,
                f"{case_id}: expected category={expected_category} got {claim_payload.get('category')}",
            )

        expected_entity_source = expected.get("entity_inference_source")
        expected_category_source = expected.get("category_inference_source")
        evidence = claim_payload.get("evidence") or []
        first = evidence[0] if isinstance(evidence, list) and evidence else {}
        if expected_entity_source is not None and str(first.get("entity_inference_source")) != str(expected_entity_source):
            return (
                False,
                f"{case_id}: expected entity_inference_source={expected_entity_source} got {first.get('entity_inference_source')}",
            )
        if expected_category_source is not None and str(first.get("category_inference_source")) != str(expected_category_source):
            return (
                False,
                f"{case_id}: expected category_inference_source={expected_category_source} got {first.get('category_inference_source')}",
            )
        return True, f"{case_id}: ok"

    return False, f"{case_id}: unknown kind={kind}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic synthesis regression dataset.")
    parser.add_argument(
        "--dataset",
        default="eval/synthesis_cases.json",
        help="Path to synthesis evaluator dataset JSON file",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print compact summary without per-case result payloads.",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(json.dumps({"status": "error", "error": "dataset_not_found", "dataset": str(dataset_path)}))
        sys.exit(2)

    raw = json.loads(dataset_path.read_text(encoding="utf-8"))
    cases = raw.get("cases") or []
    engine = WikiSynthesisEngine()

    results: list[dict[str, Any]] = []
    passed = 0
    failed = 0
    for case in cases:
        ok, message = _run_case(engine, case)
        results.append({"id": case.get("id"), "ok": ok, "message": message})
        if ok:
            passed += 1
        else:
            failed += 1

    summary = {
        "status": "ok" if failed == 0 else "failed",
        "dataset": str(dataset_path),
        "total": len(cases),
        "passed": passed,
        "failed": failed,
    }
    if args.summary_only:
        summary["failed_case_ids"] = [str(item.get("id")) for item in results if not item.get("ok")]
    else:
        summary["results"] = results
    print(json.dumps(summary, indent=2))
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
