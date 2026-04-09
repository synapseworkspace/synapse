#!/usr/bin/env python3
"""Bump release version across Synapse publishable packages."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")

PYPROJECT_PATH = ROOT_DIR / "packages" / "synapse-sdk-py" / "pyproject.toml"
NPM_PACKAGE_PATHS = (
    ROOT_DIR / "packages" / "synapse-sdk-ts" / "package.json",
    ROOT_DIR / "packages" / "synapse-schema" / "package.json",
    ROOT_DIR / "packages" / "synapse-openclaw-plugin" / "package.json",
)


def _replace_pyproject_version(content: str, new_version: str) -> tuple[str, str]:
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"\s*$', content)
    if match is None:
        raise RuntimeError(f"could not find `version = ...` in {PYPROJECT_PATH}")
    old_version = match.group(1)
    updated = content[: match.start(1)] + new_version + content[match.end(1) :]
    return updated, old_version


def _replace_package_json_version(content: str, *, file_path: Path, new_version: str) -> tuple[str, str]:
    data = json.loads(content)
    old_version = str(data.get("version") or "").strip()
    if not old_version:
        raise RuntimeError(f"missing version field in {file_path}")
    data["version"] = new_version
    updated = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    return updated, old_version


def main() -> int:
    parser = argparse.ArgumentParser(description="Bump Synapse release version in all publishable package manifests.")
    parser.add_argument("version", help="New version (semver).")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing files.")
    args = parser.parse_args()

    new_version = str(args.version).strip()
    if not SEMVER_RE.match(new_version):
        print(json.dumps({"status": "failed", "reason": "invalid_semver", "version": new_version}))
        return 1

    changes: list[dict[str, str]] = []

    py_content = PYPROJECT_PATH.read_text(encoding="utf-8")
    py_updated, py_old = _replace_pyproject_version(py_content, new_version)
    changes.append({"path": str(PYPROJECT_PATH.relative_to(ROOT_DIR)), "old": py_old, "new": new_version})
    if not args.dry_run:
        PYPROJECT_PATH.write_text(py_updated, encoding="utf-8")

    for pkg_path in NPM_PACKAGE_PATHS:
        content = pkg_path.read_text(encoding="utf-8")
        updated, old = _replace_package_json_version(content, file_path=pkg_path, new_version=new_version)
        changes.append({"path": str(pkg_path.relative_to(ROOT_DIR)), "old": old, "new": new_version})
        if not args.dry_run:
            pkg_path.write_text(updated, encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "ok",
                "dry_run": bool(args.dry_run),
                "version": new_version,
                "changes": changes,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
