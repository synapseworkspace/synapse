#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys


def _tracked_files() -> list[str] | None:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            check=False,
            capture_output=True,
            text=False,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    payload = result.stdout.decode("utf-8", errors="replace")
    entries = [item for item in payload.split("\x00") if item]
    return entries


def _matches_forbidden(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized.startswith(".venv/") or "/.venv/" in normalized:
        return True
    if normalized.startswith("node_modules/") or "/node_modules/" in normalized:
        return True
    if normalized == ".env":
        return True
    if normalized.startswith(".env.") and not normalized.endswith(".example"):
        return True
    return False


def main() -> int:
    tracked = _tracked_files()
    if tracked is None:
        print('[repo-hygiene] skipped (git metadata unavailable in current workspace)')
        return 0

    offenders = [path for path in tracked if _matches_forbidden(path)]
    if offenders:
        print("[repo-hygiene] tracked forbidden artifacts detected:")
        for path in offenders:
            print(f"- {path}")
        print("[repo-hygiene] remove these files from git history/index and keep them ignored.")
        return 1

    print("[repo-hygiene] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
