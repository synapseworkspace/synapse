#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.selfhost.yml"
KEEP_STACK="${SYNAPSE_KEEP_SELFHOST_STACK:-0}"
REPORT_FILE=""
PROJECT_ID="selfhost_dr_$(date +%s)"

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
  ./scripts/run_selfhost_dr_ci_acceptance.sh [options]

Options:
  --compose-file <path>    Docker compose file path (default: infra/docker-compose.selfhost.yml)
  --project-id <id>        Seed project_id for API data before drill (default: selfhost_dr_<timestamp>)
  --report-file <path>     Optional JSON report output path
  --keep-stack             Keep compose stack running after success/failure
  -h, --help               Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --compose-file)
      COMPOSE_FILE="$2"
      shift 2
      ;;
    --project-id)
      PROJECT_ID="$2"
      shift 2
      ;;
    --report-file)
      REPORT_FILE="$2"
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

ENV_FILE="$(mktemp "${TMPDIR:-/tmp}/synapse-selfhost-dr-ci.XXXXXX.env")"
ARTIFACT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/synapse-selfhost-dr-ci.XXXXXX")"
SEED_RESULT_FILE="$ARTIFACT_DIR/seed.json"
DRILL_RESULT_FILE="$ARTIFACT_DIR/drill.json"
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

echo "[selfhost-dr-ci] cleaning previous stack"
"${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true

echo "[selfhost-dr-ci] starting clean self-hosted stack"
"${COMPOSE[@]}" up -d --build >/dev/null

echo "[selfhost-dr-ci] waiting for API health ${API_URL}/health"
for _ in $(seq 1 120); do
  if curl -fsS "${API_URL}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
curl -fsS "${API_URL}/health" >/dev/null

MCP_CONTAINER_ID="$("${COMPOSE[@]}" ps -q mcp)"
if [[ -z "$MCP_CONTAINER_ID" ]]; then
  echo "[selfhost-dr-ci] mcp container id is empty" >&2
  exit 1
fi
echo "[selfhost-dr-ci] waiting for MCP container health"
for _ in $(seq 1 120); do
  MCP_STATE="$(docker inspect --format '{{.State.Status}}' "$MCP_CONTAINER_ID" 2>/dev/null || echo "unknown")"
  MCP_HEALTH="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$MCP_CONTAINER_ID" 2>/dev/null || echo "unknown")"
  if [[ "$MCP_STATE" == "running" && ( "$MCP_HEALTH" == "healthy" || "$MCP_HEALTH" == "none" ) ]]; then
    break
  fi
  sleep 1
done
MCP_RESTART_COUNT="$(docker inspect --format '{{.RestartCount}}' "$MCP_CONTAINER_ID" 2>/dev/null || echo "999")"
if [[ "$MCP_RESTART_COUNT" != "0" ]]; then
  echo "[selfhost-dr-ci] mcp restart loop detected (restart_count=$MCP_RESTART_COUNT)" >&2
  "${COMPOSE[@]}" logs --no-color mcp | tail -n 200 >&2 || true
  exit 1
fi

echo "[selfhost-dr-ci] seeding API with event + proposal"
python3 - "$API_URL" "$PROJECT_ID" "$SEED_RESULT_FILE" <<'PY'
import json
import sys
from datetime import UTC, datetime
from urllib.request import Request, urlopen
from uuid import uuid4

api_url = sys.argv[1].rstrip("/")
project_id = sys.argv[2]
out_file = sys.argv[3]
now = datetime.now(UTC).isoformat()

event = {
    "id": str(uuid4()),
    "schema_version": "v1",
    "project_id": project_id,
    "event_type": "tool_result",
    "payload": {
        "tool": "dispatch.plan_route",
        "result": "Gate requires card access after 10:00",
    },
    "observed_at": now,
    "agent_id": "selfhost-dr-checker",
    "session_id": f"dr-{uuid4()}",
}
event_req = Request(
    url=f"{api_url}/v1/events",
    method="POST",
    data=json.dumps({"events": [event]}).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)
with urlopen(event_req, timeout=15) as response:
    event_result = json.loads(response.read().decode("utf-8"))

claim = {
    "id": str(uuid4()),
    "schema_version": "v1",
    "project_id": project_id,
    "entity_key": "bc_omega",
    "category": "access_policy",
    "claim_text": "Gate is card-only after 10:00",
    "status": "pending",
    "evidence": [{"source_id": event["id"], "source_type": "event"}],
    "observed_at": now,
}
claim_req = Request(
    url=f"{api_url}/v1/facts/proposals",
    method="POST",
    data=json.dumps({"claim": claim}).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)
with urlopen(claim_req, timeout=15) as response:
    claim_result = json.loads(response.read().decode("utf-8"))

payload = {
    "status": "ok",
    "project_id": project_id,
    "event_result": event_result,
    "claim_result": claim_result,
    "seeded_at": now,
}
with open(out_file, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, ensure_ascii=False, indent=2)
print(json.dumps(payload, ensure_ascii=False))
PY

echo "[selfhost-dr-ci] running backup/restore drill"
./scripts/run_selfhost_backup_restore_drill.sh \
  --env-file "$ENV_FILE" \
  --compose-file "$COMPOSE_FILE" \
  --source-service postgres \
  --backup-file "$ARTIFACT_DIR/backup.sql" \
  --keep-artifacts > "$DRILL_RESULT_FILE"

python3 - "$SEED_RESULT_FILE" "$DRILL_RESULT_FILE" "$REPORT_TMP_FILE" "$PROJECT_ID" <<'PY'
import json
import sys
from datetime import UTC, datetime

seed_file, drill_file, report_file, project_id = sys.argv[1:5]
with open(seed_file, "r", encoding="utf-8") as handle:
    seed = json.load(handle)
with open(drill_file, "r", encoding="utf-8") as handle:
    drill = json.load(handle)

status = "ok" if seed.get("status") == "ok" and drill.get("status") == "ok" else "failed"
report = {
    "status": status,
    "project_id": project_id,
    "seed": seed,
    "drill": drill,
    "generated_at": datetime.now(UTC).isoformat(),
}
with open(report_file, "w", encoding="utf-8") as handle:
    json.dump(report, handle, ensure_ascii=False, indent=2)
print(json.dumps(report, ensure_ascii=False, indent=2))
if status != "ok":
    raise SystemExit(1)
PY

if [[ -n "$REPORT_FILE" ]]; then
  mkdir -p "$(dirname "$REPORT_FILE")"
  cp "$REPORT_TMP_FILE" "$REPORT_FILE"
fi

echo "[selfhost-dr-ci] success"
