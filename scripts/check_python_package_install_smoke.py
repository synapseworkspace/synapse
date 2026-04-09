#!/usr/bin/env python3
"""Verify installed Synapse Python package version and import surface."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from importlib import metadata


def main() -> int:
    parser = argparse.ArgumentParser(description="Python install smoke for published/build artifacts.")
    parser.add_argument("--expected-version", required=True, help="Expected installed version.")
    parser.add_argument("--package-name", default="synapseworkspace-sdk", help="Distribution name in pip metadata.")
    parser.add_argument(
        "--module-name",
        default="synapse_sdk",
        help="Importable module name to validate runtime import.",
    )
    parser.add_argument(
        "--check-cli",
        action="store_true",
        help="Also run `synapse-cli --help` to verify console script installation.",
    )
    args = parser.parse_args()

    expected = str(args.expected_version).strip()
    package_name = str(args.package_name).strip()
    module_name = str(args.module_name).strip()
    if not expected:
        raise SystemExit("--expected-version is required")

    try:
        installed = metadata.version(package_name)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "reason": "distribution_not_found",
                    "package": package_name,
                    "error": f"{type(exc).__name__}: {exc}",
                },
                ensure_ascii=False,
            )
        )
        return 1

    if installed != expected:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "reason": "version_mismatch",
                    "package": package_name,
                    "expected_version": expected,
                    "installed_version": installed,
                },
                ensure_ascii=False,
            )
        )
        return 1

    try:
        module = __import__(module_name)
        synapse_class = getattr(module, "Synapse", None)
        if synapse_class is None:
            raise RuntimeError(f"{module_name}.Synapse export missing")
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "reason": "import_failed",
                    "module": module_name,
                    "error": f"{type(exc).__name__}: {exc}",
                },
                ensure_ascii=False,
            )
        )
        return 1

    cli_checked = False
    if args.check_cli:
        try:
            completed = subprocess.run(
                ["synapse-cli", "--help"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            output = (completed.stdout or "") + (completed.stderr or "")
            if "synapse-cli" not in output and "usage:" not in output.lower():
                raise RuntimeError("unexpected synapse-cli help output")
            cli_checked = True
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "status": "failed",
                        "reason": "cli_smoke_failed",
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                    ensure_ascii=False,
                )
            )
            return 1

    print(
        json.dumps(
            {
                "status": "ok",
                "package": package_name,
                "module": module_name,
                "installed_version": installed,
                "expected_version": expected,
                "cli_checked": cli_checked,
                "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
