#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SKIP_PYTHON=0
SKIP_NODE=0
SKIP_DOCS=0
KEEP_ARTIFACTS="${SYNAPSE_KEEP_RC_ARTIFACTS:-0}"
REPORT_FILE=""
TMP_DIR=""

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/run_oss_rc_dress_rehearsal.sh [options]

Options:
  --skip-python              Skip Python clean-room package drill
  --skip-node                Skip npm clean-room package drill
  --skip-docs                Skip docs walkthrough checks
  --report-file <path>       Optional JSON report output path
  --keep-artifacts           Keep temporary artifacts directory
  -h, --help                 Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-python)
      SKIP_PYTHON=1
      shift 1
      ;;
    --skip-node)
      SKIP_NODE=1
      shift 1
      ;;
    --skip-docs)
      SKIP_DOCS=1
      shift 1
      ;;
    --report-file)
      REPORT_FILE="$2"
      shift 2
      ;;
    --keep-artifacts)
      KEEP_ARTIFACTS=1
      shift 1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 2
  fi
}

require_cmd python3
require_cmd npm

TMP_DIR="$(mktemp -d "/tmp/synapse-rc-rehearsal-XXXXXX")"

cleanup() {
  if [[ "$KEEP_ARTIFACTS" != "1" && -n "$TMP_DIR" && -d "$TMP_DIR" ]]; then
    rm -rf "$TMP_DIR"
  fi
}
trap cleanup EXIT

python_result='{"status":"skipped"}'
node_result='{"status":"skipped"}'
docs_result='{"status":"skipped"}'

RELEASE_VERSION="$(python3 scripts/check_release_versions.py | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])')"
if [[ -z "$RELEASE_VERSION" ]]; then
  echo "Could not resolve release version via scripts/check_release_versions.py" >&2
  exit 1
fi
python3 scripts/check_publish_hygiene.py >/dev/null

if [[ "$SKIP_DOCS" != "1" ]]; then
  python3 - <<'PY' > "$TMP_DIR/docs-result.json"
import json
from pathlib import Path

root = Path(".").resolve()
required = [
    root / "README.md",
    root / "CHANGELOG.md",
    root / "ROADMAP.md",
    root / "docs" / "release-workflow.md",
    root / "docs" / "oss-readiness.md",
    root / "docs" / "compatibility-matrix.md",
    root / "docs" / "self-hosted-deployment.md",
]
missing = [str(path) for path in required if not path.exists()]
payload = {
    "status": "ok" if not missing else "failed",
    "checked_files": [str(path) for path in required],
    "missing": missing,
}
print(json.dumps(payload, ensure_ascii=False))
if missing:
    raise SystemExit(1)
PY
  docs_result="$(cat "$TMP_DIR/docs-result.json")"
fi

if [[ "$SKIP_PYTHON" != "1" ]]; then
  PY_BUILD_VENV="$TMP_DIR/py-build-venv"
  PY_INSTALL_VENV="$TMP_DIR/py-install-venv"
  PY_DIST_DIR="$TMP_DIR/py-dist"

  python3 -m venv "$PY_BUILD_VENV"
  source "$PY_BUILD_VENV/bin/activate"
  python -m pip install --quiet --upgrade pip build
  python -m build packages/synapse-sdk-py --outdir "$PY_DIST_DIR" >/dev/null
  deactivate

  WHEEL_PATH="$(find "$PY_DIST_DIR" -type f -name '*.whl' | head -n 1)"
  SDIST_PATH="$(find "$PY_DIST_DIR" -type f -name '*.tar.gz' | head -n 1)"
  if [[ -z "$WHEEL_PATH" || -z "$SDIST_PATH" ]]; then
    echo "Python build artifacts not found in $PY_DIST_DIR" >&2
    exit 1
  fi

  python3 -m venv "$PY_INSTALL_VENV"
  source "$PY_INSTALL_VENV/bin/activate"
  python -m pip install --quiet "$WHEEL_PATH"
  python scripts/check_python_package_install_smoke.py --expected-version "$RELEASE_VERSION" --check-cli > "$TMP_DIR/python-result.json"
  deactivate
  python_result="$(cat "$TMP_DIR/python-result.json")"
fi

if [[ "$SKIP_NODE" != "1" ]]; then
  NPM_PACK_DIR="$TMP_DIR/npm-packs"
  NPM_APP_DIR="$TMP_DIR/npm-cleanroom"
  mkdir -p "$NPM_PACK_DIR" "$NPM_APP_DIR"

  npm --prefix packages/synapse-sdk-ts install --silent
  npm --prefix packages/synapse-sdk-ts run build >/dev/null
  npm --prefix packages/synapse-openclaw-plugin install --silent
  npm --prefix packages/synapse-openclaw-plugin run build >/dev/null

  SCHEMA_TGZ="$(npm pack --silent --pack-destination "$NPM_PACK_DIR" ./packages/synapse-schema | tail -n 1)"
  SDK_TGZ="$(npm pack --silent --pack-destination "$NPM_PACK_DIR" ./packages/synapse-sdk-ts | tail -n 1)"
  OPENCLAW_TGZ="$(npm pack --silent --pack-destination "$NPM_PACK_DIR" ./packages/synapse-openclaw-plugin | tail -n 1)"

  cat > "$NPM_APP_DIR/package.json" <<'JSON'
{
  "name": "synapse-rc-cleanroom",
  "private": true,
  "type": "module",
  "version": "0.0.0"
}
JSON

  npm --prefix "$NPM_APP_DIR" install --silent \
    "$NPM_PACK_DIR/$SCHEMA_TGZ" \
    "$NPM_PACK_DIR/$SDK_TGZ" \
    "$NPM_PACK_DIR/$OPENCLAW_TGZ"

  node scripts/check_npm_package_install_smoke.mjs \
    --expected-version "$RELEASE_VERSION" \
    --project-root "$NPM_APP_DIR" > "$TMP_DIR/node-result.json"
  node_result="$(cat "$TMP_DIR/node-result.json")"
fi

python3 - "$python_result" "$node_result" "$docs_result" "$TMP_DIR" > "$TMP_DIR/result.json" <<'PY'
import json
import sys

python_result = json.loads(sys.argv[1])
node_result = json.loads(sys.argv[2])
docs_result = json.loads(sys.argv[3])
tmp_dir = sys.argv[4]

components = {
    "python": python_result,
    "node": node_result,
    "docs": docs_result,
}
failed = [name for name, payload in components.items() if payload.get("status") not in {"ok", "skipped"}]
status = "ok" if not failed else "failed"

result = {
    "status": status,
    "components": components,
    "temp_artifacts_dir": tmp_dir,
}
print(json.dumps(result, ensure_ascii=False, indent=2))
if failed:
    raise SystemExit(1)
PY

if [[ -n "$REPORT_FILE" ]]; then
  mkdir -p "$(dirname "$REPORT_FILE")"
  cp "$TMP_DIR/result.json" "$REPORT_FILE"
fi

cat "$TMP_DIR/result.json"
