ALTER TABLE shared_memory_fanout_deliveries
  ADD COLUMN IF NOT EXISTS scheduled_for TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS processing_started_at TIMESTAMPTZ;

UPDATE shared_memory_fanout_deliveries
SET scheduled_for = created_at
WHERE scheduled_for IS NULL
  AND status = 'pending';

CREATE INDEX IF NOT EXISTS idx_shared_memory_fanout_deliveries_pending_due
  ON shared_memory_fanout_deliveries(project_id, status, scheduled_for)
  WHERE status = 'pending';
