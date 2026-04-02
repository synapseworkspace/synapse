CREATE TABLE IF NOT EXISTS gatekeeper_calibration_schedules (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  name TEXT NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  preset TEXT NOT NULL CHECK (preset IN ('nightly', 'weekly')),
  interval_hours INTEGER CHECK (interval_hours IS NULL OR (interval_hours >= 1 AND interval_hours <= 4320)),
  lookback_days INTEGER NOT NULL DEFAULT 60 CHECK (lookback_days >= 1 AND lookback_days <= 365),
  limit_rows INTEGER NOT NULL DEFAULT 20000 CHECK (limit_rows >= 100 AND limit_rows <= 200000),
  holdout_ratio NUMERIC(6, 4) NOT NULL DEFAULT 0.3000 CHECK (holdout_ratio > 0 AND holdout_ratio < 1),
  split_seed TEXT NOT NULL DEFAULT 'synapse-gatekeeper-prod-holdout-v1',
  weights JSONB NOT NULL DEFAULT '[]'::jsonb,
  confidences JSONB NOT NULL DEFAULT '[]'::jsonb,
  score_thresholds JSONB NOT NULL DEFAULT '[]'::jsonb,
  top_k INTEGER NOT NULL DEFAULT 5 CHECK (top_k >= 1 AND top_k <= 20),
  allow_guardrail_fail BOOLEAN NOT NULL DEFAULT FALSE,
  snapshot_note TEXT,
  updated_by TEXT NOT NULL,
  last_run_at TIMESTAMPTZ,
  last_status TEXT CHECK (last_status IN ('ok', 'alert', 'partial_failure', 'failed')),
  last_run_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (project_id, name)
);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_calibration_schedules_project_enabled
  ON gatekeeper_calibration_schedules (project_id, enabled, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_calibration_schedules_enabled_preset
  ON gatekeeper_calibration_schedules (enabled, preset, updated_at DESC);
