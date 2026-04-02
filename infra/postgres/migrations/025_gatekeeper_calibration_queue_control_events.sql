CREATE TABLE IF NOT EXISTS gatekeeper_calibration_queue_control_events (
  id BIGSERIAL PRIMARY KEY,
  project_id TEXT NOT NULL,
  action TEXT NOT NULL,
  actor TEXT NOT NULL,
  reason TEXT,
  paused_until TIMESTAMPTZ,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_calibration_queue_control_events_project_created
  ON gatekeeper_calibration_queue_control_events (project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_calibration_queue_control_events_created
  ON gatekeeper_calibration_queue_control_events (created_at DESC);
