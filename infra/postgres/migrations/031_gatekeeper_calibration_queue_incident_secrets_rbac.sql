ALTER TABLE gatekeeper_calibration_queue_incident_hooks
  ADD COLUMN IF NOT EXISTS secret_edit_roles TEXT[] NOT NULL DEFAULT ARRAY['incident_admin', 'security_admin', 'admin']::text[];

ALTER TABLE gatekeeper_calibration_queue_incident_policies
  ADD COLUMN IF NOT EXISTS secret_edit_roles TEXT[] NOT NULL DEFAULT ARRAY['incident_admin', 'security_admin', 'admin']::text[];

CREATE TABLE IF NOT EXISTS gatekeeper_calibration_queue_incident_secrets (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  scope TEXT NOT NULL CHECK (scope IN ('hook', 'policy')),
  scope_ref TEXT NOT NULL,
  provider TEXT NOT NULL CHECK (provider IN ('webhook', 'pagerduty', 'jira')),
  secret_key TEXT NOT NULL,
  secret_value TEXT NOT NULL,
  secret_hash TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,
  updated_by TEXT NOT NULL DEFAULT 'system',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT gatekeeper_calibration_queue_incident_secrets_version_check
    CHECK (version >= 1)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_gatekeeper_queue_incident_secrets_scope_key
  ON gatekeeper_calibration_queue_incident_secrets (project_id, scope, scope_ref, provider, secret_key);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_queue_incident_secrets_scope
  ON gatekeeper_calibration_queue_incident_secrets (project_id, scope, scope_ref, updated_at DESC);

CREATE TABLE IF NOT EXISTS gatekeeper_calibration_queue_incident_secret_events (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  scope TEXT NOT NULL CHECK (scope IN ('hook', 'policy')),
  scope_ref TEXT NOT NULL,
  provider TEXT NOT NULL CHECK (provider IN ('webhook', 'pagerduty', 'jira')),
  secret_key TEXT NOT NULL,
  action TEXT NOT NULL CHECK (action IN ('created', 'rotated', 'cleared')),
  version_before INTEGER,
  version_after INTEGER,
  actor TEXT NOT NULL DEFAULT 'system',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_queue_incident_secret_events_scope
  ON gatekeeper_calibration_queue_incident_secret_events (project_id, scope, scope_ref, created_at DESC);
