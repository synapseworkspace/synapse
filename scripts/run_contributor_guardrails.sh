#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PROFILE="quick"
RUN_SELFHOST_CORE=0
RUN_SELFHOST_DR=0
REPORT_FILE="artifacts/release/rc-dress-rehearsal.json"

usage() {
  cat <<'EOF'
Synapse contributor guardrails runner.

Usage:
  ./scripts/run_contributor_guardrails.sh [options]

Options:
  --profile <quick|full|release>  Validation profile (default: quick).
  --selfhost-core                 Also run self-hosted core acceptance via ci_checks toggle.
  --selfhost-dr                   Also run self-hosted DR acceptance via ci_checks toggle.
  --report-file <path>            Release rehearsal report path (release profile only).
  -h, --help                      Show this help and exit.

Profiles:
  quick   -> run CI checks with browser e2e skipped (fast newcomer baseline).
  full    -> run full CI checks including browser e2e.
  release -> quick checks + OSS release-candidate dress rehearsal.
EOF
}

log() {
  printf '[guardrails] %s\n' "$1"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf '[guardrails] missing required command: %s\n' "$1" >&2
    exit 1
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile)
      if [[ $# -lt 2 ]]; then
        echo "--profile requires a value" >&2
        exit 1
      fi
      PROFILE="$2"
      shift 2
      ;;
    --selfhost-core)
      RUN_SELFHOST_CORE=1
      shift
      ;;
    --selfhost-dr)
      RUN_SELFHOST_DR=1
      shift
      ;;
    --report-file)
      if [[ $# -lt 2 ]]; then
        echo "--report-file requires a value" >&2
        exit 1
      fi
      REPORT_FILE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ "$PROFILE" != "quick" && "$PROFILE" != "full" && "$PROFILE" != "release" ]]; then
  echo "Invalid profile: $PROFILE (expected quick|full|release)" >&2
  exit 1
fi

require_cmd python3
require_cmd node
require_cmd npm
require_cmd jq
require_cmd bash

PYTHON_VERSION="$(
python3 - <<'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)"
NODE_VERSION="$(node -p "process.versions.node")"
NPM_VERSION="$(npm --version)"

log "workspace: $ROOT_DIR"
log "profile: $PROFILE"
log "python: $PYTHON_VERSION"
log "node: $NODE_VERSION"
log "npm: $NPM_VERSION"

if [[ "$RUN_SELFHOST_CORE" == "1" || "$RUN_SELFHOST_DR" == "1" ]]; then
  require_cmd docker
  log "docker: $(docker --version)"
fi

if [[ "$PROFILE" == "quick" || "$PROFILE" == "release" ]]; then
  log "running ci checks in quick mode (browser e2e skipped)"
  SYNAPSE_SKIP_WEB_E2E=1 \
  SYNAPSE_RUN_SELFHOST_CORE_ACCEPTANCE="$RUN_SELFHOST_CORE" \
  SYNAPSE_RUN_SELFHOST_DR_ACCEPTANCE="$RUN_SELFHOST_DR" \
  ./scripts/ci_checks.sh
fi

if [[ "$PROFILE" == "full" ]]; then
  log "running full ci checks"
  SYNAPSE_RUN_SELFHOST_CORE_ACCEPTANCE="$RUN_SELFHOST_CORE" \
  SYNAPSE_RUN_SELFHOST_DR_ACCEPTANCE="$RUN_SELFHOST_DR" \
  ./scripts/ci_checks.sh
fi

if [[ "$PROFILE" == "release" ]]; then
  log "running OSS release-candidate dress rehearsal"
  mkdir -p "$(dirname "$REPORT_FILE")"
  ./scripts/run_oss_rc_dress_rehearsal.sh --report-file "$REPORT_FILE"
  log "release rehearsal report: $REPORT_FILE"
fi

log "all guardrails passed"
log "next docs: docs/contributor-quickstart.md"
