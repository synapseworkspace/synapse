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
- `SYNAPSE_WIKI_UPLOAD_MAX_BYTES` (default: `15728640` / 15MB)

## Endpoints

- `GET /health`
- `GET /v1/auth/mode`
- `GET /v1/enterprise/rbac/decisions?project_id=...&decision=deny&path_prefix=/v1/wiki/&limit=100` (compliance audit stream for RBAC/tenancy policy decisions)
- `GET /v1/enterprise/idp/connections?tenant_id=...&provider=saml` (enterprise IdP bridge registry)
- `PUT /v1/enterprise/idp/connections` (upsert tenant-scoped OIDC/SAML bridge config)
- `GET /v1/enterprise/idp/saml/metadata?tenant_id=...&name=default` (SAML SP metadata document)
- `GET /v1/enterprise/scim/tokens?tenant_id=...` (list SCIM provisioning tokens with masked hints)
- `PUT /v1/enterprise/scim/tokens` (create SCIM provisioning token; returns secret once)
- `DELETE /v1/enterprise/scim/tokens/{token_id}?updated_by=...` (revoke SCIM token)
- `POST /v1/auth/session`
- `GET /v1/auth/session`
- `DELETE /v1/auth/session`
- `POST /v1/tenants`
- `GET /v1/tenants`
- `GET /v1/tenants/{tenant_id}`
- `PUT /v1/tenants/{tenant_id}/memberships`
- `PUT /v1/tenants/{tenant_id}/projects`
- `GET /scim/v2/ServiceProviderConfig` (SCIM discovery endpoint; bearer token protected)
- `GET /scim/v2/Users?startIndex=1&count=50&filter=userName eq "alice"` (supports equality filters on `userName` / `externalId`)
- `GET /scim/v2/Users/{user_id}`
- `POST /scim/v2/Users`
- `PUT /scim/v2/Users/{user_id}`
- `DELETE /scim/v2/Users/{user_id}` (soft-disables tenant membership)
- `POST /v1/events` (idempotent by `event.id`, plus request-level idempotency via `Idempotency-Key`)
- `GET /v1/events/throughput?project_id=...&window_hours=24&event_type=tool_result` (ingest latency + throughput SLO metrics)
- `POST /v1/facts/proposals` (request-level idempotency via `Idempotency-Key`)
- `POST /v1/backfill/memory` (runtime/event lane backfill; strict event-noise filtering defaults)
- `POST /v1/backfill/knowledge` (corporate knowledge lane backfill; avoids source-type transport hard-block defaults)
- `GET /v1/backfill/batches/{batch_id}?project_id=...`
  - includes adoption-quality counters: `dropped_event_like`, `kept_durable`, `trusted_bypass` (for backfill explainability)
