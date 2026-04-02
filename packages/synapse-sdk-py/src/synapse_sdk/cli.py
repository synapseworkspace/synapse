from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from typing import Any, Sequence
from uuid import uuid4

import requests

from synapse_sdk.extractors import ExtractedInsight, InsightContext, default_extractors
from synapse_sdk.synthesizers import SynthesisContext, default_synthesizers
from synapse_sdk.types import Claim, EvidenceRef

UTC = timezone.utc


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if not getattr(args, "command", None) or not callable(getattr(args, "func", None)):
        parser.print_help()
        return 1
    return args.func(args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="synapse-cli",
        description="Synapse local extraction simulation and trace replay CLI",
    )
    subparsers = parser.add_subparsers(dest="command")

    extract = subparsers.add_parser("extract", help="Run extractor/synthesizer pipeline over local input")
    extract.add_argument("--text", help="Inline text payload")
    extract.add_argument("--file", help="Path to text or JSON file")
    extract.add_argument("--stdin", action="store_true", help="Read payload from stdin")
    extract.add_argument("--result-json", action="store_true", help="Parse input payload as JSON result object")
    extract.add_argument("--category", default="general", help="Category hint")
    extract.add_argument("--entity-key", default="unknown_entity", help="Entity hint")
    extract.add_argument("--integration", default="cli", help="Integration label in context")
    extract.add_argument("--function-name", default="synapse_cli.extract", help="Function name in context")
    extract.add_argument("--source-id", default="cli_input", help="Source id for context/evidence")
    extract.add_argument("--extractors", help="Comma-separated extractor names (default: all)")
    extract.add_argument("--synthesizers", help="Comma-separated synthesizer names (default: all)")
    extract.add_argument("--min-confidence", type=float, default=0.0, help="Filter insights below this confidence")
    extract.add_argument("--as-claims", action="store_true", help="Render output as typed claim proposals")
    extract.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    extract.set_defaults(func=_cmd_extract)

    replay = subparsers.add_parser("replay", help="Replay trace/debug events from JSONL/JSON")
    replay.add_argument("--input", required=True, help="Path to JSONL/JSON records")
    replay.add_argument("--trace-id", help="Trace ID to filter")
    replay.add_argument("--limit", type=int, default=200, help="Max rows in output timeline")
    replay.add_argument("--json", action="store_true", help="Render full replay report as JSON")
    replay.set_defaults(func=_cmd_replay)

    doctor = subparsers.add_parser("doctor", help="Run local connectivity checks for Synapse API core loop")
    doctor.add_argument(
        "--api-url",
        default=os.getenv("SYNAPSE_API_URL", "http://localhost:8080"),
        help="Synapse API URL (default: env SYNAPSE_API_URL or http://localhost:8080)",
    )
    doctor.add_argument(
        "--project-id",
        default=os.getenv("SYNAPSE_PROJECT_ID"),
        help="Project ID for project-scoped checks (tasks/wiki/mcp explain).",
    )
    doctor.add_argument(
        "--timeout-seconds",
        type=float,
        default=4.0,
        help="HTTP timeout per check in seconds.",
    )
    doctor.add_argument(
        "--skip-mcp",
        action="store_true",
        help="Skip MCP retrieval explain endpoint check.",
    )
    doctor.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any non-skipped check fails.",
    )
    doctor.add_argument(
        "--json",
        action="store_true",
        help="Render doctor report as JSON.",
    )
    doctor.set_defaults(func=_cmd_doctor)

    init = subparsers.add_parser("init", help="Scaffold local Synapse SDK config for a project")
    init.add_argument(
        "--dir",
        default=".",
        help="Target directory for generated config (default: current directory).",
    )
    init.add_argument(
        "--env-file",
        default=".env.synapse",
        help="Config file name to create in target directory (default: .env.synapse).",
    )
    init.add_argument(
        "--project-id",
        default=os.getenv("SYNAPSE_PROJECT_ID"),
        help="Project ID (default: env SYNAPSE_PROJECT_ID or derived from directory name).",
    )
    init.add_argument(
        "--api-url",
        default=os.getenv("SYNAPSE_API_URL", "http://localhost:8080"),
        help="Synapse API URL (default: env SYNAPSE_API_URL or http://localhost:8080).",
    )
    init.add_argument(
        "--context-policy-profile",
        default="enforced",
        help="Default context policy profile for MCP helper (default: enforced).",
    )
    init.add_argument(
        "--openclaw-bootstrap-preset",
        default="hybrid",
        help="Default OpenClaw bootstrap preset hint (default: hybrid).",
    )
    init.add_argument("--force", action="store_true", help="Overwrite existing env file.")
    init.add_argument("--dry-run", action="store_true", help="Print generated payload without writing file.")
    init.add_argument("--json", action="store_true", help="Render init result as JSON.")
    init.set_defaults(func=_cmd_init)

    connect = subparsers.add_parser("connect", help="Generate integration snippets for common runtimes")
    connect_subparsers = connect.add_subparsers(dest="connect_target")

    connect_openclaw = connect_subparsers.add_parser(
        "openclaw",
        help="Generate env-aware OpenClaw attach snippet (SDK + MCP context callback).",
    )
    connect_openclaw.add_argument("--dir", default=".", help="Workspace directory for env-file resolution.")
    connect_openclaw.add_argument(
        "--env-file",
        default=".env.synapse",
        help="Env file path to read defaults from (default: .env.synapse).",
    )
    connect_openclaw.add_argument("--api-url", default=None, help="Override Synapse API URL.")
    connect_openclaw.add_argument("--project-id", default=None, help="Override Synapse project id.")
    connect_openclaw.add_argument(
        "--context-policy-profile",
        default=None,
        help="MCP context policy profile (advisory|enforced|strict_enforced|off).",
    )
    connect_openclaw.add_argument(
        "--openclaw-bootstrap-preset",
        default=None,
        help="Bootstrap preset (runtime_memory|event_log|hybrid).",
    )
    connect_openclaw.add_argument("--tool-prefix", default="synapse", help="OpenClaw tool prefix.")
    connect_openclaw.add_argument("--agent-id", default=None, help="Default agent id to annotate captured events.")
    connect_openclaw.add_argument("--session-id", default=None, help="Default session id to annotate captured events.")
    connect_openclaw.add_argument(
        "--entity-key",
        default=None,
        help="Optional default entity_key filter for MCP search callback.",
    )
    connect_openclaw.add_argument(
        "--runtime-var",
        default="openclaw_runtime",
        help="Variable name for OpenClaw runtime object in generated snippet.",
    )
    connect_openclaw.add_argument("--no-mcp", action="store_true", help="Generate snippet without MCP callback wiring.")
    connect_openclaw.add_argument("--json", action="store_true", help="Render connect output as JSON.")
    connect_openclaw.set_defaults(func=_cmd_connect_openclaw)

    verify = subparsers.add_parser("verify", help="Run end-to-end verification helpers")
    verify_subparsers = verify.add_subparsers(dest="verify_target")

    verify_core_loop = verify_subparsers.add_parser(
        "core-loop",
        help="Run core acceptance scenario (`ingest -> draft -> approve -> MCP retrieval`).",
    )
    verify_core_loop.add_argument(
        "--script",
        default=None,
        help="Path to integration_core_loop.py (auto-detected when omitted).",
    )
    verify_core_loop.add_argument(
        "--api-python",
        default=sys.executable,
        help="Python executable used to run integration script (default: current python).",
    )
    verify_core_loop.add_argument(
        "--api-url",
        default=None,
        help="Forwarded to integration script (optional, use existing API).",
    )
    verify_core_loop.add_argument(
        "--database-url",
        default=None,
        help="Forwarded DB DSN (optional, defaults to script behavior).",
    )
    verify_core_loop.add_argument(
        "--project-id",
        default=None,
        help="Override project id scope.",
    )
    verify_core_loop.add_argument(
        "--request-timeout",
        type=float,
        default=8.0,
        help="HTTP timeout forwarded to integration script.",
    )
    verify_core_loop.add_argument(
        "--worker-mode",
        choices=["local", "poll"],
        default=None,
        help="Worker mode override (`local` or `poll`).",
    )
    verify_core_loop.add_argument(
        "--max-worker-cycles",
        type=int,
        default=5,
        help="Max synthesis worker cycles before failure (forwarded).",
    )
    verify_core_loop.add_argument(
        "--worker-poll-interval",
        type=float,
        default=1.0,
        help="Polling interval in seconds for `worker-mode=poll`.",
    )
    verify_core_loop.add_argument(
        "--mcp-probe-mode",
        choices=["local", "container"],
        default=None,
        help="MCP probe mode override (`local` or `container`).",
    )
    verify_core_loop.add_argument(
        "--mcp-container-name",
        default=None,
        help="Container name for `mcp-probe-mode=container`.",
    )
    verify_core_loop.add_argument(
        "--mcp-host",
        default=None,
        help="Host reachability check target for container probe mode.",
    )
    verify_core_loop.add_argument(
        "--mcp-port",
        type=int,
        default=None,
        help="Port reachability check target for container probe mode.",
    )
    verify_core_loop.add_argument(
        "--dry-run",
        action="store_true",
        help="Print resolved command without execution.",
    )
    verify_core_loop.add_argument(
        "--json",
        action="store_true",
        help="Render verify result as JSON.",
    )
    verify_core_loop.set_defaults(func=_cmd_verify_core_loop)

    quickstart = subparsers.add_parser(
        "quickstart",
        help="Run one-command onboarding flow (`init -> doctor -> connect`, optional verify).",
    )
    quickstart.add_argument(
        "--dir",
        default=".",
        help="Workspace directory for generated config and snippet defaults.",
    )
    quickstart.add_argument(
        "--env-file",
        default=".env.synapse",
        help="Env file path (relative to --dir by default).",
    )
    quickstart.add_argument(
        "--project-id",
        default=os.getenv("SYNAPSE_PROJECT_ID"),
        help="Project id override.",
    )
    quickstart.add_argument(
        "--api-url",
        default=os.getenv("SYNAPSE_API_URL", "http://localhost:8080"),
        help="Synapse API URL.",
    )
    quickstart.add_argument(
        "--context-policy-profile",
        default="enforced",
        help="MCP context policy profile for generated connect snippet.",
    )
    quickstart.add_argument(
        "--openclaw-bootstrap-preset",
        default="hybrid",
        help="OpenClaw bootstrap preset for generated connect snippet.",
    )
    quickstart.add_argument("--tool-prefix", default="synapse", help="OpenClaw tool prefix for connect snippet.")
    quickstart.add_argument("--runtime-var", default="openclaw_runtime", help="OpenClaw runtime variable name.")
    quickstart.add_argument(
        "--doctor-strict",
        action="store_true",
        help="Fail quickstart if doctor finds failed checks.",
    )
    quickstart.add_argument("--skip-doctor", action="store_true", help="Skip doctor readiness checks.")
    quickstart.add_argument("--force-init", action="store_true", help="Overwrite existing env file during init.")
    quickstart.add_argument("--verify-core-loop", action="store_true", help="Run `verify core-loop` at the end.")
    quickstart.add_argument(
        "--verify-script",
        default=None,
        help="Optional script path forwarded to `verify core-loop --script`.",
    )
    quickstart.add_argument(
        "--verify-worker-mode",
        choices=["local", "poll"],
        default=None,
        help="Optional worker mode forwarded to `verify core-loop`.",
    )
    quickstart.add_argument(
        "--verify-mcp-probe-mode",
        choices=["local", "container"],
        default=None,
        help="Optional MCP probe mode forwarded to `verify core-loop`.",
    )
    quickstart.add_argument("--json", action="store_true", help="Render quickstart result as JSON.")
    quickstart.set_defaults(func=_cmd_quickstart)

    return parser


