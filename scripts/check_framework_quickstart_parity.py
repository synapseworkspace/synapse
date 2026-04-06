#!/usr/bin/env python3
"""Validate 5-minute quickstart parity across core framework docs."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]

QUICKSTART_FILES = {
    "openclaw": ROOT_DIR / "docs" / "openclaw-quickstart-5-min.md",
    "langgraph": ROOT_DIR / "docs" / "langgraph-quickstart-5-min.md",
    "langchain": ROOT_DIR / "docs" / "langchain-quickstart-5-min.md",
    "crewai": ROOT_DIR / "docs" / "crewai-quickstart-5-min.md",
}

REQUIRED_MARKERS = [
    "Last updated:",
    "Goal:",
    "## 0. Prerequisites",
    "## 1. Install SDK",
    "## 2. Attach Synapse",
    "## 4. Verify Loop",
    "pip install synapseworkspace-sdk",
    "pip install -e packages/synapse-sdk-py",
]


def main() -> int:
    errors: list[str] = []
    docs_snapshot: dict[str, dict[str, str | int]] = {}

    for framework, path in QUICKSTART_FILES.items():
        if not path.exists():
            errors.append(f"{path.relative_to(ROOT_DIR)}: file_missing")
            continue
        raw = path.read_text(encoding="utf-8")
        docs_snapshot[framework] = {
            "path": str(path.relative_to(ROOT_DIR)),
            "size_chars": len(raw),
        }
        for marker in REQUIRED_MARKERS:
            if marker not in raw:
                errors.append(f"{path.relative_to(ROOT_DIR)}: missing marker `{marker}`")

    output = {
        "status": "ok" if not errors else "failed",
        "checked": docs_snapshot,
    }
    if errors:
        output["errors"] = errors
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
