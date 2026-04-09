# synapse-cli

`synapse-cli` is a local terminal helper for:
- extraction simulation (`extract`);
- trace/debug replay (`replay`);
- readiness diagnostics (`doctor`).
- project bootstrap scaffolding (`init`).
- integration snippet generation (`connect`).
- coexistence/adoption rollout planning (`adopt`).
- adoption operations (`adoption`).
- one-command end-to-end core loop verification (`verify core-loop`).
- one-command onboarding orchestration (`quickstart`).

## Install (editable workspace)

```bash
cd /Users/maksimborisov/synapse/packages/synapse-sdk-py
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## extract

Run extractor + synthesizer pipeline against local input without API calls.

```bash
synapse-cli extract \
  --text "BC Omega gate now requires access cards" \
  --category access_policy \
  --entity-key bc_omega \
  --pretty
```

Use JSON payload mode:

```bash
synapse-cli extract --file ./tool_result.json --result-json --as-claims --pretty
```

## replay

Replay trace timelines from debug JSONL/JSON exports.

```bash
synapse-cli replay --input ./debug_records.jsonl --trace-id trace_123
```

```bash
synapse-cli replay --input ./events.json --json
```

## doctor

Check local Synapse API readiness and core endpoints.

```bash
synapse-cli doctor --api-url http://localhost:8080 --project-id omega_demo
```

Strict CI-friendly mode:

```bash
synapse-cli doctor --api-url http://localhost:8080 --project-id omega_demo --strict --json
```

If `--project-id` is missing, project-scoped checks are skipped.

## init

Generate an opinionated local env scaffold for SDK onboarding.

```bash
synapse-cli init --dir . --project-id omega_demo --api-url http://localhost:8080
```

Dry run preview:

```bash
synapse-cli init --dir . --project-id omega_demo --dry-run --json
```

## connect openclaw

Generate env-aware attach snippet for OpenClaw runtime:

```bash
synapse-cli connect openclaw --dir . --env-file .env.synapse
```

JSON mode for automation/copy pipelines:

```bash
synapse-cli connect openclaw --dir . --env-file .env.synapse --json
```

## adopt

Generate coexistence rollout plan for projects that already have memory systems:

```bash
synapse-cli adopt \
  --dir . \
  --memory-system ops_kb_items \
  --memory-source hybrid \
  --adoption-mode observe_only \
  --sample-file ./memory_export.jsonl
```

Run shadow retrieval diff (Synapse retrieval vs lexical baseline from sample records):

```bash
synapse-cli adopt \
  --dir . \
  --sample-file ./memory_export.jsonl \
  --shadow-retrieval-check \
  --shadow-query "bc omega gate access policy" \
  --json
```

## adoption

Operate project-scoped adoption workflows without raw API calls.

Inspect cursor health:

```bash
synapse-cli adoption cursor-health \
  --api-url http://localhost:8080 \
  --project-id omega_demo \
  --stale-after-hours 24
```

Run enterprise sync preset (dry-run by default):

```bash
synapse-cli adoption sync-preset \
  --api-url http://localhost:8080 \
  --project-id omega_demo \
  --updated-by ops_admin \
  --with-pipeline
```

Apply preset for real:

```bash
synapse-cli adoption sync-preset \
  --api-url http://localhost:8080 \
  --project-id omega_demo \
  --updated-by ops_admin \
  --apply \
  --with-pipeline
```

Bootstrap connector in one step (`resolve -> upsert source -> queue`):

```bash
synapse-cli adoption connect-source \
  --api-url http://localhost:8080 \
  --project-id omega_demo \
  --updated-by ops_admin \
  --connector-id postgres_sql:ops_kb_items:polling \
  --field-overrides-json '{"sql_dsn_env":"OPS_PG_DSN"}' \
  --apply
```

Inspect enterprise readiness (auth/rbac/tenancy + table checks):

```bash
synapse-cli adoption enterprise-readiness \
  --api-url http://localhost:8080 \
  --project-id omega_demo
```

Inspect funnel bottlenecks:

```bash
synapse-cli adoption pipeline \
  --api-url http://localhost:8080 \
  --project-id omega_demo \
  --days 14
```

Inspect rejection reasons:

```bash
synapse-cli adoption rejections \
  --api-url http://localhost:8080 \
  --project-id omega_demo \
  --days 14 \
  --sample-limit 5
```

List and bulk-moderate drafts:

```bash
synapse-cli adoption list-drafts --api-url http://localhost:8080 --project-id omega_demo --status pending_review --limit 50
synapse-cli adoption bulk-review-drafts --api-url http://localhost:8080 --project-id omega_demo --reviewed-by ops_reviewer --action approve --category policy --category-mode prefix --source-system postgres_sql --min-confidence 0.85
```

## verify core-loop

Run end-to-end acceptance from CLI:
`ingest -> draft -> approve -> MCP retrieval`.

```bash
synapse-cli verify core-loop --project-id omega_demo --json
```

Use an explicit script path (for custom workspace layouts or CI):

```bash
synapse-cli verify core-loop --script ./scripts/integration_core_loop.py --project-id omega_demo
```

Dry-run command preview:

```bash
synapse-cli verify core-loop --project-id omega_demo --dry-run
```

## quickstart

Run full onboarding path in one command:
`init -> doctor -> connect` (optionally `verify core-loop`).

```bash
synapse-cli quickstart --dir . --project-id omega_demo --api-url http://localhost:8080 --doctor-strict
```

Include end-to-end verification in the same run:

```bash
synapse-cli quickstart --dir . --project-id omega_demo --api-url http://localhost:8080 --doctor-strict --verify-core-loop
```

Machine-readable output:

```bash
synapse-cli quickstart --dir . --project-id omega_demo --json
```