def _cmd_extract(args: argparse.Namespace) -> int:
    try:
        payload = _read_payload(args)
    except ValueError as exc:
        print(f"[synapse-cli] invalid input: {exc}", file=sys.stderr)
        return 2

    extractors = _resolve_extractors(_split_csv(args.extractors))
    synthesizers = _resolve_synthesizers(_split_csv(args.synthesizers))
    context = InsightContext(
        function_name=args.function_name,
        integration=args.integration,
        args=(),
        kwargs={},
        result=payload,
        category_hint=args.category,
        entity_hint=args.entity_key,
        source_id=args.source_id,
    )
    extracted: list[ExtractedInsight] = []
    for extractor in extractors:
        extracted.extend(extractor.extract(context))

    synthesized = list(extracted)
    for synthesizer in synthesizers:
        synth_context = SynthesisContext(
            function_name=args.function_name,
            integration=args.integration,
            extracted_insights=tuple(synthesized),
            args=(),
            kwargs={},
            result=payload,
            category_hint=args.category,
            entity_hint=args.entity_key,
            source_id=args.source_id,
        )
        synthesized = list(synthesizer.synthesize(synth_context))

    min_confidence = max(0.0, min(1.0, float(args.min_confidence)))
    filtered = [
        item
        for item in synthesized
        if item.claim_text.strip() and (item.confidence is None or float(item.confidence) >= min_confidence)
    ]
    output: dict[str, Any] = {
        "input_kind": "json" if args.result_json else "text",
        "extractors": [item.name for item in extractors],
        "synthesizers": [item.name for item in synthesizers],
        "counts": {
            "extracted": len(extracted),
            "synthesized": len(synthesized),
            "filtered": len(filtered),
        },
        "insights": [asdict(item) for item in filtered],
    }
    if args.as_claims:
        output["claims"] = [_insight_to_claim_dict(item, args) for item in filtered]
    _print_json(output, pretty=bool(args.pretty))
    return 0


