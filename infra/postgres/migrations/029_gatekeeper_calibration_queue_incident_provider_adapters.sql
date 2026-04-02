ALTER TABLE gatekeeper_calibration_queue_incident_hooks
  ADD COLUMN IF NOT EXISTS provider_config JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE gatekeeper_calibration_queue_incident_hooks
  DROP CONSTRAINT IF EXISTS gatekeeper_calibration_queue_incident_hooks_provider_check;

ALTER TABLE gatekeeper_calibration_queue_incident_hooks
  ADD CONSTRAINT gatekeeper_calibration_queue_incident_hooks_provider_check
  CHECK (provider IN ('webhook', 'pagerduty', 'jira'));

ALTER TABLE gatekeeper_calibration_queue_incident_hooks
  DROP CONSTRAINT IF EXISTS gatekeeper_calibration_queue_incident_hooks_enabled_url_check;

ALTER TABLE gatekeeper_calibration_queue_incident_hooks
  ADD CONSTRAINT gatekeeper_calibration_queue_incident_hooks_enabled_url_check
  CHECK (
    enabled = FALSE
    OR provider IN ('pagerduty', 'jira')
    OR (
      open_webhook_url IS NOT NULL
      AND LENGTH(BTRIM(open_webhook_url)) > 0
    )
  );

CREATE INDEX IF NOT EXISTS idx_gatekeeper_queue_incident_hooks_provider
  ON gatekeeper_calibration_queue_incident_hooks (provider, enabled, updated_at DESC);