- `GET /v1/adoption/rejections/diagnostics?project_id=...&days=14&sample_limit=5` (aggregated reject reasons, blocked patterns, and suggested policy knobs)
- `GET /v1/adoption/source-ownership?project_id=...`
- `PUT /v1/adoption/source-ownership`
- `DELETE /v1/adoption/source-ownership/{domain}?project_id=...`
- `GET /v1/wiki/pages/search?project_id=...&q=...` (includes `meta` debug payload: scope, filters, page/draft status counters)
- `GET /v1/wiki/pages?project_id=...&status=published&updated_by=ops_manager&with_open_drafts=true&q=...&sort_by=activity&sort_dir=desc&limit=200&offset=0` (page index for wiki tree; includes draft counters per page, plus actor/open-draft filters)
- `GET /v1/wiki/stats?project_id=...` (page/draft status counters and latest update timestamps)
- `GET /v1/wiki/lifecycle/stats?project_id=...&stale_days=21&critical_days=45&stale_limit=20&space_key=operations` (lifecycle counters + stale page candidates for dashboards/diagnostics; optional `space_key` narrows scope for high-cardinality workspaces; response `meta` includes `searched_scope`, `filters_applied`, and `empty_scope` diagnostics with explanation codes `no_published|all_open_drafts|below_threshold`, details counters, and actionable `suggested_actions` hints)
- `POST /v1/wiki/lifecycle/telemetry/snapshot` (ingest client-side empty-scope action counters by session; server computes monotonic deltas and updates daily telemetry aggregates)
- `GET /v1/wiki/lifecycle/telemetry?project_id=...&days=7&action_key=create_page` (7/30/90-day action telemetry summary + daily trend for `empty_scope_action_shown` and `empty_scope_action_applied`; optional `action_key` filter for drill-down)
- `GET /v1/wiki/routing/metrics?project_id=...&window_days=30` (routing quality counters/rates: precision@1, manual reassign rate, new-page false positives, conflict/ambiguity rates)
- `GET /v1/wiki/routing/recommendations?project_id=...&window_days=30` (threshold tuning recommendations for `threshold_mid` / `new_page_margin` / `ambiguity_gap`)
- `GET /v1/mcp/retrieval/explain?project_id=...&q=...&limit=10&related_entity_key=...&retrieval_intent=process&max_context_snippets=3&context_policy_mode=enforced&min_retrieval_confidence=0.45` (MCP-compatible retrieval diagnostics with score/confidence breakdown, intent-aware ranking, top-k context injection snippets, per-result provenance links to claim evidence/tickets, and context-policy controls)
- `POST /v1/mcp/retrieval/feedback` (runtime usefulness feedback for retrieved context; positive/negative/neutral)
- `GET /v1/mcp/retrieval/feedback/stats?project_id=...&days=30` (feedback aggregates by claim for policy tuning)
- `POST /v1/wiki/pages` (guided/manual page create with initial version + optional sections/statements from markdown)
- `PUT /v1/wiki/pages/{slug}` (direct human page edit, new page version + statement re-index + snapshot)
- `PUT /v1/wiki/pages/{slug}/move` (move/rename page slug, optional subtree move, alias back-compat, and snapshot invalidation)
- `PUT /v1/wiki/pages/{slug}/reparent` (explicit parent-child operation: move page under target parent slug, optional leaf rename + subtree move)
- `PUT /v1/wiki/pages/{slug}/archive` (archive page lifecycle state; optional subtree status transition)
- `PUT /v1/wiki/pages/{slug}/restore` (restore archived page lifecycle state to `published`/`draft`; optional subtree transition)
- `GET /v1/wiki/pages/{slug}/aliases?project_id=...`
- `POST /v1/wiki/pages/{slug}/aliases`
- `DELETE /v1/wiki/pages/{slug}/aliases/{alias_text}?project_id=...&deleted_by=...`
- `GET /v1/wiki/pages/{slug}/comments?project_id=...&limit=100`
- `POST /v1/wiki/pages/{slug}/comments`
- `DELETE /v1/wiki/pages/{slug}/comments/{comment_id}`
- `GET /v1/wiki/pages/{slug}/watchers?project_id=...`
- `PUT /v1/wiki/pages/{slug}/watchers`
- `GET /v1/wiki/pages/{slug}/review-assignments?project_id=...&status=open|resolved`
- `PUT /v1/wiki/pages/{slug}/review-assignments`
- `POST /v1/wiki/pages/{slug}/review-assignments/{assignment_id}/resolve`
- `GET /v1/wiki/spaces/{space_key}/policy?project_id=...`
- `PUT /v1/wiki/spaces/{space_key}/policy`
- `GET /v1/wiki/spaces/{space_key}/policy/audit?project_id=...&limit=40` (space policy change timeline: who changed what and when)
- `GET /v1/wiki/spaces/{space_key}/policy/adoption-summary?project_id=...&limit=200` (who-updates/cadence/checklist-usage aggregate over policy audit events)
- `GET /v1/wiki/spaces/{space_key}/owners?project_id=...`
- `PUT /v1/wiki/spaces/{space_key}/owners`
- `GET /v1/wiki/pages/{slug}/owners?project_id=...`
- `PUT /v1/wiki/pages/{slug}/owners`
- `GET /v1/wiki/notifications?project_id=...&recipient=...&status=all|unread|read`
- `POST /v1/wiki/notifications/{notification_id}/read`
- `POST /v1/wiki/notifications/read-all`
- `POST /v1/wiki/uploads` (multipart upload with policy enforcement + markdown snippet generation)
- `GET /v1/wiki/uploads?project_id=...&page_slug=...`
- `GET /v1/wiki/uploads/{upload_id}/content?project_id=...&download=false`
- `GET /v1/wiki/pages/{slug}?project_id=...`
- `GET /v1/wiki/pages/{slug}/history?project_id=...&limit=20&include_markdown=true`
- `PUT /v1/wiki/pages/{slug}/rollback` (create new page version from a selected historical version; keeps audit trail)
- `POST /v1/wiki/process/simulate` (pre-publish process safety simulation: impact scan + risk tier + suggested publish mode + rollback hints)
- `PUT /v1/wiki/pages/{slug}` publish path now supports `confirm_high_risk_publish=true`; when process simulation detects blocking risk, API returns `409 publish_blocked_by_process_simulation` until explicit confirmation.
- `GET /v1/wiki/drafts?project_id=...&status=pending_review`
- `GET /v1/wiki/drafts/{draft_id}?project_id=...` (includes normalized `gatekeeper` summary: tier/score, LLM reason-code, routing hard-block flags)
- `GET /v1/wiki/drafts/{draft_id}/conflicts/explain?project_id=...` (MCP `explain_conflicts` compatible enrichment for UI conflict resolver)
- `GET /v1/wiki/drafts/bootstrap-approve/recommendation?project_id=...` (server-side migration preset with trusted-source defaults + queue/backfill quality diagnostics)
- `POST /v1/wiki/auto-publish/run` (policy-driven auto-approve runner for eligible drafts; supports `dry_run`)
  - includes ticket/outcome-aware prioritization (`ticket_outcome_signal`, `effective_score`, `effective_min_sources`) so resolved incident evidence can be promoted faster than raw low-signal drafts.
