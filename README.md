<p align="center">
  <img src="assets/synapse-logo.svg" alt="Synapse logo" width="680" />
</p>

<p align="center">
  <strong>Synapse is the workspace and cognitive state layer for AI agents.</strong><br/>
  Turn agent runtime signals into a human-curated wiki and feed it back via MCP.
</p>

<p align="center">
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-Apache%202.0-1f6feb"></a>
  <a href="docs/compatibility-matrix.md"><img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-3776AB"></a>
  <a href="docs/compatibility-matrix.md"><img alt="Node" src="https://img.shields.io/badge/node-18%2B-339933"></a>
  <a href="services/mcp/README.md"><img alt="MCP Native" src="https://img.shields.io/badge/MCP-native-0f766e"></a>
</p>

<p align="center">
  <img src="assets/synapse-hero.svg" alt="Synapse core loop: Observe, Synthesize, Curate, Execute" width="980" />
</p>

## What Is Synapse?

Most agent stacks lose operational learning between sessions. Synapse solves that by creating a continuous knowledge loop:

1. Observe runtime signals from agents and tools.
2. Synthesize raw evidence into draft knowledge.
3. Curate drafts in a wiki-like human review UI.
4. Execute with MCP so every agent uses approved, current knowledge.

In short: Synapse turns token spend into reusable company knowledge.

## Why Teams Use It

- Persistent memory across sessions and across agents.
- Human-in-the-loop governance instead of hidden prompt drift.
- Conflict-aware wiki updates instead of static RAG documents.
- MCP-native retrieval for runtime context injection.
- Day-0 onboarding from existing memory and legacy docs (cold start).

## Quickstart

### Fastest proof (recommended)

Run one command to validate the full core loop (`ingest -> draft -> approve -> MCP retrieval`):

```bash
./scripts/run_selfhost_core_acceptance.sh
```

### CLI onboarding (from this repo)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e packages/synapse-sdk-py
synapse-cli quickstart --dir . --project-id omega_demo --api-url http://localhost:8080 --doctor-strict --verify-core-loop
```

### Local web workspace

```bash
cp .env.selfhost.example .env.selfhost
docker compose --env-file .env.selfhost -f infra/docker-compose.selfhost.yml up -d --build
cd apps/web && npm install && npm run dev
```

Open `http://localhost:5173`.

## SDK Integration (2 Minutes)

### Python

```python
from synapse_sdk import Synapse, SynapseConfig

synapse = Synapse(
    SynapseConfig(
        api_url="http://localhost:8080",
        project_id="water_delivery_logistics",
    )
)

agent = synapse.attach(
    my_openclaw_runtime,
    integration="openclaw",
    openclaw_bootstrap_preset="hybrid",
    openclaw_bootstrap_max_records=2000,
)
```

### TypeScript

```ts
import { Synapse } from "@synapse/sdk";

const synapse = new Synapse({
  apiUrl: "http://localhost:8080",
  projectId: "water_delivery_logistics"
});

const runtime = synapse.attach(openclawRuntime, {
  integration: "openclaw",
  openclawBootstrapPreset: "hybrid",
  openclawBootstrapMaxRecords: 2000
});
```

## Core Product Surface

Synapse core is focused on the essential workflow:

- **SDK + Observer**: capture runtime events, claims, and provenance.
- **Weaver (Synthesizer)**: convert noisy logs into structured draft knowledge.
- **Wiki UI**: review, approve, edit, and trace knowledge lineage.
- **Knowledge API (MCP)**: serve approved facts to all connected agents.
- **Agentic Task Tracker**: task timeline linked to drafts, conflicts, and evidence.
- **Legacy Import**: bootstrap from local docs and Notion sources.

## OpenClaw-First Experience

- Install plugin package: `npm install @synapse/openclaw-plugin`
- OpenClaw integration overview: [docs/openclaw-integration.md](docs/openclaw-integration.md)
- OpenClaw plugin package: [packages/synapse-openclaw-plugin/README.md](packages/synapse-openclaw-plugin/README.md)
- Provenance verification: [docs/openclaw-provenance-verification.md](docs/openclaw-provenance-verification.md)
- Onboarding demo kit: [demos/openclaw_onboarding/README.md](demos/openclaw_onboarding/README.md)

## Architecture and Components

- API service: [services/api/README.md](services/api/README.md)
- Worker service: [services/worker/README.md](services/worker/README.md)
- MCP runtime: [services/mcp/README.md](services/mcp/README.md)
- Web app: [apps/web/README.md](apps/web/README.md)
- Schema package: [packages/synapse-schema/README.md](packages/synapse-schema/README.md)
- Python SDK: [packages/synapse-sdk-py/README.md](packages/synapse-sdk-py/README.md)
- TypeScript SDK: [packages/synapse-sdk-ts/README.md](packages/synapse-sdk-ts/README.md)

## Documentation

- First 15 minutes: [docs/getting-started.md](docs/getting-started.md)
- Core product scope: [docs/core-product-scope.md](docs/core-product-scope.md)
- Wiki engine logic: [docs/wiki-engine-design.md](docs/wiki-engine-design.md)
- MCP runtime and retrieval model: [docs/mcp-runtime.md](docs/mcp-runtime.md)
- Legacy import and sync: [docs/legacy-import.md](docs/legacy-import.md), [docs/legacy-sync-orchestration.md](docs/legacy-sync-orchestration.md)
- Agent simulator sandbox: [docs/agent-simulator.md](docs/agent-simulator.md)
- Tutorials: [docs/tutorials/README.md](docs/tutorials/README.md)
- SDK API reference: [docs/reference/README.md](docs/reference/README.md)

## Demos

- Omega end-to-end scenario: [demos/omega_gate/README.md](demos/omega_gate/README.md)
- Cookbook examples: [demos/cookbook/README.md](demos/cookbook/README.md)
- OpenClaw onboarding kit: [demos/openclaw_onboarding/README.md](demos/openclaw_onboarding/README.md)

## OSS and Release

- Contributing: [CONTRIBUTING.md](CONTRIBUTING.md)
- Release workflow: [docs/release-workflow.md](docs/release-workflow.md)
- OSS publish checklist: [docs/oss-publish-checklist.md](docs/oss-publish-checklist.md)
- OSS readiness checklist: [docs/oss-readiness.md](docs/oss-readiness.md)
- Security policy: [SECURITY.md](SECURITY.md)
- License: [LICENSE](LICENSE)
