# Synapse Core Product Scope

This document defines what is considered core for Synapse adoption and what belongs to advanced operations.

## Core Loop (Default Experience)

The default product path should let a new team complete this loop in minutes:

1. Connect SDK to an existing agent runtime.
2. Observe facts/events from real execution.
3. Generate draft knowledge updates.
4. Let a human approve/reject in the wiki UI.
5. Retrieve approved knowledge via MCP in the next agent run.

Core must be usable without tuning dozens of controls.

## Core Surface (UI)

In `Core Mode` (default), the web app should prioritize:

1. Workspace connection (`API URL`, `Project ID`, `Reviewer`).
2. Draft Inbox + Draft Detail moderation.
3. Task Tracker (create, status transitions, comments, links).
4. Clear indication that advanced analytics are hidden by default.

## Advanced Surface (Opt-In)

The following belong to `Advanced Mode`:

- calibration and rollback governance
- queue throughput and incident controls
- cross-project operational analytics
- scheduler/fleet orchestration controls

These are powerful but not required for first-value onboarding.

## Core Acceptance Criteria

Core is considered healthy when:

1. SDK can emit events without breaking agent execution on transport failures.
2. Drafts appear from observed activity and are actionable in moderation UI.
3. Approved knowledge is retrievable through MCP tools.
4. Task Core supports auditable execution state and links to knowledge artifacts.
5. Local quickstart + CI checks are reproducible without manual patching.
6. Core loop is reproducible via a single acceptance script (`scripts/integration_core_loop.py`).

## Non-Goals for Core

- Full enterprise governance setup on first run.
- Mandatory manual tuning of calibration/incident systems.
- Requiring business operators to understand low-level control-plane knobs.
