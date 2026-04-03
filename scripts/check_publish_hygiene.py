#!/usr/bin/env python3
"""Validate OSS publishing hygiene across package metadata and release docs."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


ROOT_DIR = Path(__file__).resolve().parents[1]

EXPECTED_LICENSE = "Apache-2.0"
EXPECTED_REPO = str(os.getenv("SYNAPSE_EXPECTED_REPO", "https://github.com/synapseworkspace/synapse")).rstrip("/")
EXPECTED_ISSUES = str(os.getenv("SYNAPSE_EXPECTED_ISSUES", f"{EXPECTED_REPO}/issues")).rstrip("/")

NPM_PACKAGE_CONFIG = {
    "synapse-schema": {
        "name": "@synapseworkspace/schema",
        "required_files_entry": "schemas",
        "require_dist_entrypoints": False,
    },
    "synapse-sdk-ts": {
        "name": "@synapseworkspace/sdk",
        "required_files_entry": "dist",
        "require_dist_entrypoints": True,
    },
    "synapse-openclaw-plugin": {
        "name": "@synapseworkspace/openclaw-plugin",
        "required_files_entry": "dist",
        "require_dist_entrypoints": True,
    },
}


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_toml(path: Path) -> dict[str, object]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _assert(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _validate_npm_package(package_dir: str, cfg: dict[str, object], errors: list[str]) -> None:
    package_path = ROOT_DIR / "packages" / package_dir / "package.json"
    data = _read_json(package_path)
    prefix = f"packages/{package_dir}/package.json"

    _assert(data.get("name") == cfg["name"], f"{prefix}: unexpected name", errors)
    _assert(str(data.get("license") or "") == EXPECTED_LICENSE, f"{prefix}: missing/invalid license", errors)
    _assert(data.get("private") is False, f"{prefix}: private must be false for publishable package", errors)

    repository = data.get("repository")
    repo_url = repository.get("url") if isinstance(repository, dict) else None
    _assert(isinstance(repo_url, str) and EXPECTED_REPO in repo_url, f"{prefix}: invalid repository.url", errors)

    homepage = data.get("homepage")
    _assert(isinstance(homepage, str) and EXPECTED_REPO in homepage, f"{prefix}: invalid homepage", errors)

    bugs = data.get("bugs")
    bugs_url = bugs.get("url") if isinstance(bugs, dict) else None
    _assert(isinstance(bugs_url, str) and bugs_url == EXPECTED_ISSUES, f"{prefix}: invalid bugs.url", errors)

    publish_config = data.get("publishConfig")
    access = publish_config.get("access") if isinstance(publish_config, dict) else None
    provenance = publish_config.get("provenance") if isinstance(publish_config, dict) else None
    _assert(access == "public", f"{prefix}: publishConfig.access must be 'public'", errors)
    _assert(provenance is True, f"{prefix}: publishConfig.provenance must be true", errors)

    engines = data.get("engines")
    node_engine = engines.get("node") if isinstance(engines, dict) else None
    _assert(isinstance(node_engine, str) and node_engine.strip(), f"{prefix}: missing engines.node", errors)

    files = data.get("files")
    files_list = files if isinstance(files, list) else []
    _assert(cfg["required_files_entry"] in files_list, f"{prefix}: files must include {cfg['required_files_entry']!r}", errors)

    if cfg["require_dist_entrypoints"]:
        _assert(str(data.get("main") or "").startswith("dist/"), f"{prefix}: main must point to dist/*", errors)
        _assert(str(data.get("types") or "").startswith("dist/"), f"{prefix}: types must point to dist/*", errors)
        exports = data.get("exports")
        dot = exports.get(".") if isinstance(exports, dict) else None
        dot_types = dot.get("types") if isinstance(dot, dict) else None
        dot_default = dot.get("default") if isinstance(dot, dict) else None
        _assert(isinstance(dot_types, str) and dot_types.startswith("./dist/"), f"{prefix}: exports['.'].types must use ./dist/*", errors)
        _assert(
            isinstance(dot_default, str) and dot_default.startswith("./dist/"),
            f"{prefix}: exports['.'].default must use ./dist/*",
            errors,
        )


def _validate_python_package(errors: list[str]) -> None:
    pyproject_path = ROOT_DIR / "packages" / "synapse-sdk-py" / "pyproject.toml"
    data = _read_toml(pyproject_path)
    project = data.get("project")
    prefix = "packages/synapse-sdk-py/pyproject.toml"
    _assert(isinstance(project, dict), f"{prefix}: missing [project]", errors)
    if not isinstance(project, dict):
        return

    _assert(project.get("name") == "synapseworkspace-sdk", f"{prefix}: project.name must be synapseworkspace-sdk", errors)
    _assert(project.get("license") == EXPECTED_LICENSE, f"{prefix}: project.license must be Apache-2.0", errors)

    urls = project.get("urls")
    _assert(isinstance(urls, dict), f"{prefix}: missing [project.urls]", errors)
    if not isinstance(urls, dict):
        return
    _assert(str(urls.get("Homepage") or "") == EXPECTED_REPO, f"{prefix}: Homepage URL mismatch", errors)
    _assert(str(urls.get("Repository") or "") == EXPECTED_REPO, f"{prefix}: Repository URL mismatch", errors)
    _assert(str(urls.get("Issues") or "") == EXPECTED_ISSUES, f"{prefix}: Issues URL mismatch", errors)


def _validate_docs_consistency(errors: list[str]) -> None:
    release_workflow = (ROOT_DIR / "docs" / "release-workflow.md").read_text(encoding="utf-8")
    compatibility = (ROOT_DIR / "docs" / "compatibility-matrix.md").read_text(encoding="utf-8")
    root_readme = (ROOT_DIR / "README.md").read_text(encoding="utf-8")
    quickstart_openclaw = (ROOT_DIR / "docs" / "openclaw-quickstart-5-min.md").read_text(encoding="utf-8")

    required_release_mentions = [
        "synapseworkspace-sdk",
        "@synapseworkspace/sdk",
        "@synapseworkspace/schema",
        "@synapseworkspace/openclaw-plugin",
    ]
    for pkg in required_release_mentions:
        _assert(pkg in release_workflow, f"docs/release-workflow.md: missing package mention {pkg}", errors)

    required_compat_rows = [
        "`synapseworkspace-sdk` (Python)",
        "`@synapseworkspace/sdk` (TypeScript)",
        "`@synapseworkspace/schema`",
        "`@synapseworkspace/openclaw-plugin`",
    ]
    for marker in required_compat_rows:
        _assert(marker in compatibility, f"docs/compatibility-matrix.md: missing row {marker}", errors)

    _assert(
        "packages/synapse-openclaw-plugin" in root_readme,
        "README.md: missing monorepo package path for synapse-openclaw-plugin",
        errors,
    )
    _assert(
        "@synapseworkspace/openclaw-plugin" in root_readme,
        "README.md: missing npm package mention for @synapseworkspace/openclaw-plugin",
        errors,
    )
    _assert(
        "Package Registry Status" in root_readme,
        "README.md: missing explicit package registry status section",
        errors,
    )
    _assert(
        "pip install -e packages/synapse-sdk-py" in root_readme,
        "README.md: missing repo-local Python install path for preview period",
        errors,
    )
    _assert(
        "Current status (as of" in quickstart_openclaw,
        "docs/openclaw-quickstart-5-min.md: missing explicit registry status note",
        errors,
    )
    _assert(
        "pip install -e packages/synapse-sdk-py" in quickstart_openclaw,
        "docs/openclaw-quickstart-5-min.md: missing repo-local install command",
        errors,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Check OSS publish hygiene and docs consistency.")
    parser.parse_args()

    errors: list[str] = []

    for package_dir, cfg in NPM_PACKAGE_CONFIG.items():
        _validate_npm_package(package_dir, cfg, errors)
    _validate_python_package(errors)
    _validate_docs_consistency(errors)

    if errors:
        print(json.dumps({"status": "failed", "errors": errors}, ensure_ascii=False, indent=2))
        return 1

    print(
        json.dumps(
            {
                "status": "ok",
                "checked": {
                    "npm_packages": sorted(NPM_PACKAGE_CONFIG.keys()),
                    "python_package": "packages/synapse-sdk-py/pyproject.toml",
                    "docs": [
                        "README.md",
                        "docs/release-workflow.md",
                        "docs/compatibility-matrix.md",
                    ],
                },
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
