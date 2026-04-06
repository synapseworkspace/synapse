#!/usr/bin/env python3
"""Check that core docs keep dual positioning: Agentic Wiki + L2 layer."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]

DOCS = [
    ROOT_DIR / "README.md",
    ROOT_DIR / "docs" / "agentic-wiki-overview.md",
    ROOT_DIR / "docs" / "getting-started.md",
    ROOT_DIR / "docs" / "cognitive-state-layer.md",
]


def _contains_any(text: str, markers: list[str]) -> bool:
    text_lower = text.lower()
    return any(marker.lower() in text_lower for marker in markers)


def main() -> int:
    errors: list[str] = []
    checked: list[str] = []
    for path in DOCS:
        if not path.exists():
            errors.append(f"{path.relative_to(ROOT_DIR)}: file_missing")
            continue
        raw = path.read_text(encoding="utf-8")
        checked.append(str(path.relative_to(ROOT_DIR)))
        has_wiki = _contains_any(raw, ["agentic wiki"])
        has_l2 = _contains_any(raw, ["cognitive state layer", "l2"])
        if not has_wiki:
            errors.append(f"{path.relative_to(ROOT_DIR)}: missing Agentic Wiki positioning marker")
        if not has_l2:
            errors.append(f"{path.relative_to(ROOT_DIR)}: missing L2/Cognitive State Layer positioning marker")

    output: dict[str, object] = {
        "status": "ok" if not errors else "failed",
        "checked_docs": checked,
    }
    if errors:
        output["errors"] = errors
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
