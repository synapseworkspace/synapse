#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.wiki_engine import ClaimInput, GatekeeperConfig, GatekeeperLLMAssessment, WikiSynthesisEngine

CANONICAL_TIERS = ["operational_memory", "insight_candidate", "golden_candidate"]


@dataclass(slots=True)
class CandidateConfig:
    llm_score_weight: float
    llm_min_confidence: float
    min_score_for_golden: float

    def as_dict(self) -> dict[str, float]:
        return {
            "llm_score_weight": round(self.llm_score_weight, 4),
            "llm_min_confidence": round(self.llm_min_confidence, 4),
            "min_score_for_golden": round(self.min_score_for_golden, 4),
        }


def _parse_float_list(raw: str) -> list[float]:
    out: list[float] = []
    for item in str(raw).split(","):
        value = item.strip()
        if not value:
            continue
        out.append(float(value))
    if not out:
        raise ValueError("empty float list")
    return out


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
        min_sources_for_golden=max(2, int(payload.get("min_sources_for_golden", engine.gatekeeper_min_sources_for_golden))),
        conflict_free_days=max(1, int(payload.get("conflict_free_days", engine.gatekeeper_conflict_free_days))),
        min_score_for_golden=max(0.0, min(1.0, float(payload.get("min_score_for_golden", engine.gatekeeper_min_score_for_golden)))),
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
        llm_score_weight=max(0.0, min(1.0, float(payload.get("llm_score_weight", engine.gatekeeper_llm_score_weight)))),
        llm_min_confidence=max(0.0, min(1.0, float(payload.get("llm_min_confidence", engine.gatekeeper_llm_min_confidence)))),
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
    precision_vals_supported: list[float] = []
    recall_vals_supported: list[float] = []
    f1_vals_supported: list[float] = []

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
        if by_tier[label]["support"] > 0:
            precision_vals_supported.append(precision)
            recall_vals_supported.append(recall)
            f1_vals_supported.append(f1)

    macro_precision = round(sum(precision_vals) / max(len(precision_vals), 1), 4)
    macro_recall = round(sum(recall_vals) / max(len(recall_vals), 1), 4)
    macro_f1 = round(sum(f1_vals) / max(len(f1_vals), 1), 4)
    macro_precision_supported = round(sum(precision_vals_supported) / max(len(precision_vals_supported), 1), 4)
    macro_recall_supported = round(sum(recall_vals_supported) / max(len(recall_vals_supported), 1), 4)
    macro_f1_supported = round(sum(f1_vals_supported) / max(len(f1_vals_supported), 1), 4)

    return {
        "labels": labels,
        "confusion_matrix": confusion,
        "accuracy": accuracy,
        "macro_precision": macro_precision,
        "macro_recall": macro_recall,
        "macro_f1": macro_f1,
        "macro_precision_supported": macro_precision_supported,
        "macro_recall_supported": macro_recall_supported,
        "macro_f1_supported": macro_f1_supported,
        "by_tier": by_tier,
        "total": len(results),
    }


def _predict_case(
    engine: WikiSynthesisEngine,
    case: dict[str, Any],
    candidate: CandidateConfig,
    *,
    force_llm_assist: bool,
) -> dict[str, Any] | None:
    expected = case.get("expected") or {}
    expected_tier = str(expected.get("tier") or "").strip()
    if not expected_tier:
        return None

    claim = _build_claim(case.get("claim") or {})
    raw_inputs = case.get("inputs") or {}
    config_payload = dict(raw_inputs.get("config") or {})
    config_payload["llm_score_weight"] = candidate.llm_score_weight
    config_payload["llm_min_confidence"] = candidate.llm_min_confidence
    config_payload["min_score_for_golden"] = candidate.min_score_for_golden
    if force_llm_assist:
        config_payload["llm_assist_enabled"] = True
    config = _clamped_config(engine, config_payload)

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
    return {
        "id": str(case.get("id") or ""),
        "expected_tier": expected_tier,
        "predicted_tier": decision.tier,
        "score": float(decision.score),
        "llm_applied": bool((decision.features or {}).get("llm_applied")),
    }


