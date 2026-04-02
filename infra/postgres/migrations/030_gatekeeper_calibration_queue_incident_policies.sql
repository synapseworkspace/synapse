CREATE TABLE IF NOT EXISTS gatekeeper_calibration_queue_incident_policies (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  alert_code TEXT NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  priority INTEGER NOT NULL DEFAULT 100,
  provider_override TEXT CHECK (provider_override IN ('webhook', 'pagerduty', 'jira')),
  open_webhook_url TEXT,
  resolve_webhook_url TEXT,
  provider_config_override JSONB NOT NULL DEFAULT '{}'::jsonb,
  severity_by_health JSONB NOT NULL DEFAULT '{}'::jsonb,
  open_on_health JSONB NOT NULL DEFAULT '[]'::jsonb,
  updated_by TEXT NOT NULL DEFAULT 'system',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT gatekeeper_calibration_queue_incident_policies_priority_check
    CHECK (priority >= 1 AND priority <= 1000),
  CONSTRAINT gatekeeper_calibration_queue_incident_policies_alert_code_check
    CHECK (LENGTH(BTRIM(alert_code)) > 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_gatekeeper_queue_incident_policies_project_alert
  ON gatekeeper_calibration_queue_incident_policies (project_id, alert_code);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_queue_incident_policies_project_enabled_priority
  ON gatekeeper_calibration_queue_incident_policies (project_id, enabled, priority ASC, updated_at DESC);
