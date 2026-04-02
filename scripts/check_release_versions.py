#!/usr/bin/env python3
"""Validate package versions across Synapse distributable artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


ROOT_DIR = Path(__file__).resolve().parents[1]


def _read_python_sdk_version() -> str:
    path = ROOT_DIR / "packages" / "synapse-sdk-py" / "pyproject.toml"
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def _read_npm_version(package_dir: str) -> str:
    path = ROOT_DIR / "packages" / package_dir / "package.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return str(data["version"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Synapse package release versions.")
    parser.add_argument(
        "--expected-version",
        help="If set, enforce this exact version for all distributable packages.",
    )
    args = parser.parse_args()

    versions = {
        "python:synapse-sdk": _read_python_sdk_version(),
        "npm:@synapse/sdk": _read_npm_version("synapse-sdk-ts"),
        "npm:@synapse/schema": _read_npm_version("synapse-schema"),
        "npm:@synapse/openclaw-plugin": _read_npm_version("synapse-openclaw-plugin"),
    }

    distinct_versions = sorted(set(versions.values()))
    if len(distinct_versions) != 1:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "reason": "version_mismatch",
                    "versions": versions,
                    "distinct_versions": distinct_versions,
                },
                ensure_ascii=False,
            )
        )
        return 1

    resolved_version = distinct_versions[0]
    if args.expected_version and args.expected_version != resolved_version:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "reason": "expected_version_mismatch",
                    "expected_version": args.expected_version,
                    "actual_version": resolved_version,
                    "versions": versions,
                },
                ensure_ascii=False,
            )
        )
        return 1

    print(
        json.dumps(
            {
                "status": "ok",
                "version": resolved_version,
                "packages": versions,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
