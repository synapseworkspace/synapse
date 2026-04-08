#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def _env_int(name: str, default: int, *, min_value: int = 1) -> int:
    raw = str(os.getenv(name, str(default))).strip()
    try:
        value = int(raw)
    except ValueError:
        value = default
    if value < min_value:
        return min_value
    return value


def _env_bool(name: str, default: bool) -> bool:
    raw = str(os.getenv(name, "1" if default else "0")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class JobSpec:
    name: str
    argv: list[str]
    interval_sec: int
    enabled: bool = True
    last_run_mono: float | None = None

    def due_in(self, now_mono: float) -> float:
        if not self.enabled:
            return float("inf")
        if self.last_run_mono is None:
            return 0.0
        return max(0.0, self.interval_sec - (now_mono - self.last_run_mono))


def _run_job(job: JobSpec) -> None:
    started = datetime.now(UTC).isoformat()
    proc = subprocess.run(
        job.argv,
        cwd=SCRIPT_DIR.parent.parent.parent,
        text=True,
        capture_output=True,
        check=False,
    )
    finished = datetime.now(UTC).isoformat()
    payload = {
        "event": "worker_job_run",
        "job": job.name,
        "status": "ok" if proc.returncode == 0 else "failed",
        "returncode": proc.returncode,
        "started_at": started,
        "finished_at": finished,
    }
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if stdout:
        payload["stdout"] = stdout[-4000:]
    if stderr:
        payload["stderr"] = stderr[-4000:]
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run production-like Synapse worker loop.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run all enabled jobs once and exit.",
    )
    parser.add_argument(
        "--synthesis-interval-sec",
        type=int,
        default=_env_int("SYNAPSE_WORKER_SYNTHESIS_INTERVAL_SEC", 15),
        help="Interval for wiki synthesis job.",
    )
    parser.add_argument(
        "--synthesis-limit",
        type=int,
        default=_env_int("SYNAPSE_WORKER_SYNTHESIS_LIMIT", 100),
        help="Claim proposal limit per synthesis run.",
    )
    parser.add_argument(
        "--synthesis-extract-limit",
        type=int,
        default=_env_int("SYNAPSE_WORKER_SYNTHESIS_EXTRACT_LIMIT", 200),
        help="Backfill extraction limit per synthesis run.",
    )
    parser.add_argument(
        "--enable-legacy-sync",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("SYNAPSE_WORKER_ENABLE_LEGACY_SYNC", True),
        help="Enable periodic legacy import queue scheduler/processor job.",
    )
    parser.add_argument(
        "--legacy-sync-interval-sec",
        type=int,
        default=_env_int("SYNAPSE_WORKER_LEGACY_SYNC_INTERVAL_SEC", 20),
        help="Interval for legacy import sync scheduler job.",
    )
    parser.add_argument(
        "--legacy-sync-enqueue-limit",
        type=int,
        default=_env_int("SYNAPSE_WORKER_LEGACY_SYNC_ENQUEUE_LIMIT", 50),
        help="Maximum due legacy sources queued per scheduler run.",
    )
    parser.add_argument(
        "--legacy-sync-process-limit",
        type=int,
        default=_env_int("SYNAPSE_WORKER_LEGACY_SYNC_PROCESS_LIMIT", 50),
        help="Maximum queued legacy sync runs processed per scheduler run.",
    )
    parser.add_argument(
        "--legacy-sync-all-projects",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("SYNAPSE_WORKER_LEGACY_SYNC_ALL_PROJECTS", True),
        help="Process legacy sync queue across all projects.",
    )
    parser.add_argument(
        "--legacy-sync-api-url",
        default=str(os.getenv("SYNAPSE_WORKER_LEGACY_SYNC_API_URL") or os.getenv("SYNAPSE_API_URL") or "http://api:8080"),
        help="API URL passed to legacy sync scheduler for backfill upload.",
    )
    parser.add_argument(
        "--legacy-sync-api-key",
        default=str(os.getenv("SYNAPSE_WORKER_LEGACY_SYNC_API_KEY") or os.getenv("SYNAPSE_API_KEY") or ""),
        help="Optional API key passed to legacy sync scheduler.",
    )
    parser.add_argument(
        "--legacy-sync-requested-by",
        default=str(os.getenv("SYNAPSE_WORKER_LEGACY_SYNC_REQUESTED_BY") or "legacy_sync_scheduler"),
        help="Actor identity for scheduler-created legacy sync runs.",
    )
    parser.add_argument(
        "--enable-intelligence",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("SYNAPSE_WORKER_ENABLE_INTELLIGENCE", True),
        help="Enable periodic intelligence digest generation + delivery job.",
    )
    parser.add_argument(
        "--intelligence-interval-sec",
        type=int,
        default=_env_int("SYNAPSE_WORKER_INTELLIGENCE_INTERVAL_SEC", 600),
        help="Interval for intelligence scheduler job.",
    )
    parser.add_argument(
        "--intelligence-delivery-limit",
        type=int,
        default=_env_int("SYNAPSE_WORKER_INTELLIGENCE_DELIVERY_LIMIT", 200),
        help="Delivery limit passed to intelligence scheduler.",
    )
    parser.add_argument(
        "--sleep-floor-sec",
        type=int,
        default=_env_int("SYNAPSE_WORKER_SLEEP_FLOOR_SEC", 2),
        help="Minimum sleep between scheduler ticks.",
    )
    parser.add_argument(
        "--enable-auto-publish",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("SYNAPSE_WORKER_ENABLE_AUTO_PUBLISH", True),
        help="Enable periodic wiki auto-publish policy job.",
    )
    parser.add_argument(
        "--auto-publish-interval-sec",
        type=int,
        default=_env_int("SYNAPSE_WORKER_AUTO_PUBLISH_INTERVAL_SEC", 20),
        help="Interval for wiki auto-publish job.",
    )
    parser.add_argument(
        "--auto-publish-limit-per-project",
        type=int,
        default=_env_int("SYNAPSE_WORKER_AUTO_PUBLISH_LIMIT_PER_PROJECT", 50),
        help="Per-project draft scan limit for auto-publish run.",
    )
    parser.add_argument(
        "--auto-publish-reviewed-by",
        default=str(os.getenv("SYNAPSE_AUTOPUBLISH_REVIEWED_BY", "synapse_autopublisher") or "synapse_autopublisher"),
        help="Actor identity used for auto-publish approvals.",
    )
    parser.add_argument(
        "--enable-agent-worklogs",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("SYNAPSE_WORKER_ENABLE_AGENT_WORKLOGS", True),
        help="Enable periodic per-agent daily worklog generation.",
    )
    parser.add_argument(
        "--agent-worklogs-interval-sec",
        type=int,
        default=_env_int("SYNAPSE_WORKER_AGENT_WORKLOGS_INTERVAL_SEC", 86400),
        help="Interval for agent worklog scheduler job.",
    )
    parser.add_argument(
        "--agent-worklogs-discover-limit",
        type=int,
        default=_env_int("SYNAPSE_WORKER_AGENT_WORKLOGS_DISCOVER_LIMIT", 500),
        help="Maximum projects discovered from agent directory per scheduler run.",
    )
    parser.add_argument(
        "--agent-worklogs-days-back",
        type=int,
        default=_env_int("SYNAPSE_WORKER_AGENT_WORKLOGS_DAYS_BACK", 1),
        help="How many days to regenerate on each scheduler run.",
    )
    parser.add_argument(
        "--agent-worklogs-max-agents",
        type=int,
        default=_env_int("SYNAPSE_WORKER_AGENT_WORKLOGS_MAX_AGENTS", 500),
        help="Maximum agents processed per project on each scheduler run.",
    )
    parser.add_argument(
        "--agent-worklogs-max-logs-per-agent-page",
        type=int,
        default=_env_int("SYNAPSE_WORKER_AGENT_WORKLOGS_MAX_LOGS_PER_PAGE", 14),
        help="Maximum daily report entries retained per agent page.",
    )
    parser.add_argument(
        "--agent-worklogs-generated-by",
        default=str(os.getenv("SYNAPSE_AGENT_WORKLOG_GENERATED_BY", "agent_worklog_scheduler") or "agent_worklog_scheduler"),
        help="Actor label used for generated worklog updates.",
    )
    parser.add_argument(
        "--agent-worklogs-include-retired",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("SYNAPSE_WORKER_AGENT_WORKLOGS_INCLUDE_RETIRED", False),
        help="Include retired agents in periodic worklog generation.",
    )
    parser.add_argument(
        "--agent-worklogs-respect-schedule",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("SYNAPSE_WORKER_AGENT_WORKLOGS_RESPECT_SCHEDULE", True),
        help="Respect project local daily worklog schedule in batch mode.",
    )
    parser.add_argument(
        "--enable-agent-worklogs-realtime",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("SYNAPSE_WORKER_ENABLE_AGENT_WORKLOGS_REALTIME", True),
        help="Enable realtime worklog refresh on session/task close signals.",
    )
    parser.add_argument(
        "--agent-worklogs-realtime-interval-sec",
        type=int,
        default=_env_int("SYNAPSE_WORKER_AGENT_WORKLOGS_REALTIME_INTERVAL_SEC", 300),
        help="Interval for realtime worklog trigger job.",
    )
    parser.add_argument(
        "--agent-worklogs-realtime-lookback-minutes",
        type=int,
        default=_env_int("SYNAPSE_WORKER_AGENT_WORKLOGS_REALTIME_LOOKBACK_MINUTES", 15),
        help="Lookback window for session/task close trigger scan.",
    )
    return parser.parse_args()


