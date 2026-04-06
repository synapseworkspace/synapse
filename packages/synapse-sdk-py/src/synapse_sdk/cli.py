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
from urllib.parse import quote, urlencode
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
    connect_openclaw.add_argument(
        "--adoption-mode",
        default=None,
        help="Attach coexistence mode (full_loop|observe_only|draft_only|retrieve_only).",
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

    adopt = subparsers.add_parser(
        "adopt",
        help="Generate coexistence rollout plan for integrating Synapse into existing agent memory stacks.",
    )
    adopt.add_argument("--dir", default=".", help="Workspace directory for env-file resolution.")
    adopt.add_argument(
        "--env-file",
        default=".env.synapse",
        help="Env file path to read defaults from (default: .env.synapse).",
    )
    adopt.add_argument("--api-url", default=None, help="Override Synapse API URL.")
    adopt.add_argument("--project-id", default=None, help="Override Synapse project id.")
    adopt.add_argument(
        "--memory-system",
        default="existing_memory",
        help="Current canonical memory system label (for report metadata).",
    )
    adopt.add_argument(
        "--memory-source",
        default="hybrid",
        help="Primary source shape (runtime_memory|event_log|hybrid|external_kb).",
    )
    adopt.add_argument(
        "--adoption-mode",
        default="observe_only",
        help="Attach coexistence mode (full_loop|observe_only|draft_only|retrieve_only).",
    )
    adopt.add_argument(
        "--sample-file",
        default=None,
        help="Optional JSON/JSONL file with existing memory records for quality/risk analysis.",
    )
    adopt.add_argument(
        "--max-sample-records",
        type=int,
        default=5000,
        help="Maximum records to load from --sample-file.",
    )
    adopt.add_argument(
        "--shadow-retrieval-check",
        action="store_true",
        help="Run shadow retrieval diff report against /v1/mcp/retrieval/explain using sample-file as baseline.",
    )
    adopt.add_argument(
        "--shadow-query",
        action="append",
        default=None,
        help="Explicit query for shadow retrieval check (repeatable).",
    )
    adopt.add_argument(
        "--shadow-limit",
        type=int,
        default=5,
        help="Top-k limit for baseline and Synapse retrieval comparison (default: 5).",
    )
    adopt.add_argument(
        "--shadow-timeout-seconds",
        type=float,
        default=4.0,
        help="HTTP timeout per shadow retrieval request (default: 4.0).",
    )
    adopt.add_argument(
        "--context-policy-profile",
        default=None,
        help="MCP context policy profile (advisory|enforced|strict_enforced|off).",
    )
    adopt.add_argument(
        "--openclaw-bootstrap-preset",
        default=None,
        help="Bootstrap preset (runtime_memory|event_log|hybrid).",
    )
    adopt.add_argument("--tool-prefix", default="synapse", help="OpenClaw tool prefix for snippet.")
    adopt.add_argument(
        "--runtime-var",
        default="openclaw_runtime",
        help="Variable name for OpenClaw runtime object in generated snippet.",
    )
    adopt.add_argument("--agent-id", default=None, help="Default agent id in generated snippet.")
    adopt.add_argument("--session-id", default=None, help="Default session id in generated snippet.")
    adopt.add_argument(
        "--entity-key",
        default=None,
        help="Optional default entity_key filter for MCP search callback.",
    )
    adopt.add_argument("--no-mcp", action="store_true", help="Generate snippet without MCP callback wiring.")
    adopt.add_argument("--json", action="store_true", help="Render adoption plan as JSON.")
    adopt.set_defaults(func=_cmd_adopt_existing_memory)

    wiki_space_policy = subparsers.add_parser(
        "wiki-space-policy",
        help="Inspect and update wiki space policy (including publish checklist presets).",
    )
    wiki_space_policy_subparsers = wiki_space_policy.add_subparsers(dest="wiki_space_policy_command")

    wiki_space_policy_get = wiki_space_policy_subparsers.add_parser(
        "get",
        help="Fetch current policy for a wiki space.",
    )
    wiki_space_policy_get.add_argument(
        "--api-url",
        default=os.getenv("SYNAPSE_API_URL", "http://localhost:8080"),
        help="Synapse API URL (default: env SYNAPSE_API_URL or http://localhost:8080).",
    )
    wiki_space_policy_get.add_argument(
        "--project-id",
        default=os.getenv("SYNAPSE_PROJECT_ID"),
        help="Project ID scope (default: env SYNAPSE_PROJECT_ID).",
    )
    wiki_space_policy_get.add_argument("--space-key", required=True, help="Space key/slug (e.g. operations).")
    wiki_space_policy_get.add_argument(
        "--timeout-seconds",
        type=float,
        default=6.0,
        help="HTTP timeout per request in seconds.",
    )
    wiki_space_policy_get.add_argument("--json", action="store_true", help="Render output as JSON.")
    wiki_space_policy_get.set_defaults(func=_cmd_wiki_space_policy_get)

    wiki_space_policy_audit = wiki_space_policy_subparsers.add_parser(
        "audit",
        help="List recent policy changes for a wiki space.",
    )
    wiki_space_policy_audit.add_argument(
        "--api-url",
        default=os.getenv("SYNAPSE_API_URL", "http://localhost:8080"),
        help="Synapse API URL (default: env SYNAPSE_API_URL or http://localhost:8080).",
    )
    wiki_space_policy_audit.add_argument(
        "--project-id",
        default=os.getenv("SYNAPSE_PROJECT_ID"),
        help="Project ID scope (default: env SYNAPSE_PROJECT_ID).",
    )
    wiki_space_policy_audit.add_argument("--space-key", required=True, help="Space key/slug (e.g. operations).")
    wiki_space_policy_audit.add_argument(
        "--limit",
        type=int,
        default=40,
        help="Max audit entries to return (1..200, default: 40).",
    )
    wiki_space_policy_audit.add_argument(
        "--timeout-seconds",
        type=float,
        default=6.0,
        help="HTTP timeout per request in seconds.",
    )
    wiki_space_policy_audit.add_argument("--json", action="store_true", help="Render output as JSON.")
    wiki_space_policy_audit.set_defaults(func=_cmd_wiki_space_policy_audit)

    wiki_space_policy_set = wiki_space_policy_subparsers.add_parser(
        "set",
        help="Upsert full policy for a wiki space.",
    )
    wiki_space_policy_set.add_argument(
        "--api-url",
        default=os.getenv("SYNAPSE_API_URL", "http://localhost:8080"),
        help="Synapse API URL (default: env SYNAPSE_API_URL or http://localhost:8080).",
    )
    wiki_space_policy_set.add_argument(
        "--project-id",
        default=os.getenv("SYNAPSE_PROJECT_ID"),
        help="Project ID scope (default: env SYNAPSE_PROJECT_ID).",
    )
    wiki_space_policy_set.add_argument("--space-key", required=True, help="Space key/slug (e.g. operations).")
    wiki_space_policy_set.add_argument("--updated-by", required=True, help="Actor id for audit trail.")
    wiki_space_policy_set.add_argument(
        "--write-mode",
        choices=["open", "owners_only"],
        default="open",
        help="Write policy mode (default: open).",
    )
    wiki_space_policy_set.add_argument(
        "--comment-mode",
        choices=["open", "owners_only"],
        default="open",
        help="Comment policy mode (default: open).",
    )
    wiki_space_policy_set.add_argument(
        "--review-assignment-required",
        action="store_true",
        help="Require reviewer assignment before publish.",
    )
    wiki_space_policy_set.add_argument(
        "--metadata-json",
        default=None,
        help="Optional metadata JSON object merged as policy metadata.",
    )
    wiki_space_policy_set.add_argument(
        "--idempotency-key",
        default=None,
        help="Optional idempotency key for upsert request.",
    )
    wiki_space_policy_set.add_argument(
        "--timeout-seconds",
        type=float,
        default=6.0,
        help="HTTP timeout per request in seconds.",
    )
    wiki_space_policy_set.add_argument("--json", action="store_true", help="Render output as JSON.")
    wiki_space_policy_set.set_defaults(func=_cmd_wiki_space_policy_set)

    wiki_space_policy_set_preset = wiki_space_policy_subparsers.add_parser(
        "set-checklist-preset",
        help="Update only publish checklist preset while preserving other policy fields.",
    )
    wiki_space_policy_set_preset.add_argument(
        "--api-url",
        default=os.getenv("SYNAPSE_API_URL", "http://localhost:8080"),
        help="Synapse API URL (default: env SYNAPSE_API_URL or http://localhost:8080).",
    )
    wiki_space_policy_set_preset.add_argument(
        "--project-id",
        default=os.getenv("SYNAPSE_PROJECT_ID"),
        help="Project ID scope (default: env SYNAPSE_PROJECT_ID).",
    )
    wiki_space_policy_set_preset.add_argument("--space-key", required=True, help="Space key/slug (e.g. operations).")
    wiki_space_policy_set_preset.add_argument("--updated-by", required=True, help="Actor id for audit trail.")
    wiki_space_policy_set_preset.add_argument(
        "--preset",
        required=True,
        choices=["none", "ops_standard", "policy_strict"],
        help="Publish checklist preset.",
    )
    wiki_space_policy_set_preset.add_argument(
        "--reason",
        default=None,
        help="Optional policy-change reason persisted in metadata.",
    )
    wiki_space_policy_set_preset.add_argument(
        "--idempotency-key",
        default=None,
        help="Optional idempotency key for upsert request.",
    )
    wiki_space_policy_set_preset.add_argument(
        "--timeout-seconds",
        type=float,
        default=6.0,
        help="HTTP timeout per request in seconds.",
    )
    wiki_space_policy_set_preset.add_argument("--json", action="store_true", help="Render output as JSON.")
    wiki_space_policy_set_preset.set_defaults(func=_cmd_wiki_space_policy_set_preset)

    wiki_lifecycle = subparsers.add_parser(
        "wiki-lifecycle",
        help="Lifecycle diagnostics helpers for stale-page triage and deep-link generation.",
    )
    wiki_lifecycle_subparsers = wiki_lifecycle.add_subparsers(dest="wiki_lifecycle_command")

    wiki_lifecycle_stale = wiki_lifecycle_subparsers.add_parser(
        "stale",
        help="List stale wiki pages from lifecycle diagnostics.",
    )
    wiki_lifecycle_stale.add_argument(
        "--api-url",
        default=os.getenv("SYNAPSE_API_URL", "http://localhost:8080"),
        help="Synapse API URL (default: env SYNAPSE_API_URL or http://localhost:8080).",
    )
    wiki_lifecycle_stale.add_argument(
        "--project-id",
        default=os.getenv("SYNAPSE_PROJECT_ID"),
        help="Project ID scope (default: env SYNAPSE_PROJECT_ID).",
    )
    wiki_lifecycle_stale.add_argument(
        "--space",
        default=None,
        help="Optional wiki space key scope (for example: operations).",
    )
    wiki_lifecycle_stale.add_argument(
        "--preset",
        choices=["stale_21", "critical_45", "custom"],
        default="stale_21",
        help="Lifecycle threshold preset (default: stale_21).",
    )
    wiki_lifecycle_stale.add_argument(
        "--stale-days",
        type=int,
        default=21,
        help="Stale threshold in days (used when --preset=custom, default: 21).",
    )
    wiki_lifecycle_stale.add_argument(
        "--critical-days",
        type=int,
        default=45,
        help="Critical stale threshold in days (used when --preset=custom, default: 45).",
    )
    wiki_lifecycle_stale.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max stale candidates to fetch (default: 20).",
    )
    wiki_lifecycle_stale.add_argument(
        "--web-base-url",
        default=None,
        help="Optional base URL for deep-link suggestions (default: derive from --api-url).",
    )
    wiki_lifecycle_stale.add_argument(
        "--timeout-seconds",
        type=float,
        default=6.0,
        help="HTTP timeout per request in seconds.",
    )
    wiki_lifecycle_stale.add_argument("--json", action="store_true", help="Render output as JSON.")
    wiki_lifecycle_stale.set_defaults(func=_cmd_wiki_lifecycle_stale)

    wiki_lifecycle_telemetry = wiki_lifecycle_subparsers.add_parser(
        "telemetry",
        help="Show empty-scope lifecycle action telemetry summary.",
    )
    wiki_lifecycle_telemetry.add_argument(
        "--api-url",
        default=os.getenv("SYNAPSE_API_URL", "http://localhost:8080"),
        help="Synapse API URL (default: env SYNAPSE_API_URL or http://localhost:8080).",
    )
    wiki_lifecycle_telemetry.add_argument(
        "--project-id",
        default=os.getenv("SYNAPSE_PROJECT_ID"),
        help="Project ID scope (default: env SYNAPSE_PROJECT_ID).",
    )
    wiki_lifecycle_telemetry.add_argument(
        "--days",
        type=int,
        default=7,
        help="Telemetry window in days (default: 7, max: 90).",
    )
    wiki_lifecycle_telemetry.add_argument(
        "--top",
        type=int,
        default=5,
        help="Max top actions to print in text mode (default: 5).",
    )
    wiki_lifecycle_telemetry.add_argument(
        "--timeout-seconds",
        type=float,
        default=6.0,
        help="HTTP timeout per request in seconds.",
    )
    wiki_lifecycle_telemetry.add_argument("--json", action="store_true", help="Render output as JSON.")
    wiki_lifecycle_telemetry.set_defaults(func=_cmd_wiki_lifecycle_telemetry)

    wiki_lifecycle_open_drafts = wiki_lifecycle_subparsers.add_parser(
        "open-drafts",
        help="Generate deep-link URL to open drafts inbox for a page.",
    )
    wiki_lifecycle_open_drafts.add_argument(
        "--project-id",
        default=os.getenv("SYNAPSE_PROJECT_ID"),
        help="Project ID scope (default: env SYNAPSE_PROJECT_ID).",
    )
    wiki_lifecycle_open_drafts.add_argument("--page-slug", required=True, help="Wiki page slug.")
    wiki_lifecycle_open_drafts.add_argument(
        "--web-base-url",
        default=None,
        help="Web app base URL (default: derive from SYNAPSE_WEB_BASE_URL or http://localhost:5173).",
    )
    wiki_lifecycle_open_drafts.add_argument("--json", action="store_true", help="Render output as JSON.")
    wiki_lifecycle_open_drafts.set_defaults(func=_cmd_wiki_lifecycle_open_drafts)

    wiki_lifecycle_open_policy = wiki_lifecycle_subparsers.add_parser(
        "open-policy",
        help="Generate deep-link URL to open governance/policy view for a page.",
    )
    wiki_lifecycle_open_policy.add_argument(
        "--project-id",
        default=os.getenv("SYNAPSE_PROJECT_ID"),
        help="Project ID scope (default: env SYNAPSE_PROJECT_ID).",
    )
    wiki_lifecycle_open_policy.add_argument("--page-slug", required=True, help="Wiki page slug.")
    wiki_lifecycle_open_policy.add_argument(
        "--web-base-url",
        default=None,
        help="Web app base URL (default: derive from SYNAPSE_WEB_BASE_URL or http://localhost:5173).",
    )
    wiki_lifecycle_open_policy.add_argument("--json", action="store_true", help="Render output as JSON.")
    wiki_lifecycle_open_policy.set_defaults(func=_cmd_wiki_lifecycle_open_policy)

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
        "SYNAPSE_ADOPTION_MODE=full_loop",
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

    try:
        resolved_adoption_mode = _normalize_adoption_mode_value(
            _resolve_setting(
                explicit=_coerce_text(args.adoption_mode),
                env_key="SYNAPSE_ADOPTION_MODE",
                env_file_values=env_values,
                fallback="full_loop",
            )
        )
    except ValueError as exc:
        print(f"[synapse-cli] {exc}", file=sys.stderr)
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
        adoption_mode=resolved_adoption_mode,
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
        "adoption_mode": resolved_adoption_mode,
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
        print(f"- adoption_mode: {resolved_adoption_mode}")
        print("Python snippet:")
        print(snippet)
        print("Next:")
        for command in quickstart:
            print(f"- {command}")
    return 0


