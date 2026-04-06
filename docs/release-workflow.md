# Synapse OSS Release Workflow

Last updated: 2026-04-05

This runbook defines how Synapse OSS packages are released to PyPI and npm.

Practical step-by-step checklist:
- `/Users/maksimborisov/synapse/docs/oss-publish-checklist.md`

## Published Packages

- PyPI: `synapseworkspace-sdk`
- npm: `@synapseworkspace/sdk`
- npm: `@synapseworkspace/schema`
- npm: `@synapseworkspace/openclaw-plugin`

All packages must share the same version (enforced by `scripts/check_release_versions.py`).

## Registry Verification

Do not rely on static status text in docs. Verify package availability from registries:

```bash
python3 scripts/check_registry_package_availability.py --require-available
```

Check a specific release version across all packages:

```bash
python3 scripts/check_registry_package_availability.py --require-available --expected-version 0.1.2
```

Generate release evidence bundle from workflow artifacts (local/manual):

```bash
python3 scripts/generate_release_evidence_bundle.py \
  --version 0.1.2 \
  --registry-report artifacts/release/registry-availability.json \
  --workflow-run-url "https://github.com/synapseworkspace/synapse/actions/runs/<run_id>" \
  --output-md artifacts/release/release-evidence.md \
  --output-json artifacts/release/release-evidence.json
```

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
5. Verify clean-room install/import matrix from local release artifacts (`verify-artifact-install-matrix`, Linux + macOS).
6. Generate provenance attestations for build artifacts.
7. Publish:
   - PyPI via trusted publishing (`pypa/gh-action-pypi-publish`)
   - npm with provenance (`npm publish --provenance`)
8. Verify public registry propagation:
   - run `scripts/check_registry_package_availability.py` with retries and expected version;
   - upload verification report as CI artifact.
9. Verify clean-room install/import matrix from registries:
   - run Linux + macOS checks for `pip install synapseworkspace-sdk==<version>`;
   - run Linux + macOS checks for npm scoped packages (`@synapseworkspace/sdk`, `@synapseworkspace/schema`, `@synapseworkspace/openclaw-plugin`) at the same version.
10. Generate release evidence bundle (`release-evidence.md` + `release-evidence.json`) from workflow outputs.
11. Create/update draft GitHub Release for the tag with combined body:
   - optional product notes from `docs/releases/vX.Y.Z.md` (if file exists);
   - release evidence bundle appendix from workflow artifacts.

Publishing guard:
- release workflow publishes only when repository variable `RELEASE_PUBLISH_ENABLED=true`.
- when disabled (default), workflow still builds and uploads release artifacts, but skips publish jobs.

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
7. Enable repository variable `RELEASE_PUBLISH_ENABLED=true` only after Trusted Publishing is confirmed for both PyPI and npm.

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
5. Validate draft GitHub Release body for tag `vX.Y.Z`:
   - includes `docs/releases/vX.Y.Z.md` when present;
   - includes release evidence appendix.
6. Publish or edit draft Release notes as needed.

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
