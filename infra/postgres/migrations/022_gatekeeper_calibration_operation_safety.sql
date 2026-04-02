CREATE TABLE IF NOT EXISTS gatekeeper_calibration_operation_runs (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  operation_token TEXT NOT NULL,
  requested_by TEXT,
  dry_run BOOLEAN NOT NULL DEFAULT FALSE,
  status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
  request_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  result_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (project_id, operation_token)
);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_calibration_operation_runs_project_created
  ON gatekeeper_calibration_operation_runs (project_id, created_at DESC);

