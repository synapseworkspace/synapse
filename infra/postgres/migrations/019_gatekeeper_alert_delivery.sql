CREATE TABLE IF NOT EXISTS gatekeeper_alert_targets (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  channel TEXT NOT NULL CHECK (channel IN ('slack_webhook', 'email_smtp')),
  target TEXT NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  config JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT,
  updated_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (project_id, channel, target)
);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_alert_targets_project
  ON gatekeeper_alert_targets (project_id, enabled, updated_at DESC);

CREATE TABLE IF NOT EXISTS gatekeeper_alert_attempts (
  id UUID PRIMARY KEY,
  run_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  channel TEXT NOT NULL,
  target TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('sent', 'failed', 'skipped')),
  alert_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
  error_message TEXT,
  response_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  attempted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_alert_attempts_project
  ON gatekeeper_alert_attempts (project_id, attempted_at DESC);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_alert_attempts_run
  ON gatekeeper_alert_attempts (run_id, attempted_at DESC);
