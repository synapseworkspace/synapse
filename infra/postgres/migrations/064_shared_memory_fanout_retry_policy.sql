ALTER TABLE shared_memory_fanout_hooks
  ADD COLUMN IF NOT EXISTS retry_max_attempts INTEGER NOT NULL DEFAULT 3,
  ADD COLUMN IF NOT EXISTS retry_backoff_seconds INTEGER NOT NULL DEFAULT 300;

ALTER TABLE shared_memory_fanout_hooks
  DROP CONSTRAINT IF EXISTS shared_memory_fanout_hooks_retry_max_attempts_check;

ALTER TABLE shared_memory_fanout_hooks
  DROP CONSTRAINT IF EXISTS shared_memory_fanout_hooks_retry_backoff_seconds_check;

ALTER TABLE shared_memory_fanout_hooks
  ADD CONSTRAINT shared_memory_fanout_hooks_retry_max_attempts_check
  CHECK (retry_max_attempts BETWEEN 1 AND 10);

ALTER TABLE shared_memory_fanout_hooks
  ADD CONSTRAINT shared_memory_fanout_hooks_retry_backoff_seconds_check
  CHECK (retry_backoff_seconds BETWEEN 30 AND 86400);

ALTER TABLE shared_memory_fanout_deliveries
  ADD COLUMN IF NOT EXISTS attempt_no INTEGER NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS max_attempts INTEGER NOT NULL DEFAULT 3,
  ADD COLUMN IF NOT EXISTS next_retry_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS last_retry_at TIMESTAMPTZ;

ALTER TABLE shared_memory_fanout_deliveries
  DROP CONSTRAINT IF EXISTS shared_memory_fanout_deliveries_attempt_no_check;

ALTER TABLE shared_memory_fanout_deliveries
  DROP CONSTRAINT IF EXISTS shared_memory_fanout_deliveries_max_attempts_check;

ALTER TABLE shared_memory_fanout_deliveries
  ADD CONSTRAINT shared_memory_fanout_deliveries_attempt_no_check
  CHECK (attempt_no BETWEEN 1 AND 20);

ALTER TABLE shared_memory_fanout_deliveries
  ADD CONSTRAINT shared_memory_fanout_deliveries_max_attempts_check
  CHECK (max_attempts BETWEEN 1 AND 20);

CREATE INDEX IF NOT EXISTS idx_shared_memory_fanout_deliveries_due_retries
  ON shared_memory_fanout_deliveries (project_id, status, next_retry_at);