- `POST /v1/wiki/drafts/bootstrap-approve/run` (trusted-source migration helper: confidence/conflict/source-gated bootstrap; apply path enforces trusted sources and soft batch cap unless explicitly overridden)
- `GET /v1/agents?project_id=...&status=active&team=Support` (agent directory listing with status/team summaries)
- `GET /v1/agents/orgchart?project_id=...&include_handoffs=true` (graph-ready orgchart payload: nodes + optional handoff edges + team groups)
- `POST /v1/agents/register` (upsert agent profile and sync Confluence-like agent wiki scaffold: `agents/index`, per-agent folder + `overview/runbooks/daily-reports/created-pages/incidents/changelog`)
- `GET /v1/agents/publish-policy?project_id=...&agent_id=support_bot` (agent-level publish guardrails by domain/page type)
- `PUT /v1/agents/publish-policy` (upsert guardrails; `human_required` blocks direct publish and requires review-first status flow)
- `POST /v1/agents/worklogs/sync` (generate per-agent daily worklogs from runtime/task activity and refresh `daily-reports` wiki pages; supports `timezone`, `include_idle_days`, `min_activity_score`, and trigger metadata `trigger_mode/trigger_reason` for daily batch + realtime close-signal flows)
- `GET /v1/agents/capability-matrix?project_id=...&min_confidence=0.4` (agent capability view with confidence and evidence links from recent worklogs)
- `POST /v1/agents/capability-matrix/sync` (publish capability matrix into wiki page `agents/capability-matrix`)
- `GET /v1/agents/handoffs?project_id=...` (inter-agent handoff graph with input/output contracts and SLA fields)
- `POST /v1/agents/handoffs/sync` (publish handoff map into wiki page `agents/handoffs`)
- `GET /v1/agents/scorecards?project_id=...&lookback_days=14` (agent quality/reliability scorecards from rolling worklog + task posture)
- `POST /v1/agents/scorecards/sync` (publish scorecards into wiki page `agents/scorecards`)
- `GET /v1/agents/provenance?project_id=...&agent_id=support_bot&limit=100` (agent-authored wiki activity feed with rollback readiness metadata)
- `POST /v1/agents/provenance/{activity_id}/rollback` (one-click rollback of latest agent-authored page update to the previous version)
- `GET /v1/wiki/moderation/throughput?project_id=...&window_hours=24&top_reviewers=5` (core moderation throughput/backlog/latency analytics)
- `POST /v1/wiki/drafts/{draft_id}/approve`
- `POST /v1/wiki/drafts/{draft_id}/reject`
- `GET /v1/wiki/moderation/actions?project_id=...`
- `GET /v1/gatekeeper/decisions?project_id=...&tier=golden_candidate`
- `GET /v1/gatekeeper/config?project_id=...`
- `PUT /v1/gatekeeper/config`
- Gatekeeper config supports `routing_policy` (event-stream/telemetry demotion, deny keywords for category/source-system/source-type/entity/source_id, durable knowledge-signal thresholds, optional backfill LLM classifier mode `off|assist|enforce` with confidence threshold, assertion-class publish-mode map, retrieval-feedback guardrails, auto-publish risk tiers for legal/financial changes, process-simulation publish gate controls, minimum independent evidence rules, and backfill policy gating before wiki routing).
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
- `GET /v1/legacy-import/profiles?source_type=postgres_sql`
- `GET /v1/legacy-import/mapper-templates?source_type=postgres_sql&profile=ops_kb_items`
- `GET /v1/legacy-import/sync-contracts?source_type=postgres_sql&profile=ops_kb_items`
- `PUT /v1/legacy-import/sources`
- `POST /v1/legacy-import/sources/{source_id}/sync`
- `GET /v1/legacy-import/runs?project_id=...`

