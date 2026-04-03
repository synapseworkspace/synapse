# synapse-api

FastAPI service for Synapse ingestion and claim proposal intake.

## Local run

```bash
cd services/api
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --port 8080
```

Environment:
- `DATABASE_URL` (default: `postgresql://synapse:synapse@localhost:55432/synapse`)
- `IDEMPOTENCY_TTL_SECONDS` (default: `86400`)
- `IDEMPOTENCY_IN_PROGRESS_WAIT_SECONDS` (default: `5.0`)
- `IDEMPOTENCY_CLEANUP_INTERVAL_SECONDS` (default: `60.0`)
- `IDEMPOTENCY_CLEANUP_BATCH_SIZE` (default: `1000`)
- `SYNAPSE_AUTH_MODE` (`open|oidc`, default: `open`)
- `SYNAPSE_RBAC_MODE` (`open|enforce`, default: `open`)
- `SYNAPSE_TENANCY_MODE` (`open|enforce`, default: `open`)
- `SYNAPSE_OIDC_ISSUER_URL` (required in `SYNAPSE_AUTH_MODE=oidc`)
- `SYNAPSE_OIDC_AUDIENCE` (optional audience validation)
- `SYNAPSE_OIDC_ROLES_CLAIM` (default: `roles`)
- `SYNAPSE_OIDC_TENANT_CLAIM` (default: `tenant_id`)
- `SYNAPSE_OIDC_EMAIL_CLAIM` (default: `email`)

## Endpoints

