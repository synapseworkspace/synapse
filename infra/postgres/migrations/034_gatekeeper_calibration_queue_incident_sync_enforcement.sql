ALTER TABLE gatekeeper_calibration_queue_controls
  ADD COLUMN IF NOT EXISTS incident_preflight_enforcement_mode TEXT NOT NULL DEFAULT 'off',
  ADD COLUMN IF NOT EXISTS incident_preflight_pause_hours INTEGER NOT NULL DEFAULT 4,
  ADD COLUMN IF NOT EXISTS incident_preflight_critical_fail_threshold INTEGER NOT NULL DEFAULT 1;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'gatekeeper_calibration_queue_controls'::regclass
      AND conname = 'gatekeeper_calibration_queue_controls_preflight_enforcement_mode_check'
  ) THEN
    ALTER TABLE gatekeeper_calibration_queue_controls
      ADD CONSTRAINT gatekeeper_calibration_queue_controls_preflight_enforcement_mode_check
      CHECK (incident_preflight_enforcement_mode IN ('off', 'block', 'pause'));
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'gatekeeper_calibration_queue_controls'::regclass
      AND conname = 'gatekeeper_calibration_queue_controls_preflight_pause_hours_check'
  ) THEN
    ALTER TABLE gatekeeper_calibration_queue_controls
      ADD CONSTRAINT gatekeeper_calibration_queue_controls_preflight_pause_hours_check
      CHECK (incident_preflight_pause_hours >= 1 AND incident_preflight_pause_hours <= 168);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'gatekeeper_calibration_queue_controls'::regclass
      AND conname = 'gatekeeper_calibration_queue_controls_preflight_critical_threshold_check'
  ) THEN
    ALTER TABLE gatekeeper_calibration_queue_controls
      ADD CONSTRAINT gatekeeper_calibration_queue_controls_preflight_critical_threshold_check
      CHECK (incident_preflight_critical_fail_threshold >= 1 AND incident_preflight_critical_fail_threshold <= 100);
  END IF;
END $$;