def _cmd_adopt_existing_memory(args: argparse.Namespace) -> int:
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

    try:
        resolved_adoption_mode = _normalize_adoption_mode_value(
            _resolve_setting(
                explicit=_coerce_text(args.adoption_mode),
                env_key="SYNAPSE_ADOPTION_MODE",
                env_file_values=env_values,
                fallback="observe_only",
            ),
            fallback="observe_only",
        )
    except ValueError as exc:
        print(f"[synapse-cli] {exc}", file=sys.stderr)
        return 2
    memory_system = _sanitize_simple_key(args.memory_system, fallback="existing_memory")
    memory_source = _sanitize_simple_key(args.memory_source, fallback="hybrid")
    tool_prefix = _sanitize_simple_key(args.tool_prefix, fallback="synapse")
    runtime_var = _sanitize_python_identifier(args.runtime_var, fallback="openclaw_runtime")
    include_mcp = not bool(args.no_mcp)
    agent_id = _coerce_text(args.agent_id)
    session_id = _coerce_text(args.session_id)
    entity_key = _sanitize_simple_key(args.entity_key, fallback="") if _coerce_text(args.entity_key) else None

    sample_records: list[dict[str, Any]] | None = None
    sample_report: dict[str, Any] | None = None
    sample_file = _coerce_text(args.sample_file)
    if sample_file:
        sample_path = Path(sample_file).expanduser().resolve()
        if not sample_path.exists() or not sample_path.is_file():
            print(f"[synapse-cli] --sample-file does not exist: {sample_path}", file=sys.stderr)
            return 2
        sample_records = _load_adoption_memory_records(sample_path, max_records=max(1, int(args.max_sample_records)))
        sample_report = _analyze_adoption_memory_records(
            sample_path,
            sample_records,
            max_records=max(1, int(args.max_sample_records)),
        )

    snippet = _build_openclaw_connect_snippet(
        api_url=api_url,
        project_id=project_id,
        runtime_var=runtime_var,
        tool_prefix=tool_prefix,
        bootstrap_preset=resolved_bootstrap_preset,
        adoption_mode=resolved_adoption_mode,
        context_policy_profile=resolved_profile,
        include_mcp=include_mcp,
        entity_key=entity_key,
        agent_id=agent_id,
        session_id=session_id,
    )

    ownership_policy = {
        "runtime_memory": {
            "write_master": memory_system,
            "synapse_role": "observe_and_synthesize",
        },
        "ops_kb_static": {
            "write_master": memory_system,
            "synapse_role": "reference_or_mirror",
        },
        "synapse_wiki": {
            "write_master": "synapse",
            "synapse_role": "human_or_policy_gated_canonical",
        },
    }
    rollout = [
        {
            "phase": "observe_only",
            "goal": "Ingest existing memory and validate draft quality without behavior impact.",
            "exit": "Draft precision and conflict-rate are acceptable for first production slice.",
        },
        {
            "phase": "draft_only",
            "goal": "Enable proposal path while keeping retrieval behavior unchanged.",
            "exit": "Moderation throughput and approval latency meet team target.",
        },
        {
            "phase": "retrieve_only_shadow",
            "goal": "Evaluate retrieval quality using Synapse in shadow/non-blocking mode.",
            "exit": "Top-k relevance and conflict explainability pass acceptance checks.",
        },
        {
            "phase": "full_loop",
            "goal": "Enable policy-driven publish/retrieval for selected categories.",
            "exit": "SLO, audit, and operator workflows are stable over production load.",
        },
    ]
    risks: list[str] = [
        "Dual source of truth if both existing KB and Synapse Wiki are writable for the same domain.",
        "Source provenance drift if source_id is unstable across retries/import batches.",
        "Behavior regressions if retrieval is enabled before moderation quality is calibrated.",
    ]
    if sample_report is not None:
        for item in sample_report.get("risks", []):
            text = str(item).strip()
            if text:
                risks.append(text)

    quickstart_commands = [
        f"synapse-cli doctor --api-url {api_url} --project-id {project_id}",
        (
            "synapse-cli connect openclaw "
            f"--dir {workspace_dir} --env-file {env_path.name} "
            f"--api-url {api_url} --project-id {project_id} --adoption-mode {resolved_adoption_mode}"
        ),
        (
            "python -m synapse_sdk.cli verify core-loop "
            f"--project-id {project_id} --dry-run"
        ),
    ]
    shadow_report: dict[str, Any] | None = None
    if bool(args.shadow_retrieval_check):
        if not sample_records:
            print(
                "[synapse-cli] --shadow-retrieval-check requires --sample-file with at least one parseable record",
                file=sys.stderr,
            )
            return 2
        queries = [
            query
            for raw in list(args.shadow_query or [])
            for query in [_coerce_text(raw)]
            if query
        ]
        if not queries:
            queries = _derive_shadow_queries_from_records(sample_records, max_queries=5)
        if not queries:
            print(
                "[synapse-cli] unable to derive shadow queries from sample records; pass --shadow-query",
                file=sys.stderr,
            )
            return 2
        shadow_report = _run_shadow_retrieval_check(
            api_url=api_url,
            project_id=project_id,
            records=sample_records,
            queries=queries,
            limit=max(1, int(args.shadow_limit)),
            timeout_seconds=max(0.2, float(args.shadow_timeout_seconds)),
        )
        if shadow_report.get("summary", {}).get("status") == "error":
            print(
                "[synapse-cli] shadow retrieval check failed: "
                f"{shadow_report.get('summary', {}).get('error')}",
                file=sys.stderr,
            )
            return 3

    result = {
        "status": "ok",
        "target": "existing_memory_adoption",
        "workspace_dir": str(workspace_dir),
        "env_path": str(env_path),
        "env_file_found": bool(env_path.exists()),
        "api_url": api_url,
        "project_id": project_id,
        "memory_system": memory_system,
        "memory_source": memory_source,
        "context_policy_profile": resolved_profile,
        "openclaw_bootstrap_preset": resolved_bootstrap_preset,
        "adoption_mode": resolved_adoption_mode,
        "ownership_policy": ownership_policy,
        "rollout_plan": rollout,
        "risks": risks,
        "sample_report": sample_report,
        "shadow_retrieval_report": shadow_report,
        "snippet": snippet,
        "quickstart_commands": quickstart_commands,
    }
    if bool(args.json):
        _print_json(result, pretty=True)
    else:
        print("Synapse Adoption Plan")
        print(f"- project_id: {project_id}")
        print(f"- memory_system: {memory_system}")
        print(f"- memory_source: {memory_source}")
        print(f"- adoption_mode: {resolved_adoption_mode}")
        if sample_report is not None:
            print(
                "- sample: "
                f"records={sample_report.get('records_total', 0)} "
                f"risk={sample_report.get('risk_level')} "
                f"missing_source_id={sample_report.get('missing_source_id', 0)}"
            )
        if shadow_report is not None:
            summary = shadow_report.get("summary") if isinstance(shadow_report, dict) else {}
            print(
                "- shadow_retrieval: "
                f"queries={summary.get('queries_total', 0)} "
                f"avg_overlap={summary.get('avg_overlap_ratio', 0.0)} "
                f"status={summary.get('status')}"
            )
        print("Python snippet:")
        print(snippet)
        print("Next:")
        for command in quickstart_commands:
            print(f"- {command}")
    return 0


