#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.selfhost.yml"
KEEP_STACK="${SYNAPSE_KEEP_SELFHOST_STACK:-0}"

pick_free_port() {
  python3 - <<'PY'
import socket
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind(("127.0.0.1", 0))
    print(s.getsockname()[1])
PY
}

POSTGRES_PORT="${SYNAPSE_SELFHOST_POSTGRES_PORT:-$(pick_free_port)}"
API_PORT="${SYNAPSE_SELFHOST_API_PORT:-$(pick_free_port)}"
MCP_PORT="${SYNAPSE_SELFHOST_MCP_PORT:-$(pick_free_port)}"
POSTGRES_DB="${SYNAPSE_SELFHOST_POSTGRES_DB:-synapse}"
POSTGRES_USER="${SYNAPSE_SELFHOST_POSTGRES_USER:-synapse}"
POSTGRES_PASSWORD="${SYNAPSE_SELFHOST_POSTGRES_PASSWORD:-synapse}"

ENV_FILE="$(mktemp "${TMPDIR:-/tmp}/synapse-selfhost-acceptance.XXXXXX.env")"
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
SYNAPSE_WORKER_ENABLE_LEGACY_SYNC=1
SYNAPSE_WORKER_LEGACY_SYNC_INTERVAL_SEC=3
SYNAPSE_WORKER_LEGACY_SYNC_ENQUEUE_LIMIT=100
SYNAPSE_WORKER_LEGACY_SYNC_PROCESS_LIMIT=100
SYNAPSE_WORKER_LEGACY_SYNC_ALL_PROJECTS=1
SYNAPSE_WORKER_LEGACY_SYNC_API_URL=http://api:8080
SYNAPSE_WORKER_LEGACY_SYNC_API_KEY=
SYNAPSE_WORKER_LEGACY_SYNC_REQUESTED_BY=legacy_sync_scheduler
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
LEGACY_SQL_DSN_IN_CONTAINER="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}"
COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")

cleanup() {
  if [[ "$KEEP_STACK" != "1" ]]; then
    "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
  fi
  rm -f "$ENV_FILE"
}
trap cleanup EXIT

echo "[selfhost-acceptance] cleaning previous stack"
"${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true

echo "[selfhost-acceptance] starting clean self-hosted stack"
"${COMPOSE[@]}" up -d --build >/dev/null

echo "[selfhost-acceptance] waiting for API health ${API_URL}/health"
for _ in $(seq 1 120); do
  if curl -fsS "${API_URL}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
curl -fsS "${API_URL}/health" >/dev/null

MCP_CONTAINER_ID="$("${COMPOSE[@]}" ps -q mcp)"
if [[ -z "$MCP_CONTAINER_ID" ]]; then
  echo "[selfhost-acceptance] mcp container id is empty" >&2
  exit 1
fi
MCP_CONTAINER_NAME="$(docker inspect --format '{{.Name}}' "$MCP_CONTAINER_ID" | sed 's#^/##')"

echo "[selfhost-acceptance] waiting for MCP container health"
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
  echo "[selfhost-acceptance] mcp restart loop detected (restart_count=$MCP_RESTART_COUNT)" >&2
  "${COMPOSE[@]}" logs --no-color mcp | tail -n 200 >&2 || true
  exit 1
fi

WORKER_CONTAINER_ID="$("${COMPOSE[@]}" ps -q worker)"
if [[ -z "$WORKER_CONTAINER_ID" ]]; then
  echo "[selfhost-acceptance] worker container id is empty" >&2
  exit 1
fi
WORKER_RESTART_COUNT="$(docker inspect --format '{{.RestartCount}}' "$WORKER_CONTAINER_ID" 2>/dev/null || echo "999")"
if [[ "$WORKER_RESTART_COUNT" != "0" ]]; then
  echo "[selfhost-acceptance] worker restart loop detected (restart_count=$WORKER_RESTART_COUNT)" >&2
  "${COMPOSE[@]}" logs --no-color worker | tail -n 200 >&2 || true
  exit 1
fi

echo "[selfhost-acceptance] running core loop acceptance against compose stack"
python3 "$ROOT_DIR/scripts/integration_core_loop.py" \
  --api-url "$API_URL" \
  --database-url "$HOST_DB_URL" \
  --worker-mode poll \
  --worker-poll-interval 1.0 \
  --max-worker-cycles 60 \
  --mcp-probe-mode container \
  --mcp-container-name "$MCP_CONTAINER_NAME" \
  --mcp-host 127.0.0.1 \
  --mcp-port "$MCP_PORT" \
  --project-id "core_selfhost_$(date +%s)"

echo "[selfhost-acceptance] running legacy sync queue processing acceptance"
python3 "$ROOT_DIR/scripts/integration_legacy_sync_queue_processing.py" \
  --api-url "$API_URL" \
  --legacy-sql-dsn "$LEGACY_SQL_DSN_IN_CONTAINER" \
  --project-id "legacy_selfhost_$(date +%s)" \
  --timeout-seconds 240 \
  --poll-interval-seconds 2

echo "[selfhost-acceptance] success"
