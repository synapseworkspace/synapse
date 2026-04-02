DO $$
BEGIN
  -- Replace status check to support queued runs for async simulator execution.
  IF EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'agent_simulator_runs'::regclass
      AND conname = 'agent_simulator_runs_status_check'
  ) THEN
    ALTER TABLE agent_simulator_runs
      DROP CONSTRAINT agent_simulator_runs_status_check;
  END IF;

  ALTER TABLE agent_simulator_runs
    ADD CONSTRAINT agent_simulator_runs_status_check
    CHECK (status IN ('queued', 'running', 'completed', 'failed'));
END $$;