def _cmd_replay(args: argparse.Namespace) -> int:
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        print(f"[synapse-cli] input file not found: {input_path}", file=sys.stderr)
        return 2
    try:
        raw_records = _load_records(input_path)
    except ValueError as exc:
        print(f"[synapse-cli] failed to parse {input_path}: {exc}", file=sys.stderr)
        return 2
    normalized = [_normalize_record(item) for item in raw_records]
    records = [item for item in normalized if item is not None]
    if not records:
        print("[synapse-cli] no replayable records found", file=sys.stderr)
        return 3

    filtered = records
    if args.trace_id:
        filtered = [item for item in records if item["trace_id"] == args.trace_id]
        if not filtered:
            print(f"[synapse-cli] no records for trace_id={args.trace_id}", file=sys.stderr)
            return 3

    traces_counter = Counter(item["trace_id"] or "no-trace" for item in records)
    target_trace_id = args.trace_id or (traces_counter.most_common(1)[0][0] if traces_counter else "no-trace")
    if not args.trace_id:
        filtered = [item for item in records if (item["trace_id"] or "no-trace") == target_trace_id]

    filtered.sort(key=lambda item: (item["ts"] or "", item["order"]))
    limited = filtered[: max(1, int(args.limit))]
    span_counter = Counter(item["span_id"] or "no-span" for item in limited)
    event_counter = Counter(item["event"] for item in limited)
    report = {
        "input": str(input_path),
        "records_total": len(records),
        "records_in_trace": len(filtered),
        "records_output": len(limited),
        "trace_id": target_trace_id,
        "spans": len(span_counter),
        "top_events": event_counter.most_common(10),
        "timeline": limited,
    }
    if args.json:
        _print_json(report, pretty=True)
        return 0

    print(f"Trace: {target_trace_id}")
    print(
        f"Records: total={report['records_total']} trace={report['records_in_trace']} shown={report['records_output']} spans={report['spans']}"
    )
    print("Top events:")
    for event, count in report["top_events"]:
        print(f"- {event}: {count}")
    print("Timeline:")
    for row in limited:
        summary = row["summary"]
        print(f"- {row['ts'] or 'n/a'} | {row['span_id'] or 'no-span'} | {row['event']} | {summary}")
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    api_url = str(args.api_url or "").strip().rstrip("/")
    if not api_url:
        print("[synapse-cli] --api-url cannot be empty", file=sys.stderr)
        return 2
    project_id = _coerce_text(args.project_id)
    timeout = max(0.2, float(args.timeout_seconds))
    checks: list[dict[str, Any]] = []

    checks.append(
        _run_http_check(
            name="api_health",
            method="GET",
            url=f"{api_url}/health",
            timeout=timeout,
            validator=lambda payload: isinstance(payload, dict) and str(payload.get("status") or "").lower() == "ok",
            hint="Start local stack: `docker compose -f infra/docker-compose.selfhost.yml up -d`.",
        )
    )

    if project_id:
        checks.append(
            _run_http_check(
                name="tasks_api",
                method="GET",
                url=f"{api_url}/v1/tasks",
                timeout=timeout,
                params={"project_id": project_id, "limit": 1},
                validator=lambda payload: isinstance(payload, dict) and isinstance(payload.get("tasks"), list),
                hint="Verify API migrations and `project_id` value.",
            )
        )
        checks.append(
            _run_http_check(
                name="wiki_drafts_api",
                method="GET",
                url=f"{api_url}/v1/wiki/drafts",
                timeout=timeout,
                params={"project_id": project_id, "status": "open", "limit": 1},
                validator=lambda payload: isinstance(payload, dict) and isinstance(payload.get("drafts"), list),
                hint="Check worker/API compatibility and wiki tables migrations.",
            )
        )
        if not bool(args.skip_mcp):
            checks.append(
                _run_http_check(
                    name="mcp_retrieval_explain_api",
                    method="GET",
                    url=f"{api_url}/v1/mcp/retrieval/explain",
                    timeout=timeout,
                    params={"project_id": project_id, "q": "synapse health check", "limit": 1},
                    validator=lambda payload: isinstance(payload, dict) and "results" in payload,
                    hint="If this fails, ensure API version includes MCP retrieval diagnostics endpoint.",
                )
            )
    else:
        checks.append(
            {
                "name": "project_scoped_checks",
                "ok": None,
                "skipped": True,
                "detail": "Set --project-id (or SYNAPSE_PROJECT_ID) to run tasks/wiki/mcp checks.",
                "hint": None,
            }
        )

    summary = {
        "total": len(checks),
        "ok": sum(1 for item in checks if item.get("ok") is True),
        "failed": sum(1 for item in checks if item.get("ok") is False),
        "skipped": sum(1 for item in checks if item.get("ok") is None),
    }
    report = {
        "api_url": api_url,
        "project_id": project_id,
        "timeout_seconds": timeout,
        "summary": summary,
        "checks": checks,
    }
    if args.json:
        _print_json(report, pretty=True)
    else:
        _print_doctor_report(report)

    if bool(args.strict) and summary["failed"] > 0:
        return 1
    return 0


