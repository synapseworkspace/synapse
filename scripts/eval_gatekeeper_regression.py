#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any

from app.wiki_engine import ClaimInput, GatekeeperConfig, GatekeeperLLMAssessment, WikiSynthesisEngine

CANONICAL_TIERS = ["operational_memory", "insight_candidate", "golden_candidate"]


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


def _clamped_config(engine: WikiSynthesisEngine, payload: dict[str, Any]) -> GatekeeperConfig:
    return GatekeeperConfig(
        min_sources_for_golden=max(
            2,
            int(payload.get("min_sources_for_golden", engine.gatekeeper_min_sources_for_golden)),
        ),
        conflict_free_days=max(
            1,
            int(payload.get("conflict_free_days", engine.gatekeeper_conflict_free_days)),
        ),
        min_score_for_golden=max(
            0.0,
            min(1.0, float(payload.get("min_score_for_golden", engine.gatekeeper_min_score_for_golden))),
        ),
        operational_short_text_len=max(
            8,
            int(payload.get("operational_short_text_len", engine.gatekeeper_operational_short_text_len)),
        ),
        operational_short_token_len=max(
            1,
            int(payload.get("operational_short_token_len", engine.gatekeeper_operational_short_token_len)),
        ),
        llm_assist_enabled=bool(payload.get("llm_assist_enabled", engine.gatekeeper_llm_assist_enabled)),
        llm_provider=str(payload.get("llm_provider", engine.gatekeeper_llm_provider) or "openai"),
        llm_model=str(payload.get("llm_model", engine.gatekeeper_llm_model) or "gpt-4.1-mini"),
        llm_score_weight=max(
            0.0,
            min(1.0, float(payload.get("llm_score_weight", engine.gatekeeper_llm_score_weight))),
        ),
        llm_min_confidence=max(
            0.0,
            min(1.0, float(payload.get("llm_min_confidence", engine.gatekeeper_llm_min_confidence))),
        ),
        llm_timeout_ms=max(200, int(payload.get("llm_timeout_ms", engine.gatekeeper_llm_timeout_ms))),
    )


def _safe_div(num: float, den: float) -> float:
    if den <= 0:
        return 0.0
    return num / den


