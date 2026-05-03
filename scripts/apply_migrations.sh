#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATABASE_URL="${DATABASE_URL:-postgresql://synapse:synapse@localhost:55432/synapse}"
MIGRATIONS_DIR="${MIGRATIONS_DIR:-$ROOT_DIR/infra/postgres/migrations}"

if ! command -v psql >/dev/null 2>&1; then
  echo "psql is required but not found in PATH" >&2
  exit 1
fi

echo "Applying migrations to ${DATABASE_URL}"
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 <<'SQL' >/dev/null
CREATE TABLE IF NOT EXISTS schema_migration_runs (
  migration_name TEXT PRIMARY KEY,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
SQL

for migration in "$MIGRATIONS_DIR"/*.sql; do
  name="$(basename "$migration")"
  already_applied="$(psql "$DATABASE_URL" -tA -v ON_ERROR_STOP=1 -c "SELECT 1 FROM schema_migration_runs WHERE migration_name = '$name' LIMIT 1")"
  if [[ "$already_applied" == "1" ]]; then
    echo "-> ${name} (already applied, skipping)"
    continue
  fi
  echo "-> ${name}"
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$migration" >/dev/null
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "INSERT INTO schema_migration_runs (migration_name) VALUES ('$name') ON CONFLICT (migration_name) DO NOTHING" >/dev/null
done

echo "Migrations applied successfully"