def _cmd_wiki_space_policy_get(args: argparse.Namespace) -> int:
    resolved = _resolve_wiki_space_policy_api_args(args)
    if not resolved["ok"]:
        print(f"[synapse-cli] {resolved['error']}", file=sys.stderr)
        return 2
    api_url = str(resolved["api_url"])
    project_id = str(resolved["project_id"])
    space_key = str(resolved["space_key"])
    timeout = float(resolved["timeout_seconds"])
    response = _synapse_api_json(
        method="GET",
        url=f"{api_url}/v1/wiki/spaces/{space_key}/policy",
        params={"project_id": project_id},
        timeout=timeout,
    )
    payload = response["payload"] if isinstance(response.get("payload"), dict) else {}
    if bool(args.json):
        _print_json(
            {
                **payload,
                "_http_status": response["status_code"],
                "_ok": bool(response["ok"]),
                "_error": response.get("error"),
            },
            pretty=True,
        )
    else:
        policy = payload.get("policy") if isinstance(payload.get("policy"), dict) else {}
        metadata = policy.get("metadata") if isinstance(policy.get("metadata"), dict) else {}
        preset = metadata.get("publish_checklist_preset") or "none"
        print("Wiki Space Policy")
        print(f"- project_id: {project_id}")
        print(f"- space_key: {space_key}")
        print(f"- http_status: {response['status_code']}")
        print(f"- write_mode: {policy.get('write_mode') or 'open'}")
        print(f"- comment_mode: {policy.get('comment_mode') or 'open'}")
        print(f"- review_assignment_required: {bool(policy.get('review_assignment_required'))}")
        print(f"- publish_checklist_preset: {preset}")
        if response.get("error"):
            print(f"- error: {response['error']}")
    return 0 if bool(response["ok"]) else 1


