# Tutorial: MCP Context Injection

Goal: inject approved wiki facts and task state into agent prompts.

## 1. Start MCP runtime

```bash
PYTHONPATH=services/mcp python services/mcp/scripts/run_mcp_server.py --transport stdio
```

## 2. Build context with SDK helper (Python)

```python
from synapse_sdk import MCPContextHelper

helper = MCPContextHelper(
    project_id="omega_demo",
    call_tool=lambda tool, payload: mcp_client.call_tool(tool, payload),
    default_context_policy_profile="enforced",  # advisory | enforced | strict_enforced
)

context_md = helper.build_context_markdown(
    query="Deliver to BC Omega",
    entity_key="bc_omega",
    include_recent_changes=True,
    context_policy_profile="enforced",
)
print(context_md)
```

`context_policy_profile` presets:
- `advisory`: retrieval diagnostics only, no strict filtering.
- `enforced`: production-safe confidence/score filtering defaults.
- `strict_enforced`: tighter filtering for high-risk domains.

To auto-pick profile/threshold hints from benchmark trend data:

```bash
python3 scripts/check_mcp_retrieval_trend.py \
  --latest-benchmark eval/mcp_benchmark_latest_sample.json \
  --history-file eval/mcp_benchmark_history_sample.jsonl
```

Use `recommended_context_policy_profile.profile` as your helper default.

For OpenClaw callback wiring:

```python
search_cb = helper.make_openclaw_search_callback(
    default_filters={"entity_key": "bc_omega"},
    context_policy_profile="enforced",
)
```

## 3. Pull tasks for execution loop

Use MCP tools:
- `get_open_tasks`
- `get_task_details`

Pattern:

1. fetch active tasks
2. pick relevant task by `entity_key`/assignee
3. inject task timeline + links into prompt
4. update status via Synapse API/SDK after execution

## 4. Validate retrieval quality

```bash
PYTHONPATH=services/mcp python scripts/eval_mcp_retrieval_regression.py --dataset eval/mcp_retrieval_cases.json
```
