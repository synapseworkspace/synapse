#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any


CANONICAL_TIERS = {"operational_memory", "insight_candidate", "golden_candidate"}


def _parse_project_ids(raw: list[str]) -> list[str]:
    items: list[str] = []
    for value in raw:
        for token in str(value).split(","):
            normalized = token.strip()
            if normalized:
                items.append(normalized)
    dedup: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        dedup.append(item)
    return dedup


def _deterministic_split(case_id: str, seed: str, holdout_ratio: float) -> str:
    ratio = max(0.0, min(0.95, holdout_ratio))
    digest = hashlib.sha256(f"{seed}:{case_id}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) / 0xFFFFFFFF
    return "holdout" if bucket < ratio else "train"


def _coerce_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _coerce_source_ids(metadata: dict[str, Any], features: dict[str, Any]) -> list[str]:
    from_features = features.get("incoming_source_ids")
    if isinstance(from_features, list):
        out = [str(item).strip() for item in from_features if str(item).strip()]
        if out:
            return out
    source_ids = metadata.get("source_ids")
    if isinstance(source_ids, list):
        return [str(item).strip() for item in source_ids if str(item).strip()]
    return []


def _extract_label(predicted_tier: str, moderation_action: str | None) -> tuple[str | None, str]:
    tier = str(predicted_tier or "").strip()
    action = str(moderation_action or "").strip().lower() or None
    if tier == "operational_memory":
        return "operational_memory", "gatekeeper_operational"
    if action == "approve":
        return "golden_candidate", "moderation_approve"
    if action == "reject":
        return "insight_candidate", "moderation_reject"
    return None, "unlabeled"


def _build_case(
    *,
    row: dict[str, Any],
    holdout_ratio: float,
    split_seed: str,
    include_unlabeled: bool,
) -> tuple[dict[str, Any] | None, str]:
    claim_id = str(row["claim_id"])
    features = _coerce_dict(row.get("features"))
    metadata = _coerce_dict(row.get("claim_metadata"))
    source_ids = _coerce_source_ids(metadata, features)

    expected_tier, label_source = _extract_label(str(row.get("predicted_tier") or ""), row.get("moderation_action"))
    if expected_tier is None and not include_unlabeled:
        return None, label_source

    claim_payload: dict[str, Any] = {
        "id": claim_id,
        "project_id": str(row.get("project_id") or ""),
        "entity_key": str(row.get("entity_key") or "unknown_entity"),
        "category": str(row.get("category") or "general"),
        "claim_text": str(row.get("claim_text") or ""),
        "observed_at": row["decision_updated_at"].astimezone(UTC).isoformat()
        if row.get("decision_updated_at") is not None
        else None,
        "evidence": [{"source_id": source_id} for source_id in source_ids],
    }

    inputs: dict[str, Any] = {
        "repeated_count": int(features.get("repeated_count", 0)),
        "historical_source_count": int(features.get("historical_source_count", 0)),
        "has_recent_open_conflict": bool(features.get("has_recent_open_conflict", False)),
    }
    if source_ids:
        inputs["incoming_source_ids"] = source_ids

    config: dict[str, Any] = {}
    feature_to_config = {
        "gatekeeper_min_sources_for_golden": "min_sources_for_golden",
        "gatekeeper_conflict_free_days": "conflict_free_days",
        "gatekeeper_min_score_for_golden": "min_score_for_golden",
        "gatekeeper_operational_short_text_len": "operational_short_text_len",
        "gatekeeper_operational_short_token_len": "operational_short_token_len",
        "gatekeeper_llm_assist_enabled": "llm_assist_enabled",
        "gatekeeper_llm_provider": "llm_provider",
        "gatekeeper_llm_model": "llm_model",
        "gatekeeper_llm_score_weight": "llm_score_weight",
        "gatekeeper_llm_min_confidence": "llm_min_confidence",
        "gatekeeper_llm_timeout_ms": "llm_timeout_ms",
    }
    for feature_key, config_key in feature_to_config.items():
        if feature_key in features and features.get(feature_key) is not None:
            config[config_key] = features[feature_key]
    if config:
        inputs["config"] = config

    llm_status = str(features.get("llm_status") or "")
    llm_suggested_tier = features.get("llm_suggested_tier")
    llm_score = features.get("llm_score")
    llm_confidence = features.get("llm_confidence")
    if (
        llm_status == "ok"
        and llm_suggested_tier in CANONICAL_TIERS
        and llm_score is not None
        and llm_confidence is not None
    ):
        inputs["llm_assessment"] = {
            "status": "ok",
            "provider": features.get("llm_provider"),
            "model": features.get("llm_model"),
            "suggested_tier": llm_suggested_tier,
            "score": float(llm_score),
            "confidence": float(llm_confidence),
            "rationale": features.get("llm_rationale"),
            "error": features.get("llm_error"),
        }

    expected = {
        "tier": expected_tier,
        "label_source": label_source,
    }
    if features.get("llm_applied") is not None:
        expected["llm_applied"] = bool(features.get("llm_applied"))

    split = _deterministic_split(case_id=claim_id, seed=split_seed, holdout_ratio=holdout_ratio)
    case = {
        "id": claim_id,
        "claim": claim_payload,
        "inputs": inputs,
        "expected": expected,
        "split": split,
        "meta": {
            "predicted_tier": row.get("predicted_tier"),
            "moderation_action": row.get("moderation_action"),
            "decision_score": float(row.get("decision_score") or 0.0),
            "label_source": label_source,
            "moderation_created_at": row["moderation_created_at"].astimezone(UTC).isoformat()
            if row.get("moderation_created_at") is not None
            else None,
        },
    }
    return case, label_source


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Gatekeeper holdout dataset from production-like DB decisions + moderation actions."
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", "postgresql://synapse:synapse@localhost:55432/synapse"),
        help="Postgres connection URL.",
    )
    parser.add_argument(
        "--project-id",
        action="append",
        default=[],
        help="Project id filter; can be repeated or comma-separated. Omit to include all projects.",
    )
    parser.add_argument("--lookback-days", type=int, default=60, help="Lookback horizon in days.")
    parser.add_argument("--limit", type=int, default=20000, help="Max claims to inspect.")
    parser.add_argument("--holdout-ratio", type=float, default=0.3, help="Deterministic holdout split ratio.")
    parser.add_argument(
        "--split-seed",
        default="synapse-gatekeeper-prod-holdout-v1",
        help="Seed for deterministic train/holdout split.",
    )
    parser.add_argument(
        "--include-unlabeled",
        action="store_true",
        help="Include unlabeled rows (without expected tier). Not recommended for calibration.",
    )
    parser.add_argument(
        "--output",
        default="eval/gatekeeper_cases_from_db.json",
        help="Path to output dataset JSON.",
    )
    args = parser.parse_args()

    try:
        import psycopg
    except Exception as exc:  # pragma: no cover
        raise SystemExit("Install psycopg[binary] to build DB-backed holdout dataset.") from exc

    project_ids = _parse_project_ids(list(args.project_id or []))
    lookback_days = max(1, int(args.lookback_days))
    limit = max(1, int(args.limit))

    query = """
    SELECT
      gd.claim_id::text AS claim_id,
      gd.project_id,
      gd.tier AS predicted_tier,
      gd.score AS decision_score,
      gd.features,
      gd.updated_at AS decision_updated_at,
      c.entity_key,
      c.category,
      c.claim_text,
      COALESCE(c.metadata, '{}'::jsonb) AS claim_metadata,
      ma.action_type AS moderation_action,
      ma.created_at AS moderation_created_at
    FROM gatekeeper_decisions gd
    JOIN claims c ON c.id = gd.claim_id
    LEFT JOIN LATERAL (
      SELECT action_type, created_at
      FROM moderation_actions ma
      WHERE ma.claim_id = gd.claim_id
      ORDER BY ma.created_at DESC
      LIMIT 1
    ) ma ON TRUE
    WHERE gd.updated_at >= NOW() - make_interval(days => %s)
      AND (%s::text[] IS NULL OR gd.project_id = ANY(%s))
    ORDER BY gd.updated_at DESC
    LIMIT %s
    """

    with psycopg.connect(args.database_url, autocommit=True) as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(query, (lookback_days, project_ids or None, project_ids or None, limit))
            rows: list[dict[str, Any]] = list(cur.fetchall())

    cases: list[dict[str, Any]] = []
    label_source_counts: dict[str, int] = {}
    expected_tier_counts: dict[str, int] = {}
    train_count = 0
    holdout_count = 0

    for row in rows:
        case, label_source = _build_case(
            row=row,
            holdout_ratio=float(args.holdout_ratio),
            split_seed=str(args.split_seed),
            include_unlabeled=bool(args.include_unlabeled),
        )
        label_source_counts[label_source] = label_source_counts.get(label_source, 0) + 1
        if case is None:
            continue
        expected_tier = str((case.get("expected") or {}).get("tier") or "")
        expected_tier_counts[expected_tier] = expected_tier_counts.get(expected_tier, 0) + 1
        if case.get("split") == "holdout":
            holdout_count += 1
        else:
            train_count += 1
        cases.append(case)

    payload = {
        "meta": {
            "name": "synapse_gatekeeper_db_holdout",
            "version": "v1",
            "generated_at": datetime.now(UTC).isoformat(),
            "source": "gatekeeper_decisions + claims + latest moderation_actions",
            "lookback_days": lookback_days,
            "project_ids": project_ids,
            "holdout_ratio": float(args.holdout_ratio),
            "split_seed": str(args.split_seed),
            "raw_rows": len(rows),
            "labeled_cases": len(cases),
            "label_source_counts": label_source_counts,
            "expected_tier_counts": expected_tier_counts,
            "train_cases": train_count,
            "holdout_cases": holdout_count,
        },
        "cases": cases,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "status": "ok",
        "output": str(output_path),
        "raw_rows": len(rows),
        "labeled_cases": len(cases),
        "train_cases": train_count,
        "holdout_cases": holdout_count,
        "expected_tier_counts": expected_tier_counts,
        "label_source_counts": label_source_counts,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if len(cases) == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