- `GET /health`
- `GET /v1/auth/mode`
- `POST /v1/auth/session`
- `GET /v1/auth/session`
- `DELETE /v1/auth/session`
- `POST /v1/tenants`
- `GET /v1/tenants`
- `GET /v1/tenants/{tenant_id}`
- `PUT /v1/tenants/{tenant_id}/memberships`
- `PUT /v1/tenants/{tenant_id}/projects`
- `POST /v1/events` (idempotent by `event.id`, plus request-level idempotency via `Idempotency-Key`)
- `GET /v1/events/throughput?project_id=...&window_hours=24&event_type=tool_result` (ingest latency + throughput SLO metrics)
- `POST /v1/facts/proposals` (request-level idempotency via `Idempotency-Key`)
- `POST /v1/backfill/memory` (bulk historical memory ingestion with `batch_id` and status transitions)
- `GET /v1/backfill/batches/{batch_id}?project_id=...`
- `GET /v1/wiki/pages/search?project_id=...&q=...`
- `GET /v1/mcp/retrieval/explain?project_id=...&q=...&limit=10&related_entity_key=...&context_policy_mode=enforced&min_retrieval_confidence=0.45` (MCP-compatible retrieval diagnostics with score/confidence breakdown, reason traces, and context-injection policy controls)
- `POST /v1/wiki/pages` (guided/manual page create with initial version + optional sections/statements from markdown)
- `GET /v1/wiki/pages/{slug}?project_id=...`
- `GET /v1/wiki/pages/{slug}/history?project_id=...&limit=20&include_markdown=true`
- `GET /v1/wiki/drafts?project_id=...&status=pending_review`
- `GET /v1/wiki/drafts/{draft_id}?project_id=...`
- `GET /v1/wiki/drafts/{draft_id}/conflicts/explain?project_id=...` (MCP `explain_conflicts` compatible enrichment for UI conflict resolver)
- `GET /v1/wiki/moderation/throughput?project_id=...&window_hours=24&top_reviewers=5` (core moderation throughput/backlog/latency analytics)
- `POST /v1/wiki/drafts/{draft_id}/approve`
- `POST /v1/wiki/drafts/{draft_id}/reject`
- `GET /v1/wiki/moderation/actions?project_id=...`
- `GET /v1/gatekeeper/decisions?project_id=...&tier=golden_candidate`
- `GET /v1/gatekeeper/config?project_id=...`
- `PUT /v1/gatekeeper/config`
- `GET /v1/gatekeeper/config/snapshots?project_id=...&source=calibration_cycle&limit=20`
- `POST /v1/gatekeeper/config/snapshots`
- `GET /v1/gatekeeper/calibration/trends?project_id=...&limit=24`
- `GET /v1/gatekeeper/calibration/schedules?project_id=...&enabled=true`
- `PUT /v1/gatekeeper/calibration/schedules`
- `DELETE /v1/gatekeeper/calibration/schedules/{schedule_id}?project_id=...`
- `POST /v1/gatekeeper/calibration/runs`
- `GET /v1/gatekeeper/calibration/runs?project_id=...`
- `GET /v1/gatekeeper/calibration/runs/trends?project_id=...&days=30`
- `GET /v1/gatekeeper/calibration/operations/throughput?project_id=...&window_hours=24`
- `GET /v1/gatekeeper/calibration/operations/throughput/compare?project_ids=a,b&limit=30`
- `GET /v1/gatekeeper/calibration/operations/throughput/owners?project_ids=a,b&window_hours=24&sla_hours=24`
- `GET /v1/gatekeeper/calibration/operations/governance/drift?project_ids=a,b&window_hours=24&audit_days=7`
- `GET /v1/gatekeeper/calibration/operations/incidents/slo_board?project_ids=a,b&incident_window_days=30&mttr_sla_hours=24&mtta_proxy_sla_minutes=15`
- `GET /v1/gatekeeper/calibration/operations/throughput/recommendations?project_ids=a,b&history_hours=72`
- `POST /v1/gatekeeper/calibration/operations/throughput/recommendations/apply`
- `GET /v1/gatekeeper/calibration/operations/ownership?project_ids=a,b`
- `PUT /v1/gatekeeper/calibration/operations/ownership`
- `GET /v1/gatekeeper/calibration/operations/incidents/hooks?project_ids=a,b`
- `PUT /v1/gatekeeper/calibration/operations/incidents/hooks`
- `GET /v1/gatekeeper/calibration/operations/incidents/policies?project_ids=a,b`
- `PUT /v1/gatekeeper/calibration/operations/incidents/policies`
- `POST /v1/gatekeeper/calibration/operations/incidents/policies/simulate`
- `GET /v1/gatekeeper/calibration/operations/incidents/preflight/presets?project_ids=a,b`
- `PUT /v1/gatekeeper/calibration/operations/incidents/preflight/presets`
- `POST /v1/gatekeeper/calibration/operations/incidents/preflight/run`
- `GET /v1/gatekeeper/calibration/operations/incidents?project_ids=a,b&status=open`
- `GET /v1/gatekeeper/calibration/operations/incidents/sync/schedules?project_ids=a,b&due_only=true&status=failed&project_contains=omega&name_contains=default&sort_by=next_run_at&sort_dir=asc&offset=0&limit=50`
- `PUT /v1/gatekeeper/calibration/operations/incidents/sync/schedules`
- `DELETE /v1/gatekeeper/calibration/operations/incidents/sync/schedules/{schedule_id}?project_id=...`
- `POST /v1/gatekeeper/calibration/operations/incidents/sync/schedules/run`
- `GET /v1/gatekeeper/calibration/operations/incidents/sync/schedules/{schedule_id}/timeline?project_id=...&days=30&limit=120`
- `POST /v1/gatekeeper/calibration/operations/incidents/sync`
- `PUT /v1/gatekeeper/calibration/operations/incidents/sync/enforcement`
- `GET /v1/gatekeeper/calibration/operations/throughput/compare/export?project_ids=a,b&format=csv`
- `POST /v1/gatekeeper/calibration/operations/throughput/compare/export/webhook`
- `GET /v1/gatekeeper/calibration/operations/throughput/audit?days=30&limit=120`
- `POST /v1/gatekeeper/calibration/operations/throughput/audit/{event_id}/acknowledge`
- `POST /v1/gatekeeper/calibration/operations/throughput/audit/{event_id}/resolve`
- `GET /v1/gatekeeper/alerts/targets?project_id=...`
- `PUT /v1/gatekeeper/alerts/targets`
- `DELETE /v1/gatekeeper/alerts/targets/{target_id}?project_id=...`
- `POST /v1/gatekeeper/alerts/attempts`
- `GET /v1/gatekeeper/alerts/attempts?project_id=...`
- `POST /v1/gatekeeper/config/rollback`
- `POST /v1/gatekeeper/config/rollback/preview`
- `POST /v1/gatekeeper/config/rollback/requests`
- `GET /v1/gatekeeper/config/rollback/requests?project_id=...&status=pending_approval`
- `POST /v1/gatekeeper/config/rollback/requests/{request_id}/approve`
- `POST /v1/gatekeeper/config/rollback/requests/{request_id}/reject`
- `GET /v1/intelligence/metrics/daily?project_id=...&from_date=YYYY-MM-DD&to_date=YYYY-MM-DD`
- `GET /v1/intelligence/trends/weekly?project_id=...&anchor_date=YYYY-MM-DD&weeks=8`
- `GET /v1/intelligence/queue/governance_digest?project_ids=a,b&window_hours=24`
- `GET /v1/intelligence/queue/incident_escalation_digest?project_ids=a,b&window_hours=24&incident_sla_hours=24`
- `GET /v1/intelligence/conflicts/drilldown?project_id=...&anchor_date=YYYY-MM-DD&weeks=8&type_limit=6`
- `GET /v1/intelligence/digests?project_id=...&kind=daily|weekly|incident_escalation_daily`
- `GET /v1/intelligence/digests/latest?project_id=...&kind=daily|weekly|incident_escalation_daily`
- `GET /v1/intelligence/delivery/targets?project_id=...`
- `PUT /v1/intelligence/delivery/targets`
- `GET /v1/intelligence/delivery/attempts?project_id=...&kind=daily|weekly|incident_escalation_daily`
- `GET /v1/legacy-import/sources?project_id=...`
- `PUT /v1/legacy-import/sources`
- `POST /v1/legacy-import/sources/{source_id}/sync`
- `GET /v1/legacy-import/runs?project_id=...`
- `POST /v1/simulator/runs`
- `GET /v1/simulator/runs?project_id=...`
- `GET /v1/simulator/runs/{run_id}?project_id=...&findings_limit=50`

