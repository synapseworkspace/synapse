#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import difflib
import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PY_INIT = ROOT / "packages" / "synapse-sdk-py" / "src" / "synapse_sdk" / "__init__.py"
TS_SRC = ROOT / "packages" / "synapse-sdk-ts" / "src"
TS_INDEX = TS_SRC / "index.ts"
REF_DIR = ROOT / "docs" / "reference"
PY_REF = REF_DIR / "python-sdk-api.md"
TS_REF = REF_DIR / "typescript-sdk-api.md"
INDEX_REF = REF_DIR / "README.md"


@dataclass(frozen=True)
class RenderedFile:
    path: Path
    content: str


def _parse_python_exports() -> tuple[list[str], dict[str, str]]:
    raw = PY_INIT.read_text(encoding="utf-8")
    tree = ast.parse(raw)
    source_map: dict[str, str] = {}
    exports: list[str] = []

    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                source_map[alias.asname or alias.name] = node.module
        elif isinstance(node, ast.Assign):
            targets = [item.id for item in node.targets if isinstance(item, ast.Name)]
            if "__all__" in targets and isinstance(node.value, (ast.List, ast.Tuple)):
                exports = [
                    item.value
                    for item in node.value.elts
                    if isinstance(item, ast.Constant) and isinstance(item.value, str)
                ]

    if not exports:
        raise RuntimeError("Failed to parse Python __all__ exports from synapse_sdk/__init__.py")
    return exports, source_map


def _parse_ts_modules() -> list[str]:
    raw = TS_INDEX.read_text(encoding="utf-8")
    modules: list[str] = []
    for match in re.finditer(r'export\s+\*\s+from\s+"(\./[^"]+)\.js";', raw):
        modules.append(match.group(1))
    if not modules:
        raise RuntimeError("Failed to parse TypeScript export modules from src/index.ts")
    return modules


def _parse_ts_exports(module_rel: str) -> list[str]:
    module_path = (TS_SRC / f"{module_rel[2:]}.ts").resolve()
    raw = module_path.read_text(encoding="utf-8")
    names: set[str] = set()

    for pattern in (
        r"\bexport\s+interface\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"\bexport\s+type\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"\bexport\s+class\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"\bexport\s+function\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"\bexport\s+const\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"\bexport\s+enum\s+([A-Za-z_][A-Za-z0-9_]*)",
    ):
        for match in re.finditer(pattern, raw):
            names.add(match.group(1))

    for match in re.finditer(r"\bexport\s+\{\s*([^}]+?)\s*\};", raw, flags=re.DOTALL):
        payload = match.group(1)
        for token in payload.split(","):
            candidate = token.strip()
            if not candidate:
                continue
            if " as " in candidate:
                candidate = candidate.split(" as ", 1)[1].strip()
            names.add(candidate)

    return sorted(names)


def _render_python_reference() -> str:
    exports, source_map = _parse_python_exports()
    lines = [
        "# Python SDK API Reference",
        "",
        "Canonical entrypoint: `from synapse_sdk import ...`",
        "",
        "## Public Exports (`synapse_sdk.__all__`)",
        "",
        "| Symbol | Source Module |",
        "| --- | --- |",
    ]
    for name in exports:
        lines.append(f"| `{name}` | `{source_map.get(name, 'synapse_sdk')}` |")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- `init(config)` is deprecated; use `Synapse(config)` directly.")
    lines.append("- Keep this file generated via `scripts/generate_sdk_api_reference.py`.")
    lines.append("")
    return "\n".join(lines)


def _render_ts_reference() -> str:
    modules = _parse_ts_modules()
    lines = [
        "# TypeScript SDK API Reference",
        "",
        "Canonical entrypoint: `import { ... } from \"@synapseworkspace/sdk\"`",
        "",
        "## Re-exported Modules (`src/index.ts`)",
        "",
    ]
    for module in modules:
        module_path = f"packages/synapse-sdk-ts/src/{module[2:]}.ts"
        symbols = _parse_ts_exports(module)
        lines.append(f"### `{module}`")
        lines.append("")
        lines.append(f"Source: `{module_path}`")
        lines.append("")
        if symbols:
            lines.append("Exports:")
            for name in symbols:
                lines.append(f"- `{name}`")
        else:
            lines.append("Exports: (no direct declarations parsed; module is re-exported as-is)")
        lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- `init(config)` is deprecated; use `new Synapse(config)` directly.")
    lines.append("- Keep this file generated via `scripts/generate_sdk_api_reference.py`.")
    lines.append("")
    return "\n".join(lines)


def _render_index_reference() -> str:
    lines = [
        "# SDK API Reference",
        "",
        "- [Python SDK API](python-sdk-api.md)",
        "- [TypeScript SDK API](typescript-sdk-api.md)",
        "",
        "Regenerate all reference files:",
        "",
        "```bash",
        "python3 scripts/generate_sdk_api_reference.py",
        "```",
        "",
    ]
    return "\n".join(lines)


def _render_all() -> list[RenderedFile]:
    return [
        RenderedFile(path=PY_REF, content=_render_python_reference()),
        RenderedFile(path=TS_REF, content=_render_ts_reference()),
        RenderedFile(path=INDEX_REF, content=_render_index_reference()),
    ]


def _write_files(rendered: list[RenderedFile]) -> int:
    changed = 0
    for item in rendered:
        item.path.parent.mkdir(parents=True, exist_ok=True)
        previous = item.path.read_text(encoding="utf-8") if item.path.exists() else None
        if previous != item.content:
            item.path.write_text(item.content, encoding="utf-8")
            changed += 1
    return changed


def _check_files(rendered: list[RenderedFile]) -> int:
    mismatches = 0
    for item in rendered:
        current = item.path.read_text(encoding="utf-8") if item.path.exists() else ""
        if current != item.content:
            mismatches += 1
            print(f"[api-reference] mismatch: {item.path}")
            diff = difflib.unified_diff(
                current.splitlines(),
                item.content.splitlines(),
                fromfile=f"{item.path} (current)",
                tofile=f"{item.path} (expected)",
                lineterm="",
            )
            for line in diff:
                print(line)
    if mismatches:
        print("[api-reference] run `python3 scripts/generate_sdk_api_reference.py` to refresh docs.")
        return 1
    print("[api-reference] OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate SDK API reference docs for Python and TypeScript packages.")
    parser.add_argument("--check", action="store_true", help="Verify docs/reference is up to date without writing.")
    args = parser.parse_args()
    rendered = _render_all()
    if args.check:
        return _check_files(rendered)
    changed = _write_files(rendered)
    print(f"[api-reference] updated files: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
