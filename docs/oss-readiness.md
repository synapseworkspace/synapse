# Synapse OSS Readiness Checklist

Last reviewed: 2026-04-02

## Summary

Current state: **ready for OSS preview+** (core + publishing hygiene + release automation + onboarding polish + governance baseline), with first public package publication still pending.

Core runtime, SDKs, and CI/e2e flows are operational. Remaining work is focused on deployment hardening and docs expansion.

## Readiness Matrix

## Core Product

- [x] SDK ingest path implemented (Python + TS).
- [x] Synthesis/draft workflow implemented.
- [x] Human curation UI implemented.
- [x] MCP runtime retrieval implemented.
- [x] Task core loop implemented.
- [x] Core-first UI mode added (`Core Mode` default, `Advanced Mode` opt-in).

## Engineering Quality

- [x] End-to-end browser tests (`apps/web` Playwright).
- [x] Deterministic synthesis regression checks.
- [x] Gatekeeper regression checks.
- [x] MCP retrieval regression checks.
- [x] Offline smoke checks for SDK/OpenClaw/MCP.
- [x] Unified CI script (`scripts/ci_checks.sh`) passes locally.

## Publishing Hygiene

- [x] `README.md` present.
- [x] `CONTRIBUTING.md` present.
- [x] `SECURITY.md` present.
- [x] `CODE_OF_CONDUCT.md` present.
- [x] Final OSS `LICENSE` decision and file.
- [x] Changelog/release notes convention (`CHANGELOG.md` + versioning policy).
- [x] GitHub issue/PR templates for contributor onboarding.
- [x] Maintainer/support/deprecation governance docs (`MAINTAINERS.md`, `SUPPORT.md`, `DEPRECATION_POLICY.md`).
- [x] CODEOWNERS baseline in repo (`.github/CODEOWNERS`).
- [x] Repo hygiene gate for tracked local artifacts (`scripts/check_repo_hygiene.py` + CI step).

## SDK Distribution

- [x] Confirm package names/versioning strategy for PyPI/NPM publication.
- [x] Add signed release workflow (tag -> build -> publish).
- [x] Add compatibility matrix (Python versions / Node versions / tested frameworks).
- [x] Add multi-version compatibility workflow (`.github/workflows/compat-matrix.yml`).
- [x] Add automated publish-hygiene validator (package metadata + docs consistency) in CI/release path.
- [x] Add generated SDK API reference baseline (`docs/reference/*`) with freshness check in CI.
- [ ] Complete first successful public publish to PyPI/npm and validate install commands from clean machines.

## Security Automation

- [x] CodeQL workflow baseline (`.github/workflows/codeql.yml`).
- [x] Secret scanning workflow baseline (`.github/workflows/secret-scan.yml` via Gitleaks).
- [x] Dependabot updates baseline (`.github/dependabot.yml`) for Actions/npm/pip manifests.

## Documentation Gaps Before Public Launch

High priority:

1. "First 15 minutes" tutorial for core loop. ✅ (`docs/getting-started.md`)
2. OpenClaw quick integration tutorial. ✅ (`docs/openclaw-quickstart-5-min.md`)
3. MCP retrieval integration tutorial. ✅ (`docs/tutorials/03-mcp-context-injection.md`)
4. "Core vs Advanced" product guide. ✅ (`docs/core-product-scope.md`)
5. Deployment guide for self-hosted API/worker/MCP. ✅ (`docs/self-hosted-deployment.md`)

Recommended:

1. Troubleshooting guide (DB, migrations, CORS, MCP transport). ✅ (`docs/troubleshooting.md`)
2. Production hardening guide (RBAC, secrets, observability). ✅ (`docs/production-hardening.md`, `docs/observability-incident-playbooks.md`)
3. Performance tuning notes (MCP graph knobs, queue limits). ✅ (`docs/performance-tuning.md`)
4. OSS publish walkthrough checklist. ✅ (`docs/oss-publish-checklist.md`)

## Proposed Pre-Release Sequence

1. Freeze core scope for OSS preview.
2. Finalize license + release versioning policy.
3. Publish contributor docs and templates.
4. Run CI on clean environment.
5. Cut `v0.x` preview release with focused core messaging.
