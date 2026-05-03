CREATE TABLE IF NOT EXISTS shared_memory_runtime_acks (
  id BIGSERIAL PRIMARY KEY,
  project_id TEXT NOT NULL,
  hook_id BIGINT REFERENCES shared_memory_fanout_hooks(id) ON DELETE SET NULL,
  delivery_id BIGINT REFERENCES shared_memory_fanout_deliveries(id) ON DELETE SET NULL,
  delivery_correlation_id TEXT,
  runtime_id TEXT NOT NULL,
  space_key TEXT,
  dispatch_mode TEXT NOT NULL DEFAULT 'invalidation',
  ack_status TEXT NOT NULL DEFAULT 'accepted' CHECK (ack_status IN ('accepted', 'refreshed', 'ignored', 'failed')),
  invalidation_token TEXT,
  context_token TEXT,
  applied_change_at TIMESTAMPTZ,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_shared_memory_runtime_acks_project_created
  ON shared_memory_runtime_acks(project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_shared_memory_runtime_acks_project_runtime
  ON shared_memory_runtime_acks(project_id, runtime_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_shared_memory_runtime_acks_delivery
  ON shared_memory_runtime_acks(delivery_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_shared_memory_runtime_acks_correlation
  ON shared_memory_runtime_acks(project_id, delivery_correlation_id, created_at DESC);
