# Synapse OSS Publish Checklist (Walkthrough)

Last updated: 2026-04-05

Use this checklist when cutting a new public release.

## A) Pre-Flight (Local)

- [ ] Update package versions consistently (`synapseworkspace-sdk`, `@synapseworkspace/sdk`, `@synapseworkspace/schema`, `@synapseworkspace/openclaw-plugin`).
- [ ] Update `CHANGELOG.md`.
- [ ] Run CI checks locally:

```bash
cd /Users/maksimborisov/synapse
./scripts/ci_checks.sh
```

- [ ] Run release-candidate rehearsal:

```bash
./scripts/run_oss_rc_dress_rehearsal.sh --report-file artifacts/release/rc-dress-rehearsal.json
```

- [ ] Or run both with one command (recommended):

```bash
./scripts/run_contributor_guardrails.sh --profile release --report-file artifacts/release/rc-dress-rehearsal.json
```

Expected:
- report contains `"status": "ok"`;
- `python`, `node`, `docs` components are `"ok"`.

## B) Repository Readiness

### B0) Create GitHub Repository (if not created yet)

Recommended values in GitHub "Create repository" form:

- Owner: `synapseworkspace` (or your org name)
- Repository name: `synapse`
- Description: `Cognitive state layer for AI agents (observe -> synthesize -> curate -> execute via MCP).`
- Visibility: `Public` (for OSS launch)
- Initialize with README: `No` (push this repo content instead)
- Add .gitignore: `None` (already in repo)
- Choose license: `None` (already in repo as `LICENSE`)

After repo creation:

1. Set `origin` and push:

```bash
git remote add origin git@github.com:synapseworkspace/synapse.git
git push -u origin main
```

2. In repository Settings -> General:
- enable Discussions (optional but recommended for OSS support questions).

3. In repository Settings -> Branches:
- add protection for `main`:
  - Require pull request before merging;
  - Require approvals: `1+`;
  - Require status checks: `ci`, `compat-matrix`, `codeql`, `secret-scan`.

4. In repository Settings -> Security:
- enable dependency graph + Dependabot alerts;
- enable secret scanning (if available on your plan).

- [ ] GitHub Environment `pypi` is configured.
- [ ] GitHub Environment `npm` is configured.
- [ ] Trusted Publishing is configured in PyPI and npm for this repository.
- [ ] Repository variable `RELEASE_PUBLISH_ENABLED` is set to `true` (only after Trusted Publishing is verified).
- [ ] Tag protection / maintainer access rules are in place.

Reference:
- `/Users/maksimborisov/synapse/docs/release-workflow.md`

## C) Trigger Release

- [ ] Create tag:

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

- [ ] Wait for `.github/workflows/release-packages.yml` to finish.
- [ ] Confirm jobs are green:
  - `build`
  - `verify-artifact-install-matrix`
  - `publish-pypi` / `publish-npm`
  - `verify-registry`
  - `verify-install-matrix`
  - `release-evidence-pack`
  - `create-release-draft`

## D) Post-Release Verification

- [ ] Verify PyPI package resolves:

```bash
python3 -m pip index versions synapseworkspace-sdk
```

- [ ] Verify npm packages resolve:

```bash
npm view @synapseworkspace/sdk version
npm view @synapseworkspace/schema version
npm view @synapseworkspace/openclaw-plugin version
```

- [ ] Review auto-generated draft GitHub Release for tag `vX.Y.Z` (job `create-release-draft`).
- [ ] Publish/edit Release notes as needed and verify release evidence appendix is present.

## E) If Release Fails

- npm: publish patch (`X.Y.(Z+1)`), avoid unpublish for stable releases.
- PyPI: yank broken version and publish patch version.
- Document incident and mitigation in `CHANGELOG.md`.
