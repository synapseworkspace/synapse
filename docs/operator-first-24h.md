# Operator Playbook: First 24 Hours After Synapse Adoption

Use this checklist after connecting an existing memory source.

## Hour 0-1: Connect and Validate

1. Open `/wiki` and run **Connect Existing Agent Memory** wizard.
2. Confirm connector validation has no `errors`.
3. Run bootstrap preview (`Preview recommended`).
4. Verify draft sample quality (policy/process signals, not event stream payloads).

## Hour 1-4: Tune for Signal Quality

1. Check pipeline: `GET /v1/adoption/pipeline/visibility`.
2. Check reject diagnostics: `GET /v1/adoption/rejections/diagnostics`.
3. Run quick calibration preview:
   - `GET /v1/adoption/policy-calibration/quick-loop`
   - `POST /v1/adoption/policy-calibration/quick-loop/apply` with `dry_run=true`.
4. Apply preset only if changed keys align with your expectations.

## Hour 4-12: First Publish Loop

1. Apply trusted batch from Drafts migration mode.
2. Publish first process/policy pages.
3. Confirm retrieval path:
   - open `/wiki` page
   - run MCP retrieval explain for relevant queries.

## Hour 12-24: KPI Baseline and Guardrails

Track onboarding KPI:

- `time_to_first_draft`
- `time_to_first_publish`
- `draft_noise_ratio`
- `publish_revert_rate`

API: `GET /v1/adoption/kpi?project_id=<id>&days=30`

If alerts appear:

1. Re-run curated explain (`/v1/backfill/curated-explain`) on representative samples.
2. Tighten noise preset or source filters.
3. Re-run policy quick loop.

## Exit Criteria

- At least one high-signal page published.
- `draft_noise_ratio` trending down after policy tuning.
- New agents can answer with wiki-backed context without prompt redeploy.
