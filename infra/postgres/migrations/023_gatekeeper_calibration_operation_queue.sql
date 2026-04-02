DO $$
DECLARE
  status_check_name text;
BEGIN
  SELECT conname
  INTO status_check_name
  FROM pg_constraint
  WHERE conrelid = 'gatekeeper_calibration_operation_runs'::regclass
    AND contype = 'c'
    AND pg_get_constraintdef(oid) ILIKE '%status%';

  IF status_check_name IS NOT NULL THEN
    EXECUTE format(
      'ALTER TABLE gatekeeper_calibration_operation_runs DROP CONSTRAINT %I',
      status_check_name
    );
  END IF;
END $$;

ALTER TABLE gatekeeper_calibration_operation_runs
  ADD COLUMN IF NOT EXISTS mode TEXT NOT NULL DEFAULT 'sync',
  ADD COLUMN IF NOT EXISTS progress_percent NUMERIC(5,2) NOT NULL DEFAULT 0.0,
  ADD COLUMN IF NOT EXISTS progress_phase TEXT,
  ADD COLUMN IF NOT EXISTS attempt_no INTEGER NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS max_attempts INTEGER NOT NULL DEFAULT 3,
  ADD COLUMN IF NOT EXISTS retry_of UUID REFERENCES gatekeeper_calibration_operation_runs(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS cancel_requested BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS cancel_requested_by TEXT,
  ADD COLUMN IF NOT EXISTS cancel_requested_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS finished_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS worker_id TEXT,
  ADD COLUMN IF NOT EXISTS error_message TEXT;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'gatekeeper_calibration_operation_runs'::regclass
      AND conname = 'gatekeeper_calibration_operation_runs_status_check'
  ) THEN
    ALTER TABLE gatekeeper_calibration_operation_runs
      ADD CONSTRAINT gatekeeper_calibration_operation_runs_status_check
      CHECK (status IN ('queued', 'running', 'cancel_requested', 'succeeded', 'failed', 'canceled'));
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'gatekeeper_calibration_operation_runs'::regclass
      AND conname = 'gatekeeper_calibration_operation_runs_mode_check'
  ) THEN
    ALTER TABLE gatekeeper_calibration_operation_runs
      ADD CONSTRAINT gatekeeper_calibration_operation_runs_mode_check
      CHECK (mode IN ('sync', 'async'));
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'gatekeeper_calibration_operation_runs'::regclass
      AND conname = 'gatekeeper_calibration_operation_runs_attempt_no_check'
  ) THEN
    ALTER TABLE gatekeeper_calibration_operation_runs
      ADD CONSTRAINT gatekeeper_calibration_operation_runs_attempt_no_check
      CHECK (attempt_no >= 1 AND attempt_no <= 100);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'gatekeeper_calibration_operation_runs'::regclass
      AND conname = 'gatekeeper_calibration_operation_runs_max_attempts_check'
  ) THEN
    ALTER TABLE gatekeeper_calibration_operation_runs
      ADD CONSTRAINT gatekeeper_calibration_operation_runs_max_attempts_check
      CHECK (max_attempts >= 1 AND max_attempts <= 20);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_gatekeeper_calibration_operation_runs_project_status_created
  ON gatekeeper_calibration_operation_runs (project_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_calibration_operation_runs_status_created
  ON gatekeeper_calibration_operation_runs (status, created_at ASC);

CREATE TABLE IF NOT EXISTS gatekeeper_calibration_operation_events (
  id BIGSERIAL PRIMARY KEY,
  operation_run_id UUID NOT NULL REFERENCES gatekeeper_calibration_operation_runs(id) ON DELETE CASCADE,
  project_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  phase TEXT,
  message TEXT NOT NULL,
  progress_percent NUMERIC(5,2),
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_calibration_operation_events_run_id
  ON gatekeeper_calibration_operation_events (operation_run_id, id ASC);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_calibration_operation_events_project_created
  ON gatekeeper_calibration_operation_events (project_id, created_at DESC);
