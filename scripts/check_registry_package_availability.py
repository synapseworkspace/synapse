#!/usr/bin/env python3
"""Validate Synapse package availability on PyPI and npm registries."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request


ROOT_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class RegistryPackage:
    ecosystem: str
    name: str
    metadata_url: str


PACKAGES: tuple[RegistryPackage, ...] = (
    RegistryPackage(
        ecosystem="pypi",
        name="synapseworkspace-sdk",
        metadata_url="https://pypi.org/pypi/synapseworkspace-sdk/json",
    ),
    RegistryPackage(
        ecosystem="npm",
        name="@synapseworkspace/sdk",
        metadata_url=f"https://registry.npmjs.org/{urllib_parse.quote('@synapseworkspace/sdk', safe='')}",
    ),
    RegistryPackage(
        ecosystem="npm",
        name="@synapseworkspace/schema",
        metadata_url=f"https://registry.npmjs.org/{urllib_parse.quote('@synapseworkspace/schema', safe='')}",
    ),
    RegistryPackage(
        ecosystem="npm",
        name="@synapseworkspace/openclaw-plugin",
        metadata_url=f"https://registry.npmjs.org/{urllib_parse.quote('@synapseworkspace/openclaw-plugin', safe='')}",
    ),
)


def _fetch_json(url: str, timeout_s: float) -> dict[str, Any]:
    req = urllib_request.Request(url, headers={"accept": "application/json"})
    with urllib_request.urlopen(req, timeout=timeout_s) as response:
        raw = response.read().decode("utf-8")
    parsed = json.loads(raw or "{}")
    if not isinstance(parsed, dict):
        raise RuntimeError(f"unexpected non-object payload from {url}")
    return parsed


def _versions_from_payload(pkg: RegistryPackage, payload: dict[str, Any]) -> tuple[bool, str | None, set[str]]:
    if pkg.ecosystem == "pypi":
        info = payload.get("info")
        releases = payload.get("releases")
        latest = info.get("version") if isinstance(info, dict) else None
        versions = set(releases.keys()) if isinstance(releases, dict) else set()
        if isinstance(latest, str) and latest.strip():
            versions.add(latest.strip())
        return bool(versions), (latest.strip() if isinstance(latest, str) and latest.strip() else None), versions

    dist_tags = payload.get("dist-tags")
    versions_raw = payload.get("versions")
    latest = dist_tags.get("latest") if isinstance(dist_tags, dict) else None
    versions = set(versions_raw.keys()) if isinstance(versions_raw, dict) else set()
    if isinstance(latest, str) and latest.strip():
        versions.add(latest.strip())
    return bool(versions), (latest.strip() if isinstance(latest, str) and latest.strip() else None), versions


def _probe_package(pkg: RegistryPackage, timeout_s: float) -> dict[str, Any]:
    started_ms = int(time.time() * 1000)
    try:
        payload = _fetch_json(pkg.metadata_url, timeout_s)
        available, latest, versions = _versions_from_payload(pkg, payload)
        return {
            "ecosystem": pkg.ecosystem,
            "name": pkg.name,
            "available": available,
            "latest": latest,
            "versions_count": len(versions),
            "versions": sorted(versions),
            "error": None,
            "latency_ms": int(time.time() * 1000) - started_ms,
        }
    except urllib_error.HTTPError as exc:
        message = f"http_{exc.code}"
        if exc.code == 404:
            message = "not_found"
        return {
            "ecosystem": pkg.ecosystem,
            "name": pkg.name,
            "available": False,
            "latest": None,
            "versions_count": 0,
            "versions": [],
            "error": message,
            "latency_ms": int(time.time() * 1000) - started_ms,
        }
    except Exception as exc:  # pragma: no cover - network/runtime variability
        return {
            "ecosystem": pkg.ecosystem,
            "name": pkg.name,
            "available": False,
            "latest": None,
            "versions_count": 0,
            "versions": [],
            "error": f"{type(exc).__name__}: {exc}",
            "latency_ms": int(time.time() * 1000) - started_ms,
        }


def _is_success(
    result: dict[str, Any],
    *,
    require_available: bool,
    expected_version: str | None,
    require_version_absent: bool,
    require_latest_match: bool,
) -> bool:
    if require_available and not bool(result.get("available")):
        return False
    latest = str(result.get("latest") or "").strip()
    versions = result.get("versions")
    versions_set = {str(item) for item in versions} if isinstance(versions, list) else set()

    if require_version_absent:
        if not expected_version:
            return False
        return expected_version not in versions_set

    if expected_version:
        if not versions_set:
            return False
        if expected_version not in versions_set:
            return False
        if require_latest_match and latest and latest != expected_version:
            return False
        return True

    if require_latest_match:
        if not latest:
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Synapse package availability on public registries.")
    parser.add_argument("--expected-version", help="Require this version to be available in every package.")
    parser.add_argument("--require-available", action="store_true", help="Fail if any package is unavailable.")
    parser.add_argument(
        "--attempts",
        type=int,
        default=1,
        help="Retry attempts for eventual-consistency registries (default: 1).",
    )
    parser.add_argument(
        "--retry-delay-seconds",
        type=float,
        default=10.0,
        help="Delay between attempts when checks fail (default: 10).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=12.0,
        help="HTTP timeout per package request (default: 12).",
    )
    parser.add_argument(
        "--require-version-absent",
        action="store_true",
        help="Fail if expected version already exists in any package registry.",
    )
    parser.add_argument(
        "--require-latest-match",
        action="store_true",
        help="When expected version is set, require registry latest tag/version to match it.",
    )
    parser.add_argument("--output-json", help="Optional path to write JSON report.")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    attempts = max(1, int(args.attempts))
    expected_version = str(args.expected_version).strip() if args.expected_version else None
    require_version_absent = bool(args.require_version_absent)
    require_latest_match = bool(args.require_latest_match)
    if require_version_absent and not expected_version:
        parser.error("--require-version-absent requires --expected-version")
    if require_latest_match and not expected_version:
        parser.error("--require-latest-match requires --expected-version")
    final_results: list[dict[str, Any]] = []
    success = False

    for attempt in range(1, attempts + 1):
        results = [_probe_package(pkg, timeout_s=float(args.timeout_seconds)) for pkg in PACKAGES]
        checks = [
            _is_success(
                item,
                require_available=bool(args.require_available),
                expected_version=expected_version,
                require_version_absent=require_version_absent,
                require_latest_match=require_latest_match,
            )
            for item in results
        ]
        success = all(checks)
        final_results = results

        if args.verbose:
            print(
                json.dumps(
                    {
                        "attempt": attempt,
                        "attempts": attempts,
                        "results": results,
                        "success": success,
                    },
                    ensure_ascii=False,
                )
            )

        if success:
            break
        if attempt < attempts:
            time.sleep(max(0.0, float(args.retry_delay_seconds)))

    report = {
        "status": "ok" if success else "failed",
        "attempts": attempts,
        "expected_version": expected_version,
        "require_available": bool(args.require_available),
        "require_version_absent": require_version_absent,
        "require_latest_match": require_latest_match,
        "results": final_results,
    }

    if args.output_json:
        Path(args.output_json).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False))
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