def build_jobs(args: argparse.Namespace) -> list[JobSpec]:
    python_bin = sys.executable
    synthesis_cmd = [
        python_bin,
        str(SCRIPT_DIR / "run_wiki_synthesis.py"),
        "--extract-limit",
        str(max(1, args.synthesis_extract_limit)),
        "--limit",
        str(max(1, args.synthesis_limit)),
        "--cycles",
        "1",
    ]
    jobs: list[JobSpec] = [
        JobSpec(
            name="wiki_synthesis",
            argv=synthesis_cmd,
            interval_sec=max(1, args.synthesis_interval_sec),
            enabled=True,
        )
    ]
    if args.enable_legacy_sync:
        legacy_sync_cmd = [
            python_bin,
            str(SCRIPT_DIR / "run_legacy_sync_scheduler.py"),
            "--enqueue-limit",
            str(max(1, int(args.legacy_sync_enqueue_limit))),
            "--process-limit",
            str(max(1, int(args.legacy_sync_process_limit))),
            "--api-url",
            str(args.legacy_sync_api_url).strip() or "http://api:8080",
            "--requested-by",
            str(args.legacy_sync_requested_by).strip() or "legacy_sync_scheduler",
        ]
        if bool(args.legacy_sync_all_projects):
            legacy_sync_cmd.append("--all-projects")
        api_key = str(args.legacy_sync_api_key).strip()
        if api_key:
            legacy_sync_cmd.extend(["--api-key", api_key])
        jobs.append(
            JobSpec(
                name="legacy_sync_scheduler",
                argv=legacy_sync_cmd,
                interval_sec=max(1, int(args.legacy_sync_interval_sec)),
                enabled=True,
            )
        )
    if args.enable_intelligence:
        intelligence_cmd = [
            python_bin,
            str(SCRIPT_DIR / "run_intelligence_scheduler.py"),
            "--all-projects",
            "--generate-kind",
            "daily",
            "--delivery-kind",
            "daily",
            "--delivery-limit",
            str(max(1, args.intelligence_delivery_limit)),
        ]
        jobs.append(
            JobSpec(
                name="intelligence_scheduler_daily",
                argv=intelligence_cmd,
                interval_sec=max(1, args.intelligence_interval_sec),
                enabled=True,
            )
        )
    if args.enable_auto_publish:
        auto_publish_cmd = [
            python_bin,
            str(SCRIPT_DIR / "run_wiki_autopublish.py"),
            "--limit-per-project",
            str(max(1, int(args.auto_publish_limit_per_project))),
            "--reviewed-by",
            str(args.auto_publish_reviewed_by).strip() or "synapse_autopublisher",
        ]
        jobs.append(
            JobSpec(
                name="wiki_auto_publish",
                argv=auto_publish_cmd,
                interval_sec=max(1, int(args.auto_publish_interval_sec)),
                enabled=True,
            )
        )
    if args.enable_agent_worklogs:
        agent_worklogs_cmd = [
            python_bin,
            str(SCRIPT_DIR / "run_agent_worklog_scheduler.py"),
            "--all-projects",
            "--discover-limit",
            str(max(1, int(args.agent_worklogs_discover_limit))),
            "--trigger-mode",
            "daily_batch",
            "--days-back",
            str(max(1, min(30, int(args.agent_worklogs_days_back)))),
            "--max-agents",
            str(max(1, min(2000, int(args.agent_worklogs_max_agents)))),
            "--max-logs-per-agent-page",
            str(max(1, min(60, int(args.agent_worklogs_max_logs_per_agent_page)))),
            "--generated-by",
            str(args.agent_worklogs_generated_by).strip() or "agent_worklog_scheduler",
            "--fail-on-errors",
        ]
        if bool(args.agent_worklogs_respect_schedule):
            agent_worklogs_cmd.append("--respect-project-schedule")
        else:
            agent_worklogs_cmd.append("--no-respect-project-schedule")
        if bool(args.agent_worklogs_include_retired):
            agent_worklogs_cmd.append("--include-retired")
        jobs.append(
            JobSpec(
                name="agent_worklog_scheduler",
                argv=agent_worklogs_cmd,
                interval_sec=max(1, int(args.agent_worklogs_interval_sec)),
                enabled=True,
            )
        )
        if bool(args.enable_agent_worklogs_realtime):
            realtime_worklogs_cmd = [
                python_bin,
                str(SCRIPT_DIR / "run_agent_worklog_scheduler.py"),
                "--all-projects",
                "--discover-limit",
                str(max(1, int(args.agent_worklogs_discover_limit))),
                "--trigger-mode",
                "realtime",
                "--trigger-lookback-minutes",
                str(max(1, min(240, int(args.agent_worklogs_realtime_lookback_minutes)))),
                "--days-back",
                "1",
                "--max-agents",
                str(max(1, min(2000, int(args.agent_worklogs_max_agents)))),
                "--max-logs-per-agent-page",
                str(max(1, min(60, int(args.agent_worklogs_max_logs_per_agent_page)))),
                "--generated-by",
                str(args.agent_worklogs_generated_by).strip() or "agent_worklog_scheduler",
                "--no-respect-project-schedule",
                "--fail-on-errors",
            ]
            if bool(args.agent_worklogs_include_retired):
                realtime_worklogs_cmd.append("--include-retired")
            jobs.append(
                JobSpec(
                    name="agent_worklog_realtime",
                    argv=realtime_worklogs_cmd,
                    interval_sec=max(1, int(args.agent_worklogs_realtime_interval_sec)),
                    enabled=True,
                )
            )
    return jobs


def main() -> None:
    args = parse_args()
    jobs = build_jobs(args)

    print(
        json.dumps(
            {
                "event": "worker_loop_started",
                "once": bool(args.once),
                "jobs": [
                    {
                        "name": job.name,
                        "interval_sec": job.interval_sec,
                        "enabled": job.enabled,
                    }
                    for job in jobs
                ],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    if args.once:
        for job in jobs:
            if job.enabled:
                _run_job(job)
        print(json.dumps({"event": "worker_loop_finished_once"}, ensure_ascii=False), flush=True)
        return

    sleep_floor = max(1, args.sleep_floor_sec)
    while True:
        now_mono = time.monotonic()
        due_jobs = [job for job in jobs if job.enabled and job.due_in(now_mono) <= 0.0]
        if due_jobs:
            for job in due_jobs:
                _run_job(job)
                job.last_run_mono = time.monotonic()
            continue

        next_due = min((job.due_in(now_mono) for job in jobs if job.enabled), default=float(sleep_floor))
        sleep_for = max(float(sleep_floor), min(next_due, float(max(sleep_floor, 30))))
        time.sleep(sleep_for)


if __name__ == "__main__":
    main()
