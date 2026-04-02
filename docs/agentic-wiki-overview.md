# Synapse Agentic Wiki Overview

Last updated: 2026-04-02

## One-Line Definition

Synapse is an open-source Agentic Wiki layer that turns runtime agent experience into a human-curated, MCP-readable source of truth.

## Problem

Most companies hit the same three issues when moving agents to production:

1. Session memory loss:
   useful discoveries disappear after each run.
2. Static knowledge drift:
   agents rely on stale docs while operations change in real time.
3. Black-box behavior:
   teams cannot safely inspect and correct learned behavior without code/prompts redeploy.

## Solution

Synapse inserts a knowledge loop between agent execution and company operations:

1. Observe:
   SDK captures facts from tool outputs, messages, and runtime events.
2. Synthesize:
   worker turns noisy signals into draft wiki updates.
3. Curate:
   operators approve/edit/reject drafts in workspace UI.
4. Execute:
   approved knowledge is served to agents through MCP tools.

This creates a practical single source of truth for agent behavior.

## Why This Matters

- Every approved insight becomes reusable across agents.
- Human review is built-in, not bolted on.
- Knowledge updates affect behavior without prompt rewrite cycles.
- New agents can bootstrap from existing memory on day 0.

## OpenClaw-First Fit

Synapse is designed to layer cleanly on OpenClaw:

- runtime hooks are observed without rewriting business logic;
- OpenClaw tools are auto-registered (`search_wiki`, `propose_to_wiki`, task helpers);
- historical runtime memory can be backfilled during attach.

See:
- [OpenClaw 5-Minute Quickstart](openclaw-quickstart-5-min.md)
- [OpenClaw Integration Design](openclaw-integration.md)

## Current Implementation Status

Implemented in OSS core:

- Python/TypeScript SDK observers
- synthesis + draft pipeline
- moderation workspace (approve/edit/reject + conflict explain)
- MCP retrieval runtime
- OpenClaw plugin/connector
- day-0 bootstrap/backfill
- task tracker core

Partially implemented:

- hybrid retrieval (pgvector + graph hints/traversal), but not a standalone graph database product.

Not fully in OSS core yet:

- full enterprise tenancy/RBAC/SSO layer
- complete enterprise governance packaging

## Product Narrative (Canonical)

Use this narrative consistently in docs, demos, and onboarding:

1. Goldfish AI problem
2. Agentic Wiki loop
3. Human-curated source of truth
4. MCP execution to all connected agents
5. OpenClaw-first onboarding in minutes
