# Synapse Architecture Diagram Pack

Last updated: 2026-04-04

## 1) Core Loop (Observe -> Synthesize -> Curate -> Execute)

```mermaid
flowchart LR
    A["Agent Runtime (OpenClaw / LangGraph / LangChain / CrewAI)"] --> B["Observe (Synapse SDK)"]
    B --> C["Ingestion API + Event Store"]
    C --> D["Weaver / Knowledge Compiler"]
    D --> E["Draft Wiki Changes"]
    E --> F["Human Curation UI"]
    F --> G["Published Wiki Pages + Knowledge Snapshots"]
    G --> H["MCP Runtime Retrieval + Context Injection"]
    H --> A
```

## 2) Raw RAG vs Synapse L2

| Dimension | Raw RAG on static docs | Synapse L2 cognitive state layer |
| --- | --- | --- |
| Freshness | Depends on manual document updates | Continuously updated from agent observations + curation |
| Governance | Coarse, document-level | Statement/page-level approvals and rollback |
| Explainability | Weak source-to-answer traceability | Evidence-linked drafts, revisions, moderation timeline |
| Runtime fit | Keyword/embedding retrieval only | Intent-aware retrieval with policy/process constraints |
| Multi-agent sharing | Indirect and inconsistent | Shared published wiki knowledge across all connected agents |

## 3) Adoption Sequence

```mermaid
flowchart TD
    S1["observe_only"] --> S2["draft_only"]
    S2 --> S3["retrieve_only"]
    S3 --> S4["full_loop"]
    S2 --> G1["Human moderation baseline"]
    S3 --> G2["Retrieval quality validation"]
    S4 --> G3["Risk-tier auto-publish + rollback"]
```

## 4) Governance Overlay

```mermaid
flowchart LR
    R["Routing Policy (Gatekeeper)"] --> P["Draft Queue"]
    P --> M["Moderation (Approve/Edit/Reject)"]
    M --> W["Wiki Publish"]
    W --> X["MCP Retrieval"]
    X --> F["Runtime Feedback"]
    F --> R
```
