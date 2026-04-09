#!/usr/bin/env python3
"""Validate package versions across Synapse distributable artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


ROOT_DIR = Path(__file__).resolve().parents[1]
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")


def _read_python_sdk_meta() -> tuple[str, str]:
    path = ROOT_DIR / "packages" / "synapse-sdk-py" / "pyproject.toml"
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return str(data["project"]["name"]), str(data["project"]["version"])


def _read_npm_meta(package_dir: str) -> tuple[str, str]:
    path = ROOT_DIR / "packages" / package_dir / "package.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return str(data["name"]), str(data["version"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Synapse package release versions.")
    parser.add_argument(
        "--expected-version",
        help="If set, enforce this exact version for all distributable packages.",
    )
    args = parser.parse_args()

    expected_names = {
        "python": "synapseworkspace-sdk",
        "npm_sdk": "@synapseworkspace/sdk",
        "npm_schema": "@synapseworkspace/schema",
        "npm_openclaw_plugin": "@synapseworkspace/openclaw-plugin",
    }
    py_name, py_version = _read_python_sdk_meta()
    sdk_name, sdk_version = _read_npm_meta("synapse-sdk-ts")
    schema_name, schema_version = _read_npm_meta("synapse-schema")
    plugin_name, plugin_version = _read_npm_meta("synapse-openclaw-plugin")

    package_names = {
        "python:synapseworkspace-sdk": py_name,
        "npm:@synapseworkspace/sdk": sdk_name,
        "npm:@synapseworkspace/schema": schema_name,
        "npm:@synapseworkspace/openclaw-plugin": plugin_name,
    }
    versions = {
        "python:synapseworkspace-sdk": py_version,
        "npm:@synapseworkspace/sdk": sdk_version,
        "npm:@synapseworkspace/schema": schema_version,
        "npm:@synapseworkspace/openclaw-plugin": plugin_version,
    }
    name_errors: list[str] = []
    if py_name != expected_names["python"]:
        name_errors.append(f"python package name mismatch: expected {expected_names['python']}, got {py_name}")
    if sdk_name != expected_names["npm_sdk"]:
        name_errors.append(f"npm sdk package name mismatch: expected {expected_names['npm_sdk']}, got {sdk_name}")
    if schema_name != expected_names["npm_schema"]:
        name_errors.append(f"npm schema package name mismatch: expected {expected_names['npm_schema']}, got {schema_name}")
    if plugin_name != expected_names["npm_openclaw_plugin"]:
        name_errors.append(
            f"npm openclaw plugin name mismatch: expected {expected_names['npm_openclaw_plugin']}, got {plugin_name}"
        )
    if name_errors:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "reason": "package_name_mismatch",
                    "errors": name_errors,
                    "package_names": package_names,
                },
                ensure_ascii=False,
            )
        )
        return 1

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
    if not SEMVER_RE.match(resolved_version):
        print(
            json.dumps(
                {
                    "status": "failed",
                    "reason": "invalid_semver",
                    "version": resolved_version,
                    "versions": versions,
                },
                ensure_ascii=False,
            )
        )
        return 1

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
                "package_names": package_names,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
