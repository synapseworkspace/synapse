# Agent Simulator Sandbox

`run_agent_simulator.py` replays proposed policy changes on historical sessions and predicts rollout impact before production.

## Input format

Provide policy changes as JSON array (or object with `policy_changes`):

```json
[
  {
    "policy_id": "omega_gate_card_only",
    "entity_key": "bc_omega",
    "category": "access",
    "old_statement": "Gate is open for all deliveries.",
    "new_statement": "Gate is card-only after 10:00."
  }
]
```

## Run and persist simulator results

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_agent_simulator.py \
  --project-id omega_demo \
  --policy-file ./policies.json \
  --lookback-days 14 \
  --max-sessions 200
```

This creates:

- `agent_simulator_runs` row with aggregated summary and metadata.
- `agent_simulator_findings` rows with per-session impact details.

## Dry run mode

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_agent_simulator.py \
  --project-id omega_demo \
  --policy-file ./policies.json \
  --dry-run
```

Dry run computes findings without writing run/finding rows to DB.

## API read endpoints

- `GET /v1/simulator/runs?project_id=...`
- `GET /v1/simulator/runs/{run_id}?project_id=...&findings_limit=50`

These endpoints are read-only and intended for UI/reporting after worker execution.

## API enqueue + async worker flow

Queue a run from API:

```bash
curl -sS -X POST http://localhost:8080/v1/simulator/runs \
  -H 'Content-Type: application/json' \
  -d '{
    "project_id": "omega_demo",
    "created_by": "ops_ui",
    "policy_changes": [
      {
        "policy_id": "omega_gate_card_only",
        "entity_key": "bc_omega",
        "category": "access",
        "old_statement": "Gate is open for all deliveries.",
        "new_statement": "Gate is card-only after 10:00."
      }
    ]
  }'
```

Process queue in worker:

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_agent_simulator_queue.py --limit 10
```

## Templates + Scheduler Presets

Synapse scheduler can auto-queue simulator runs from reusable templates:

- `gate_access_card_only`
- `warehouse_quarantine`
- `prepaid_only_dispatch`

Supported presets:

- `hourly`
- `every_6_hours`
- `daily`
- `weekly`

Dry-run schedule preview:

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_agent_simulator_scheduler.py \
  --dry-run \
  --schedules-json '{
    "schedules": [
      {
        "project_id": "omega_demo",
        "template_id": "gate_access_card_only",
        "template_params": {"entity_key": "bc_omega", "location_name": "BC Omega"},
        "preset": "daily"
      }
    ]
  }'
```

Queue due runs in production mode:

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_agent_simulator_scheduler.py \
  --schedules-file ./simulator_schedules.json
```

Then process queued jobs:

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_agent_simulator_queue.py --limit 20
```
