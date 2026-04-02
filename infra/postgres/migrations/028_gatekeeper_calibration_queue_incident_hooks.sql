CREATE TABLE IF NOT EXISTS gatekeeper_calibration_queue_incident_hooks (
  project_id TEXT PRIMARY KEY,
  enabled BOOLEAN NOT NULL DEFAULT FALSE,
  provider TEXT NOT NULL DEFAULT 'webhook' CHECK (provider IN ('webhook')),
  open_webhook_url TEXT,
  resolve_webhook_url TEXT,
  open_on_health JSONB NOT NULL DEFAULT '["critical"]'::jsonb,
  auto_resolve BOOLEAN NOT NULL DEFAULT TRUE,
  cooldown_minutes INTEGER NOT NULL DEFAULT 30,
  timeout_sec INTEGER NOT NULL DEFAULT 10,
  updated_by TEXT NOT NULL DEFAULT 'system',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT gatekeeper_calibration_queue_incident_hooks_cooldown_check
    CHECK (cooldown_minutes >= 1 AND cooldown_minutes <= 1440),
  CONSTRAINT gatekeeper_calibration_queue_incident_hooks_timeout_check
    CHECK (timeout_sec >= 1 AND timeout_sec <= 60),
  CONSTRAINT gatekeeper_calibration_queue_incident_hooks_enabled_url_check
    CHECK (
      enabled = FALSE OR (
        open_webhook_url IS NOT NULL
        AND LENGTH(BTRIM(open_webhook_url)) > 0
      )
    )
);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_queue_incident_hooks_enabled
  ON gatekeeper_calibration_queue_incident_hooks (enabled, updated_at DESC);

CREATE TABLE IF NOT EXISTS gatekeeper_calibration_queue_incidents (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('open', 'resolved')),
  trigger_health TEXT NOT NULL,
  trigger_alert_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
  open_reason TEXT,
  resolve_reason TEXT,
  external_provider TEXT NOT NULL DEFAULT 'webhook',
  external_ticket_id TEXT,
  external_ticket_url TEXT,
  open_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  resolve_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resolved_at TIMESTAMPTZ,
  last_sync_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by TEXT NOT NULL DEFAULT 'system',
  updated_by TEXT NOT NULL DEFAULT 'system'
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_gatekeeper_queue_incidents_open_project
  ON gatekeeper_calibration_queue_incidents (project_id)
  WHERE status = 'open' AND resolved_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_gatekeeper_queue_incidents_project_opened
  ON gatekeeper_calibration_queue_incidents (project_id, opened_at DESC);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_queue_incidents_status_sync
  ON gatekeeper_calibration_queue_incidents (status, last_sync_at DESC);