def _cmd_init(args: argparse.Namespace) -> int:
    target_dir = Path(str(args.dir or ".")).expanduser().resolve()
    if not target_dir.exists():
        print(f"[synapse-cli] target directory not found: {target_dir}", file=sys.stderr)
        return 2
    if not target_dir.is_dir():
        print(f"[synapse-cli] target path is not a directory: {target_dir}", file=sys.stderr)
        return 2

    env_name = str(args.env_file or ".env.synapse").strip() or ".env.synapse"
    if "/" in env_name or "\\" in env_name:
        print("[synapse-cli] --env-file should be a file name, not a nested path", file=sys.stderr)
        return 2
    env_path = target_dir / env_name
    api_url = str(args.api_url or "").strip().rstrip("/")
    if not api_url:
        print("[synapse-cli] --api-url cannot be empty", file=sys.stderr)
        return 2

    project_id = _sanitize_project_id(args.project_id) or _infer_project_id_from_dir(target_dir)
    policy_profile = _sanitize_simple_key(args.context_policy_profile, fallback="enforced")
    bootstrap_preset = _sanitize_simple_key(args.openclaw_bootstrap_preset, fallback="hybrid")

    content_lines = [
        "# Synapse SDK bootstrap config (generated by synapse-cli init)",
        f"# generated_at={datetime.now(UTC).isoformat()}",
        f"SYNAPSE_API_URL={api_url}",
        f"SYNAPSE_PROJECT_ID={project_id}",
        "SYNAPSE_API_KEY=",
        f"SYNAPSE_CONTEXT_POLICY_PROFILE={policy_profile}",
        f"SYNAPSE_OPENCLAW_BOOTSTRAP_PRESET={bootstrap_preset}",
        "",
    ]
    rendered = "\n".join(content_lines)

    existed_before = env_path.exists()
    if existed_before and not bool(args.force) and not bool(args.dry_run):
        print(
            f"[synapse-cli] {env_path} already exists. Use --force to overwrite or --dry-run to preview.",
            file=sys.stderr,
        )
        return 3

    if not bool(args.dry_run):
        env_path.write_text(rendered, encoding="utf-8")

    quickstart = [
        f"source {env_path}",
        "synapse-cli doctor --api-url \"$SYNAPSE_API_URL\" --project-id \"$SYNAPSE_PROJECT_ID\"",
        "python -m synapse_sdk.cli extract --text \"BC Omega gate now requires access cards\" --category access_policy --entity-key bc_omega --pretty",
    ]
    result = {
        "status": "ok",
        "mode": "dry_run" if bool(args.dry_run) else "written",
        "target_dir": str(target_dir),
        "env_path": str(env_path),
        "env_file_existed": existed_before,
        "project_id": project_id,
        "api_url": api_url,
        "context_policy_profile": policy_profile,
        "openclaw_bootstrap_preset": bootstrap_preset,
        "quickstart_commands": quickstart,
        "content": rendered,
    }
    if bool(args.json):
        _print_json(result, pretty=True)
    else:
        print("Synapse Init")
        print(f"- mode: {result['mode']}")
        print(f"- env: {env_path}")
        print(f"- project_id: {project_id}")
        print("Next:")
        for command in quickstart:
            print(f"- {command}")
    return 0


