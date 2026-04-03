#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE=".env.selfhost"
COMPOSE_FILE="infra/docker-compose.selfhost.yml"
SOURCE_SERVICE="postgres"
SOURCE_CONTAINER=""
KEEP_ARTIFACTS="${SYNAPSE_KEEP_BACKUP_DRILL_ARTIFACTS:-0}"
BACKUP_FILE=""
TEMP_PORT=""
TEMP_CONTAINER=""

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/run_selfhost_backup_restore_drill.sh [options]

Options:
  --env-file <path>            Environment file for self-hosted stack (default: .env.selfhost)
  --compose-file <path>        Compose file path (default: infra/docker-compose.selfhost.yml)
  --source-service <name>      Compose Postgres service name (default: postgres)
  --source-container <name>    Optional direct Postgres container name (legacy override)
  --backup-file <path>         Backup SQL output path (default: /tmp/synapse-backup-drill-<ts>.sql)
  --temp-port <port>           Host port for temporary restore Postgres (default: auto)
  --keep-artifacts             Keep backup SQL file after successful drill
  -h, --help                   Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    --compose-file)
      COMPOSE_FILE="$2"
      shift 2
      ;;
    --source-container)
      SOURCE_CONTAINER="$2"
      shift 2
      ;;
    --source-service)
      SOURCE_SERVICE="$2"
      shift 2
      ;;
    --backup-file)
      BACKUP_FILE="$2"
      shift 2
      ;;
    --temp-port)
      TEMP_PORT="$2"
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

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 2
fi
COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")

if [[ -z "$BACKUP_FILE" ]]; then
  BACKUP_FILE="/tmp/synapse-backup-drill-$(date +%Y%m%d%H%M%S).sql"
fi

pick_free_port() {
  python3 - <<'PY'
import socket
s = socket.socket()
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])
s.close()
PY
}

if [[ -z "$TEMP_PORT" ]]; then
  TEMP_PORT="$(pick_free_port)"
fi

set -a
source "$ENV_FILE"
set +a

POSTGRES_USER="${POSTGRES_USER:-synapse}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-synapse}"
POSTGRES_DB="${POSTGRES_DB:-synapse}"

COUNTS_SQL=$'SELECT json_build_object(\n  \'events\', (SELECT COUNT(*) FROM events),\n  \'claims\', (SELECT COUNT(*) FROM claims),\n  \'claim_proposals\', (SELECT COUNT(*) FROM claim_proposals),\n  \'wiki_pages\', (SELECT COUNT(*) FROM wiki_pages),\n  \'wiki_statements\', (SELECT COUNT(*) FROM wiki_statements),\n  \'wiki_draft_changes\', (SELECT COUNT(*) FROM wiki_draft_changes),\n  \'knowledge_snapshots\', (SELECT COUNT(*) FROM knowledge_snapshots),\n  \'synapse_tasks\', (SELECT COUNT(*) FROM synapse_tasks)\n)::text;'

cleanup() {
  if [[ -n "$TEMP_CONTAINER" ]]; then
    docker rm -f "$TEMP_CONTAINER" >/dev/null 2>&1 || true
  fi
  if [[ "$KEEP_ARTIFACTS" != "1" && -f "$BACKUP_FILE" ]]; then
    rm -f "$BACKUP_FILE"
  fi
}
trap cleanup EXIT

if [[ -n "$SOURCE_CONTAINER" ]]; then
  if ! docker ps --format '{{.Names}}' | grep -qx "$SOURCE_CONTAINER"; then
    echo "Source Postgres container is not running: $SOURCE_CONTAINER" >&2
    exit 2
  fi
  SOURCE_COUNTS="$(docker exec "$SOURCE_CONTAINER" psql -U "$POSTGRES_USER" "$POSTGRES_DB" -Atqc "$COUNTS_SQL")"
  docker exec "$SOURCE_CONTAINER" pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > "$BACKUP_FILE"
else
  if ! "${COMPOSE[@]}" ps --status running --services | grep -qx "$SOURCE_SERVICE"; then
    echo "Source Postgres service is not running in compose stack: $SOURCE_SERVICE" >&2
    exit 2
  fi
  SOURCE_COUNTS="$("${COMPOSE[@]}" exec -T "$SOURCE_SERVICE" psql -U "$POSTGRES_USER" "$POSTGRES_DB" -Atqc "$COUNTS_SQL")"
  "${COMPOSE[@]}" exec -T "$SOURCE_SERVICE" pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > "$BACKUP_FILE"
fi

TEMP_CONTAINER="synapse-restore-drill-$RANDOM"
docker run -d --rm \
  --name "$TEMP_CONTAINER" \
  -e POSTGRES_USER="$POSTGRES_USER" \
  -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  -e POSTGRES_DB="$POSTGRES_DB" \
  -p "$TEMP_PORT:5432" \
  pgvector/pgvector:pg15 >/dev/null

for _ in $(seq 1 60); do
  if docker exec "$TEMP_CONTAINER" pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! docker exec "$TEMP_CONTAINER" pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; then
  echo "Temporary restore Postgres did not become ready." >&2
  exit 1
fi

cat "$BACKUP_FILE" | docker exec -i "$TEMP_CONTAINER" psql -U "$POSTGRES_USER" "$POSTGRES_DB" >/dev/null

RESTORED_COUNTS="$(docker exec "$TEMP_CONTAINER" psql -U "$POSTGRES_USER" "$POSTGRES_DB" -Atqc "$COUNTS_SQL")"

python3 - "$SOURCE_COUNTS" "$RESTORED_COUNTS" "$BACKUP_FILE" "$TEMP_PORT" "$TEMP_CONTAINER" <<'PY'
import json
import sys

source_raw, restored_raw, backup_file, temp_port, temp_container = sys.argv[1:6]

source = json.loads(source_raw)
restored = json.loads(restored_raw)
status = "ok" if source == restored else "failed"
payload = {
    "status": status,
    "source_counts": source,
    "restored_counts": restored,
    "backup_file": backup_file,
    "temp_restore_port": int(temp_port),
    "temp_container": temp_container,
}
print(json.dumps(payload, ensure_ascii=False, indent=2))
if status != "ok":
    raise SystemExit(1)
PY
