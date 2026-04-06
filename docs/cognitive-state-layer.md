# Synapse as Cognitive State Layer (L2)

Synapse is not only a wiki UI.  
It is a **Cognitive State Layer** for agent systems:

- captures what agents learn in operations;
- filters noise and preserves reusable knowledge;
- governs publication and rollback;
- serves trusted context back into runtime via MCP/SDK.

## Memory Layering Model

1. **L0: Model Layer**
   - base model behavior (weights + system prompt).
2. **L1: Session Layer**
   - ephemeral task context and short-term runtime memory.
3. **L2: Synapse Layer**
   - durable, curated, cross-agent cognitive state.

L2 is where policy, process knowledge, exceptions, and validated operational facts live.

## Why L2 Matters

Without L2:
- insights die with sessions;
- raw memory streams pollute retrieval;
- teams cannot safely correct behavior without prompt/code churn.

With L2 (Synapse):
- one agent learns, all agents inherit;
- process playbooks become executable context;
- human moderation and rollback keep autonomy safe.

## Agentic Wiki Relationship

Agentic Wiki is the human-facing interface to L2:
- operators review and refine drafts;
- experts edit process pages and policies;
- governance controls define auto vs human-required publish.

The runtime value remains L2-first: better context quality, lower drift, faster onboarding.
