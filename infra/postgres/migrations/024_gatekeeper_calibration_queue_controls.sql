CREATE TABLE IF NOT EXISTS gatekeeper_calibration_queue_controls (
  project_id TEXT PRIMARY KEY,
  paused_until TIMESTAMPTZ,
  pause_reason TEXT,
  worker_lag_sla_minutes INTEGER NOT NULL DEFAULT 20,
  queue_depth_warn INTEGER NOT NULL DEFAULT 12,
  updated_by TEXT NOT NULL DEFAULT 'system',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'gatekeeper_calibration_queue_controls'::regclass
      AND conname = 'gatekeeper_calibration_queue_controls_worker_lag_sla_check'
  ) THEN
    ALTER TABLE gatekeeper_calibration_queue_controls
      ADD CONSTRAINT gatekeeper_calibration_queue_controls_worker_lag_sla_check
      CHECK (worker_lag_sla_minutes >= 1 AND worker_lag_sla_minutes <= 1440);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'gatekeeper_calibration_queue_controls'::regclass
      AND conname = 'gatekeeper_calibration_queue_controls_queue_depth_warn_check'
  ) THEN
    ALTER TABLE gatekeeper_calibration_queue_controls
      ADD CONSTRAINT gatekeeper_calibration_queue_controls_queue_depth_warn_check
      CHECK (queue_depth_warn >= 1 AND queue_depth_warn <= 50000);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_gatekeeper_calibration_queue_controls_paused_until
  ON gatekeeper_calibration_queue_controls (paused_until DESC)
  WHERE paused_until IS NOT NULL;
