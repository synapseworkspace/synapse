# Synapse x OpenClaw Integration

This document defines how Synapse layers on top of OpenClaw as a persistent, human-curated memory plane.

Start here for first implementation:
- `/Users/maksimborisov/synapse/docs/openclaw-quickstart-5-min.md`

This page is the technical deep dive and contract reference.

## Why This Fit Works

OpenClaw already has plugin and hook primitives (`registerTool`, lifecycle hooks, event-driven automation). Synapse can plug into those primitives as memory infrastructure.

Relevant OpenClaw docs:
- Plugin API (`registerTool`, `registerHook`): https://docs.openclaw.ai/tools/plugin
- Hooks and event context (`command`, `agent`, `message`, `gateway`): https://docs.openclaw.ai/automation/hooks

## Target Architecture

1. OpenClaw runtime emits events (tool results, message flow, agent lifecycle).
2. `OpenClawConnector` captures those events into Synapse (`ObservationEvent`).
3. Connector exposes two memory tools back to OpenClaw agents:
   - `synapse_search_wiki`
   - `synapse_propose_to_wiki`
   - `synapse_get_open_tasks`
   - `synapse_update_task_status`
4. Proposed facts flow through Synapse approval workflow.
5. Approved knowledge is retrieved at runtime (MCP/context injection path).

## What Is Implemented Now

In Python SDK:
- Generic monitor layer + convenience wrappers:
  - `client.monitor(...)`
  - `client.monitor_langgraph(...)`
  - `client.monitor_crewai(...)`
  - `client.monitor_openclaw(...)`
- OpenClaw connector:
  - `OpenClawConnector.attach(runtime, ...)`
  - `OpenClawConnector.register_tools(...)`
  - `OpenClawConnector.search_wiki(...)`
  - `OpenClawConnector.propose_to_wiki(...)`
  - `OpenClawConnector.get_open_tasks(...)`
  - `OpenClawConnector.set_task_status(...)`
  - Signed provenance injection on `propose_to_wiki`:
    - `evidence[].provenance`
    - `claim.metadata.synapse_provenance`
  - Attach-time historical memory bootstrap:
    - `Synapse.attach(..., bootstrap_memory=BootstrapMemoryOptions(...))`
    - `Synapse.attach(..., openclaw_bootstrap_preset="runtime_memory|event_log|hybrid")`
    - Default `Synapse.attach(..., integration="openclaw")` auto-applies `hybrid` preset unless disabled.
    - Provider or record-list ingestion into `/v1/backfill/memory` before live monitoring.
- MCP context helper:
  - `MCPContextHelper` for `search_knowledge` / `get_entity_facts` / `get_recent_changes` aggregation.
  - `make_openclaw_search_callback(...)` to plug MCP retrieval directly into `OpenClawConnector`.
  - Context-policy rollout profiles (`advisory`, `enforced`, `strict_enforced`) for one-flag OpenClaw context injection defaults.

Validated integration script:
- `/Users/maksimborisov/synapse/scripts/integration_openclaw_mcp_runtime.py`
- Runs a real stdio MCP client session (`ClientSession`) against a live FastMCP server process and verifies OpenClaw tool wiring + context injection end-to-end.

Runtime contract matrix script:
- `/Users/maksimborisov/synapse/scripts/integration_openclaw_runtime_contract.py`
- Verifies connector compatibility against multiple OpenClaw runtime API profiles:
  - `on(...)` + positional `register_tool(...)`
  - `register_hook(...)` + keyword-style `register_tool(...)`
  - signed provenance fields are emitted and consistent across evidence + claim metadata

OpenClaw-first onboarding kit:
- Canonical quickstart: `/Users/maksimborisov/synapse/docs/openclaw-quickstart-5-min.md`
- `/Users/maksimborisov/synapse/demos/openclaw_onboarding/README.md`
- Includes runtime template, seed memory dataset, and 5-minute runnable flow for day-0 wiki bootstrap.
- Guided tutorial: `/Users/maksimborisov/synapse/docs/tutorials/04-openclaw-onboarding-kit.md`

In TypeScript OSS packages:
- SDK first-class attach path (parity with Python):
  - `Synapse.attach(openclawRuntime, { integration: "openclaw" })`
  - auto hook registration (`tool:result`, `message:received`, `agent:completed`, `session:reset`)
  - runtime tools wired by default:
    - `synapse_search_wiki`
    - `synapse_propose_to_wiki`
    - `synapse_get_open_tasks`
    - `synapse_update_task_status`
  - optional overrides:
    - `openclawSearchKnowledge`
    - `openclawHookEvents`
    - `openclawRegisterTools`
    - `openclawToolPrefix`
  - signed provenance injection on `propose_to_wiki` (HMAC-SHA256 when secret configured, digest-only fallback).
- Official plugin package (optional advanced embedding):
  - `@synapse/openclaw-plugin`
  - `createSynapseOpenClawPlugin(...)`
  - `SynapseOpenClawPlugin.attach(...)`
  - Signed provenance injection (HMAC-SHA256 when secret configured, digest-only fallback).
  - runtime fixture tests: `/Users/maksimborisov/synapse/packages/synapse-openclaw-plugin/tests/runtime-fixture.test.mjs`
- SDK OpenClaw bootstrap helpers:
  - `buildOpenClawBootstrapOptions(...)`
  - `listOpenClawBootstrapPresets()`
  - `collectOpenClawBootstrapRecords(...)`
  - `Synapse.attach(..., { integration: "openclaw", openclawBootstrapPreset: "runtime_memory|event_log|hybrid" })`

## OpenClaw Runtime Contract (Current)

The connector expects runtime object to provide:
- hook registration via `on(event_name, handler)` or `register_hook(event_name, handler)`
- tool registration via `register_tool(name, handler, description?)`

This keeps integration transport-agnostic and allows compatibility with plugin-managed or embedded runtimes.

## Next Hardening Steps

1. Add event mapping profiles (`tool:result`, `message:*`, `agent:*`) with per-event schema normalization.
2. Add bidirectional retrieval policy: task-context lookup first, then entity-level fallback.
3. Add key-rotation aware provenance verification store (multiple active key ids).
