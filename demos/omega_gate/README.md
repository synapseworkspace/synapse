# Omega Gate Demo

Vertical demo for the scenario:

> "BC Omega gate is now card-only. All dispatching agents must account for this immediately."

The demo runs through Synapse SDK + OpenClaw connector path and verifies persistence in API/DB.

## Prerequisites

1. Start Postgres:

```bash
cd infra
docker compose up -d
```

2. Apply DB migrations:

```bash
psql postgresql://synapse:synapse@localhost:55432/synapse -f infra/postgres/migrations/001_init.sql
psql postgresql://synapse:synapse@localhost:55432/synapse -f infra/postgres/migrations/002_idempotency_requests.sql
```

3. Start API:

```bash
cd services/api
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --port 8080
```

## Run Demo

In another terminal:

```bash
python3 -m venv /tmp/synapse-demo-venv
source /tmp/synapse-demo-venv/bin/activate
pip install requests 'psycopg[binary]'
PYTHONPATH=/Users/maksimborisov/synapse/packages/synapse-sdk-py/src \
python /Users/maksimborisov/synapse/demos/omega_gate/run_demo.py
```

What happens:

1. Simulated OpenClaw hook events are captured into Synapse (`tool:result`, `message:received`, `agent:completed`).
2. Agent runs `synapse_search_wiki` tool.
3. Agent runs `synapse_propose_to_wiki` tool.
4. Synapse flushes events/fact proposal to API.
5. Script verifies rows in Postgres.