def _cmd_wiki_space_policy_audit(args: argparse.Namespace) -> int:
    resolved = _resolve_wiki_space_policy_api_args(args)
    if not resolved["ok"]:
        print(f"[synapse-cli] {resolved['error']}", file=sys.stderr)
        return 2
    api_url = str(resolved["api_url"])
    project_id = str(resolved["project_id"])
    space_key = str(resolved["space_key"])
    timeout = float(resolved["timeout_seconds"])
    limit = max(1, min(200, int(args.limit)))
    response = _synapse_api_json(
        method="GET",
        url=f"{api_url}/v1/wiki/spaces/{space_key}/policy/audit",
        params={"project_id": project_id, "limit": limit},
        timeout=timeout,
    )
    payload = response["payload"] if isinstance(response.get("payload"), dict) else {}
    entries = payload.get("entries") if isinstance(payload.get("entries"), list) else []
    if bool(args.json):
        _print_json(
            {
                **payload,
                "_http_status": response["status_code"],
                "_ok": bool(response["ok"]),
                "_error": response.get("error"),
            },
            pretty=True,
        )
    else:
        print("Wiki Space Policy Audit")
        print(f"- project_id: {project_id}")
        print(f"- space_key: {space_key}")
        print(f"- entries: {len(entries)}")
        print(f"- http_status: {response['status_code']}")
        if entries:
            print("Recent changes:")
            for entry in entries[:10]:
                if not isinstance(entry, dict):
                    continue
                changed_fields = entry.get("changed_fields") if isinstance(entry.get("changed_fields"), list) else []
                print(
                    "- "
                    f"{entry.get('created_at') or 'n/a'} "
                    f"by={entry.get('changed_by') or 'unknown'} "
                    f"fields={','.join(str(item) for item in changed_fields) or '-'}"
                )
        if response.get("error"):
            print(f"- error: {response['error']}")
    return 0 if bool(response["ok"]) else 1


def _cmd_wiki_space_policy_set(args: argparse.Namespace) -> int:
    resolved = _resolve_wiki_space_policy_api_args(args)
    if not resolved["ok"]:
        print(f"[synapse-cli] {resolved['error']}", file=sys.stderr)
        return 2
    api_url = str(resolved["api_url"])
    project_id = str(resolved["project_id"])
    space_key = str(resolved["space_key"])
    timeout = float(resolved["timeout_seconds"])
    metadata, metadata_error = _parse_metadata_json(_coerce_text(args.metadata_json))
    if metadata_error:
        print(f"[synapse-cli] {metadata_error}", file=sys.stderr)
        return 2
    request_payload = {
        "project_id": project_id,
        "space_key": space_key,
        "updated_by": str(args.updated_by).strip(),
        "write_mode": str(args.write_mode).strip().lower(),
        "comment_mode": str(args.comment_mode).strip().lower(),
        "review_assignment_required": bool(args.review_assignment_required),
        "metadata": metadata,
    }
    response = _synapse_api_json(
        method="PUT",
        url=f"{api_url}/v1/wiki/spaces/{space_key}/policy",
        payload=request_payload,
        timeout=timeout,
        idempotency_key=_coerce_text(args.idempotency_key),
    )
    payload = response["payload"] if isinstance(response.get("payload"), dict) else {}
    if bool(args.json):
        _print_json(
            {
                **payload,
                "_http_status": response["status_code"],
                "_ok": bool(response["ok"]),
                "_error": response.get("error"),
            },
            pretty=True,
        )
    else:
        policy = payload.get("policy") if isinstance(payload.get("policy"), dict) else {}
        print("Wiki Space Policy Upsert")
        print(f"- project_id: {project_id}")
        print(f"- space_key: {space_key}")
        print(f"- status: {payload.get('status') or ('ok' if response['ok'] else 'error')}")
        print(f"- write_mode: {policy.get('write_mode') or request_payload['write_mode']}")
        print(f"- comment_mode: {policy.get('comment_mode') or request_payload['comment_mode']}")
        print(
            "- review_assignment_required: "
            f"{bool(policy.get('review_assignment_required') if isinstance(policy, dict) else request_payload['review_assignment_required'])}"
        )
        audit = payload.get("audit") if isinstance(payload.get("audit"), dict) else {}
        changed_fields = audit.get("changed_fields") if isinstance(audit.get("changed_fields"), list) else []
        if changed_fields:
            print(f"- changed_fields: {', '.join(str(item) for item in changed_fields)}")
        print(f"- http_status: {response['status_code']}")
        if response.get("error"):
            print(f"- error: {response['error']}")
    return 0 if bool(response["ok"]) else 1


