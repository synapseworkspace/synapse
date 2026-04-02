CREATE TABLE IF NOT EXISTS gatekeeper_calibration_queue_ownership (
  project_id TEXT PRIMARY KEY,
  owner_name TEXT,
  owner_contact TEXT,
  oncall_channel TEXT,
  escalation_channel TEXT,
  updated_by TEXT NOT NULL DEFAULT 'system',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_queue_ownership_updated_at
  ON gatekeeper_calibration_queue_ownership (updated_at DESC);