def _deterministic_split(case_id: str, seed: str, holdout_ratio: float) -> str:
    holdout_ratio = max(0.0, min(0.95, holdout_ratio))
    digest = hashlib.sha256(f"{seed}:{case_id}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) / 0xFFFFFFFF
    return "holdout" if bucket < holdout_ratio else "train"


def _split_cases(cases: list[dict[str, Any]], *, split_field: str, holdout_ratio: float, seed: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    train: list[dict[str, Any]] = []
    holdout: list[dict[str, Any]] = []
    for idx, case in enumerate(cases):
        split_raw = case.get(split_field)
        if isinstance(split_raw, str) and split_raw.strip().lower() in {"train", "holdout"}:
            split = split_raw.strip().lower()
        else:
            case_id = str(case.get("id") or f"case_{idx}")
            split = _deterministic_split(case_id=case_id, seed=seed, holdout_ratio=holdout_ratio)
        if split == "holdout":
            holdout.append(case)
        else:
            train.append(case)

    if not holdout and train:
        holdout.append(train.pop())
    if not train and holdout:
        train.append(holdout.pop())
    return train, holdout


def _guardrails(
    metrics: dict[str, Any],
    *,
    min_golden_precision: float,
    min_golden_recall: float,
    min_macro_precision: float,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    by_tier = metrics.get("by_tier") or {}
    golden = by_tier.get("golden_candidate") or {}
    golden_precision = float(golden.get("precision", 0.0))
    golden_recall = float(golden.get("recall", 0.0))
    macro_precision = float(metrics.get("macro_precision_supported", metrics.get("macro_precision", 0.0)))

    if golden_precision < min_golden_precision:
        errors.append(
            f"golden_precision {golden_precision:.4f} < threshold {min_golden_precision:.4f}"
        )
    if golden_recall < min_golden_recall:
        errors.append(
            f"golden_recall {golden_recall:.4f} < threshold {min_golden_recall:.4f}"
        )
    if macro_precision < min_macro_precision:
        errors.append(
            f"macro_precision {macro_precision:.4f} < threshold {min_macro_precision:.4f}"
        )
    return len(errors) == 0, errors


def _rank_key(item: dict[str, Any]) -> tuple[Any, ...]:
    holdout = item["holdout_metrics"]
    golden = (holdout.get("by_tier") or {}).get("golden_candidate") or {}
    return (
        1 if item["guardrails_met"] else 0,
        float(holdout.get("macro_f1", 0.0)),
        float(holdout.get("macro_precision", 0.0)),
        float(golden.get("precision", 0.0)),
        float(golden.get("recall", 0.0)),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calibrate LLM-assisted Gatekeeper thresholds on deterministic train/holdout split."
    )
    parser.add_argument("--dataset", default="eval/gatekeeper_cases.json", help="Path to labeled gatekeeper dataset.")
    parser.add_argument("--split-field", default="split", help="Case field for explicit split labels (`train|holdout`).")
    parser.add_argument("--holdout-ratio", type=float, default=0.3, help="Holdout ratio if split field is missing.")
    parser.add_argument("--seed", default="synapse-gatekeeper-calibration-v1", help="Seed used for deterministic split.")
    parser.add_argument("--weights", default="0.2,0.3,0.35,0.4,0.5,0.6", help="Comma-separated llm_score_weight grid.")
    parser.add_argument(
        "--confidences",
        default="0.55,0.6,0.65,0.7,0.75,0.8,0.85",
        help="Comma-separated llm_min_confidence grid.",
    )
    parser.add_argument(
        "--score-thresholds",
        default="0.68,0.72,0.76",
        help="Comma-separated min_score_for_golden grid.",
    )
    parser.add_argument("--top-k", type=int, default=5, help="How many best candidates to include in report.")
    parser.add_argument("--force-llm-assist", action="store_true", help="Force llm_assist_enabled=true for every candidate.")
    parser.add_argument("--golden-precision-min", type=float, default=0.9, help="Guardrail for golden tier precision.")
    parser.add_argument("--golden-recall-min", type=float, default=0.8, help="Guardrail for golden tier recall.")
    parser.add_argument("--macro-precision-min", type=float, default=0.9, help="Guardrail for macro precision.")
    parser.add_argument("--output", default=None, help="Optional path to write full JSON report.")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(json.dumps({"status": "error", "error": "dataset_not_found", "dataset": str(dataset_path)}))
        sys.exit(2)
    raw = json.loads(dataset_path.read_text(encoding="utf-8"))
    cases = raw.get("cases") or []
    if not isinstance(cases, list) or not cases:
        print(json.dumps({"status": "error", "error": "dataset_empty", "dataset": str(dataset_path)}))
        sys.exit(2)

    train_cases, holdout_cases = _split_cases(
        [item for item in cases if isinstance(item, dict)],
        split_field=args.split_field,
        holdout_ratio=float(args.holdout_ratio),
        seed=args.seed,
    )
    if not train_cases or not holdout_cases:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": "split_failed",
                    "train_cases": len(train_cases),
                    "holdout_cases": len(holdout_cases),
                }
            )
        )
        sys.exit(2)

    weights = sorted(set(_parse_float_list(args.weights)))
    confidences = sorted(set(_parse_float_list(args.confidences)))
    score_thresholds = sorted(set(_parse_float_list(args.score_thresholds)))

    engine = WikiSynthesisEngine()
    candidates: list[dict[str, Any]] = []
    combos = 0

    for weight in weights:
        for confidence in confidences:
            for score_threshold in score_thresholds:
                combos += 1
                candidate = CandidateConfig(
                    llm_score_weight=max(0.0, min(1.0, float(weight))),
                    llm_min_confidence=max(0.0, min(1.0, float(confidence))),
                    min_score_for_golden=max(0.0, min(1.0, float(score_threshold))),
                )

                train_preds = [
                    item
                    for case in train_cases
                    if (item := _predict_case(engine, case, candidate, force_llm_assist=bool(args.force_llm_assist))) is not None
                ]
                holdout_preds = [
                    item
                    for case in holdout_cases
                    if (item := _predict_case(engine, case, candidate, force_llm_assist=bool(args.force_llm_assist))) is not None
                ]
                if not train_preds or not holdout_preds:
                    continue

                train_metrics = _compute_metrics(train_preds)
                holdout_metrics = _compute_metrics(holdout_preds)
                guardrails_met, guardrail_errors = _guardrails(
                    holdout_metrics,
                    min_golden_precision=float(args.golden_precision_min),
                    min_golden_recall=float(args.golden_recall_min),
                    min_macro_precision=float(args.macro_precision_min),
                )

                candidates.append(
                    {
                        "config": candidate.as_dict(),
                        "train_metrics": train_metrics,
                        "holdout_metrics": holdout_metrics,
                        "guardrails_met": guardrails_met,
                        "guardrail_errors": guardrail_errors,
                    }
                )

    if not candidates:
        print(json.dumps({"status": "error", "error": "no_candidates_evaluated"}))
        sys.exit(2)

    ranked = sorted(candidates, key=_rank_key, reverse=True)
    best = ranked[0]
    top_k = max(1, int(args.top_k))
    top = ranked[:top_k]

    recommended_payload = {
        "llm_assist_enabled": True,
        "llm_provider": "openai",
        "llm_model": "gpt-4.1-mini",
        "llm_score_weight": best["config"]["llm_score_weight"],
        "llm_min_confidence": best["config"]["llm_min_confidence"],
        "min_score_for_golden": best["config"]["min_score_for_golden"],
    }

    report = {
        "status": "ok",
        "dataset": str(dataset_path),
        "split": {
            "mode": f"explicit:{args.split_field}" if any(isinstance(item.get(args.split_field), str) for item in cases if isinstance(item, dict)) else "deterministic_hash",
            "seed": args.seed,
            "holdout_ratio": float(args.holdout_ratio),
            "train_cases": len(train_cases),
            "holdout_cases": len(holdout_cases),
        },
        "grid": {
            "weights": weights,
            "confidences": confidences,
            "score_thresholds": score_thresholds,
            "combinations": combos,
            "evaluated": len(candidates),
        },
        "guardrails": {
            "golden_precision_min": float(args.golden_precision_min),
            "golden_recall_min": float(args.golden_recall_min),
            "macro_precision_min": float(args.macro_precision_min),
        },
        "best_candidate": best,
        "recommended_gatekeeper_config_payload": recommended_payload,
        "top_candidates": top,
    }

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not bool(best.get("guardrails_met")):
        sys.exit(1)


if __name__ == "__main__":
    main()
