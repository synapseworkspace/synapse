# Company Knowledge Roadmap

Last updated: 2026-05-04
Owner: Core team

## Goal

Move Synapse from:

- runtime/system wiki
- tooling/source/process observability
- agent-facing operational memory

to:

- company-facing knowledge wiki
- distilled business memory
- canonical human-readable operational knowledge

## Product Thesis

Synapse already has a strong first layer:

- agent/runtime description
- tooling map
- data-source landscape
- process playbooks
- diagnostics and observability

The next layer is different in kind:

- business entities
- process canon
- trust rules
- exceptions and heuristics
- company glossary

The goal is not “more pages.”
The goal is:

`raw memory -> distilled knowledge -> canonical company wiki`

## Current Gap

Today Synapse is better at answering:

- “How is the agent/runtime configured?”

than:

- “How does this company actually operate?”

Missing pieces:

1. business ontology
2. entity/process-centric page model
3. trust / source-of-truth modeling
4. exception / heuristic synthesis
5. memory-to-canon compiler
6. humanized business language layer

## Canonical Page Classes

The company knowledge layer should treat these as first-class page families:

1. `Entity`
2. `Process`
3. `Policy`
4. `Source of Truth`
5. `Glossary Term`
6. `Known Exception`
7. `Escalation Rule`

These are now modeled in `services/api/app/synthesis_packs.py` as the canonical page-class contract for company knowledge generation.

## Phase 1: Company Knowledge Foundation

Status: `in_progress`

Deliverables:

1. canonical page-class catalog
2. company knowledge pack abstraction in synthesis packs
3. logistics company-knowledge seed pages
4. generic company-knowledge seed pages
5. starter-profile integration for `logistics_ops` and `ai_employee_org`

Definition of done:

- company-facing page classes exist as code, not only docs
- logistics starter/bootstrap flows can generate a business-facing knowledge core
- synthesis tests cover the new page-family contract

## Phase 2: Business Ontology Extraction

Status: `planned`

Needed signals:

1. entity signals
   - entity type
   - display label
   - key identifiers
   - linked systems
   - operational states
2. process signals
   - owner
   - trigger
   - inputs
   - outputs
   - source of truth
   - success condition
   - common exceptions
3. trust signals
   - canonical vs derived
   - source priority
   - freshness windows
   - override rules
4. memory distillation signals
   - repeated facts
   - repeated operator decisions
   - recurring exception patterns
   - contradiction/resolution history

Definition of done:

- Synapse can infer first-class entities/processes from memory + runtime + KB signals
- system can group observations by business object, not only by tool/task/page

## Phase 3: Memory-to-Canon Compiler

Status: `planned`

Goal:

Compile candidate canon blocks from:

- comments
- knowledge-base fragments
- operator decisions
- recurring incidents
- source deltas
- repeated runtime patterns

Expected output:

1. canonical claims
2. grouped heuristics
3. source-of-truth summaries
4. resolved contradiction summaries
5. candidate business SOP sections

Definition of done:

- raw operational memory is no longer promoted directly into company wiki shape
- canon pages are synthesized from repeated, stable, confidence-backed patterns

## Phase 4: Humanization Layer

Status: `planned`

Goal:

Translate internal/system wording into company language.

Examples:

- `responsibilities` -> “за что отвечает агент”
- `source bindings` -> “какие данные используются”
- `approval mode` -> “когда нужно подтверждение”
- `standing order` -> “регулярная задача”

Definition of done:

- company pages read naturally to operators and managers
- evidence/debug language stays available, but no longer leaks into canonical page titles and summaries by default

## Phase 5: Knowledge Quality Lifecycle

Status: `planned`

Knowledge states:

1. `candidate`
2. `reviewed`
3. `canonical`
4. `stale`
5. `contradicted`
6. `superseded`

Goal:

Treat company knowledge as something that matures over time, rather than as static generated markdown.

Definition of done:

- candidate/canonical/stale/contradicted states are queryable and visible in operations/governance flows
- company knowledge can be promoted, corrected, superseded, and retired deliberately

## First 10 Target Pages for Logistics

These pages define the minimum viable business wiki for a logistics deployment:

1. `How the Logistics Operation Works`
2. `Logistics Glossary`
3. `Roles and Responsibility Zones`
4. `Documents and Shift Readiness`
5. `Daily Logistics Operating Cycle`
6. `Incidents and Escalations`
7. `Driver Economics and Reporting`
8. `ERP and Operational Systems`
9. `Trust Rules for Logistics Data`
10. `Known Pitfalls and Working Heuristics`

These are now seeded by the `logistics_ops` synthesis pack as company-knowledge starter pages.

## What Can Wait

Not everything is urgent in the same batch.

Can wait until after Phase 1 foundation:

1. perfect extraction accuracy
2. universal cross-domain ontology
3. UI-heavy canon editors
4. rich conflict-resolution authoring flows
5. domain-specific pack variants beyond logistics/generic

## Success Metric

Synapse should gradually move from:

- “wiki about the agent”

to:

- “wiki about the company the agent works inside”

The key indicator is when a new operator can answer:

1. how the business works
2. what the main entities and workflows are
3. which systems are trustworthy for which decisions
4. what the known exceptions and heuristics are

without needing to decode runtime-only or tool-centric language.
