# Contributor Quickstart (Single-Command Guardrails)

Last updated: 2026-04-02

This path is optimized for new contributors who want one command that validates local readiness and runs the right checks.

## Recommended First Command

```bash
cd /Users/maksimborisov/synapse
./scripts/run_contributor_guardrails.sh --profile quick
```

What `quick` does:
- checks required local tools (`python3`, `node`, `npm`, `jq`, `bash`);
- runs `./scripts/ci_checks.sh` with browser e2e skipped (`SYNAPSE_SKIP_WEB_E2E=1`);
- prints concise pass/fail status with the next docs shortcut.

## Profiles

1. `quick` (default)
- fastest newcomer baseline;
- ideal before first PR iteration.

2. `full`
- runs full CI checks including Playwright browser e2e;
- use before opening/updating PR when you changed web flows.

3. `release`
- runs `quick` checks;
- runs OSS RC dress rehearsal (`run_oss_rc_dress_rehearsal.sh`) and writes report.

## Common Commands

Run full contributor checks:

```bash
./scripts/run_contributor_guardrails.sh --profile full
```

Run release-prep checks with report:

```bash
./scripts/run_contributor_guardrails.sh --profile release --report-file artifacts/release/rc-dress-rehearsal.json
```

Include self-hosted acceptance toggles:

```bash
./scripts/run_contributor_guardrails.sh --profile quick --selfhost-core
./scripts/run_contributor_guardrails.sh --profile quick --selfhost-dr
```

## Related Docs

- `/Users/maksimborisov/synapse/CONTRIBUTING.md`
- `/Users/maksimborisov/synapse/docs/getting-started.md`
- `/Users/maksimborisov/synapse/docs/release-workflow.md`
- `/Users/maksimborisov/synapse/docs/oss-publish-checklist.md`