def _cmd_wiki_space_policy_set_preset(args: argparse.Namespace) -> int:
    resolved = _resolve_wiki_space_policy_api_args(args)
    if not resolved["ok"]:
        print(f"[synapse-cli] {resolved['error']}", file=sys.stderr)
        return 2
    api_url = str(resolved["api_url"])
    project_id = str(resolved["project_id"])
    space_key = str(resolved["space_key"])
    timeout = float(resolved["timeout_seconds"])
    preset = str(args.preset).strip().lower()
    if preset not in {"none", "ops_standard", "policy_strict"}:
        print(f"[synapse-cli] unsupported --preset value: {preset}", file=sys.stderr)
        return 2

    current_response = _synapse_api_json(
        method="GET",
        url=f"{api_url}/v1/wiki/spaces/{space_key}/policy",
        params={"project_id": project_id},
        timeout=timeout,
    )
    if not bool(current_response["ok"]):
        print(
            "[synapse-cli] failed to load current policy before preset update: "
            f"{current_response.get('error') or current_response.get('status_code')}",
            file=sys.stderr,
        )
        return 1
    current_payload = current_response["payload"] if isinstance(current_response.get("payload"), dict) else {}
    current_policy = current_payload.get("policy") if isinstance(current_payload.get("policy"), dict) else {}
    current_metadata = current_policy.get("metadata") if isinstance(current_policy.get("metadata"), dict) else {}
    next_metadata = dict(current_metadata)
    next_metadata["publish_checklist_preset"] = preset
    reason = _coerce_text(args.reason)
    if reason:
        next_metadata["policy_change_reason"] = reason

    request_payload = {
        "project_id": project_id,
        "space_key": space_key,
        "updated_by": str(args.updated_by).strip(),
        "write_mode": str(current_policy.get("write_mode") or "open").strip().lower(),
        "comment_mode": str(current_policy.get("comment_mode") or "open").strip().lower(),
        "review_assignment_required": bool(current_policy.get("review_assignment_required")),
        "metadata": next_metadata,
    }
    response = _synapse_api_json(
        method="PUT",
        url=f"{api_url}/v1/wiki/spaces/{space_key}/policy",
        payload=request_payload,
        timeout=timeout,
        idempotency_key=_coerce_text(args.idempotency_key),
    )
    payload = response["payload"] if isinstance(response.get("payload"), dict) else {}
    if bool(args.json):
        _print_json(
            {
                **payload,
                "_http_status": response["status_code"],
                "_ok": bool(response["ok"]),
                "_error": response.get("error"),
            },
            pretty=True,
        )
    else:
        policy = payload.get("policy") if isinstance(payload.get("policy"), dict) else {}
        metadata = policy.get("metadata") if isinstance(policy.get("metadata"), dict) else next_metadata
        print("Wiki Space Policy Preset Update")
        print(f"- project_id: {project_id}")
        print(f"- space_key: {space_key}")
        print(f"- status: {payload.get('status') or ('ok' if response['ok'] else 'error')}")
        print(f"- publish_checklist_preset: {metadata.get('publish_checklist_preset') or preset}")
        audit = payload.get("audit") if isinstance(payload.get("audit"), dict) else {}
        changed_fields = audit.get("changed_fields") if isinstance(audit.get("changed_fields"), list) else []
        if changed_fields:
            print(f"- changed_fields: {', '.join(str(item) for item in changed_fields)}")
        print(f"- http_status: {response['status_code']}")
        if response.get("error"):
            print(f"- error: {response['error']}")
    return 0 if bool(response["ok"]) else 1


def _cmd_wiki_lifecycle_stale(args: argparse.Namespace) -> int:
    resolved = _resolve_lifecycle_api_args(args)
    if not resolved["ok"]:
        print(f"[synapse-cli] {resolved['error']}", file=sys.stderr)
        return 2
    api_url = str(resolved["api_url"])
    project_id = str(resolved["project_id"])
    space_key = _coerce_text(resolved.get("space_key"))
    timeout = float(resolved["timeout_seconds"])
    preset = str(_coerce_text(getattr(args, "preset", None)) or "stale_21").strip().lower()
    if preset not in {"stale_21", "critical_45", "custom"}:
        preset = "stale_21"
    if preset == "critical_45":
        stale_days = 45
        critical_days = 45
    elif preset == "custom":
        stale_days = max(1, int(args.stale_days))
        critical_days = max(stale_days, int(args.critical_days))
    else:
        stale_days = 21
        critical_days = 45
    limit = max(1, min(200, int(args.limit)))
    request_params: dict[str, Any] = {
        "project_id": project_id,
        "stale_days": stale_days,
        "critical_days": critical_days,
        "stale_limit": limit,
    }
    if space_key:
        request_params["space_key"] = space_key
    response = _synapse_api_json(
        method="GET",
        url=f"{api_url}/v1/wiki/lifecycle/stats",
        params=request_params,
        timeout=timeout,
    )
    payload = response["payload"] if isinstance(response.get("payload"), dict) else {}
    stale_pages = payload.get("stale_pages") if isinstance(payload.get("stale_pages"), list) else []
    web_base_url = _resolve_web_base_url(args.web_base_url, api_url=api_url)
    if bool(args.json):
        with_links: list[dict[str, Any]] = []
        for item in stale_pages:
            if not isinstance(item, dict):
                continue
            slug = str(item.get("slug") or "").strip()
            if not slug:
                continue
            with_links.append(
                {
                    **item,
                    "deep_links": {
                        "drafts": _build_wiki_lifecycle_deeplink(
                            web_base_url,
                            project_id=project_id,
                            page_slug=slug,
                            target="drafts",
                            space_key=space_key,
                        ),
                        "policy": _build_wiki_lifecycle_deeplink(
                            web_base_url,
                            project_id=project_id,
                            page_slug=slug,
                            target="policy",
                            space_key=space_key,
                        ),
                    },
                }
            )
        _print_json(
            {
                **payload,
                "stale_pages": with_links,
                "meta_cli": {"web_base_url": web_base_url, "preset": preset},
                "_http_status": response["status_code"],
                "_ok": bool(response["ok"]),
                "_error": response.get("error"),
            },
            pretty=True,
        )
    else:
        counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
        print("Wiki Lifecycle Stale")
        print(f"- project_id: {project_id}")
        print(f"- preset: {preset}")
        if space_key:
            print(f"- space: {space_key}")
        print(f"- stale_days: {stale_days}")
        print(f"- critical_days: {critical_days}")
        print(f"- fetched: {len(stale_pages)}")
        print(
            "- counts: "
            f"published={counts.get('published_pages', 0)} "
            f"stale={counts.get('stale_warning_pages', 0)} "
            f"critical={counts.get('stale_critical_pages', 0)}"
        )
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        empty_scope = meta.get("empty_scope") if isinstance(meta.get("empty_scope"), dict) else None
        if empty_scope:
            code = str(empty_scope.get("code") or "").strip() or "unknown"
            message = str(empty_scope.get("message") or "").strip() or "No stale pages in selected scope."
            print(f"- empty_scope: {code}")
            print(f"  reason: {message}")
            details = empty_scope.get("details") if isinstance(empty_scope.get("details"), dict) else {}
            if details:
                print(
                    "  details: "
                    f"published={details.get('published_pages', 0)} "
                    f"with_open_drafts={details.get('published_pages_with_open_drafts', 0)} "
                    f"below_threshold={details.get('published_pages_below_stale_threshold', 0)} "
                    f"stale_days={details.get('stale_days', stale_days)}"
                )
            suggested_actions = (
                empty_scope.get("suggested_actions") if isinstance(empty_scope.get("suggested_actions"), list) else []
            )
            if suggested_actions:
                print("  suggested_actions:")
                for raw_action in suggested_actions:
                    if not isinstance(raw_action, dict):
                        continue
                    action = str(raw_action.get("action") or "").strip()
                    label = str(raw_action.get("label") or action or "action")
                    deep_link = raw_action.get("deep_link") if isinstance(raw_action.get("deep_link"), dict) else {}
                    deep_tab = str(deep_link.get("core_tab") or "").strip().lower()
                    deep_focus = str(deep_link.get("wiki_focus") or "").strip().lower()
                    if deep_tab in {"wiki", "drafts", "tasks"}:
                        if deep_focus:
                            print(
                                f"    - {label} ({action}) | deep_link: core_tab={deep_tab}, wiki_focus={deep_focus}"
                            )
                        else:
                            print(f"    - {label} ({action}) | deep_link: core_tab={deep_tab}")
                    else:
                        print(f"    - {label} ({action})")
        if stale_pages:
            print("Stale candidates:")
            for item in stale_pages[: min(10, len(stale_pages))]:
                if not isinstance(item, dict):
                    continue
                slug = str(item.get("slug") or "").strip()
                if not slug:
                    continue
                title = str(item.get("title") or slug)
                severity = str(item.get("severity") or "warning")
                age_days = item.get("age_days")
                open_draft_count = max(0, int(item.get("open_draft_count") or 0))
                print(
                    f"- {title} ({slug}) | severity={severity} age_days={age_days} open_drafts={open_draft_count}"
                )
                print(
                    "  links: "
                    f"drafts={_build_wiki_lifecycle_deeplink(web_base_url, project_id=project_id, page_slug=slug, target='drafts', space_key=space_key)} "
                    f"policy={_build_wiki_lifecycle_deeplink(web_base_url, project_id=project_id, page_slug=slug, target='policy', space_key=space_key)}"
                )
        if response.get("error"):
            print(f"- error: {response['error']}")
    return 0 if bool(response["ok"]) else 1


