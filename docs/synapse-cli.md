# synapse-cli

`synapse-cli` is a local terminal helper for:
- extraction simulation (`extract`);
- trace/debug replay (`replay`);
- readiness diagnostics (`doctor`).
- project bootstrap scaffolding (`init`).
- integration snippet generation (`connect`).
- coexistence/adoption rollout planning (`adopt`).
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
