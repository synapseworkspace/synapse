CREATE TABLE IF NOT EXISTS gatekeeper_calibration_queue_incident_sync_schedules (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  name TEXT NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  preset TEXT NOT NULL CHECK (preset IN ('hourly', 'every_4h', 'daily', 'weekly', 'custom')),
  interval_minutes INTEGER NOT NULL DEFAULT 60 CHECK (interval_minutes >= 5 AND interval_minutes <= 10080),
  window_hours INTEGER NOT NULL DEFAULT 24 CHECK (window_hours >= 1 AND window_hours <= 168),
  batch_size INTEGER NOT NULL DEFAULT 50 CHECK (batch_size >= 1 AND batch_size <= 200),
  sync_limit INTEGER NOT NULL DEFAULT 200 CHECK (sync_limit >= 1 AND sync_limit <= 200),
  dry_run BOOLEAN NOT NULL DEFAULT FALSE,
  force_resolve BOOLEAN NOT NULL DEFAULT FALSE,
  preflight_enforcement_mode TEXT NOT NULL DEFAULT 'inherit' CHECK (preflight_enforcement_mode IN ('inherit', 'off', 'block', 'pause')),
  preflight_pause_hours INTEGER CHECK (preflight_pause_hours IS NULL OR (preflight_pause_hours >= 1 AND preflight_pause_hours <= 168)),
  preflight_critical_fail_threshold INTEGER CHECK (
    preflight_critical_fail_threshold IS NULL OR (
      preflight_critical_fail_threshold >= 1 AND preflight_critical_fail_threshold <= 100
    )
  ),
  preflight_include_run_before_live_sync_only BOOLEAN NOT NULL DEFAULT TRUE,
  preflight_record_audit BOOLEAN NOT NULL DEFAULT TRUE,
  requested_by TEXT NOT NULL DEFAULT 'incident_sync_scheduler',
  next_run_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_run_at TIMESTAMPTZ,
  last_status TEXT CHECK (last_status IN ('ok', 'failed', 'partial_failure', 'skipped')),
  last_run_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (project_id, name)
);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_queue_incident_sync_schedules_due
  ON gatekeeper_calibration_queue_incident_sync_schedules (enabled, next_run_at ASC, project_id);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_queue_incident_sync_schedules_project
  ON gatekeeper_calibration_queue_incident_sync_schedules (project_id, updated_at DESC);
