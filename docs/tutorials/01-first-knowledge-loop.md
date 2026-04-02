# Tutorial: First Knowledge Loop

Goal: run Synapse core loop end-to-end in local mode.

## 1. Start stack

```bash
cp .env.example .env
cd infra && docker compose up -d
cd ..
./scripts/apply_migrations.sh
```

## 2. Start API

```bash
cd services/api
python -m venv .venv && source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --port 8080
```

## 3. Send sample observations

Use Python SDK quickstart:

```bash
PYTHONPATH=packages/synapse-sdk-py/src python packages/synapse-sdk-py/examples/quickstart.py
```

## 4. Run synthesis worker

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_wiki_synthesis.py --limit 100 --cycles 1
```

## 5. Open web UI

```bash
cd apps/web
npm install
npm run dev
```

Open `http://localhost:5173` and use:
- `Core Mode` (default)
- `Project ID` from your sample data
- `Refresh Inbox`

Review a draft and approve/reject it in Draft Detail.

## 6. Read approved knowledge through MCP

```bash
PYTHONPATH=services/mcp python services/mcp/scripts/run_mcp_server.py --transport stdio
```

Then call MCP tool `search_knowledge` for your project/entity and verify approved statement appears.

## Expected Outcome

You should complete:

1. observation captured
2. draft synthesized
3. human moderation action
4. retrieval through MCP

