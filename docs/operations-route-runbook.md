# Operations Route Runbook (`/operations`)

Last updated: 2026-04-05

This runbook explains when to use the dedicated operations route and how to return to wiki-first mode.

## Why `/operations` exists

Synapse now separates two different workflows:

1. `Wiki` route (`/wiki`) for page-first work:
   - read and edit wiki pages;
   - review drafts as inbox + detail;
   - run day-to-day knowledge curation.
2. `Operations` route (`/operations`) for heavy adoption workflows:
   - migration mode;
   - bootstrap trusted-batch approvals;
   - advanced gatekeeper tuning surfaces.

The goal is to keep the main wiki UX clean while preserving powerful tooling for rollout phases.

## When to use `/operations`

Use `/operations` only when you are doing one of these:

1. Initial legacy-memory migration.
2. Trusted-source batch bootstrap approvals.
3. Gatekeeper/migration diagnostics during onboarding.

If none of the above is true, stay in `/wiki`.

## Entry points

1. From Draft Inbox in `/wiki`:
   - click `Open operations`.
2. Direct URL:
   - `/operations?project=<project_id>&core_tab=drafts`.

## Safe operating sequence

1. Verify workspace scope (`project` and `wiki_space`).
2. Run preview first for any batch apply action.
3. Confirm sample quality (no event-stream noise).
4. Apply trusted batch.
5. Return to `/wiki` via `Back to Drafts`.

## Utility Gate v2.1 controls

Use these controls in operations mode when backfill quality needs tuning:

1. `LLM classifier mode`:
   - `off`: deterministic heuristics only;
   - `assist`: keeps heuristics, records reason-codes for observability;
   - `enforce`: allows LLM override for ambiguous backfill records.
2. `Min confidence`:
   - recommended starting point: `0.78`;
   - increase to reduce false positives.
3. `Classify ambiguous only`:
   - keep enabled for safer rollouts;
   - disable only during supervised migration waves.
4. `Model override`:
   - optional project-level override for backfill classifier model.

Draft detail now surfaces normalized `Gatekeeper Signal` reason-codes (for example, `override_skip_event`, `below_confidence_threshold`, `routing_policy_hard_block`) without exposing raw payload internals.

## Exit criteria before returning to `/wiki`

1. No active migration batch is running.
2. Queue conflicts are understood or resolved.
3. Publish mode is back to your intended default (`human_required` or policy-defined mode).

## Troubleshooting

1. You still see migration blocks in `/wiki`:
   - check URL path is `/wiki`, not `/operations`.
2. Route changed but context lost:
   - confirm `project` query param is present.
3. Unexpected draft volume after migration:
   - tighten source filters and rerun from `/operations` with preview-first policy.