Queue incident hook provider modes (`PUT /v1/gatekeeper/calibration/operations/incidents/hooks`):
- `provider=webhook`: generic open/resolve webhook URLs + optional `provider_config.headers`.
- `provider=pagerduty`: PagerDuty Events API preset (`routing_key`, optional dedup/metadata) with default endpoint fallback.
- `provider=jira`: Jira issue create/resolve preset (`base_url`, project/auth settings, transition-based resolve or resolve override webhook).
- secret fields (`pagerduty.routing_key`, `jira.api_token`) are returned masked (`********`) on read; sending masked value preserves existing secret, sending a new value rotates it.
- optional `secret_edit_roles` controls who can rotate/clear adapter secrets for this hook.

Alert-to-incident policy templates (`PUT /v1/gatekeeper/calibration/operations/incidents/policies`):
- match by `alert_code` with per-project priority order;
- optional provider override (`webhook` / `pagerduty` / `jira`);
- optional open/resolve endpoint overrides;
- optional `severity_by_health` mapping (`healthy|watch|critical`) merged into provider payload config;
- optional `open_on_health` override for policy-scoped open gating.
- optional `secret_edit_roles` for policy-level secret rotation permissions.

Incident policy simulation (`POST /v1/gatekeeper/calibration/operations/incidents/policies/simulate`):
- performs dry-run routing resolution for `{project_id, alert_code, health}` without ticket side effects;
- returns `matched_policy`, `effective_hook`, `decision.should_open_incident`, and `route_trace` candidate policy ordering;
- can optionally request secrets via `include_secrets=true`; secret values are still masked unless caller roles allow access.

Incident preflight checks:
- `GET /v1/gatekeeper/calibration/operations/incidents/preflight/presets` lists per-project preflight presets (optional disabled/run-before-live-sync filtering).
- `PUT /v1/gatekeeper/calibration/operations/incidents/preflight/presets` upserts a preflight preset (`alert_code`, health, expected decision, optional provider requirement, severity, strict mode).
- `POST /v1/gatekeeper/calibration/operations/incidents/preflight/run` batch-runs preset simulations and returns summary + project rollups + failed checks.
- failed checks can emit queue audit events (`incident_preflight_alert`) and per-project run rollups (`incident_preflight_run`) for operational traceability.

