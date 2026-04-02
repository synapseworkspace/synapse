#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
import json
import os
import sys
from typing import Any


LABELS = ["operational_memory", "insight_candidate", "golden_candidate"]


def _label_expected(predicted_tier: str, moderation_action: str | None) -> str | None:
    tier = str(predicted_tier or "").strip()
    action = str(moderation_action or "").strip().lower() or None
    if tier == "operational_memory":
        return "operational_memory"
    if action == "approve":
        return "golden_candidate"
    if action == "reject":
        return "insight_candidate"
    return None


def _safe_div(n: float, d: float) -> float:
    if d <= 0:
        return 0.0
    return n / d


def _compute_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    confusion: dict[str, dict[str, int]] = {actual: {pred: 0 for pred in LABELS} for actual in LABELS}
    for row in rows:
        expected = str(row["expected_tier"])
        predicted = str(row["predicted_tier"])
        if expected not in confusion:
            continue
        if predicted not in confusion[expected]:
            continue
        confusion[expected][predicted] += 1

    total = max(1, len(rows))
    correct = sum(confusion[label][label] for label in LABELS)
    accuracy = round(_safe_div(correct, total), 4)

    by_tier: dict[str, dict[str, float]] = {}
    for label in LABELS:
        tp = confusion[label][label]
        fp = sum(confusion[other][label] for other in LABELS if other != label)
        fn = sum(confusion[label][other] for other in LABELS if other != label)
        precision = round(_safe_div(tp, tp + fp), 4)
        recall = round(_safe_div(tp, tp + fn), 4)
        f1 = round(_safe_div(2 * precision * recall, precision + recall), 4) if (precision + recall) > 0 else 0.0
        by_tier[label] = {
            "support": int(sum(confusion[label].values())),
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }

    macro_precision = round(sum(by_tier[label]["precision"] for label in LABELS) / len(LABELS), 4)
    macro_recall = round(sum(by_tier[label]["recall"] for label in LABELS) / len(LABELS), 4)
    macro_f1 = round(sum(by_tier[label]["f1"] for label in LABELS) / len(LABELS), 4)
    return {
        "total": len(rows),
        "accuracy": accuracy,
        "macro_precision": macro_precision,
        "macro_recall": macro_recall,
        "macro_f1": macro_f1,
        "by_tier": by_tier,
        "confusion_matrix": confusion,
    }


