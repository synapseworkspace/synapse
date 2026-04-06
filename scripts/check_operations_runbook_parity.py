#!/usr/bin/env python3
"""Assert operations runbook covers required Utility Gate and route-split semantics."""

from __future__ import annotations

import argparse
from pathlib import Path


REQUIRED_SNIPPETS = (
    "/operations",
    "/wiki",
    "utility gate v2.1 controls",
    "llm classifier mode",
    "min confidence",
    "classify ambiguous only",
    "model override",
    "gatekeeper signal",
    "reason-codes",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Checks docs/operations-route-runbook.md for required Utility Gate coverage.",
    )
    parser.add_argument(
        "--path",
        default="docs/operations-route-runbook.md",
        help="Path to operations runbook markdown file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runbook_path = Path(args.path)
    if not runbook_path.exists():
        print(f"operations runbook missing: {runbook_path}")
        return 1

    content = runbook_path.read_text(encoding="utf-8").lower()
    missing = [snippet for snippet in REQUIRED_SNIPPETS if snippet not in content]
    if missing:
        print("operations runbook parity check failed.")
        print("missing snippets:")
        for snippet in missing:
            print(f"- {snippet}")
        return 1

    print("operations runbook parity check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

