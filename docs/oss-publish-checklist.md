# Synapse OSS Publish Checklist (Walkthrough)

Last updated: 2026-04-02

Use this checklist when cutting a new public release.

## A) Pre-Flight (Local)

- [ ] Update package versions consistently (`synapse-sdk`, `@synapse/sdk`, `@synapse/schema`, `@synapse/openclaw-plugin`).
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

- Owner: `maksbdev`
- Repository name: `synapse`
- Description: `Cognitive state layer for AI agents (observe -> synthesize -> curate -> execute via MCP).`
- Visibility: `Public` (for OSS launch)
- Initialize with README: `No` (push this repo content instead)
- Add .gitignore: `None` (already in repo)
- Choose license: `None` (already in repo as `LICENSE`)

After repo creation:

1. Set `origin` and push:

```bash
git remote add origin git@github.com:maksbdev/synapse.git
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

## D) Post-Release Verification

- [ ] Verify PyPI package resolves:

```bash
python3 -m pip index versions synapse-sdk
```

- [ ] Verify npm packages resolve:

```bash
npm view @synapse/sdk version
npm view @synapse/schema version
npm view @synapse/openclaw-plugin version
```

- [ ] Publish GitHub Release notes referencing `CHANGELOG.md`.

## E) If Release Fails

- npm: publish patch (`X.Y.(Z+1)`), avoid unpublish for stable releases.
- PyPI: yank broken version and publish patch version.
- Document incident and mitigation in `CHANGELOG.md`.