Live incident sync preflight enforcement:
- `PUT /v1/gatekeeper/calibration/operations/incidents/sync/enforcement` stores per-project sync gate config in queue controls:
  - `incident_preflight_enforcement_mode`: `off|block|pause`
  - `incident_preflight_pause_hours`: pause window when mode=`pause`
  - `incident_preflight_critical_fail_threshold`: minimum critical preflight failures to trigger gate
- `POST /v1/gatekeeper/calibration/operations/incidents/sync` now supports enforcement overrides (`preflight_enforcement_mode=inherit|off|block|pause`) and preflight run options (`preflight_include_run_before_live_sync_only`, `preflight_record_audit`).
- sync results now include enforcement counters in `summary` (`blocked`, `paused`) and project-level `action` markers (`blocked_by_preflight`, `paused_by_preflight`, dry-run `would_*` variants).
- queue command-center compare CSV/webhook snapshots now include enforcement posture columns (`incident_preflight_enforcement_mode`, `incident_preflight_pause_hours`, `incident_preflight_critical_fail_threshold`).

Incident sync schedules (persisted unattended windows):
- `GET /v1/gatekeeper/calibration/operations/incidents/sync/schedules` lists schedule configs with server-side fleet controls:
  - filters: `project_id|project_ids`, `schedule_ids`, `enabled`, `due_only`, `status`, `project_contains`, `name_contains`.
  - sorting: `sort_by=next_run_at|updated_at|last_run_at|name|project_id|status`, `sort_dir=asc|desc`.
  - pagination: `limit`, `offset`, optional opaque `cursor`.
  - response includes `paging` (`limit`, `offset`, `cursor`, `next_cursor`, `has_more`, `total`) plus echoed filter/sort fields.
- `PUT /v1/gatekeeper/calibration/operations/incidents/sync/schedules` upserts per-project schedules (`preset`/`interval_minutes`, sync options, preflight options, `requested_by`, optional `next_run_at`).
- `DELETE /v1/gatekeeper/calibration/operations/incidents/sync/schedules/{schedule_id}?project_id=...` removes a schedule.
- `POST /v1/gatekeeper/calibration/operations/incidents/sync/schedules/run` executes enabled due schedules (or forced mode), updates `last_run_*` + `next_run_at`, records schedule audit actions, and returns per-result `audit_event_id` plus `sync_trace` payload for command-center drill-down.
- `GET /v1/gatekeeper/calibration/operations/incidents/sync/schedules/{schedule_id}/timeline` returns run history for one schedule (status trend, latest runs, and failure-class breakdown from queue audit events).

Incident escalation digest delivery workflow:
- `intelligence_digests.digest_kind=incident_escalation_daily` stores daily escalation pulse payloads (over-SLA unresolved incidents + routing gaps).
- delivery targets can scope channel routing via `config.digest_kinds` (`daily`, `weekly`, `incident_escalation_daily`).
- for escalation pulse delivery, `config.incident_escalation_require_over_sla=true` (default) skips sends when there are no over-SLA open incidents.
- `config.incident_escalation_playbook` enables route orchestration for `incident_escalation_daily`:
  - `enabled`: enable/disable playbook routing for the target.
  - `owner_tier_enabled`, `owner_tier_max_candidates`: route top incident candidates to owner fields.
  - `owner_tier_channels_by_severity`: choose ownership field per severity (`owner_name|owner_contact|oncall_channel|escalation_channel`).
  - `owner_tier_fallback_recipients`: fallback recipients when owner routes are missing.
  - `severity_fanout`: severity-based fan-out recipients (`info|warning|critical`).
  - `quiet_hours`: suppress sends inside configured windows with timezone and severity bypass (`allow_severity_at_or_above`).
- each delivery attempt now includes `response_payload.routing` metadata (`severity`, `route_type`, `route_source`, `recipient`) for audit/traceability.

Incident secret RBAC:
- pass roles via request header `X-Synapse-Roles: incident_admin,security_admin`.
- `SYNAPSE_INCIDENT_SECRET_RBAC_MODE=enforce` requires role match for secret rotations/clears; `open` (default) allows writes when roles are not provided.

