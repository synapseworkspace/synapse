#!/usr/bin/env python3
"""Regression guard for cookbook demo outputs."""

from __future__ import annotations

import argparse
import difflib
import importlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
COOKBOOK_DIR = ROOT_DIR / "demos" / "cookbook"
SNAPSHOT_DIR = COOKBOOK_DIR / "snapshots"

SCENARIOS = {
    "openclaw_playbook_sync": "openclaw_playbook_sync",
    "langgraph_playbook_sync": "langgraph_playbook_sync",
    "sql_ops_guardrails": "sql_ops_guardrails",
    "support_ops_triage": "support_ops_triage",
}

UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalize(val) for key, val in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, str):
        return UUID_PATTERN.sub("<uuid>", value)
    return value


def _render(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _run_scenario(module_name: str) -> Any:
    module = importlib.import_module(module_name)
    run_demo = getattr(module, "run_demo", None)
    if not callable(run_demo):
        raise RuntimeError(f"{module_name}.run_demo is missing")
    return run_demo()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate cookbook outputs against golden snapshots.")
    parser.add_argument("--update", action="store_true", help="Refresh snapshots with current outputs.")
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT_DIR / "packages" / "synapse-sdk-py" / "src"))
    sys.path.insert(0, str(COOKBOOK_DIR))

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    for scenario_name, module_name in SCENARIOS.items():
        output = _normalize(_run_scenario(module_name))
        rendered = _render(output)
        snapshot_path = SNAPSHOT_DIR / f"{scenario_name}.json"
        if args.update:
            snapshot_path.write_text(rendered, encoding="utf-8")
            print(f"[cookbook-snapshots] updated {snapshot_path.relative_to(ROOT_DIR)}")
            continue
        if not snapshot_path.exists():
            failures.append(f"missing snapshot: {snapshot_path.relative_to(ROOT_DIR)} (run with --update)")
            continue
        expected = snapshot_path.read_text(encoding="utf-8")
        if expected != rendered:
            diff = "\n".join(
                difflib.unified_diff(
                    expected.splitlines(),
                    rendered.splitlines(),
                    fromfile=str(snapshot_path.relative_to(ROOT_DIR)),
                    tofile=f"{scenario_name} (current)",
                    lineterm="",
                )
            )
            failures.append(f"snapshot mismatch for {scenario_name}\n{diff}")

    if failures:
        print("[cookbook-snapshots] FAILED")
        for item in failures:
            print(item)
        return 1

    print("[cookbook-snapshots] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
