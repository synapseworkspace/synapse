#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _request_json(method: str, url: str, *, json_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        import requests
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("`requests` is required to call Synapse API. Install it before applying calibration.") from exc
    response = requests.request(method=method, url=url, json=json_payload, timeout=20)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"unexpected response payload type from {url}")
    return payload


def _pick_recommended_payload(report: dict[str, Any]) -> dict[str, Any]:
    payload = report.get("recommended_gatekeeper_config_payload")
    if not isinstance(payload, dict):
        raise ValueError("calibration report missing `recommended_gatekeeper_config_payload`")
    return dict(payload)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply recommended Gatekeeper calibration payload to project config via API."
    )
    parser.add_argument(
        "--report",
        required=True,
        help="Path to calibration report JSON from calibrate_gatekeeper_llm_thresholds.py",
    )
    parser.add_argument("--project-id", required=True, help="Project id to update.")
    parser.add_argument("--api-url", default="http://localhost:8080", help="Synapse API base URL.")
    parser.add_argument(
        "--updated-by",
        default="gatekeeper_calibration_bot",
        help="Actor string for config audit fields.",
    )
    parser.add_argument(
        "--allow-guardrail-fail",
        action="store_true",
        help="Allow apply even if calibration report indicates guardrails are not met.",
    )
    parser.add_argument(
        "--skip-current-fetch",
        action="store_true",
        help="Do not fetch current config from API (use defaults + recommended payload). Useful for offline dry-run.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print payload without calling PUT.")
    args = parser.parse_args()

    report_path = Path(args.report)
    if not report_path.exists():
        raise SystemExit(f"report file not found: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    recommended = _pick_recommended_payload(report)
    best_candidate = report.get("best_candidate") if isinstance(report, dict) else None
    guardrails_met = bool((best_candidate or {}).get("guardrails_met"))
    if not guardrails_met and not args.allow_guardrail_fail:
        raise SystemExit(
            "refusing to apply config because guardrails are not met in calibration report "
            "(pass --allow-guardrail-fail to override)"
        )

    api_url = args.api_url.rstrip("/")
    get_url = f"{api_url}/v1/gatekeeper/config"
    put_url = f"{api_url}/v1/gatekeeper/config"

    if args.skip_current_fetch:
        current_config = {
            "min_sources_for_golden": 3,
            "conflict_free_days": 7,
            "min_score_for_golden": 0.72,
            "operational_short_text_len": 32,
            "operational_short_token_len": 5,
            "llm_assist_enabled": False,
            "llm_provider": "openai",
            "llm_model": "gpt-4.1-mini",
            "llm_score_weight": 0.35,
            "llm_min_confidence": 0.65,
            "llm_timeout_ms": 3500,
        }
    else:
        try:
            current_payload = _request_json("GET", f"{get_url}?project_id={args.project_id}")
        except Exception as exc:
            raise SystemExit(f"failed to fetch current gatekeeper config: {exc}") from exc
        current_config = current_payload.get("config") if isinstance(current_payload, dict) else None
        if not isinstance(current_config, dict):
            raise SystemExit("invalid gatekeeper config response: missing `config` object")

    update_payload = {
        "project_id": args.project_id,
        "min_sources_for_golden": int(current_config.get("min_sources_for_golden", 3)),
        "conflict_free_days": int(current_config.get("conflict_free_days", 7)),
        "min_score_for_golden": float(
            recommended.get("min_score_for_golden", current_config.get("min_score_for_golden", 0.72))
        ),
        "operational_short_text_len": int(current_config.get("operational_short_text_len", 32)),
        "operational_short_token_len": int(current_config.get("operational_short_token_len", 5)),
        "llm_assist_enabled": bool(recommended.get("llm_assist_enabled", current_config.get("llm_assist_enabled", True))),
        "llm_provider": str(recommended.get("llm_provider", current_config.get("llm_provider", "openai"))),
        "llm_model": str(recommended.get("llm_model", current_config.get("llm_model", "gpt-4.1-mini"))),
        "llm_score_weight": float(recommended.get("llm_score_weight", current_config.get("llm_score_weight", 0.35))),
        "llm_min_confidence": float(
            recommended.get("llm_min_confidence", current_config.get("llm_min_confidence", 0.65))
        ),
        "llm_timeout_ms": int(current_config.get("llm_timeout_ms", 3500)),
        "updated_by": str(args.updated_by),
    }

    result: dict[str, Any] = {
        "status": "dry_run" if args.dry_run else "pending",
        "project_id": args.project_id,
        "report": str(report_path),
        "guardrails_met": guardrails_met,
        "recommended": recommended,
        "current_config": current_config,
        "update_payload": update_payload,
    }
    if args.dry_run:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    try:
        apply_payload = _request_json("PUT", put_url, json_payload=update_payload)
    except Exception as exc:
        raise SystemExit(f"failed to apply gatekeeper config: {exc}") from exc

    result["status"] = "ok"
    result["api_result"] = apply_payload
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
