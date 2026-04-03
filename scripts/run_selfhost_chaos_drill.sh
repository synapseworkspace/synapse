#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.selfhost.yml"
KEEP_STACK="${SYNAPSE_KEEP_SELFHOST_STACK:-0}"
REPORT_FILE=""
PROJECT_PREFIX="selfhost_chaos"
FAULTS="postgres_restart,mcp_restart"
POST_FAULT_SETTLE_SECONDS=8

pick_free_port() {
  python3 - <<'PY'
import socket
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind(("127.0.0.1", 0))
    print(s.getsockname()[1])
PY
}

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/run_selfhost_chaos_drill.sh [options]

Options:
  --compose-file <path>           Docker compose file path (default: infra/docker-compose.selfhost.yml)
  --report-file <path>            Optional JSON report output path
  --project-prefix <prefix>       Prefix for generated project ids (default: selfhost_chaos)
  --faults <csv>                  Fault sequence (default: postgres_restart,mcp_restart)
  --post-fault-settle <seconds>   Wait time after service recovery before core-loop check (default: 8)
  --keep-stack                    Keep compose stack running after script completion
  -h, --help                      Show help

Supported faults:
  - postgres_restart
  - mcp_restart
  - api_restart
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --compose-file)
      COMPOSE_FILE="$2"
      shift 2
      ;;
    --report-file)
      REPORT_FILE="$2"
      shift 2
      ;;
    --project-prefix)
      PROJECT_PREFIX="$2"
      shift 2
      ;;
    --faults)
      FAULTS="$2"
      shift 2
      ;;
    --post-fault-settle)
      POST_FAULT_SETTLE_SECONDS="$2"
      shift 2
      ;;
    --keep-stack)
      KEEP_STACK=1
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

POSTGRES_PORT="${SYNAPSE_SELFHOST_POSTGRES_PORT:-$(pick_free_port)}"
API_PORT="${SYNAPSE_SELFHOST_API_PORT:-$(pick_free_port)}"
MCP_PORT="${SYNAPSE_SELFHOST_MCP_PORT:-$(pick_free_port)}"
POSTGRES_DB="${SYNAPSE_SELFHOST_POSTGRES_DB:-synapse}"
POSTGRES_USER="${SYNAPSE_SELFHOST_POSTGRES_USER:-synapse}"
POSTGRES_PASSWORD="${SYNAPSE_SELFHOST_POSTGRES_PASSWORD:-synapse}"

ENV_FILE="$(mktemp "${TMPDIR:-/tmp}/synapse-selfhost-chaos.XXXXXX.env")"
ARTIFACT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/synapse-selfhost-chaos.XXXXXX")"
STAGE_LINES_FILE="$ARTIFACT_DIR/stages.jsonl"
REPORT_TMP_FILE="$ARTIFACT_DIR/report.json"

cat >"$ENV_FILE" <<EOF
SYNAPSE_BIND_HOST=127.0.0.1
POSTGRES_DB=${POSTGRES_DB}
POSTGRES_USER=${POSTGRES_USER}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_PORT=${POSTGRES_PORT}
DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
SYNAPSE_API_URL=http://api:8080

SYNAPSE_API_PORT=${API_PORT}
SYNAPSE_UI_ORIGINS=*
SYNAPSE_INCIDENT_SECRET_RBAC_MODE=open
IDEMPOTENCY_TTL_SECONDS=86400
IDEMPOTENCY_IN_PROGRESS_WAIT_SECONDS=5.0
IDEMPOTENCY_CLEANUP_INTERVAL_SECONDS=60.0
IDEMPOTENCY_CLEANUP_BATCH_SIZE=1000

SYNAPSE_WORKER_ENABLE_INTELLIGENCE=1
SYNAPSE_WORKER_SYNTHESIS_INTERVAL_SEC=2
SYNAPSE_WORKER_SYNTHESIS_LIMIT=100
SYNAPSE_WORKER_SYNTHESIS_EXTRACT_LIMIT=200
SYNAPSE_WORKER_INTELLIGENCE_INTERVAL_SEC=600
SYNAPSE_WORKER_INTELLIGENCE_DELIVERY_LIMIT=200

