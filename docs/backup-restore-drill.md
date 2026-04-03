# Synapse Backup/Restore Drill

Last updated: 2026-04-02

Automates a safe restore validation for self-hosted deployments:
1. Reads row-count baseline from live compose `postgres` service.
2. Creates SQL backup via `pg_dump`.
3. Restores backup into temporary Postgres container.
4. Compares core table counts between source and restored DB.

Script:

```bash
./scripts/run_selfhost_backup_restore_drill.sh --env-file .env.selfhost
```

End-to-end DR acceptance (boot clean compose stack, seed API data, run drill):

```bash
./scripts/run_selfhost_dr_ci_acceptance.sh --report-file artifacts/selfhost-dr/report.json
```

## What is validated

- `events`
- `claims`
- `claim_proposals`
- `wiki_pages`
- `wiki_statements`
- `wiki_draft_changes`
- `knowledge_snapshots`
- `synapse_tasks`

Success criteria:
- script exits `0`
- JSON output has `"status": "ok"`
- source/restored counts are identical.

## Options

```bash
./scripts/run_selfhost_backup_restore_drill.sh \
  --env-file .env.selfhost \
  --source-service postgres \
  --backup-file /tmp/synapse-backup.sql \
  --temp-port 55439 \
  --keep-artifacts
```

## Notes

- Uses temporary container image: `pgvector/pgvector:pg15`.
- Does not mutate the source database.
- By default temporary backup file is removed after successful run.
- CI workflow opt-in (`.github/workflows/ci.yml`): `workflow_dispatch` input `run_selfhost_dr_drill=true`.