`Idempotency-Key` behavior:
- same key + same request payload: response replayed from persisted idempotency store.
- same key + different payload: `409 Conflict`.
- in-progress request with same key: waits briefly, then returns `409` + `Retry-After` if still processing.

## Cleanup

Run manual TTL cleanup:

```bash
cd services/api
source .venv/bin/activate
python scripts/cleanup_idempotency.py --batch-size 1000
```

## Integration Scenario

Run the focused core acceptance scenario (`ingest -> draft -> approve -> MCP retrieval`):

```bash
./scripts/integration_core_loop.py
```

Run full integration scenario for backfill lifecycle + moderation idempotency + structured approve edits + audit feed + daily/weekly/incident-escalation digest generation + webhook delivery:

```bash
./scripts/integration_moderation_backfill.py
```

## Notes

- Wiki endpoints depend on migration `003_wiki_engine.sql`.
- Backfill endpoints depend on migration `005_memory_backfill.sql`.
- Gatekeeper decision endpoint depends on migration `006_gatekeeper.sql`.
- Migration `007_claim_fingerprint.sql` improves Gatekeeper matching performance.
- Intelligence endpoints depend on migration `008_knowledge_intelligence.sql`.
- Moderation audit feed + Gatekeeper config endpoints depend on migration `009_moderation_audit_and_gatekeeper_config.sql`.
- Delivery target/attempt endpoints depend on migration `010_intelligence_delivery.sql`.
- Temporal validity constraints/indexes for claims/statements depend on migration `011_temporal_reasoning_indexes.sql`.
- LLM-assisted Gatekeeper config fields depend on migration `012_gatekeeper_llm_assist.sql`.
- Gatekeeper config snapshot endpoints depend on migration `017_gatekeeper_config_snapshots.sql`.
- Gatekeeper calibration schedule endpoints depend on migration `018_gatekeeper_calibration_schedules.sql`.
- Gatekeeper alert target/attempt endpoints depend on migration `019_gatekeeper_alert_delivery.sql`.
- Rollback approval workflow endpoints depend on migration `020_gatekeeper_rollback_requests.sql`.
- Calibration run-history endpoints depend on migration `021_gatekeeper_calibration_run_history.sql`.
- Agent Simulator read endpoints depend on migration `013_agent_simulator.sql`.
- Agent Simulator async queue status + API enqueue flow depends on migration `014_agent_simulator_queue_status.sql`.
- Legacy sync source/run orchestration endpoints depend on migration `015_legacy_sync_orchestration.sql`.
- Queue incident auto-ticket hooks + incident lifecycle endpoints depend on migration `028_gatekeeper_calibration_queue_incident_hooks.sql`.
- Incident provider adapters (webhook + PagerDuty + Jira presets with `provider_config`) depend on migration `029_gatekeeper_calibration_queue_incident_provider_adapters.sql`.
- Alert-to-incident policy templates depend on migration `030_gatekeeper_calibration_queue_incident_policies.sql`.
- Incident secret vault + RBAC-scoped secret edit roles depend on migration `031_gatekeeper_calibration_queue_incident_secrets_rbac.sql`.
- Incident escalation digest kind support depends on migration `032_intelligence_incident_escalation_digest.sql`.
- Incident preflight preset storage and run endpoints depend on migration `033_gatekeeper_calibration_queue_incident_preflight_presets.sql`.
- Incident sync preflight enforcement settings depend on migration `034_gatekeeper_calibration_queue_incident_sync_enforcement.sql`.
- Incident sync schedule persistence and due-run execution depend on migration `035_gatekeeper_calibration_queue_incident_sync_schedules.sql`.
- Enterprise tenancy/auth/session baseline depends on migration `037_enterprise_tenancy_auth_rbac.sql`.
- Backfill dedup uses deterministic event id per `batch_id + source_id`; keep `source_id` stable and unique inside a batch.
- `/v1/events` accepts optional tracing fields (`trace_id`, `span_id`, `parent_span_id`) and stores them in payload metadata (`_synapse.*`).
- `GET /v1/wiki/pages/{slug}` returns only currently valid active statements (`valid_from <= now <= valid_to`, with open bounds support).
- Apply all migrations from repo root via `./scripts/apply_migrations.sh`.
