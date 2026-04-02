CREATE TABLE IF NOT EXISTS gatekeeper_calibration_runs (
  id UUID PRIMARY KEY,
  run_id TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL,
  finished_at TIMESTAMPTZ NOT NULL,
  total_schedules INTEGER NOT NULL DEFAULT 0,
  executed_count INTEGER NOT NULL DEFAULT 0,
  alerts_count INTEGER NOT NULL DEFAULT 0,
  summary JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_calibration_runs_finished
  ON gatekeeper_calibration_runs (finished_at DESC);

CREATE TABLE IF NOT EXISTS gatekeeper_calibration_run_projects (
  id UUID PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES gatekeeper_calibration_runs(run_id) ON DELETE CASCADE,
  project_id TEXT NOT NULL,
  schedule_id UUID,
  schedule_name TEXT,
  status TEXT NOT NULL,
  project_cycle_status TEXT,
  returncode INTEGER,
  alerts JSONB NOT NULL DEFAULT '[]'::jsonb,
  result JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_calibration_run_projects_project
  ON gatekeeper_calibration_run_projects (project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_calibration_run_projects_run
  ON gatekeeper_calibration_run_projects (run_id, created_at DESC);
