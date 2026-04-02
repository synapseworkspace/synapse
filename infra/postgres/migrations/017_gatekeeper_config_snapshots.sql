CREATE TABLE IF NOT EXISTS gatekeeper_config_snapshots (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  source TEXT NOT NULL CHECK (source IN ('calibration_cycle', 'manual', 'rollback')),
  approved_by TEXT NOT NULL,
  note TEXT,
  config JSONB NOT NULL DEFAULT '{}'::jsonb,
  guardrails_met BOOLEAN,
  holdout_meta JSONB NOT NULL DEFAULT '{}'::jsonb,
  calibration_report JSONB NOT NULL DEFAULT '{}'::jsonb,
  artifact_refs JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_config_snapshots_project_time
  ON gatekeeper_config_snapshots (project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_config_snapshots_source_time
  ON gatekeeper_config_snapshots (source, created_at DESC);