def _compute_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    labels = list(CANONICAL_TIERS)
    for item in results:
        expected = str(item["expected_tier"])
        predicted = str(item["predicted_tier"])
        if expected not in labels:
            labels.append(expected)
        if predicted not in labels:
            labels.append(predicted)

    confusion: dict[str, dict[str, int]] = {actual: {pred: 0 for pred in labels} for actual in labels}
    for item in results:
        confusion[str(item["expected_tier"])][str(item["predicted_tier"])] += 1

    correct = sum(confusion[label][label] for label in labels)
    total = max(len(results), 1)
    accuracy = round(_safe_div(correct, total), 4)

    by_tier: dict[str, dict[str, float]] = {}
    precision_vals: list[float] = []
    recall_vals: list[float] = []
    f1_vals: list[float] = []

    for label in labels:
        tp = confusion[label][label]
        fp = sum(confusion[actual][label] for actual in labels if actual != label)
        fn = sum(confusion[label][pred] for pred in labels if pred != label)

        precision = round(_safe_div(tp, tp + fp), 4)
        recall = round(_safe_div(tp, tp + fn), 4)
        f1 = round(_safe_div(2 * precision * recall, precision + recall), 4) if (precision + recall) > 0 else 0.0

        by_tier[label] = {
            "support": int(sum(confusion[label].values())),
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
        precision_vals.append(precision)
        recall_vals.append(recall)
        f1_vals.append(f1)

    macro_precision = round(sum(precision_vals) / max(len(precision_vals), 1), 4)
    macro_recall = round(sum(recall_vals) / max(len(recall_vals), 1), 4)
    macro_f1 = round(sum(f1_vals) / max(len(f1_vals), 1), 4)

    return {
        "labels": labels,
        "confusion_matrix": confusion,
        "accuracy": accuracy,
        "macro_precision": macro_precision,
        "macro_recall": macro_recall,
        "macro_f1": macro_f1,
        "by_tier": by_tier,
    }


def _run_case(engine: WikiSynthesisEngine, case: dict[str, Any]) -> dict[str, Any]:
    case_id = str(case.get("id") or "unknown_case")
    claim = _build_claim(case.get("claim") or {})

    raw_inputs = case.get("inputs") or {}
    config = _clamped_config(engine, (raw_inputs.get("config") or {}))
    repeated_count = int(raw_inputs.get("repeated_count", 0))
    historical_source_count = int(raw_inputs.get("historical_source_count", 0))
    has_recent_open_conflict = bool(raw_inputs.get("has_recent_open_conflict", False))

    incoming_source_ids_raw = raw_inputs.get("incoming_source_ids")
    if isinstance(incoming_source_ids_raw, list):
        incoming_source_ids = [str(item) for item in incoming_source_ids_raw if str(item).strip()]
    else:
        incoming_source_ids = engine._extract_source_ids(claim.evidence)

    llm_assessment_override = None
    llm_payload = raw_inputs.get("llm_assessment")
    if isinstance(llm_payload, dict):
        llm_assessment_override = GatekeeperLLMAssessment(
            status=str(llm_payload.get("status") or "ok"),
            provider=llm_payload.get("provider"),
            model=llm_payload.get("model"),
            suggested_tier=llm_payload.get("suggested_tier"),
            score=float(llm_payload["score"]) if llm_payload.get("score") is not None else None,
            confidence=float(llm_payload["confidence"]) if llm_payload.get("confidence") is not None else None,
            rationale=llm_payload.get("rationale"),
            error=llm_payload.get("error"),
        )

    decision = engine._gatekeeper_decide_from_inputs(
        claim=claim,
        config=config,
        repeated_count=repeated_count,
        historical_source_count=historical_source_count,
        incoming_source_ids=incoming_source_ids,
        has_recent_open_conflict=has_recent_open_conflict,
        llm_assessment_override=llm_assessment_override,
    )

    expected = case.get("expected") or {}
    expected_tier = str(expected.get("tier") or "")
    expected_score_min = expected.get("score_min")
    expected_score_max = expected.get("score_max")
    expected_llm_applied = expected.get("llm_applied")

    failures: list[str] = []
    if expected_tier and decision.tier != expected_tier:
        failures.append(f"tier expected={expected_tier} got={decision.tier}")
    if expected_score_min is not None and float(decision.score) < float(expected_score_min):
        failures.append(f"score expected>= {expected_score_min} got={decision.score}")
    if expected_score_max is not None and float(decision.score) > float(expected_score_max):
        failures.append(f"score expected<= {expected_score_max} got={decision.score}")
    if expected_llm_applied is not None:
        actual_llm_applied = bool((decision.features or {}).get("llm_applied"))
        if actual_llm_applied != bool(expected_llm_applied):
            failures.append(f"llm_applied expected={expected_llm_applied} got={actual_llm_applied}")

    return {
        "id": case_id,
        "ok": len(failures) == 0,
        "errors": failures,
        "expected_tier": expected_tier,
        "predicted_tier": decision.tier,
        "score": decision.score,
        "rationale": decision.rationale,
        "features": decision.features,
    }


def _threshold_errors(metrics: dict[str, Any], minimum_metrics: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("accuracy", "macro_precision", "macro_recall"):
        threshold_raw = minimum_metrics.get(key)
        if threshold_raw is None:
            continue
        threshold = float(threshold_raw)
        actual = float(metrics.get(key, 0.0))
        if actual < threshold:
            errors.append(f"metric {key} below threshold: actual={actual:.4f} threshold={threshold:.4f}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic gatekeeper regression dataset.")
    parser.add_argument(
        "--dataset",
        default="eval/gatekeeper_cases.json",
        help="Path to gatekeeper evaluator dataset JSON file",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print compact summary without per-case feature payloads.",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(json.dumps({"status": "error", "error": "dataset_not_found", "dataset": str(dataset_path)}))
        sys.exit(2)

    raw = json.loads(dataset_path.read_text(encoding="utf-8"))
    cases = raw.get("cases") or []
    if not cases:
        print(json.dumps({"status": "error", "error": "dataset_empty", "dataset": str(dataset_path)}))
        sys.exit(2)

    engine = WikiSynthesisEngine()
    results = [_run_case(engine, case) for case in cases]

    passed = sum(1 for item in results if item["ok"])
    failed = len(results) - passed
    metrics = _compute_metrics(results)

    minimum_metrics = (raw.get("meta") or {}).get("minimum_metrics") or {}
    metric_errors = _threshold_errors(metrics, minimum_metrics)

    summary = {
        "status": "ok" if failed == 0 and not metric_errors else "failed",
        "dataset": str(dataset_path),
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "metric_errors": metric_errors,
        "metrics": metrics,
    }
    if args.summary_only:
        summary["failed_case_ids"] = [str(item.get("id")) for item in results if not item.get("ok")]
    else:
        summary["cases"] = results
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if failed > 0 or metric_errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
