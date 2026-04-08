# Post-Deploy Smoke Test (Core Wiki)

This is the standard release smoke flow:

1. Import 10+ memory records.
2. Produce at least 1 draft.
3. Publish at least 1 page.
4. Verify retrieval via `/wiki` + MCP/API retrieval path.

## One-Command Run

```bash
./scripts/run_selfhost_core_acceptance.sh
```

The script boots a clean self-host stack, verifies API + MCP health, runs `integration_core_loop.py`, and fails on:
- no draft produced;
- no publish transition;
- retrieval mismatch on published page.

## Expected Outcome

- exit code `0`;
- console ends with `[selfhost-acceptance] success`.

If it fails, inspect:
- compose logs (`api`, `worker`, `mcp`, `web`);
- `GET /v1/adoption/rejections/diagnostics`;
- `GET /v1/adoption/pipeline/visibility`.