def _cmd_connect_openclaw(args: argparse.Namespace) -> int:
    workspace_dir = Path(str(args.dir or ".")).expanduser().resolve()
    if not workspace_dir.exists() or not workspace_dir.is_dir():
        print(f"[synapse-cli] --dir is not a valid directory: {workspace_dir}", file=sys.stderr)
        return 2

    env_file_raw = str(args.env_file or ".env.synapse").strip() or ".env.synapse"
    env_path = Path(env_file_raw).expanduser()
    if not env_path.is_absolute():
        env_path = (workspace_dir / env_path).resolve()
    env_values = _read_env_file(env_path) if env_path.exists() else {}

    api_url = _resolve_setting(
        explicit=_coerce_text(args.api_url),
        env_key="SYNAPSE_API_URL",
        env_file_values=env_values,
        fallback="http://localhost:8080",
    ).rstrip("/")
    if not api_url:
        print("[synapse-cli] resolved API URL is empty", file=sys.stderr)
        return 2

    project_id = _sanitize_project_id(
        _resolve_setting(
            explicit=_coerce_text(args.project_id),
            env_key="SYNAPSE_PROJECT_ID",
            env_file_values=env_values,
            fallback=_infer_project_id_from_dir(workspace_dir),
        )
    )
    if not project_id:
        print("[synapse-cli] resolved project_id is empty", file=sys.stderr)
        return 2

    from synapse_sdk.integrations.openclaw import list_openclaw_bootstrap_presets
    from synapse_sdk.mcp import list_context_policy_profiles

    allowed_profiles = {str(item.get("profile")) for item in list_context_policy_profiles()}
    resolved_profile = _sanitize_simple_key(
        _resolve_setting(
            explicit=_coerce_text(args.context_policy_profile),
            env_key="SYNAPSE_CONTEXT_POLICY_PROFILE",
            env_file_values=env_values,
            fallback="enforced",
        ),
        fallback="enforced",
    )
    if resolved_profile not in allowed_profiles:
        allowed = ", ".join(sorted(allowed_profiles))
        print(
            f"[synapse-cli] unsupported context policy profile `{resolved_profile}` (allowed: {allowed})",
            file=sys.stderr,
        )
        return 2

    allowed_presets = {str(item.get("preset")) for item in list_openclaw_bootstrap_presets()}
    resolved_bootstrap_preset = _sanitize_simple_key(
        _resolve_setting(
            explicit=_coerce_text(args.openclaw_bootstrap_preset),
            env_key="SYNAPSE_OPENCLAW_BOOTSTRAP_PRESET",
            env_file_values=env_values,
            fallback="hybrid",
        ),
        fallback="hybrid",
    )
    if resolved_bootstrap_preset not in allowed_presets:
        allowed = ", ".join(sorted(allowed_presets))
        print(
            f"[synapse-cli] unsupported OpenClaw bootstrap preset `{resolved_bootstrap_preset}` (allowed: {allowed})",
            file=sys.stderr,
        )
        return 2

    tool_prefix = _sanitize_simple_key(args.tool_prefix, fallback="synapse")
    agent_id = _coerce_text(args.agent_id)
    session_id = _coerce_text(args.session_id)
    entity_key = _sanitize_simple_key(args.entity_key, fallback="") if _coerce_text(args.entity_key) else None
    runtime_var = _sanitize_python_identifier(args.runtime_var, fallback="openclaw_runtime")
    include_mcp = not bool(args.no_mcp)

    snippet = _build_openclaw_connect_snippet(
        api_url=api_url,
        project_id=project_id,
        runtime_var=runtime_var,
        tool_prefix=tool_prefix,
        bootstrap_preset=resolved_bootstrap_preset,
        context_policy_profile=resolved_profile,
        include_mcp=include_mcp,
        entity_key=entity_key,
        agent_id=agent_id,
        session_id=session_id,
    )

    quickstart: list[str] = []
    if env_path.exists():
        quickstart.append(f"source {env_path}")
    else:
        quickstart.append(
            f"synapse-cli init --dir {workspace_dir} --project-id {project_id} --api-url {api_url}"
        )
        quickstart.append(f"source {env_path}")
    quickstart.extend(
        [
            f"synapse-cli doctor --api-url {api_url} --project-id {project_id}",
            "# Paste generated Python snippet into your OpenClaw runtime bootstrap module.",
        ]
    )

    result = {
        "status": "ok",
        "target": "openclaw",
        "workspace_dir": str(workspace_dir),
        "env_path": str(env_path),
        "env_file_found": bool(env_path.exists()),
        "api_url": api_url,
        "project_id": project_id,
        "context_policy_profile": resolved_profile,
        "openclaw_bootstrap_preset": resolved_bootstrap_preset,
        "tool_prefix": tool_prefix,
        "include_mcp": include_mcp,
        "snippet": snippet,
        "quickstart_commands": quickstart,
    }
    if bool(args.json):
        _print_json(result, pretty=True)
    else:
        print("Synapse Connect: OpenClaw")
        print(f"- env: {env_path} ({'found' if env_path.exists() else 'not found'})")
        print(f"- project_id: {project_id}")
        print(f"- api_url: {api_url}")
        print(f"- context_policy_profile: {resolved_profile}")
        print(f"- openclaw_bootstrap_preset: {resolved_bootstrap_preset}")
        print("Python snippet:")
        print(snippet)
        print("Next:")
        for command in quickstart:
            print(f"- {command}")
    return 0


def _cmd_verify_core_loop(args: argparse.Namespace) -> int:
    script_path = _resolve_core_loop_script(_coerce_text(args.script))
    if script_path is None:
        print(
            "[synapse-cli] integration script not found. Provide --script or run from repository root containing scripts/integration_core_loop.py",
            file=sys.stderr,
        )
        return 2

    api_python = str(_coerce_text(args.api_python) or sys.executable).strip()
    if not api_python:
        print("[synapse-cli] --api-python cannot be empty", file=sys.stderr)
        return 2

    command: list[str] = [api_python, str(script_path)]
    api_url = _coerce_text(args.api_url)
    database_url = _coerce_text(args.database_url)
    project_id = _coerce_text(args.project_id)
    request_timeout = max(0.2, float(args.request_timeout))
    max_worker_cycles = max(1, int(args.max_worker_cycles))
    worker_poll_interval = max(0.1, float(args.worker_poll_interval))

    if api_url:
        command.extend(["--api-url", api_url.rstrip("/")])
    if database_url:
        command.extend(["--database-url", database_url])
    if project_id:
        command.extend(["--project-id", project_id])

    command.extend(
        [
            "--request-timeout",
            str(request_timeout),
            "--max-worker-cycles",
            str(max_worker_cycles),
            "--worker-poll-interval",
            str(worker_poll_interval),
        ]
    )
    if args.worker_mode:
        command.extend(["--worker-mode", str(args.worker_mode)])
    if args.mcp_probe_mode:
        command.extend(["--mcp-probe-mode", str(args.mcp_probe_mode)])
    if _coerce_text(args.mcp_container_name):
        command.extend(["--mcp-container-name", str(args.mcp_container_name)])
    if _coerce_text(args.mcp_host):
        command.extend(["--mcp-host", str(args.mcp_host)])
    if args.mcp_port is not None:
        command.extend(["--mcp-port", str(max(1, int(args.mcp_port)))])

    shell_command = shlex.join(command)
    if bool(args.dry_run):
        payload = {
            "status": "dry_run",
            "script_path": str(script_path),
            "command": shell_command,
        }
        if bool(args.json):
            _print_json(payload, pretty=True)
        else:
            print("Synapse Verify: Core Loop")
            print(f"- script: {script_path}")
            print(f"- command: {shell_command}")
        return 0

    proc = subprocess.run(command, capture_output=True, text=True, check=False)
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    parsed: dict[str, Any] | None = None
    if stdout:
        try:
            loaded = json.loads(stdout)
            if isinstance(loaded, dict):
                parsed = loaded
        except Exception:
            parsed = None

    ok = proc.returncode == 0
    payload = {
        "status": "ok" if ok else "failed",
        "script_path": str(script_path),
        "command": shell_command,
        "return_code": int(proc.returncode),
        "result": parsed,
        "stdout": stdout if not parsed else None,
        "stderr": stderr or None,
    }
    if bool(args.json):
        _print_json(payload, pretty=True)
    else:
        print("Synapse Verify: Core Loop")
        print(f"- status: {payload['status']}")
        print(f"- command: {shell_command}")
        if parsed:
            print(f"- result_status: {parsed.get('status')}")
            if parsed.get("project_id"):
                print(f"- project_id: {parsed.get('project_id')}")
            if parsed.get("batch_id"):
                print(f"- batch_id: {parsed.get('batch_id')}")
            if parsed.get("approved_draft_id"):
                print(f"- approved_draft_id: {parsed.get('approved_draft_id')}")
            if parsed.get("page_slug"):
                print(f"- page_slug: {parsed.get('page_slug')}")
        elif stdout:
            print("- stdout:")
            print(stdout[-3000:])
        if stderr:
            print("- stderr:")
            print(stderr[-3000:])
    return 0 if ok else 1


