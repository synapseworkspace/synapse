from __future__ import annotations

import argparse

from app.server import run_mcp_server


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Synapse MCP runtime server.")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "streamable-http"],
        default=None,
        help="MCP transport type. Defaults to env SYNAPSE_MCP_TRANSPORT or stdio.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_mcp_server(transport=args.transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
