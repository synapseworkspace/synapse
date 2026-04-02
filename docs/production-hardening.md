# Synapse Production Hardening Guide

Last updated: 2026-04-02

Use this checklist before public/critical production rollout.

## 1) Access Control and Auth

1. Put API/MCP behind identity-aware gateway or service mesh auth.
2. Restrict direct database access to trusted runtime identities only.
3. Enforce role boundaries for moderation/rollback/secret operations.
4. Enable auditable actor metadata for all mutating API calls.

## 2) Secrets and Key Management

1. Store API keys/tokens in secret manager, not `.env` in persistent hosts.
2. Rotate integration secrets on fixed cadence.
3. Scope secret permissions by environment (`dev`, `staging`, `prod`).
4. Use masked output and never log full tokens.

## 3) Data Safety and Backups

1. Enable Postgres WAL/archive strategy and regular snapshot backups.
2. Test restore drills at least weekly (sample project + full metadata path).
3. Keep migration scripts versioned and immutable after release.
4. Define retention policy for raw events vs curated knowledge history.

## 4) Reliability and Capacity

1. Set worker concurrency and queue pause controls per project risk profile.
2. Configure ingestion retry/backoff and tune timeout budgets.
3. Track queue lag + draft backlog SLOs.
4. Establish degraded-mode policy (`buffer|drop|sync_flush`) per SDK deployment.
5. Run periodic advisor-based tuning (`scripts/run_performance_tuning_advisor.py`) and apply profile updates through controlled change windows.

## 5) Observability and Alerting

1. Run OTel collector and scrape stack from `infra/observability`.
2. Import dashboards + monitor packs:
   - `synapse-sdk-trace-quickpack.json`
   - `synapse-sdk-alert-monitors.json`
3. Keep Prometheus rule pack enabled:
   - `prometheus-rules-sdk-alerts.yaml`
4. Define on-call response owner for transport failures, queue growth, proposal drop alerts.

## 6) Change Management

1. Require review for:
   - schema changes,
   - moderation workflow changes,
   - retrieval ranking changes.
2. Run deterministic regression suites on each release candidate.
3. Use staged rollout (`staging -> canary -> full prod`) for runtime changes.
4. Keep rollback procedure and expected blast radius documented.

## 7) Incident Readiness

1. Create incident channels and escalation matrix.
2. Store runbooks for:
   - API outage,
   - worker backlog storm,
   - MCP retrieval failure,
   - moderation queue saturation.
3. Run monthly game-days with simulated queue/transport degradation.

## 8) Compliance and Governance Baseline

1. Maintain immutable audit trail for moderation and rollback actions.
2. Track who changed knowledge and why (with evidence links).
3. Validate redaction requirements for sensitive user/company data.
4. Periodically review stale/expired knowledge windows and archival policy.
