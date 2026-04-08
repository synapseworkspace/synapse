#!/usr/bin/env python3
"""Validate self-hosted stack defaults for safe and reproducible startup."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def _assert(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []

    compose_path = ROOT_DIR / "infra" / "docker-compose.selfhost.yml"
    env_example_path = ROOT_DIR / ".env.selfhost.example"
    mcp_dockerfile_path = ROOT_DIR / "services" / "mcp" / "Dockerfile"
    selfhost_doc_path = ROOT_DIR / "docs" / "self-hosted-deployment.md"

    for path in (compose_path, env_example_path, mcp_dockerfile_path, selfhost_doc_path):
        _assert(path.exists(), f"missing file: {path.relative_to(ROOT_DIR)}", errors)
    if errors:
        print(json.dumps({"status": "failed", "errors": errors}, ensure_ascii=False, indent=2))
        return 1

    compose_text = compose_path.read_text(encoding="utf-8")
    env_example_text = env_example_path.read_text(encoding="utf-8")
    mcp_dockerfile_text = mcp_dockerfile_path.read_text(encoding="utf-8")
    selfhost_doc_text = selfhost_doc_path.read_text(encoding="utf-8")

    _assert(
        "SYNAPSE_MCP_TRANSPORT: ${SYNAPSE_MCP_TRANSPORT:-streamable-http}" in compose_text,
        "infra/docker-compose.selfhost.yml: MCP transport default must be streamable-http",
        errors,
    )
    _assert(
        "SYNAPSE_MCP_TRANSPORT=streamable-http" in env_example_text,
        ".env.selfhost.example: MCP transport default must be streamable-http",
        errors,
    )
    _assert(
        "SYNAPSE_WEB_PORT=4173" in env_example_text and "SYNAPSE_WEB_API_URL=http://localhost:8080" in env_example_text,
        ".env.selfhost.example: web defaults (port/api url) must be present",
        errors,
    )
    _assert(
        "container_name:" not in compose_text,
        "infra/docker-compose.selfhost.yml: avoid fixed container_name for multi-instance safety",
        errors,
    )
    _assert(
        "\n  web:\n" in compose_text and "SYNAPSE_WEB_PORT:-4173" in compose_text,
        "infra/docker-compose.selfhost.yml: expected bundled web service with loopback port default",
        errors,
    )
    bind_hits = len(re.findall(r'\$\{SYNAPSE_BIND_HOST:-127\.0\.0\.1\}:\$\{[^}]+\}', compose_text))
    _assert(
        bind_hits >= 4,
        "infra/docker-compose.selfhost.yml: expected loopback bind defaults for postgres/api/web/mcp ports",
        errors,
    )
    _assert(
        "healthcheck:" in compose_text and "import socket; s=socket.create_connection" in compose_text,
        "infra/docker-compose.selfhost.yml: MCP healthcheck missing",
        errors,
    )
    _assert(
        '--transport", "http"' not in mcp_dockerfile_text,
        "services/mcp/Dockerfile: must not hardcode deprecated MCP transport=http",
        errors,
    )
    _assert(
        'CMD ["python", "services/mcp/scripts/run_mcp_server.py"]' in mcp_dockerfile_text,
        "services/mcp/Dockerfile: expected runtime command without hardcoded transport",
        errors,
    )
    _assert(
        "cp .env.selfhost.example .env.selfhost" in selfhost_doc_text,
        "docs/self-hosted-deployment.md: missing env bootstrap command",
        errors,
    )
    _assert(
        "docker compose --env-file .env.selfhost -f infra/docker-compose.selfhost.yml up -d --build" in selfhost_doc_text,
        "docs/self-hosted-deployment.md: missing canonical compose up command",
        errors,
    )
    _assert(
        "http://localhost:4173/wiki?project=omega_demo" in selfhost_doc_text,
        "docs/self-hosted-deployment.md: missing canonical web wiki route check",
        errors,
    )

    if errors:
        print(json.dumps({"status": "failed", "errors": errors}, ensure_ascii=False, indent=2))
        return 1

    print(
        json.dumps(
            {
                "status": "ok",
                "checks": {
                    "compose": str(compose_path.relative_to(ROOT_DIR)),
                    "env_example": str(env_example_path.relative_to(ROOT_DIR)),
                    "mcp_dockerfile": str(mcp_dockerfile_path.relative_to(ROOT_DIR)),
                    "selfhost_doc": str(selfhost_doc_path.relative_to(ROOT_DIR)),
                },
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
