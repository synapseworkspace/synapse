#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "config" / "api_web_compat.json"
WEB_PACKAGE_PATH = ROOT / "apps" / "web" / "package.json"
COMPAT_DOC_PATH = ROOT / "docs" / "compatibility-matrix.md"
API_README_PATH = ROOT / "services" / "api" / "README.md"


def _version_to_tuple(value: Any) -> tuple[int, ...]:
    text = str(value or "").strip()
    if not text:
        return ()
    parts = re.split(r"[^0-9]+", text)
    out: list[int] = []
    for part in parts:
        if not part:
            continue
        out.append(int(part))
    return tuple(out)


def _compare_versions(left: Any, right: Any) -> int:
    l = _version_to_tuple(left)
    r = _version_to_tuple(right)
    if not l and not r:
        return 0
    if not l:
        return -1
    if not r:
        return 1
    width = max(len(l), len(r))
    l = tuple(list(l) + [0] * (width - len(l)))
    r = tuple(list(r) + [0] * (width - len(r)))
    if l < r:
        return -1
    if l > r:
        return 1
    return 0


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []

    if not CONTRACT_PATH.exists():
        errors.append(f"missing compatibility contract: {CONTRACT_PATH}")
        print("\n".join(errors), file=sys.stderr)
        return 1
    contract = _load_json(CONTRACT_PATH)
    required_keys = ("api_version", "minimum_web_build", "recommended_web_build")
    for key in required_keys:
        value = str(contract.get(key) or "").strip()
        if not value:
            errors.append(f"{CONTRACT_PATH}: missing `{key}`")

    web_pkg = _load_json(WEB_PACKAGE_PATH)
    web_version = str(web_pkg.get("version") or "").strip()
    min_web = str(contract.get("minimum_web_build") or "").strip()
    rec_web = str(contract.get("recommended_web_build") or "").strip()
    if _compare_versions(web_version, min_web) < 0:
        errors.append(
            f"apps/web version ({web_version}) is below minimum_web_build ({min_web}) from {CONTRACT_PATH}"
        )
    if _compare_versions(rec_web, min_web) < 0:
        errors.append(
            f"recommended_web_build ({rec_web}) must be >= minimum_web_build ({min_web}) in {CONTRACT_PATH}"
        )

    compat_doc = COMPAT_DOC_PATH.read_text(encoding="utf-8")
    if "/v1/meta/compatibility" not in compat_doc:
        errors.append(f"{COMPAT_DOC_PATH}: missing `/v1/meta/compatibility` contract note")
    api_readme = API_README_PATH.read_text(encoding="utf-8")
    if "/v1/meta/compatibility" not in api_readme:
        errors.append(f"{API_README_PATH}: missing endpoint docs for `/v1/meta/compatibility`")

    if errors:
        print("api/web compatibility contract check failed:", file=sys.stderr)
        for err in errors:
            print(f"- {err}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "status": "ok",
                "contract": str(CONTRACT_PATH),
                "api_version": str(contract.get("api_version") or ""),
                "minimum_web_build": min_web,
                "recommended_web_build": rec_web,
                "web_version": web_version,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
