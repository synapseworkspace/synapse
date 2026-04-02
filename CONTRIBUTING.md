# Contributing to Synapse

Thanks for contributing to Synapse. This repository is built around a core loop:
observe -> synthesize -> curate -> execute.

## Before You Start

1. Read [README.md](README.md) for local bootstrap.
2. Check active priorities in [ROADMAP.md](ROADMAP.md).
3. Prefer small, focused pull requests.
4. Review ownership and governance:
   - [MAINTAINERS.md](MAINTAINERS.md)
   - [SUPPORT.md](SUPPORT.md)
   - [DEPRECATION_POLICY.md](DEPRECATION_POLICY.md)

## Development Setup

1. Start local infrastructure:

```bash
cp .env.example .env
cd infra && docker compose up -d
cd ..
./scripts/apply_migrations.sh
```

2. Run API:

```bash
cd services/api
python -m venv .venv && source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --port 8080
```

3. Run web UI:

```bash
cd apps/web
npm install
npm run dev
```

## Required Checks

New contributor baseline (recommended first run):

```bash
./scripts/run_contributor_guardrails.sh --profile quick
```

Before opening/updating a PR, run full validation:

```bash
./scripts/run_contributor_guardrails.sh --profile full
```

Equivalent direct command (if you need raw CI script):

```bash
./scripts/ci_checks.sh
```

This includes:
- schema validation
- Python compile checks
- TypeScript build
- Playwright browser e2e
- SDK/OpenClaw/MCP offline smoke tests
- deterministic regression evaluators

## Code Guidelines

- Keep behavior deterministic where possible (especially synthesis, ranking, and evaluator code paths).
- Preserve idempotency for mutating API endpoints.
- Add or update tests for every behavior change.
- Keep docs and roadmap current when scope/status changes.

## Pull Request Expectations

A good PR should include:

1. Problem statement and user impact.
2. What changed and why.
3. Validation output (tests/scripts run).
4. Any migration/env var/compatibility implications.

If you touch product scope, also update:
- [ROADMAP.md](ROADMAP.md)
- relevant docs in `docs/`

## Versioning and Releases

- Synapse follows Semantic Versioning.
- Until `1.0.0`, minor releases (`0.x`) may include breaking changes when documented in `CHANGELOG.md`.
- Every merge with user-visible behavior change should add an `Unreleased` entry in `CHANGELOG.md`.
- Release tags should cut from a green `./scripts/ci_checks.sh` run.

## Need Help?

Open a GitHub issue with:
- reproduction steps
- expected vs actual behavior
- logs/screenshots if UI-related