def _cmd_quickstart(args: argparse.Namespace) -> int:
    workspace_dir = Path(str(args.dir or ".")).expanduser().resolve()
    if not workspace_dir.exists() or not workspace_dir.is_dir():
        print(f"[synapse-cli] --dir is not a valid directory: {workspace_dir}", file=sys.stderr)
        return 2

    env_file = str(args.env_file or ".env.synapse").strip() or ".env.synapse"
    api_url = str(_coerce_text(args.api_url) or "http://localhost:8080").strip().rstrip("/")
    if not api_url:
        print("[synapse-cli] --api-url cannot be empty", file=sys.stderr)
        return 2
    project_id_raw = _coerce_text(args.project_id)
    init_project_id = project_id_raw or _infer_project_id_from_dir(workspace_dir)
    context_policy_profile = _sanitize_simple_key(args.context_policy_profile, fallback="enforced")
    bootstrap_preset = _sanitize_simple_key(args.openclaw_bootstrap_preset, fallback="hybrid")
    tool_prefix = _sanitize_simple_key(args.tool_prefix, fallback="synapse")
    runtime_var = _sanitize_python_identifier(args.runtime_var, fallback="openclaw_runtime")

    python_exec = sys.executable
    env = dict(os.environ)
    steps: list[dict[str, Any]] = []

    init_cmd = [
        python_exec,
        "-m",
        "synapse_sdk.cli",
        "init",
        "--dir",
        str(workspace_dir),
        "--env-file",
        env_file,
        "--project-id",
        init_project_id,
        "--api-url",
        api_url,
        "--context-policy-profile",
        context_policy_profile,
        "--openclaw-bootstrap-preset",
        bootstrap_preset,
        "--json",
    ]
    if bool(args.force_init):
        init_cmd.append("--force")
    init_step = _run_cli_json_step("init", init_cmd, env=env)
    steps.append(init_step)
    if not init_step.get("ok"):
        return _render_quickstart_result(args, steps, workspace_dir)
    init_payload = init_step.get("payload") if isinstance(init_step.get("payload"), dict) else {}
    resolved_project_id = _sanitize_project_id(init_payload.get("project_id") or init_project_id)
    if not resolved_project_id:
        resolved_project_id = _sanitize_project_id(init_project_id)

    if not bool(args.skip_doctor):
        doctor_cmd = [
            python_exec,
            "-m",
            "synapse_sdk.cli",
            "doctor",
            "--api-url",
            api_url,
            "--project-id",
            resolved_project_id,
            "--json",
        ]
        if bool(args.doctor_strict):
            doctor_cmd.append("--strict")
        doctor_step = _run_cli_json_step("doctor", doctor_cmd, env=env)
        steps.append(doctor_step)
        if not doctor_step.get("ok"):
            return _render_quickstart_result(args, steps, workspace_dir)

    connect_cmd = [
        python_exec,
        "-m",
        "synapse_sdk.cli",
        "connect",
        "openclaw",
        "--dir",
        str(workspace_dir),
        "--env-file",
        env_file,
        "--api-url",
        api_url,
        "--project-id",
        resolved_project_id,
        "--context-policy-profile",
        context_policy_profile,
        "--openclaw-bootstrap-preset",
        bootstrap_preset,
        "--tool-prefix",
        tool_prefix,
        "--runtime-var",
        runtime_var,
        "--json",
    ]
    connect_step = _run_cli_json_step("connect_openclaw", connect_cmd, env=env)
    steps.append(connect_step)
    if not connect_step.get("ok"):
        return _render_quickstart_result(args, steps, workspace_dir)

    if bool(args.verify_core_loop):
        verify_cmd = [
            python_exec,
            "-m",
            "synapse_sdk.cli",
            "verify",
            "core-loop",
            "--project-id",
            resolved_project_id,
            "--json",
        ]
        if _coerce_text(args.verify_script):
            verify_cmd.extend(["--script", str(args.verify_script)])
        if _coerce_text(args.verify_worker_mode):
            verify_cmd.extend(["--worker-mode", str(args.verify_worker_mode)])
        if _coerce_text(args.verify_mcp_probe_mode):
            verify_cmd.extend(["--mcp-probe-mode", str(args.verify_mcp_probe_mode)])
        verify_step = _run_cli_json_step("verify_core_loop", verify_cmd, env=env)
        steps.append(verify_step)
        if not verify_step.get("ok"):
            return _render_quickstart_result(args, steps, workspace_dir)

    return _render_quickstart_result(args, steps, workspace_dir)


def _read_payload(args: argparse.Namespace) -> Any:
    sources = int(bool(args.text)) + int(bool(args.file)) + int(bool(args.stdin))
    if sources != 1:
        raise ValueError("exactly one input source is required: --text or --file or --stdin")
    if args.text:
        raw = args.text
    elif args.file:
        raw = Path(args.file).expanduser().resolve().read_text(encoding="utf-8")
    else:
        raw = sys.stdin.read()
    if args.result_json:
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON payload: {exc}") from exc
    return raw


def _resolve_extractors(names: list[str]) -> list[Any]:
    registry = {item.name: item for item in default_extractors()}
    if not names:
        return list(registry.values())
    missing = [name for name in names if name not in registry]
    if missing:
        raise ValueError(f"unknown extractors: {', '.join(missing)}")
    return [registry[name] for name in names]


def _resolve_synthesizers(names: list[str]) -> list[Any]:
    registry = {item.name: item for item in default_synthesizers()}
    if not names:
        return list(registry.values())
    missing = [name for name in names if name not in registry]
    if missing:
        raise ValueError(f"unknown synthesizers: {', '.join(missing)}")
    return [registry[name] for name in names]


