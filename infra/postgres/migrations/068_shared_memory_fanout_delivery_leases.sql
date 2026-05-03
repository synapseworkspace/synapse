ALTER TABLE shared_memory_fanout_deliveries
  ADD COLUMN IF NOT EXISTS lease_token TEXT,
  ADD COLUMN IF NOT EXISTS lease_owner TEXT,
  ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_shared_memory_fanout_deliveries_pending_lease
  ON shared_memory_fanout_deliveries(project_id, status, lease_expires_at)
  WHERE status = 'pending';
