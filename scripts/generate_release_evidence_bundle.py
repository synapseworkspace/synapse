#!/usr/bin/env python3
"""Generate release evidence bundle (Markdown + JSON) from CI artifacts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


UTC = timezone.utc


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root at {path} must be an object")
    return payload


def _render_markdown(payload: dict[str, Any]) -> str:
    version = _coerce_text(payload.get("version")) or "unknown"
    generated_at = _coerce_text(payload.get("generated_at")) or "unknown"
    workflow_run_url = _coerce_text(payload.get("workflow_run_url"))
    registry_summary = payload.get("registry_summary")
    registry_packages = payload.get("registry_packages")
    provenance_refs = payload.get("provenance_refs") or []
    package_urls = payload.get("package_urls") or {}

    lines: list[str] = []
    lines.append(f"# Synapse Release Evidence: v{version}")
    lines.append("")
    lines.append(f"- Generated at: `{generated_at}`")
    if workflow_run_url:
        lines.append(f"- Workflow run: {workflow_run_url}")
    lines.append("")
    lines.append("## Package Links")
    lines.append("")
    if isinstance(package_urls, dict):
        for key in sorted(package_urls.keys()):
            url = _coerce_text(package_urls.get(key))
            if url:
                lines.append(f"- `{key}`: {url}")
    lines.append("")
    lines.append("## Registry Verification")
    lines.append("")
    if isinstance(registry_summary, dict):
        status = _coerce_text(registry_summary.get("status")) or "unknown"
        expected_version = _coerce_text(registry_summary.get("expected_version")) or "n/a"
        lines.append(f"- Status: `{status}`")
        lines.append(f"- Expected version: `{expected_version}`")
        matched = registry_summary.get("matched")
        if matched is not None:
            lines.append(f"- Matched packages: `{matched}`")
    if isinstance(registry_packages, dict):
        lines.append("")
        lines.append("| package | registry | status | version |")
        lines.append("| --- | --- | --- | --- |")
        for package_name in sorted(registry_packages.keys()):
            row = registry_packages[package_name] if isinstance(registry_packages[package_name], dict) else {}
            lines.append(
                "| "
                + " | ".join(
                    [
                        package_name,
                        _coerce_text(row.get("registry")) or "unknown",
                        _coerce_text(row.get("status")) or "unknown",
                        _coerce_text(row.get("version")) or "-",
                    ]
                )
                + " |"
            )
    lines.append("")
    lines.append("## Provenance References")
    lines.append("")
    if isinstance(provenance_refs, list) and provenance_refs:
        for item in provenance_refs:
            text = _coerce_text(item)
            if text:
                lines.append(f"- {text}")
    else:
        lines.append("- Workflow-level provenance: packages were published with trusted publishing and npm `--provenance`.")
        if workflow_run_url:
            lines.append(f"- Build/publish evidence is attached to workflow artifacts in: {workflow_run_url}")
    lines.append("")
    lines.append("## Install Verification")
    lines.append("")
    lines.append("```bash")
    lines.append(f"python3 -m pip install synapseworkspace-sdk=={version}")
    lines.append(f"npm install @synapseworkspace/sdk@{version} @synapseworkspace/schema@{version} @synapseworkspace/openclaw-plugin@{version}")
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate release evidence markdown/json payload.")
    parser.add_argument("--version", required=True, help="Release version (without leading `v`).")
    parser.add_argument(
        "--registry-report",
        default=None,
        help="Path to `check_registry_package_availability.py` JSON output.",
    )
    parser.add_argument("--workflow-run-url", default=None, help="GitHub Actions run URL for release workflow.")
    parser.add_argument(
        "--provenance-ref",
        action="append",
        default=None,
        help="Explicit provenance reference link or note (repeatable).",
    )
    parser.add_argument("--output-md", default=None, help="Path to write markdown report.")
    parser.add_argument("--output-json", default=None, help="Path to write JSON report.")
    args = parser.parse_args()

    package_urls = {
        "synapseworkspace-sdk (PyPI)": "https://pypi.org/project/synapseworkspace-sdk/",
        "@synapseworkspace/sdk (npm)": "https://www.npmjs.com/package/@synapseworkspace/sdk",
        "@synapseworkspace/schema (npm)": "https://www.npmjs.com/package/@synapseworkspace/schema",
        "@synapseworkspace/openclaw-plugin (npm)": "https://www.npmjs.com/package/@synapseworkspace/openclaw-plugin",
    }

    registry_summary: dict[str, Any] = {
        "status": "not_checked",
        "expected_version": _coerce_text(args.version),
        "matched": None,
    }
    registry_packages: dict[str, dict[str, Any]] = {}
    if args.registry_report:
        report_path = Path(args.registry_report)
        if not report_path.exists():
            print(json.dumps({"status": "error", "message": f"registry report not found: {report_path}"}))
            return 2
        report = _load_json(report_path)
        registry_summary = {
            "status": _coerce_text(report.get("status")) or "unknown",
            "expected_version": _coerce_text(report.get("expected_version")) or _coerce_text(args.version),
            "matched": report.get("matched"),
        }
        legacy_packages = report.get("packages")
        if isinstance(legacy_packages, dict):
            for key, row in legacy_packages.items():
                if not isinstance(row, dict):
                    continue
                registry_packages[_coerce_text(key)] = {
                    "registry": _coerce_text(row.get("registry")) or "unknown",
                    "status": _coerce_text(row.get("status")) or "unknown",
                    "version": _coerce_text(row.get("version")) or "",
                }

        results = report.get("results")
        if isinstance(results, list):
            matched = 0
            for item in results:
                row = item if isinstance(item, dict) else {}
                name = _coerce_text(row.get("name"))
                ecosystem = _coerce_text(row.get("ecosystem")) or "unknown"
                available = bool(row.get("available"))
                latest = _coerce_text(row.get("latest"))
                versions = row.get("versions") if isinstance(row.get("versions"), list) else []
                has_expected = (_coerce_text(args.version) in {str(v) for v in versions}) if args.version else available
                if has_expected:
                    matched += 1
                if not name:
                    continue
                status = "ok" if available else "missing"
                registry_packages[name] = {
                    "registry": ecosystem,
                    "status": status,
                    "version": latest,
                }
            if results and registry_summary.get("matched") is None:
                registry_summary["matched"] = matched

    payload: dict[str, Any] = {
        "version": _coerce_text(args.version),
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "workflow_run_url": _coerce_text(args.workflow_run_url),
        "registry_summary": registry_summary,
        "registry_packages": registry_packages,
        "provenance_refs": [item for item in (args.provenance_ref or []) if _coerce_text(item)],
        "package_urls": package_urls,
    }

    markdown = _render_markdown(payload)
    if args.output_md:
        md_path = Path(args.output_md)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(markdown, encoding="utf-8")
    if args.output_json:
        json_path = Path(args.output_json)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.output_md or args.output_json:
        print(
            json.dumps(
                {
                    "status": "ok",
                    "version": payload["version"],
                    "output_md": _coerce_text(args.output_md),
                    "output_json": _coerce_text(args.output_json),
                },
                ensure_ascii=False,
            )
        )
    else:
        print(markdown)
    return 0


if __name__ == "__main__":
    sys.exit(main())