def _split_csv(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _insight_to_claim_dict(item: ExtractedInsight, args: argparse.Namespace) -> dict[str, Any]:
    claim = Claim(
        id=str(uuid4()),
        schema_version="v1",
        project_id="local_cli",
        entity_key=item.entity_key or args.entity_key or "unknown_entity",
        category=item.category or args.category or "general",
        claim_text=item.claim_text,
        status="draft",
        confidence=item.confidence,
        valid_from=item.valid_from,
        valid_to=item.valid_to,
        metadata=dict(item.metadata),
        evidence=[
            EvidenceRef(
                source_type="tool_output",
                source_id=args.source_id,
                observed_at=datetime.now(UTC).isoformat(),
            )
        ],
    )
    return asdict(claim)


def _load_records(path: Path) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    if path.suffix.lower() == ".jsonl":
        out: list[dict[str, Any]] = []
        for line_no, line in enumerate(raw.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"line {line_no}: {exc}") from exc
            if isinstance(value, dict):
                out.append(value)
        return out
    value = json.loads(raw)
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        records = value.get("records")
        if isinstance(records, list):
            return [item for item in records if isinstance(item, dict)]
        return [value]
    return []


def _normalize_record(raw: dict[str, Any]) -> dict[str, Any] | None:
    if "event" in raw:
        event = str(raw.get("event") or "")
        ts = _coerce_text(raw.get("ts")) or _coerce_text(raw.get("observed_at"))
        trace_id = _coerce_text(raw.get("trace_id")) or _coerce_text(raw.get("traceId"))
        span_id = _coerce_text(raw.get("span_id")) or _coerce_text(raw.get("spanId"))
        details = raw.get("details") if isinstance(raw.get("details"), dict) else {}
        summary = _summary_from_details(details)
        return {
            "order": int(raw.get("order", 0)),
            "ts": ts,
            "event": event,
            "trace_id": trace_id,
            "span_id": span_id,
            "summary": summary,
        }
    if "event_type" in raw:
        payload = raw.get("payload") if isinstance(raw.get("payload"), dict) else {}
        return {
            "order": int(raw.get("order", 0)),
            "ts": _coerce_text(raw.get("observed_at")) or _coerce_text(raw.get("ts")),
            "event": str(raw.get("event_type") or ""),
            "trace_id": _coerce_text(raw.get("trace_id")),
            "span_id": _coerce_text(raw.get("span_id")),
            "summary": _summary_from_details(payload),
        }
    return None


def _summary_from_details(details: dict[str, Any]) -> str:
    for key in ("phase", "method", "function", "error_message", "claim_id", "event_name"):
        value = details.get(key)
        if isinstance(value, str) and value:
            return f"{key}={value}"
    if "batch_size" in details:
        return f"batch_size={details['batch_size']}"
    if "queue_size" in details:
        return f"queue_size={details['queue_size']}"
    if not details:
        return "-"
    keys = sorted(details.keys())
    return f"keys={','.join(keys[:5])}"


def _coerce_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _print_json(payload: Any, *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(json.dumps(payload, ensure_ascii=False))


def _run_http_check(
    *,
    name: str,
    method: str,
    url: str,
    timeout: float,
    validator: Any,
    hint: str | None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        response = requests.request(method=method, url=url, params=params, timeout=timeout)
        status_code = int(response.status_code)
    except requests.RequestException as exc:
        return {
            "name": name,
            "ok": False,
            "status_code": None,
            "detail": f"{type(exc).__name__}: {exc}",
            "hint": hint,
        }

    payload: Any = None
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if status_code >= 400:
        detail = f"HTTP {status_code}"
        if isinstance(payload, dict) and payload.get("detail") is not None:
            detail = f"{detail}: {payload.get('detail')}"
        return {
            "name": name,
            "ok": False,
            "status_code": status_code,
            "detail": detail,
            "hint": hint,
        }

    try:
        passed = bool(validator(payload))
    except Exception as exc:
        return {
            "name": name,
            "ok": False,
            "status_code": status_code,
            "detail": f"validator_error: {type(exc).__name__}: {exc}",
            "hint": hint,
        }
    if passed:
        return {
            "name": name,
            "ok": True,
            "status_code": status_code,
            "detail": "ok",
            "hint": None,
        }
    return {
        "name": name,
        "ok": False,
        "status_code": status_code,
        "detail": "unexpected_response_shape",
        "hint": hint,
    }


def _print_doctor_report(report: dict[str, Any]) -> None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    print("Synapse Doctor")
    print(f"- api_url: {report.get('api_url')}")
    project_id = report.get("project_id")
    print(f"- project_id: {project_id if project_id else '(not set)'}")
    print(
        f"- checks: ok={summary.get('ok', 0)} failed={summary.get('failed', 0)} skipped={summary.get('skipped', 0)}"
    )
    print("Checks:")
    checks = report.get("checks")
    if not isinstance(checks, list):
        checks = []
    for item in checks:
        if not isinstance(item, dict):
            continue
        ok_value = item.get("ok")
        if ok_value is True:
            status = "OK"
        elif ok_value is False:
            status = "FAIL"
        else:
            status = "SKIP"
        status_code = item.get("status_code")
        detail = str(item.get("detail") or "")
        if status_code is not None:
            print(f"- [{status}] {item.get('name')} (http={status_code}) {detail}")
        else:
            print(f"- [{status}] {item.get('name')} {detail}")
        if ok_value is False and item.get("hint"):
            print(f"  hint: {item.get('hint')}")


def _sanitize_project_id(value: Any) -> str:
    text = _coerce_text(value) or ""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9_-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:80]


def _sanitize_simple_key(value: Any, *, fallback: str) -> str:
    text = _coerce_text(value) or fallback
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9_-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or fallback


def _infer_project_id_from_dir(path: Path) -> str:
    candidate = _sanitize_project_id(path.name)
    return candidate or "synapse_project"


def _resolve_setting(
    *,
    explicit: str | None,
    env_key: str,
    env_file_values: dict[str, str],
    fallback: str,
) -> str:
    if explicit:
        return explicit
    from_env = _coerce_text(os.getenv(env_key))
    if from_env:
        return from_env
    from_file = _coerce_text(env_file_values.get(env_key))
    if from_file:
        return from_file
    return fallback


def _read_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception:
        return out
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        normalized_key = key.strip()
        if not normalized_key:
            continue
        normalized_value = value.strip().strip("'").strip('"')
        out[normalized_key] = normalized_value
    return out


def _sanitize_python_identifier(value: Any, *, fallback: str) -> str:
    text = _coerce_text(value) or fallback
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", text).strip("_")
    if not normalized:
        return fallback
    if normalized[0].isdigit():
        normalized = f"_{normalized}"
    return normalized


def _build_openclaw_connect_snippet(
    *,
    api_url: str,
    project_id: str,
    runtime_var: str,
    tool_prefix: str,
    bootstrap_preset: str,
    context_policy_profile: str,
    include_mcp: bool,
    entity_key: str | None,
    agent_id: str | None,
    session_id: str | None,
) -> str:
    lines: list[str] = [
        "import os",
    ]
    if include_mcp:
        lines.append("from synapse_sdk import MCPContextHelper, Synapse, SynapseConfig")
    else:
        lines.append("from synapse_sdk import Synapse, SynapseConfig")

    lines.extend(
        [
            "",
            "synapse = Synapse(",
            "    SynapseConfig(",
            f'        api_url="{api_url}",',
            f'        project_id="{project_id}",',
            '        api_key=os.getenv("SYNAPSE_API_KEY"),',
            "    )",
            ")",
        ]
    )
    if include_mcp:
        lines.extend(
            [
                "",
                "helper = MCPContextHelper(",
                f'    project_id="{project_id}",',
                "    call_tool=lambda name, args: mcp_client.call_tool(name, args),",
                f'    default_context_policy_profile="{context_policy_profile}",',
                ")",
                "",
                "search_callback = helper.make_openclaw_search_callback(",
            ]
        )
        if entity_key:
            lines.append(f'    default_filters={{"entity_key": "{entity_key}"}},')
        else:
            lines.append("    default_filters={},")
        lines.extend(
            [
                f'    context_policy_profile="{context_policy_profile}",',
                ")",
            ]
        )

    lines.extend(
        [
            "",
            "synapse.attach(",
            f"    {runtime_var},",
            '    integration="openclaw",',
            f'    openclaw_tool_prefix="{tool_prefix}",',
            f'    openclaw_bootstrap_preset="{bootstrap_preset}",',
        ]
    )
    if include_mcp:
        lines.append("    openclaw_search_knowledge=search_callback,")
    if agent_id:
        lines.append(f'    agent_id="{agent_id}",')
    if session_id:
        lines.append(f'    session_id="{session_id}",')
    lines.append(")")
    return "\n".join(lines)


def _resolve_core_loop_script(explicit: str | None) -> Path | None:
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        if candidate.exists() and candidate.is_file():
            return candidate
        return None

    env_candidate = _coerce_text(os.getenv("SYNAPSE_CORE_LOOP_SCRIPT"))
    if env_candidate:
        candidate = Path(env_candidate).expanduser().resolve()
        if candidate.exists() and candidate.is_file():
            return candidate

    current = Path.cwd().resolve()
    candidates = [current]
    candidates.extend(current.parents)
    for root in candidates:
        candidate = root / "scripts" / "integration_core_loop.py"
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _run_cli_json_step(name: str, command: list[str], *, env: dict[str, str]) -> dict[str, Any]:
    proc = subprocess.run(command, capture_output=True, text=True, env=env, check=False)
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    payload: dict[str, Any] | None = None
    if stdout:
        try:
            loaded = json.loads(stdout)
            if isinstance(loaded, dict):
                payload = loaded
        except Exception:
            payload = None
    ok = proc.returncode == 0
    return {
        "name": name,
        "ok": ok,
        "return_code": int(proc.returncode),
        "command": shlex.join(command),
        "payload": payload,
        "stdout": stdout if payload is None else None,
        "stderr": stderr or None,
    }


def _render_quickstart_result(args: argparse.Namespace, steps: list[dict[str, Any]], workspace_dir: Path) -> int:
    failed_step = next((item for item in steps if not bool(item.get("ok"))), None)
    status = "ok" if failed_step is None else "failed"
    summary = {
        "status": status,
        "workspace_dir": str(workspace_dir),
        "steps_total": len(steps),
        "steps_ok": sum(1 for item in steps if bool(item.get("ok"))),
        "steps_failed": sum(1 for item in steps if not bool(item.get("ok"))),
    }
    payload = {
        "status": status,
        "summary": summary,
        "steps": steps,
    }

    if bool(args.json):
        _print_json(payload, pretty=True)
    else:
        print("Synapse Quickstart")
        print(f"- status: {status}")
        print(f"- workspace: {workspace_dir}")
        print(
            f"- steps: ok={summary['steps_ok']} failed={summary['steps_failed']} total={summary['steps_total']}"
        )
        for item in steps:
            marker = "OK" if bool(item.get("ok")) else "FAIL"
            print(f"- [{marker}] {item.get('name')}")
            print(f"  command: {item.get('command')}")
            data = item.get("payload")
            if isinstance(data, dict):
                if item.get("name") == "init":
                    if data.get("env_path"):
                        print(f"  env_path: {data.get('env_path')}")
                    if data.get("project_id"):
                        print(f"  project_id: {data.get('project_id')}")
                elif item.get("name") == "doctor":
                    doctor_summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
                    print(
                        "  doctor: "
                        f"ok={doctor_summary.get('ok', 0)} "
                        f"failed={doctor_summary.get('failed', 0)} "
                        f"skipped={doctor_summary.get('skipped', 0)}"
                    )
                elif item.get("name") == "connect_openclaw":
                    if data.get("env_path"):
                        print(f"  env_path: {data.get('env_path')}")
                    snippet = str(data.get("snippet") or "")
                    if snippet:
                        print("  snippet_head:")
                        for line in snippet.splitlines()[:4]:
                            print(f"    {line}")
                elif item.get("name") == "verify_core_loop":
                    result = data.get("result") if isinstance(data.get("result"), dict) else {}
                    if result:
                        print(
                            "  verify: "
                            f"status={result.get('status')} "
                            f"draft={result.get('approved_draft_id')} "
                            f"page={result.get('page_slug')}"
                        )
            if item.get("stderr"):
                print(f"  stderr: {str(item.get('stderr'))[-400:]}")
            elif item.get("stdout"):
                print(f"  stdout: {str(item.get('stdout'))[-400:]}")

    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