OPENAI_API_KEY=
OPENAI_BASE_URL=

SYNAPSE_MCP_TRANSPORT=streamable-http
SYNAPSE_MCP_PORT=${MCP_PORT}
SYNAPSE_MCP_CACHE_TTL_SEC=5
SYNAPSE_MCP_CACHE_MAX_ENTRIES=5000
SYNAPSE_MCP_GRAPH_MAX_HOPS=3
SYNAPSE_MCP_GRAPH_BOOST_HOP1=0.20
SYNAPSE_MCP_GRAPH_BOOST_HOP2=0.12
SYNAPSE_MCP_GRAPH_BOOST_HOP3=0.06
SYNAPSE_MCP_GRAPH_BOOST_OTHER=0.03
EOF

HOST_DB_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:${POSTGRES_PORT}/${POSTGRES_DB}"
API_URL="http://127.0.0.1:${API_PORT}"
COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")

cleanup() {
  if [[ "$KEEP_STACK" != "1" ]]; then
    "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
  fi
  rm -f "$ENV_FILE"
  rm -rf "$ARTIFACT_DIR"
}
trap cleanup EXIT

record_stage() {
  local stage="$1"
  local status="$2"
  local detail="$3"
  python3 - "$stage" "$status" "$detail" >> "$STAGE_LINES_FILE" <<'PY'
import json
import sys
from datetime import UTC, datetime

payload = {
    "stage": sys.argv[1],
    "status": sys.argv[2],
    "detail": sys.argv[3],
    "timestamp": datetime.now(UTC).isoformat(),
}
print(json.dumps(payload, ensure_ascii=False))
PY
}

wait_api_health() {
  local timeout_seconds="${1:-180}"
  local waited=0
  while [[ "$waited" -lt "$timeout_seconds" ]]; do
    if curl -fsS "${API_URL}/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
    waited=$((waited + 1))
  done
  return 1
}

wait_service_running() {
  local service="$1"
  local timeout_seconds="${2:-180}"
  local waited=0
  while [[ "$waited" -lt "$timeout_seconds" ]]; do
    local container_id
    container_id="$("${COMPOSE[@]}" ps -q "$service" || true)"
    if [[ -n "$container_id" ]]; then
      local state
      local health
      state="$(docker inspect --format '{{.State.Status}}' "$container_id" 2>/dev/null || echo "unknown")"
      health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_id" 2>/dev/null || echo "unknown")"
      if [[ "$state" == "running" && ( "$health" == "healthy" || "$health" == "none" ) ]]; then
        return 0
      fi
    fi
    sleep 1
    waited=$((waited + 1))
  done
  return 1
}

run_core_loop_check() {
  local stage="$1"
  local project_id="${PROJECT_PREFIX}_${stage}_$(date +%s)"
  local mcp_container_id
  mcp_container_id="$("${COMPOSE[@]}" ps -q mcp || true)"
  if [[ -z "$mcp_container_id" ]]; then
    echo "[selfhost-chaos] mcp container id is empty" >&2
    return 1
  fi
  local mcp_container_name
  mcp_container_name="$(docker inspect --format '{{.Name}}' "$mcp_container_id" | sed 's#^/##')"
  python3 "$ROOT_DIR/scripts/integration_core_loop.py" \
    --api-url "$API_URL" \
    --database-url "$HOST_DB_URL" \
    --worker-mode poll \
    --worker-poll-interval 1.0 \
    --max-worker-cycles 70 \
    --mcp-probe-mode container \
    --mcp-container-name "$mcp_container_name" \
    --mcp-host 127.0.0.1 \
    --mcp-port "$MCP_PORT" \
    --project-id "$project_id" >/dev/null
}

