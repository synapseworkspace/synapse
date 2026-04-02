#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATABASE_URL="${DATABASE_URL:-postgresql://synapse:synapse@localhost:55432/synapse}"

if ! command -v psql >/dev/null 2>&1; then
  echo "psql is required but not found in PATH" >&2
  exit 1
fi

echo "Applying migrations to ${DATABASE_URL}"
for migration in "$ROOT_DIR"/infra/postgres/migrations/*.sql; do
  echo "-> $(basename "$migration")"
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$migration" >/dev/null
done

echo "Migrations applied successfully"

