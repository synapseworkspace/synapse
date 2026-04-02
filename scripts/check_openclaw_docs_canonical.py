#!/usr/bin/env python3
"""Guard canonical OpenClaw onboarding references in docs."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
CANONICAL_DOC = ROOT_DIR / "docs" / "openclaw-quickstart-5-min.md"
ALIAS_DOC = ROOT_DIR / "docs" / "tutorials" / "02-openclaw-quickstart.md"

REQUIRED_CANONICAL_REFERENCES = {
    ROOT_DIR / "README.md",
    ROOT_DIR / "docs" / "agentic-wiki-overview.md",
    ROOT_DIR / "docs" / "getting-started.md",
    ROOT_DIR / "docs" / "openclaw-integration.md",
    ROOT_DIR / "docs" / "tutorials" / "README.md",
    ROOT_DIR / "demos" / "cookbook" / "README.md",
    ROOT_DIR / "demos" / "openclaw_onboarding" / "README.md",
}

SCAN_ROOTS = [
    ROOT_DIR / "docs",
    ROOT_DIR / "demos",
    ROOT_DIR / "packages",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _iter_markdown_files() -> list[Path]:
    files: set[Path] = {ROOT_DIR / "README.md"}
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for item in root.rglob("*.md"):
            if ROOT_DIR in item.parents:
                files.add(item)
    return sorted(files)


def main() -> int:
    errors: list[str] = []

    if not CANONICAL_DOC.exists():
        errors.append(f"Missing canonical quickstart: {CANONICAL_DOC.relative_to(ROOT_DIR)}")
    if not ALIAS_DOC.exists():
        errors.append(f"Missing alias tutorial: {ALIAS_DOC.relative_to(ROOT_DIR)}")

    canonical_ref = "openclaw-quickstart-5-min.md"
    deprecated_ref = "02-openclaw-quickstart.md"

    for path in sorted(REQUIRED_CANONICAL_REFERENCES):
        if not path.exists():
            errors.append(f"Required doc missing: {path.relative_to(ROOT_DIR)}")
            continue
        text = _read(path)
        if canonical_ref not in text:
            errors.append(f"{path.relative_to(ROOT_DIR)} must reference {canonical_ref}")

    for path in _iter_markdown_files():
        if path == ALIAS_DOC:
            continue
        text = _read(path)
        if deprecated_ref in text:
            errors.append(
                f"{path.relative_to(ROOT_DIR)} references deprecated alias `{deprecated_ref}`; use `{canonical_ref}`"
            )

    if errors:
        print("[openclaw-docs-canonical] FAILED")
        for item in errors:
            print(f"- {item}")
        return 1

    print("[openclaw-docs-canonical] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