inject_fault() {
  local fault="$1"
  case "$fault" in
    postgres_restart)
      echo "[selfhost-chaos] fault: restarting postgres"
      "${COMPOSE[@]}" restart postgres >/dev/null
      ;;
    mcp_restart)
      echo "[selfhost-chaos] fault: restarting mcp"
      "${COMPOSE[@]}" restart mcp >/dev/null
      ;;
    api_restart)
      echo "[selfhost-chaos] fault: restarting api"
      "${COMPOSE[@]}" restart api >/dev/null
      ;;
    *)
      echo "[selfhost-chaos] unsupported fault: $fault" >&2
      return 2
      ;;
  esac
  return 0
}

echo "[selfhost-chaos] cleaning previous stack"
"${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true

echo "[selfhost-chaos] starting clean self-hosted stack"
"${COMPOSE[@]}" up -d --build >/dev/null

echo "[selfhost-chaos] waiting for API health"
if ! wait_api_health 180; then
  record_stage "bootstrap" "failed" "api health check timeout"
  python3 - "$STAGE_LINES_FILE" "$REPORT_TMP_FILE" "$FAULTS" <<'PY'
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

lines_path = Path(sys.argv[1])
report_path = Path(sys.argv[2])
faults = [item.strip() for item in sys.argv[3].split(",") if item.strip()]
stages = []
if lines_path.exists():
    for line in lines_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            stages.append(json.loads(line))
report = {
    "status": "failed",
    "fault_plan": faults,
    "stages": stages,
    "generated_at": datetime.now(UTC).isoformat(),
}
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
PY
  exit 1
fi

if ! wait_service_running "mcp" 180; then
  record_stage "bootstrap" "failed" "mcp service did not reach running/healthy state"
  exit 1
fi
record_stage "bootstrap" "ok" "stack healthy"

echo "[selfhost-chaos] baseline core-loop check"
if run_core_loop_check "baseline"; then
  record_stage "baseline_core_loop" "ok" "core-loop passed"
else
  record_stage "baseline_core_loop" "failed" "core-loop failed before fault injection"
fi

IFS=',' read -r -a FAULT_LIST <<< "$FAULTS"
for raw_fault in "${FAULT_LIST[@]}"; do
  fault="$(echo "$raw_fault" | tr -d '[:space:]')"
  if [[ -z "$fault" ]]; then
    continue
  fi
  stage="fault_${fault}"
  if inject_fault "$fault"; then
    if wait_service_running "$(echo "$fault" | sed 's/_restart$//')" 180 && wait_api_health 180; then
      sleep "${POST_FAULT_SETTLE_SECONDS}"
      if run_core_loop_check "$fault"; then
        record_stage "$stage" "ok" "fault recovered and core-loop passed"
      else
        record_stage "$stage" "failed" "service recovered but core-loop failed"
      fi
    else
      record_stage "$stage" "failed" "service did not recover to healthy state"
    fi
  else
    record_stage "$stage" "failed" "fault injection command failed"
  fi
done

python3 - "$STAGE_LINES_FILE" "$REPORT_TMP_FILE" "$FAULTS" <<'PY'
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

lines_path = Path(sys.argv[1])
report_path = Path(sys.argv[2])
faults = [item.strip() for item in sys.argv[3].split(",") if item.strip()]
stages = []
if lines_path.exists():
    for line in lines_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            stages.append(json.loads(line))
status = "ok" if stages and all(item.get("status") == "ok" for item in stages) else "failed"
report = {
    "status": status,
    "fault_plan": faults,
    "stages": stages,
    "generated_at": datetime.now(UTC).isoformat(),
}
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
if status != "ok":
    raise SystemExit(1)
PY

if [[ -n "$REPORT_FILE" ]]; then
  mkdir -p "$(dirname "$REPORT_FILE")"
  cp "$REPORT_TMP_FILE" "$REPORT_FILE"
  echo "[selfhost-chaos] report saved: $REPORT_FILE"
fi

echo "[selfhost-chaos] success"