def _cmd_wiki_lifecycle_telemetry(args: argparse.Namespace) -> int:
    resolved = _resolve_lifecycle_api_args(args)
    if not resolved["ok"]:
        print(f"[synapse-cli] {resolved['error']}", file=sys.stderr)
        return 2
    api_url = str(resolved["api_url"])
    project_id = str(resolved["project_id"])
    timeout = float(resolved["timeout_seconds"])
    days = max(1, min(90, int(args.days)))
    top = max(1, min(30, int(args.top)))
    response = _synapse_api_json(
        method="GET",
        url=f"{api_url}/v1/wiki/lifecycle/telemetry",
        params={"project_id": project_id, "days": days},
        timeout=timeout,
    )
    payload = response["payload"] if isinstance(response.get("payload"), dict) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    actions = summary.get("actions") if isinstance(summary.get("actions"), list) else []
    daily = payload.get("daily") if isinstance(payload.get("daily"), list) else []
    if bool(args.json):
        _print_json(
            {
                **payload,
                "_http_status": response["status_code"],
                "_ok": bool(response["ok"]),
                "_error": response.get("error"),
            },
            pretty=True,
        )
    else:
        print("Wiki Lifecycle Telemetry")
        print(f"- project_id: {project_id}")
        print(f"- days: {days}")
        print(f"- shown_total: {int(summary.get('shown_total', 0) or 0)}")
        print(f"- applied_total: {int(summary.get('applied_total', 0) or 0)}")
        print(f"- apply_rate: {float(summary.get('apply_rate', 0.0) or 0.0):.4f}")
        if actions:
            print("Top actions:")
            for item in actions[:top]:
                if not isinstance(item, dict):
                    continue
                action_key = str(item.get("action_key") or "").strip() or "unknown"
                shown_total = int(item.get("shown_total", 0) or 0)
                applied_total = int(item.get("applied_total", 0) or 0)
                apply_rate = float(item.get("apply_rate", 0.0) or 0.0)
                print(
                    f"- {action_key}: shown={shown_total} applied={applied_total} apply_rate={apply_rate:.4f}"
                )
        if daily:
            print("Daily trend:")
            for item in daily[-7:]:
                if not isinstance(item, dict):
                    continue
                metric_date = str(item.get("metric_date") or "").strip() or "unknown-date"
                shown_total = int(item.get("shown_total", 0) or 0)
                applied_total = int(item.get("applied_total", 0) or 0)
                print(f"- {metric_date}: shown={shown_total} applied={applied_total}")
        if response.get("error"):
            print(f"- error: {response['error']}")
    return 0 if bool(response["ok"]) else 1


def _cmd_wiki_lifecycle_open_drafts(args: argparse.Namespace) -> int:
    project_id = _sanitize_project_id(args.project_id)
    page_slug = _coerce_text(args.page_slug)
    if not project_id:
        print("[synapse-cli] --project-id is required (or set SYNAPSE_PROJECT_ID)", file=sys.stderr)
        return 2
    if not page_slug:
        print("[synapse-cli] --page-slug is required", file=sys.stderr)
        return 2
    web_base_url = _resolve_web_base_url(args.web_base_url, api_url=None)
    url = _build_wiki_lifecycle_deeplink(web_base_url, project_id=project_id, page_slug=page_slug, target="drafts")
    payload = {
        "project_id": project_id,
        "page_slug": page_slug,
        "target": "drafts",
        "url": url,
    }
    if bool(args.json):
        _print_json(payload, pretty=True)
    else:
        print("Wiki Lifecycle Deep Link")
        print(f"- target: drafts")
        print(f"- project_id: {project_id}")
        print(f"- page_slug: {page_slug}")
        print(f"- url: {url}")
    return 0


def _cmd_wiki_lifecycle_open_policy(args: argparse.Namespace) -> int:
    project_id = _sanitize_project_id(args.project_id)
    page_slug = _coerce_text(args.page_slug)
    if not project_id:
        print("[synapse-cli] --project-id is required (or set SYNAPSE_PROJECT_ID)", file=sys.stderr)
        return 2
    if not page_slug:
        print("[synapse-cli] --page-slug is required", file=sys.stderr)
        return 2
    web_base_url = _resolve_web_base_url(args.web_base_url, api_url=None)
    url = _build_wiki_lifecycle_deeplink(web_base_url, project_id=project_id, page_slug=page_slug, target="policy")
    payload = {
        "project_id": project_id,
        "page_slug": page_slug,
        "target": "policy",
        "url": url,
    }
    if bool(args.json):
        _print_json(payload, pretty=True)
    else:
        print("Wiki Lifecycle Deep Link")
        print(f"- target: policy")
        print(f"- project_id: {project_id}")
        print(f"- page_slug: {page_slug}")
        print(f"- url: {url}")
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


def _resolve_wiki_space_policy_api_args(args: argparse.Namespace) -> dict[str, Any]:
    api_url = str(_coerce_text(getattr(args, "api_url", None)) or "").strip().rstrip("/")
    if not api_url:
        return {"ok": False, "error": "--api-url cannot be empty"}
    project_id = _sanitize_project_id(getattr(args, "project_id", None))
    if not project_id:
        return {"ok": False, "error": "--project-id is required (or set SYNAPSE_PROJECT_ID)"}
    raw_space_key = _coerce_text(getattr(args, "space_key", None))
    if not raw_space_key:
        return {"ok": False, "error": "--space-key is required"}
    space_key = _sanitize_simple_key(raw_space_key, fallback="")
    if not space_key:
        return {"ok": False, "error": "resolved --space-key is empty"}
    timeout_seconds = max(0.2, float(getattr(args, "timeout_seconds", 6.0)))
    return {
        "ok": True,
        "api_url": api_url,
        "project_id": project_id,
        "space_key": space_key,
        "timeout_seconds": timeout_seconds,
    }