def _delta(current: float, previous: float) -> float:
    return round(current - previous, 4)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute weekly Gatekeeper drift metrics from DB weak labels (moderation + operational tier)."
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", "postgresql://synapse:synapse@localhost:55432/synapse"),
        help="Postgres connection URL.",
    )
    parser.add_argument("--project-id", required=True, help="Project id to analyze.")
    parser.add_argument("--window-days", type=int, default=7, help="Window size in days (current and previous).")
    parser.add_argument("--min-labeled-cases", type=int, default=12, help="Minimum labeled current-window cases.")
    parser.add_argument("--min-current-accuracy", type=float, default=0.75, help="Alert if current accuracy drops below.")
    parser.add_argument("--max-accuracy-drop", type=float, default=0.1, help="Alert if accuracy delta is below negative threshold.")
    parser.add_argument(
        "--max-golden-precision-drop",
        type=float,
        default=0.12,
        help="Alert if golden precision delta is below negative threshold.",
    )
    args = parser.parse_args()

    try:
        import psycopg
    except Exception as exc:  # pragma: no cover
        raise SystemExit("Install psycopg[binary] to run drift monitor.") from exc

    now = datetime.now(UTC)
    window_days = max(1, int(args.window_days))
    current_start = now - timedelta(days=window_days)
    previous_start = now - timedelta(days=window_days * 2)

    query = """
    SELECT
      gd.claim_id::text AS claim_id,
      gd.tier AS predicted_tier,
      gd.updated_at AS decision_updated_at,
      ma.action_type AS moderation_action
    FROM gatekeeper_decisions gd
    LEFT JOIN LATERAL (
      SELECT action_type, created_at
      FROM moderation_actions ma
      WHERE ma.claim_id = gd.claim_id
      ORDER BY ma.created_at DESC
      LIMIT 1
    ) ma ON TRUE
    WHERE gd.project_id = %s
      AND gd.updated_at >= %s
    ORDER BY gd.updated_at DESC
    """

    with psycopg.connect(args.database_url, autocommit=True) as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(query, (args.project_id, previous_start))
            raw_rows: list[dict[str, Any]] = list(cur.fetchall())

    current_rows: list[dict[str, Any]] = []
    previous_rows: list[dict[str, Any]] = []
    unlabeled = 0
    for row in raw_rows:
        expected = _label_expected(str(row.get("predicted_tier") or ""), row.get("moderation_action"))
        if expected is None:
            unlabeled += 1
            continue
        entry = {
            "claim_id": row["claim_id"],
            "expected_tier": expected,
            "predicted_tier": str(row.get("predicted_tier") or ""),
        }
        ts = row.get("decision_updated_at")
        if ts is None:
            continue
        if ts >= current_start:
            current_rows.append(entry)
        else:
            previous_rows.append(entry)

    current_metrics = _compute_metrics(current_rows)
    previous_metrics = _compute_metrics(previous_rows)

    current_accuracy = float(current_metrics["accuracy"])
    previous_accuracy = float(previous_metrics["accuracy"])
    current_golden_precision = float((current_metrics.get("by_tier") or {}).get("golden_candidate", {}).get("precision", 0.0))
    previous_golden_precision = float(
        (previous_metrics.get("by_tier") or {}).get("golden_candidate", {}).get("precision", 0.0)
    )

    alerts: list[str] = []
    if len(current_rows) < int(args.min_labeled_cases):
        alerts.append(
            f"insufficient_labeled_cases: current={len(current_rows)} min_required={int(args.min_labeled_cases)}"
        )
    if current_accuracy < float(args.min_current_accuracy):
        alerts.append(
            f"accuracy_below_threshold: current={current_accuracy:.4f} threshold={float(args.min_current_accuracy):.4f}"
        )

    accuracy_delta = _delta(current_accuracy, previous_accuracy)
    if len(previous_rows) > 0 and accuracy_delta < -abs(float(args.max_accuracy_drop)):
        alerts.append(
            f"accuracy_drop_exceeded: delta={accuracy_delta:.4f} threshold=-{abs(float(args.max_accuracy_drop)):.4f}"
        )

    golden_precision_delta = _delta(current_golden_precision, previous_golden_precision)
    if len(previous_rows) > 0 and golden_precision_delta < -abs(float(args.max_golden_precision_drop)):
        alerts.append(
            "golden_precision_drop_exceeded: "
            f"delta={golden_precision_delta:.4f} threshold=-{abs(float(args.max_golden_precision_drop)):.4f}"
        )

    status = "ok" if not alerts else "alert"
    payload = {
        "status": status,
        "project_id": args.project_id,
        "window_days": window_days,
        "generated_at": now.isoformat(),
        "data": {
            "raw_rows": len(raw_rows),
            "unlabeled_rows": unlabeled,
            "current_labeled_rows": len(current_rows),
            "previous_labeled_rows": len(previous_rows),
        },
        "thresholds": {
            "min_labeled_cases": int(args.min_labeled_cases),
            "min_current_accuracy": float(args.min_current_accuracy),
            "max_accuracy_drop": float(args.max_accuracy_drop),
            "max_golden_precision_drop": float(args.max_golden_precision_drop),
        },
        "metrics": {
            "current": current_metrics,
            "previous": previous_metrics,
            "deltas": {
                "accuracy": accuracy_delta,
                "golden_precision": golden_precision_delta,
            },
        },
        "alerts": alerts,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if status != "ok":
        sys.exit(1)


if __name__ == "__main__":
    main()
