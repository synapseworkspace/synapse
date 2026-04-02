# Synapse OSS Release Workflow

Last updated: 2026-04-02

This runbook defines how Synapse OSS packages are released to PyPI and npm.

Practical step-by-step checklist:
- `/Users/maksimborisov/synapse/docs/oss-publish-checklist.md`

## Published Packages

- PyPI: `synapse-sdk`
- npm: `@synapse/sdk`
- npm: `@synapse/schema`
- npm: `@synapse/openclaw-plugin`

All packages must share the same version (enforced by `scripts/check_release_versions.py`).

## CI/CD Workflow

Workflow file: `.github/workflows/release-packages.yml`

Triggers:
- `push` tag: `v*` (recommended production release path)
- `workflow_dispatch` (manual run)

Pipeline stages:
1. Validate package version alignment.
2. Validate publish hygiene (package metadata + release docs consistency).
3. Validate tag version matches package version (for tag-triggered runs).
4. Build artifacts:
   - Python wheel/sdist via `python -m build`
   - npm tarballs via `npm pack`
5. Generate provenance attestations for build artifacts.
6. Publish:
   - PyPI via trusted publishing (`pypa/gh-action-pypi-publish`)
   - npm with provenance (`npm publish --provenance`)

## Repository Setup Checklist

1. Configure GitHub Environments:
   - `pypi`
   - `npm`
2. PyPI:
   - Configure Trusted Publisher for this repository/workflow.
3. npm:
   - Configure Trusted Publisher for this repository/workflow.
   - Optional fallback: set `NPM_TOKEN` environment secret.
4. Protect tag creation rights for release maintainers.
5. Configure branch protection for default branch:
   - require PR reviews;
   - require status checks (`ci`, `compat-matrix`, `codeql`, `secret-scan`);
   - enforce up-to-date branches before merge.
6. Ensure CODEOWNERS mapping is valid for your org/team handles (`.github/CODEOWNERS`).

## Release Procedure

1. Update changelog and verify version bump across packages.
2. Run local checks:
   - `./scripts/run_contributor_guardrails.sh --profile release --report-file artifacts/release/rc-dress-rehearsal.json`
   - or run equivalent raw commands:
     - `./scripts/ci_checks.sh`
     - `./scripts/run_oss_rc_dress_rehearsal.sh --report-file artifacts/release/rc-dress-rehearsal.json`
   - if your canonical repo URL differs, set before checks:
     - `export SYNAPSE_EXPECTED_REPO="https://github.com/<owner>/<repo>"`
     - `export SYNAPSE_EXPECTED_ISSUES="https://github.com/<owner>/<repo>/issues"`
3. Create and push a release tag:
   - `vX.Y.Z`
4. Confirm workflow `release-packages` succeeded.
5. Create GitHub Release notes referencing `CHANGELOG.md`.

## RC Dress Rehearsal

Use this script before cutting release tags:

```bash
./scripts/run_oss_rc_dress_rehearsal.sh --report-file artifacts/release/rc-dress-rehearsal.json
```

It runs:
1. release metadata checks (`check_release_versions`, `check_publish_hygiene`);
2. Python clean-room build + install/import check;
3. npm clean-room pack + install/import check (packs explicit package paths, not workspace root);
4. docs walkthrough existence checks.

## Rollback Guidance

- npm: publish a patch version (`X.Y.(Z+1)`) with fix; avoid unpublish for stable releases.
- PyPI: yank broken release and publish patched version.
- Update `CHANGELOG.md` with incident note and mitigation.