def _resolve_lifecycle_api_args(args: argparse.Namespace) -> dict[str, Any]:
    api_url = str(_coerce_text(getattr(args, "api_url", None)) or "").strip().rstrip("/")
    if not api_url:
        return {"ok": False, "error": "--api-url cannot be empty"}
    project_id = _sanitize_project_id(getattr(args, "project_id", None))
    if not project_id:
        return {"ok": False, "error": "--project-id is required (or set SYNAPSE_PROJECT_ID)"}
    raw_space_key = _coerce_text(getattr(args, "space", None))
    space_key = _sanitize_simple_key(raw_space_key, fallback="") if raw_space_key else ""
    timeout_seconds = max(0.2, float(getattr(args, "timeout_seconds", 6.0)))
    return {
        "ok": True,
        "api_url": api_url,
        "project_id": project_id,
        "space_key": space_key or None,
        "timeout_seconds": timeout_seconds,
    }


def _resolve_web_base_url(explicit: str | None, *, api_url: str | None) -> str:
    if _coerce_text(explicit):
        return str(explicit).strip().rstrip("/")
    env_value = _coerce_text(os.getenv("SYNAPSE_WEB_BASE_URL"))
    if env_value:
        return env_value.rstrip("/")
    if _coerce_text(api_url):
        candidate = str(api_url).strip().rstrip("/")
        if candidate.endswith(":8080"):
            return f"{candidate[:-5]}:5173"
    return "http://localhost:5173"


def _build_wiki_lifecycle_deeplink(
    web_base_url: str,
    *,
    project_id: str,
    page_slug: str,
    target: str,
    space_key: str | None = None,
) -> str:
    root = str(web_base_url or "http://localhost:5173").strip().rstrip("/")
    params = {
        "project": project_id,
        "wiki_status": "published",
        "wiki_page": page_slug,
    }
    if _coerce_text(space_key):
        params["wiki_space"] = str(space_key).strip()
    if target == "drafts":
        params["core_tab"] = "drafts"
        params["wiki_focus"] = "draft_inbox"
    elif target == "policy":
        params["core_tab"] = "wiki"
        params["wiki_focus"] = "policy_timeline"
    else:
        params["core_tab"] = "wiki"
    query = urlencode({key: str(value) for key, value in params.items()}, quote_via=quote)
    return f"{root}/wiki?{query}"


def _parse_metadata_json(raw: str | None) -> tuple[dict[str, Any], str | None]:
    if not raw:
        return {}, None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {}, f"--metadata-json must be a JSON object: {exc}"
    if not isinstance(parsed, dict):
        return {}, "--metadata-json must be a JSON object"
    return dict(parsed), None


