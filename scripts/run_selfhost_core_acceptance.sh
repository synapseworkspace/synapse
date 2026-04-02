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

SYNAPSE_MCP_TRANSPORT=http
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

echo "[selfhost-acceptance] running core loop acceptance against compose stack"
python3 "$ROOT_DIR/scripts/integration_core_loop.py" \
  --api-url "$API_URL" \
  --database-url "$HOST_DB_URL" \
  --worker-mode poll \
  --worker-poll-interval 1.0 \
  --max-worker-cycles 60 \
  --mcp-probe-mode container \
  --mcp-container-name synapse-mcp \
  --mcp-host 127.0.0.1 \
  --mcp-port "$MCP_PORT" \
  --project-id "core_selfhost_$(date +%s)"

echo "[selfhost-acceptance] success"
