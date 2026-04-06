# Wiki UI Visual Gallery (CI Artifacts)

Last updated: 2026-04-05

Synapse CI captures deterministic UI snapshots for wiki-first routes:

1. `wiki-route-chromium.png`
2. `operations-route-chromium.png`

Source:
- GitHub Actions job: `web-visual-snapshots`
- Artifact name: `web-visual-snapshots`
- Capture spec: `/Users/maksimborisov/synapse/apps/web/e2e/wiki-visual.spec.ts`

## How to use

1. Open latest CI run in GitHub Actions.
2. Download artifact `web-visual-snapshots`.
3. Compare current UI with previous run snapshots to detect unintended visual shifts.

## What is validated

1. `/wiki?project=omega_demo` renders page-first shell.
2. `/operations?project=omega_demo&core_tab=drafts` renders migration tooling route.
3. Route split remains visible and stable for reviewers and operators.

## Notes

- This is screenshot capture for fast visual inspection, not pixel-locked cross-platform diffing.
- Functional regression coverage stays in Playwright flow tests (`intelligence-dashboard.spec.ts`).