def _synapse_api_json(
    *,
    method: str,
    url: str,
    params: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: float,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    headers: dict[str, str] = {"content-type": "application/json"}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    try:
        response = requests.request(
            method=method,
            url=url,
            params=params,
            json=payload if method.upper() != "GET" else None,
            headers=headers if method.upper() != "GET" or idempotency_key else None,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        return {
            "ok": False,
            "status_code": None,
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    parsed_payload: dict[str, Any]
    try:
        body = response.json()
        parsed_payload = body if isinstance(body, dict) else {"data": body}
    except ValueError:
        parsed_payload = {}
    error_detail: str | None = None
    if response.status_code >= 400:
        if isinstance(parsed_payload, dict):
            detail = parsed_payload.get("detail") or parsed_payload.get("error")
            if detail is not None:
                error_detail = str(detail)
    return {
        "ok": response.status_code < 400,
        "status_code": int(response.status_code),
        "payload": parsed_payload,
        "error": error_detail,
    }


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


def _normalize_adoption_mode_value(value: Any, *, fallback: str = "full_loop") -> str:
    normalized = _sanitize_simple_key(value, fallback=fallback)
    aliases = {
        "full": "full_loop",
        "observe": "observe_only",
        "draft": "draft_only",
        "retrieve": "retrieve_only",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in {"full_loop", "observe_only", "draft_only", "retrieve_only"}:
        raise ValueError(f"unsupported adoption mode: {value}")
    return normalized


def _load_adoption_memory_records(path: Path, *, max_records: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    suffix = path.suffix.lower()
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []

    if suffix == ".jsonl":
        for line_no, line in enumerate(raw.splitlines(), start=1):
            if len(records) >= max_records:
                break
            payload = line.strip()
            if not payload:
                continue
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError:
                continue
            record = _coerce_adoption_memory_record(parsed, index=len(records))
            if record is not None:
                record["_line_no"] = line_no
                records.append(record)
        return records

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = []
    candidates: list[Any]
    if isinstance(parsed, list):
        candidates = parsed
    elif isinstance(parsed, dict) and isinstance(parsed.get("records"), list):
        candidates = list(parsed.get("records") or [])
    elif isinstance(parsed, dict):
        candidates = [parsed]
    else:
        candidates = []
    for item in candidates[:max_records]:
        record = _coerce_adoption_memory_record(item, index=len(records))
        if record is not None:
            records.append(record)
    return records


def _analyze_adoption_memory_sample(path: Path, *, max_records: int) -> dict[str, Any]:
    records = _load_adoption_memory_records(path, max_records=max_records)
    return _analyze_adoption_memory_records(path, records, max_records=max_records)


def _analyze_adoption_memory_records(
    path: Path,
    records: list[dict[str, Any]],
    *,
    max_records: int,
) -> dict[str, Any]:
    if not records:
        return {
            "path": str(path),
            "records_total": 0,
            "records_loaded": 0,
            "records_limit": max_records,
            "risk_level": "low",
            "risks": ["Sample file is empty or had no parseable records."],
        }

    categories: Counter[str] = Counter()
    missing_source_id = 0
    missing_entity_key = 0
    missing_category = 0
    duplicate_content = 0
    source_id_conflicts = 0
    source_content_by_id: dict[str, str] = {}
    content_counts: Counter[str] = Counter()
    topic_buckets: dict[tuple[str, str], set[str]] = {}

    for row in records:
        source_id = str(row.get("source_id") or "").strip()
        content = str(row.get("content") or "").strip()
        entity_key = str(row.get("entity_key") or "").strip()
        category = str(row.get("category") or "").strip().lower()
        if not source_id:
            missing_source_id += 1
        if not entity_key:
            missing_entity_key += 1
        if not category:
            missing_category += 1
            category = "uncategorized"
        categories[category] += 1

        normalized_content = re.sub(r"\s+", " ", content).strip().lower()
        if normalized_content:
            content_counts[normalized_content] += 1
            if content_counts[normalized_content] > 1:
                duplicate_content += 1

        if source_id and normalized_content:
            prev = source_content_by_id.get(source_id)
            if prev is None:
                source_content_by_id[source_id] = normalized_content
            elif prev != normalized_content:
                source_id_conflicts += 1

        bucket_key = (entity_key.lower() or "unknown_entity", category)
        topic = topic_buckets.setdefault(bucket_key, set())
        if normalized_content:
            topic.add(normalized_content)

    topic_collisions = sum(1 for values in topic_buckets.values() if len(values) > 1)
    total = len(records)
    score = 0
    if total > 0:
        if missing_source_id / total >= 0.25:
            score += 2
        if missing_category / total >= 0.3:
            score += 1
        if source_id_conflicts > 0:
            score += 2
        if topic_collisions > max(3, int(total * 0.05)):
            score += 1
    risk_level = "low" if score <= 1 else ("medium" if score <= 3 else "high")

    risks: list[str] = []
    if missing_source_id > 0:
        risks.append(f"{missing_source_id} records have missing source_id; idempotency/dedup can degrade.")
    if source_id_conflicts > 0:
        risks.append(f"{source_id_conflicts} source_id collisions map to different content.")
    if topic_collisions > 0:
        risks.append(f"{topic_collisions} entity/category buckets contain multiple divergent statements.")
    if not risks:
        risks.append("No high-signal structural conflicts found in sample records.")

    return {
        "path": str(path),
        "records_total": total,
        "records_loaded": total,
        "records_limit": max_records,
        "missing_source_id": missing_source_id,
        "missing_entity_key": missing_entity_key,
        "missing_category": missing_category,
        "duplicate_content_count": duplicate_content,
        "source_id_conflicts": source_id_conflicts,
        "topic_collisions": topic_collisions,
        "top_categories": categories.most_common(8),
        "risk_level": risk_level,
        "risks": risks,
    }


def _shadow_tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
    return {token for token in tokens if len(token) >= 2}


def _normalize_shadow_text(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _shadow_similarity(left: str, right: str) -> float:
    left_tokens = _shadow_tokenize(left)
    right_tokens = _shadow_tokenize(right)
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = left_tokens.intersection(right_tokens)
    return float(len(overlap)) / float(max(1, min(len(left_tokens), len(right_tokens))))


def _derive_shadow_queries_from_records(records: list[dict[str, Any]], *, max_queries: int = 5) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for row in records:
        entity = str(row.get("entity_key") or "").strip()
        category = str(row.get("category") or "").strip()
        content = str(row.get("content") or "").strip()
        content_words = re.findall(r"[A-Za-z0-9_#-]+", content)
        snippet = " ".join(content_words[:8]).strip()
        candidates = [
            f"{entity} {category}".strip(),
            entity,
            snippet,
        ]
        for candidate in candidates:
            normalized = re.sub(r"\s+", " ", candidate).strip()
            if len(normalized) < 4:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(normalized)
            if len(out) >= max(1, int(max_queries)):
                return out
    return out


def _rank_shadow_baseline_records(
    records: list[dict[str, Any]],
    *,
    query: str,
    limit: int,
) -> list[dict[str, Any]]:
    query_norm = _normalize_shadow_text(query)
    query_tokens = _shadow_tokenize(query_norm)
    if not query_tokens and not query_norm:
        return []

    scored: list[tuple[float, str, str]] = []
    for row in records:
        content = str(row.get("content") or "").strip()
        if not content:
            continue
        content_norm = _normalize_shadow_text(content)
        content_tokens = _shadow_tokenize(content_norm)
        if not content_tokens:
            continue
        shared = query_tokens.intersection(content_tokens)
        token_recall = float(len(shared)) / float(max(1, len(query_tokens)))
        token_precision = float(len(shared)) / float(max(1, len(content_tokens)))
        phrase_bonus = 0.35 if query_norm and query_norm in content_norm else 0.0
        score = token_recall + (0.35 * token_precision) + phrase_bonus
        if score <= 0:
            continue
        scored.append((score, str(row.get("source_id") or "").strip(), content))

    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    out: list[dict[str, Any]] = []
    for score, source_id, content in scored[: max(1, int(limit))]:
        out.append(
            {
                "source_id": source_id,
                "content": content,
                "score": round(float(score), 4),
            }
        )
    return out


def _extract_shadow_synapse_results(payload: Any, *, limit: int) -> list[str]:
    if not isinstance(payload, dict):
        return []
    raw_results = payload.get("results")
    if not isinstance(raw_results, list):
        return []
    out: list[str] = []
    for row in raw_results:
        if not isinstance(row, dict):
            continue
        text = str(
            row.get("statement_text")
            or row.get("claim_text")
            or row.get("text")
            or ""
        ).strip()
        if not text:
            continue
        out.append(text)
        if len(out) >= max(1, int(limit)):
            break
    return out


def _run_shadow_retrieval_check(
    *,
    api_url: str,
    project_id: str,
    records: list[dict[str, Any]],
    queries: list[str],
    limit: int,
    timeout_seconds: float,
) -> dict[str, Any]:
    normalized_api = str(api_url or "").strip().rstrip("/")
    top_k = max(1, int(limit))
    timeout = max(0.2, float(timeout_seconds))
    per_query: list[dict[str, Any]] = []
    overlap_values: list[float] = []
    successful_queries = 0

    for raw_query in queries:
        query = str(raw_query or "").strip()
        if not query:
            continue
        baseline = _rank_shadow_baseline_records(records, query=query, limit=top_k)
        entry: dict[str, Any] = {
            "query": query,
            "baseline": baseline,
        }
        try:
            response = requests.get(
                f"{normalized_api}/v1/mcp/retrieval/explain",
                params={"project_id": project_id, "q": query, "limit": top_k},
                timeout=timeout,
            )
            entry["http_status"] = int(response.status_code)
            if response.status_code >= 400:
                entry["status"] = "error"
                entry["error"] = f"http_{response.status_code}"
                per_query.append(entry)
                continue
            payload = response.json()
        except Exception as exc:
            entry["status"] = "error"
            entry["error"] = f"{type(exc).__name__}: {exc}"
            per_query.append(entry)
            continue

        synapse_results = _extract_shadow_synapse_results(payload, limit=top_k)
        entry["synapse"] = synapse_results
        baseline_texts = [str(item.get("content") or "") for item in baseline]
        best_similarities: list[float] = []
        matched = 0
        for baseline_text in baseline_texts:
            best = 0.0
            for synapse_text in synapse_results:
                best = max(best, _shadow_similarity(baseline_text, synapse_text))
            best_similarities.append(best)
            if best >= 0.5:
                matched += 1

        denominator = max(1, min(top_k, max(len(baseline_texts), len(synapse_results))))
        overlap_ratio = float(matched) / float(denominator)
        avg_similarity = (
            round(sum(best_similarities) / max(1, len(best_similarities)), 4)
            if best_similarities
            else 0.0
        )
        entry["status"] = "ok"
        entry["overlap_ratio"] = round(overlap_ratio, 4)
        entry["avg_similarity"] = avg_similarity
        entry["matched_items"] = int(matched)
        overlap_values.append(overlap_ratio)
        successful_queries += 1
        per_query.append(entry)

    errors = sum(1 for item in per_query if item.get("status") == "error")
    if successful_queries == 0:
        return {
            "summary": {
                "status": "error",
                "queries_total": len(per_query),
                "queries_ok": 0,
                "queries_failed": errors,
                "error": "no_successful_shadow_queries",
            },
            "queries": per_query,
        }

    avg_overlap = sum(overlap_values) / float(max(1, len(overlap_values)))
    status = "ok" if errors == 0 else "partial"
    return {
        "summary": {
            "status": status,
            "queries_total": len(per_query),
            "queries_ok": successful_queries,
            "queries_failed": errors,
            "avg_overlap_ratio": round(avg_overlap, 4),
            "low_overlap_queries": sum(
                1
                for item in per_query
                if item.get("status") == "ok" and float(item.get("overlap_ratio") or 0.0) < 0.35
            ),
            "top_k": top_k,
        },
        "queries": per_query,
    }


def _coerce_adoption_memory_record(payload: Any, *, index: int) -> dict[str, Any] | None:
    if isinstance(payload, str):
        text = payload.strip()
        if not text:
            return None
        return {
            "source_id": f"sample_{index + 1}",
            "content": text,
            "entity_key": "",
            "category": "",
        }
    if not isinstance(payload, dict):
        return None
    content = _coerce_text(
        payload.get("content")
        or payload.get("text")
        or payload.get("fact")
        or payload.get("message")
        or payload.get("summary")
    )
    if not content:
        return None
    source_id = _coerce_text(payload.get("source_id") or payload.get("id") or payload.get("key")) or f"sample_{index + 1}"
    return {
        "source_id": source_id,
        "content": content,
        "entity_key": _coerce_text(payload.get("entity_key") or payload.get("entity")) or "",
        "category": _coerce_text(payload.get("category")) or "",
    }


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
    adoption_mode: str,
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
            f'    adoption_mode="{adoption_mode}",',
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
