# `@synapseworkspace/openclaw-plugin`

Production-focused OpenClaw runtime bridge for Synapse.

It wires OpenClaw hooks and tools to Synapse so agent events become durable knowledge proposals.

## Install

```bash
npm install @synapseworkspace/openclaw-plugin @synapseworkspace/sdk
```

## Quick Start

```ts
import { Synapse } from "@synapseworkspace/sdk";
import { createSynapseOpenClawPlugin } from "@synapseworkspace/openclaw-plugin";

const synapse = new Synapse({
  apiUrl: "http://localhost:8080",
  projectId: "omega_demo"
});

const plugin = createSynapseOpenClawPlugin(synapse, {
  searchKnowledge: async (query, limit, filters) => {
    return [{ query, limit, filters, statement_text: "Gate requires key-card after 10:00" }];
  },
  provenanceSecret: process.env.SYNAPSE_OPENCLAW_PROVENANCE_SECRET,
  provenanceKeyId: "ops-key-2026-04"
});

plugin.attach(openclawRuntime, {
  toolPrefix: "synapse"
});
```

## Day-0 Bootstrap (with SDK preset helper)

Before attaching plugin hooks/tools, you can import runtime memory with preset helper:

```ts
import { Synapse, buildOpenClawBootstrapOptions } from "@synapseworkspace/sdk";

const bootstrap = buildOpenClawBootstrapOptions({
  preset: "hybrid", // runtime_memory | event_log | hybrid
  maxRecords: 2000
});

const records = bootstrap.provider?.(openclawRuntime) ?? [];
await synapse.backfillMemory(records, {
  sourceSystem: bootstrap.sourceSystem,
  createdBy: bootstrap.createdBy,
  chunkSize: bootstrap.chunkSize
});
```

## Registered Tools

- `synapse_search_wiki` (only when `searchKnowledge` callback is configured)
- `synapse_propose_to_wiki`
- `synapse_get_open_tasks` (when task API is available)
- `synapse_update_task_status` (when task API is available)

## Runtime Contract

The runtime object must provide:

- `on(eventName, handler)` or `register_hook(eventName, handler)`
- `register_tool(name, handler, description?)`

Default subscribed events:

- `tool:result`
- `message:received`
- `agent:completed`
- `session:reset`

## Signed Provenance

`synapse_propose_to_wiki` attaches provenance metadata to evidence and claim metadata:
- evidence field: `evidence[].provenance`
- claim metadata field: `metadata.synapse_provenance`

Recommended config:
- `SYNAPSE_OPENCLAW_PROVENANCE_SECRET` (or `SYNAPSE_PROVENANCE_SECRET`)
- `SYNAPSE_OPENCLAW_PROVENANCE_KEY_ID` (or `SYNAPSE_PROVENANCE_KEY_ID`)

If no secret is configured, plugin falls back to digest-only mode (`mode=digest_only`).

## Development

```bash
npm --prefix packages/synapse-openclaw-plugin install
npm --prefix packages/synapse-openclaw-plugin run test
```