Legacy source types for `PUT /v1/legacy-import/sources`:
- `local_dir`
- `notion_root_page`
- `notion_database`
- `postgres_sql`:
  - profile-driven pull for common schemas (`sql_profile=ops_kb_items|memory_items|auto`) without custom importer scripts;
  - reusable mapper templates (`/v1/legacy-import/mapper-templates`) with ready `config_patch` payloads by profile/sync-mode;
  - explicit sync runner contracts (`/v1/legacy-import/sync-contracts`) for cron/CDC services (required config + state keys + scheduler cadence);
  - query-based pull from existing Postgres memory schema (`sql_sync_mode=polling`);
  - low-latency logical-slot ingestion (`sql_sync_mode=wal_cdc`).
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

Source ownership enforcement:
- write-path endpoints (`/v1/events`, `/v1/facts/proposals`, `/v1/backfill/memory`, `/v1/backfill/knowledge`, wiki moderation/publish paths) can be governed by project-level source ownership rules from `/v1/adoption/source-ownership`.
- pass `X-Synapse-Source-System` to identify caller/source system for enforcement decisions.
- in `advisory` mode, writes succeed and response includes `source_ownership_advisories`.
- in `enforce` mode, writes from disallowed sources fail with `403` (`source_ownership_denied`).

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
- Migration `038_gatekeeper_publish_policy.sql` adds hybrid publication policy controls (`publish_mode_default`, per-category overrides, conditional auto-publish thresholds).
- Intelligence endpoints depend on migration `008_knowledge_intelligence.sql`.
- Moderation audit feed + Gatekeeper config endpoints depend on migration `009_moderation_audit_and_gatekeeper_config.sql`.
- Delivery target/attempt endpoints depend on migration `010_intelligence_delivery.sql`.
- Temporal validity constraints/indexes for claims/statements depend on migration `011_temporal_reasoning_indexes.sql`.
- LLM-assisted Gatekeeper config fields depend on migration `012_gatekeeper_llm_assist.sql`.
- Gatekeeper config snapshot endpoints depend on migration `017_gatekeeper_config_snapshots.sql`.
- Gatekeeper calibration schedule endpoints depend on migration `018_gatekeeper_calibration_schedules.sql`.
- Gatekeeper alert target/attempt endpoints depend on migration `019_gatekeeper_alert_delivery.sql`.
- Gatekeeper routing-policy fields depend on migration `049_gatekeeper_routing_policy.sql`.
- Retrieval-feedback endpoints and retrieval-governance policy feedback loop depend on migration `050_retrieval_feedback_loop.sql`.
- Rollback approval workflow endpoints depend on migration `020_gatekeeper_rollback_requests.sql`.
- Calibration run-history endpoints depend on migration `021_gatekeeper_calibration_run_history.sql`.
- Agent Simulator read endpoints depend on migration `013_agent_simulator.sql`.
- Agent Simulator async queue status + API enqueue flow depends on migration `014_agent_simulator_queue_status.sql`.
- Legacy sync source/run orchestration endpoints depend on migration `015_legacy_sync_orchestration.sql`.
- `postgres_sql` legacy source type support depends on migration `040_legacy_sync_postgres_sql_source.sql`.
- low-latency legacy-sync cadence (`sync_interval_minutes >= 1`) depends on migration `048_legacy_sync_low_latency_interval.sql`.
- wiki collaboration surfaces (comments/watchers) depend on migration `041_wiki_collaboration.sql`.
- wiki review assignment surfaces depend on migration `042_wiki_review_assignments.sql`.
- wiki governance + notifications surfaces (space/page ownership, policy, inbox) depend on migration `043_wiki_policy_notifications.sql`.
- wiki upload storage surfaces depend on migration `044_wiki_uploads.sql`.
- reviewed wiki-page status lifecycle support depends on migration `045_wiki_reviewed_status.sql`.
- RBAC/tenancy decision audit stream endpoint depends on migration `046_access_policy_decisions.sql`.
- Enterprise SAML/SCIM bridge endpoints depend on migration `047_saml_scim_bridge.sql`.
- Queue incident auto-ticket hooks + incident lifecycle endpoints depend on migration `028_gatekeeper_calibration_queue_incident_hooks.sql`.
- Incident provider adapters (webhook + PagerDuty + Jira presets with `provider_config`) depend on migration `029_gatekeeper_calibration_queue_incident_provider_adapters.sql`.
- Alert-to-incident policy templates depend on migration `030_gatekeeper_calibration_queue_incident_policies.sql`.
- Incident secret vault + RBAC-scoped secret edit roles depend on migration `031_gatekeeper_calibration_queue_incident_secrets_rbac.sql`.
- Incident escalation digest kind support depends on migration `032_intelligence_incident_escalation_digest.sql`.
- Incident preflight preset storage and run endpoints depend on migration `033_gatekeeper_calibration_queue_incident_preflight_presets.sql`.
- Incident sync preflight enforcement settings depend on migration `034_gatekeeper_calibration_queue_incident_sync_enforcement.sql`.
- Incident sync schedule persistence and due-run execution depend on migration `035_gatekeeper_calibration_queue_incident_sync_schedules.sql`.
- Enterprise tenancy/auth/session baseline depends on migration `037_enterprise_tenancy_auth_rbac.sql`.
- Source-ownership registry/enforcement endpoints depend on migration `039_source_ownership_policy.sql`.
- Backfill dedup uses deterministic event id per `batch_id + source_id`; keep `source_id` stable and unique inside a batch.
- `/v1/events` accepts optional tracing fields (`trace_id`, `span_id`, `parent_span_id`) and stores them in payload metadata (`_synapse.*`).
- `GET /v1/wiki/pages/{slug}` returns only currently valid active statements (`valid_from <= now <= valid_to`, with open bounds support).
- `GET /v1/wiki/onboarding-pack?project_id=...&role=support&max_items_per_section=5&freshness_days=14` (day-0 role pack with critical playbooks/escalations/forbidden actions/fresh changes).
- lifecycle telemetry integration smoke (real API + Postgres schema): `python3 scripts/integration_lifecycle_telemetry.py` (set `DATABASE_URL` as needed).
- Apply all migrations from repo root via `./scripts/apply_migrations.sh`.
