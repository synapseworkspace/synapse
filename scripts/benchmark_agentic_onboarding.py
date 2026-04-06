#!/usr/bin/env python3
"""Run deterministic Agentic Onboarding benchmark scenarios."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import sys
from typing import Any


@dataclass(slots=True)
class Discovery:
    knowledge_id: str
    source_id: str
    confidence: float
    risk_tier: str


@dataclass(slots=True)
class TicketCase:
    ticket_id: str
    intent: str
    required_knowledge: list[str]
    discoveries: list[Discovery]


@dataclass(slots=True)
class DraftCandidate:
    knowledge_id: str
    risk_tier: str
    created_ticket_index: int
    max_confidence: float = 0.0
    sources: set[str] = field(default_factory=set)
    approved: bool = False
    approved_mode: str | None = None
    approved_ticket_index: int | None = None


@dataclass(slots=True)
class ScenarioConfig:
    name: str
    capture_enabled: bool
    publish_enabled: bool
    publish_mode_default: str
    publish_mode_by_risk: dict[str, str]
    auto_publish_blocked_risks: set[str]
    min_confidence: float
    min_sources_for_auto_publish: int
    min_sources_for_human_review_default: int
    min_sources_for_human_review_by_risk: dict[str, int]
    human_review_delay_tickets: int


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _load_dataset(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"dataset_not_found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"dataset_parse_failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("dataset must be an object")
    return payload


def _parse_tickets(payload: dict[str, Any]) -> list[TicketCase]:
    tickets_raw = _as_list(payload.get("tickets"))
    out: list[TicketCase] = []
    for index, item in enumerate(tickets_raw):
        row = _as_dict(item)
        ticket_id = _coerce_text(row.get("ticket_id")) or f"T{index + 1:03d}"
        intent = _coerce_text(row.get("intent")) or "support_case"
        required = [_coerce_text(x) for x in _as_list(row.get("required_knowledge")) if _coerce_text(x)]

        discoveries: list[Discovery] = []
        for discovery_item in _as_list(row.get("discoveries")):
            drow = _as_dict(discovery_item)
            knowledge_id = _coerce_text(drow.get("knowledge_id"))
            source_id = _coerce_text(drow.get("source_id"))
            if not knowledge_id or not source_id:
                continue
            confidence = float(drow.get("confidence") or 0.0)
            confidence = max(0.0, min(1.0, confidence))
            risk_tier = _coerce_text(drow.get("risk_tier")) or "ops"
            discoveries.append(
                Discovery(
                    knowledge_id=knowledge_id,
                    source_id=source_id,
                    confidence=confidence,
                    risk_tier=risk_tier,
                )
            )
        out.append(
            TicketCase(
                ticket_id=ticket_id,
                intent=intent,
                required_knowledge=required,
                discoveries=discoveries,
            )
        )
    return out


def _build_scenario(profile: str) -> ScenarioConfig:
    if profile == "baseline_static":
        return ScenarioConfig(
            name=profile,
            capture_enabled=False,
            publish_enabled=False,
            publish_mode_default="off",
            publish_mode_by_risk={},
            auto_publish_blocked_risks=set(),
            min_confidence=1.0,
            min_sources_for_auto_publish=99,
            min_sources_for_human_review_default=99,
            min_sources_for_human_review_by_risk={},
            human_review_delay_tickets=99,
        )
    if profile == "synapse_balanced":
        return ScenarioConfig(
            name=profile,
            capture_enabled=True,
            publish_enabled=True,
            publish_mode_default="auto_publish",
            publish_mode_by_risk={
                "finance": "human_required",
                "policy": "human_required",
                "legal": "human_required",
            },
            auto_publish_blocked_risks={"finance", "policy", "legal"},
            min_confidence=0.78,
            min_sources_for_auto_publish=2,
            min_sources_for_human_review_default=1,
            min_sources_for_human_review_by_risk={"finance": 2, "policy": 1, "legal": 1},
            human_review_delay_tickets=1,
        )
    if profile == "synapse_human_required":
        return ScenarioConfig(
            name=profile,
            capture_enabled=True,
            publish_enabled=True,
            publish_mode_default="human_required",
            publish_mode_by_risk={},
            auto_publish_blocked_risks={"finance", "policy", "legal", "ops", "incident", "preference", "process"},
            min_confidence=0.78,
            min_sources_for_auto_publish=99,
            min_sources_for_human_review_default=1,
            min_sources_for_human_review_by_risk={"finance": 2},
            human_review_delay_tickets=1,
        )
    raise ValueError(f"unsupported profile: {profile}")


def _resolve_publish_mode(config: ScenarioConfig, risk_tier: str) -> str:
    mode = config.publish_mode_by_risk.get(risk_tier, config.publish_mode_default)
    if mode not in {"auto_publish", "human_required", "off"}:
        return "off"
    return mode


def _simulate(
    *,
    payload: dict[str, Any],
    tickets: list[TicketCase],
    config: ScenarioConfig,
    minutes_per_ticket: int,
) -> dict[str, Any]:
    seed_published = {_coerce_text(x) for x in _as_list(payload.get("seed_published_knowledge")) if _coerce_text(x)}
    published = set(seed_published)
    initial_published_count = len(published)

    drafts: dict[str, DraftCandidate] = {}
    timeline: list[dict[str, Any]] = []

    useful_answers = 0
    first_useful_ticket: int | None = None
    first_approved_ticket: int | None = None
    first_policy_safe_ticket: int | None = None
    auto_published = 0
    human_approved = 0
    draft_candidates_created = 0

    for index, ticket in enumerate(tickets, start=1):
        missing = [key for key in ticket.required_knowledge if key not in published]
        useful = len(missing) == 0
        if useful:
            useful_answers += 1
            if first_useful_ticket is None:
                first_useful_ticket = index

        created_now: list[str] = []
        published_now: list[dict[str, str]] = []

        if config.capture_enabled:
            for discovery in ticket.discoveries:
                candidate = drafts.get(discovery.knowledge_id)
                if candidate is None:
                    candidate = DraftCandidate(
                        knowledge_id=discovery.knowledge_id,
                        risk_tier=discovery.risk_tier,
                        created_ticket_index=index,
                    )
                    drafts[discovery.knowledge_id] = candidate
                    draft_candidates_created += 1
                    created_now.append(discovery.knowledge_id)
                candidate.max_confidence = max(candidate.max_confidence, discovery.confidence)
                candidate.sources.add(discovery.source_id)

        if config.publish_enabled:
            for knowledge_id, candidate in drafts.items():
                if candidate.approved:
                    continue
                if candidate.max_confidence < config.min_confidence:
                    continue

                mode = _resolve_publish_mode(config, candidate.risk_tier)
                if mode == "off":
                    continue

                if mode == "auto_publish":
                    if candidate.risk_tier in config.auto_publish_blocked_risks:
                        mode = "human_required"
                    elif len(candidate.sources) < config.min_sources_for_auto_publish:
                        continue

                if mode == "human_required":
                    min_sources = config.min_sources_for_human_review_by_risk.get(
                        candidate.risk_tier, config.min_sources_for_human_review_default
                    )
                    if len(candidate.sources) < max(1, min_sources):
                        continue
                    if index - candidate.created_ticket_index < config.human_review_delay_tickets:
                        continue

                candidate.approved = True
                candidate.approved_mode = "auto_publish" if mode == "auto_publish" else "human_required"
                candidate.approved_ticket_index = index
                published.add(knowledge_id)
                if first_approved_ticket is None:
                    first_approved_ticket = index
                if candidate.approved_mode == "auto_publish":
                    auto_published += 1
                    if first_policy_safe_ticket is None:
                        first_policy_safe_ticket = index
                else:
                    human_approved += 1
                published_now.append(
                    {
                        "knowledge_id": knowledge_id,
                        "mode": candidate.approved_mode,
                    }
                )

        timeline.append(
            {
                "ticket_index": index,
                "ticket_id": ticket.ticket_id,
                "intent": ticket.intent,
                "required_knowledge": list(ticket.required_knowledge),
                "missing_knowledge": missing,
                "useful_answer": useful,
                "drafts_created": created_now,
                "published": published_now,
            }
        )

    def _to_minutes(ticket_index: int | None) -> int | None:
        if ticket_index is None:
            return None
        return ticket_index * minutes_per_ticket

    approved_total = auto_published + human_approved
    pending_review = sum(1 for candidate in drafts.values() if not candidate.approved)
    total_tickets = len(tickets)
    useful_rate = (float(useful_answers) / float(total_tickets)) if total_tickets else 0.0
    result: dict[str, Any] = {
        "scenario": config.name,
        "tickets_total": total_tickets,
        "minutes_per_ticket": minutes_per_ticket,
        "useful_answers": useful_answers,
        "useful_answer_rate": round(useful_rate, 4),
        "first_useful_answer_ticket": first_useful_ticket,
        "first_useful_answer_minutes": _to_minutes(first_useful_ticket),
        "first_approved_draft_ticket": first_approved_ticket,
        "first_approved_draft_minutes": _to_minutes(first_approved_ticket),
        "first_policy_safe_publish_ticket": first_policy_safe_ticket,
        "first_policy_safe_publish_minutes": _to_minutes(first_policy_safe_ticket),
        "draft_candidates_created": draft_candidates_created,
        "approved_drafts_total": approved_total,
        "approved_drafts_auto_publish": auto_published,
        "approved_drafts_human_required": human_approved,
        "pending_review_drafts": pending_review,
        "seed_published_knowledge": initial_published_count,
        "published_knowledge_total": len(published),
        "published_knowledge_new": max(0, len(published) - initial_published_count),
        "kpi_cards": [
            {
                "name": "first_useful_answer",
                "ticket_index": first_useful_ticket,
                "minutes": _to_minutes(first_useful_ticket),
            },
            {
                "name": "first_approved_draft",
                "ticket_index": first_approved_ticket,
                "minutes": _to_minutes(first_approved_ticket),
            },
            {
                "name": "first_policy_safe_publish",
                "ticket_index": first_policy_safe_ticket,
                "minutes": _to_minutes(first_policy_safe_ticket),
            },
        ],
        "timeline": timeline,
    }
    return result


def _delta_number(lhs: Any, rhs: Any) -> float | None:
    if lhs is None or rhs is None:
        return None
    try:
        return round(float(lhs) - float(rhs), 4)
    except (TypeError, ValueError):
        return None


def _delta_minutes_improvement(baseline_minutes: Any, scenario_minutes: Any) -> int | None:
    if baseline_minutes is None and scenario_minutes is not None:
        return None
    if scenario_minutes is None:
        return None
    if baseline_minutes is None:
        return None
    try:
        return int(round(float(baseline_minutes) - float(scenario_minutes)))
    except (TypeError, ValueError):
        return None


def _build_comparison(scenarios: dict[str, dict[str, Any]]) -> dict[str, Any]:
    baseline = scenarios.get("baseline_static")
    if not baseline:
        return {}
    compare: dict[str, Any] = {}
    for scenario_name, scenario in scenarios.items():
        if scenario_name == "baseline_static":
            continue
        compare[scenario_name] = {
            "useful_answer_rate_delta": _delta_number(scenario.get("useful_answer_rate"), baseline.get("useful_answer_rate")),
            "approved_drafts_delta": _delta_number(
                scenario.get("approved_drafts_total"),
                baseline.get("approved_drafts_total"),
            ),
            "published_knowledge_new_delta": _delta_number(
                scenario.get("published_knowledge_new"),
                baseline.get("published_knowledge_new"),
            ),
            "first_approved_draft_minutes_improvement": _delta_minutes_improvement(
                baseline.get("first_approved_draft_minutes"),
                scenario.get("first_approved_draft_minutes"),
            ),
            "first_policy_safe_publish_minutes_improvement": _delta_minutes_improvement(
                baseline.get("first_policy_safe_publish_minutes"),
                scenario.get("first_policy_safe_publish_minutes"),
            ),
        }
    return compare


def _run_assertions(
    scenarios: dict[str, dict[str, Any]],
    *,
    min_balanced_useful_rate: float | None,
    max_balanced_first_approved_minutes: int | None,
    min_balanced_published_new: int | None,
) -> list[str]:
    failures: list[str] = []
    balanced = scenarios.get("synapse_balanced")
    if balanced is None:
        return failures
    if min_balanced_useful_rate is not None:
        useful_rate = float(balanced.get("useful_answer_rate") or 0.0)
        if useful_rate < min_balanced_useful_rate:
            failures.append(
                f"synapse_balanced useful_answer_rate {useful_rate:.4f} < {min_balanced_useful_rate:.4f}"
            )
    if max_balanced_first_approved_minutes is not None:
        first_approved_minutes = balanced.get("first_approved_draft_minutes")
        if first_approved_minutes is None or int(first_approved_minutes) > max_balanced_first_approved_minutes:
            failures.append(
                "synapse_balanced first_approved_draft_minutes "
                f"{first_approved_minutes!r} > {max_balanced_first_approved_minutes}"
            )
    if min_balanced_published_new is not None:
        published_new = int(balanced.get("published_knowledge_new") or 0)
        if published_new < min_balanced_published_new:
            failures.append(
                f"synapse_balanced published_knowledge_new {published_new} < {min_balanced_published_new}"
            )
    return failures


def _render_table(scenarios: dict[str, dict[str, Any]], comparison: dict[str, Any]) -> str:
    headers = [
        "scenario",
        "useful_rate",
        "first_approved_min",
        "first_policy_safe_min",
        "approved_drafts",
        "published_new",
    ]
    lines = [" | ".join(headers), " | ".join(["---"] * len(headers))]
    for scenario_name in sorted(scenarios.keys()):
        scenario = scenarios[scenario_name]
        lines.append(
            " | ".join(
                [
                    scenario_name,
                    str(scenario.get("useful_answer_rate")),
                    str(scenario.get("first_approved_draft_minutes")),
                    str(scenario.get("first_policy_safe_publish_minutes")),
                    str(scenario.get("approved_drafts_total")),
                    str(scenario.get("published_knowledge_new")),
                ]
            )
        )
    if comparison:
        lines.append("")
        lines.append("uplift_vs_baseline:")
        for scenario_name in sorted(comparison.keys()):
            lines.append(f"- {scenario_name}: {json.dumps(comparison[scenario_name], ensure_ascii=False)}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic Agentic Onboarding benchmark kit.")
    parser.add_argument(
        "--dataset",
        default="eval/agentic_onboarding_cases.json",
        help="Path to benchmark dataset JSON file.",
    )
    parser.add_argument(
        "--scenario",
        choices=["all", "baseline_static", "synapse_balanced", "synapse_human_required"],
        default="all",
        help="Scenario to execute. Use `all` to compare baseline and Synapse modes.",
    )
    parser.add_argument(
        "--minutes-per-ticket",
        type=int,
        default=8,
        help="Simulation minute budget per ticket (default: 8).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Render full benchmark result as JSON.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Skip timeline payload in JSON output.",
    )
    parser.add_argument(
        "--min-balanced-useful-rate",
        type=float,
        default=None,
        help="Optional assertion threshold for synapse_balanced useful_answer_rate.",
    )
    parser.add_argument(
        "--max-balanced-first-approved-minutes",
        type=int,
        default=None,
        help="Optional assertion threshold for synapse_balanced first approved draft latency.",
    )
    parser.add_argument(
        "--min-balanced-published-new",
        type=int,
        default=None,
        help="Optional assertion threshold for synapse_balanced published_knowledge_new.",
    )
    args = parser.parse_args()

    try:
        dataset_payload = _load_dataset(Path(args.dataset))
        tickets = _parse_tickets(dataset_payload)
    except ValueError as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        return 2

    selected_profiles = (
        ["baseline_static", "synapse_balanced", "synapse_human_required"]
        if args.scenario == "all"
        else [args.scenario]
    )
    scenarios: dict[str, dict[str, Any]] = {}
    for profile in selected_profiles:
        scenario = _build_scenario(profile)
        result = _simulate(
            payload=dataset_payload,
            tickets=tickets,
            config=scenario,
            minutes_per_ticket=max(1, int(args.minutes_per_ticket)),
        )
        if args.summary_only:
            result = {key: value for key, value in result.items() if key != "timeline"}
        scenarios[profile] = result

    comparison = _build_comparison(scenarios)
    failures = _run_assertions(
        scenarios,
        min_balanced_useful_rate=args.min_balanced_useful_rate,
        max_balanced_first_approved_minutes=args.max_balanced_first_approved_minutes,
        min_balanced_published_new=args.min_balanced_published_new,
    )

    output: dict[str, Any] = {
        "status": "ok" if not failures else "failed",
        "dataset": str(Path(args.dataset)),
        "dataset_version": _coerce_text(dataset_payload.get("dataset_version")) or "unknown",
        "scenarios": scenarios,
        "comparison_vs_baseline": comparison,
    }
    if failures:
        output["failures"] = failures

    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"dataset: {output['dataset']} (v{output['dataset_version']})")
        print(_render_table(scenarios, comparison))
        if failures:
            print("assertions_failed:")
            for failure in failures:
                print(f"- {failure}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
