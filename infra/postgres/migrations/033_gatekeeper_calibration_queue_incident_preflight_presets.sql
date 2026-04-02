CREATE TABLE IF NOT EXISTS gatekeeper_calibration_queue_incident_preflight_presets (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  preset_key TEXT NOT NULL,
  name TEXT NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  alert_code TEXT NOT NULL,
  health TEXT NOT NULL CHECK (health IN ('healthy', 'watch', 'critical')),
  additional_alert_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
  expected_decision TEXT NOT NULL DEFAULT 'open' CHECK (expected_decision IN ('open', 'skip', 'invalid_ok')),
  required_provider TEXT CHECK (required_provider IN ('webhook', 'pagerduty', 'jira')),
  run_before_live_sync BOOLEAN NOT NULL DEFAULT TRUE,
  severity TEXT NOT NULL DEFAULT 'warning' CHECK (severity IN ('info', 'warning', 'critical')),
  strict_mode BOOLEAN NOT NULL DEFAULT TRUE,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_by TEXT NOT NULL DEFAULT 'web_ui',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT gatekeeper_calibration_queue_incident_preflight_presets_key_check
    CHECK (LENGTH(BTRIM(preset_key)) > 0),
  CONSTRAINT gatekeeper_calibration_queue_incident_preflight_presets_name_check
    CHECK (LENGTH(BTRIM(name)) > 0),
  CONSTRAINT gatekeeper_calibration_queue_incident_preflight_presets_alert_check
    CHECK (LENGTH(BTRIM(alert_code)) > 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_gatekeeper_queue_incident_preflight_project_key
  ON gatekeeper_calibration_queue_incident_preflight_presets (project_id, preset_key);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_queue_incident_preflight_project_updated
  ON gatekeeper_calibration_queue_incident_preflight_presets (project_id, enabled, updated_at DESC);

