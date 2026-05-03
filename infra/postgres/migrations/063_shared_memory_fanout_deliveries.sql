CREATE TABLE IF NOT EXISTS shared_memory_fanout_deliveries (
  id BIGSERIAL PRIMARY KEY,
  project_id TEXT NOT NULL,
  hook_id BIGINT NOT NULL REFERENCES shared_memory_fanout_hooks(id) ON DELETE CASCADE,
  dispatch_mode TEXT NOT NULL,
  status TEXT NOT NULL,
  dry_run BOOLEAN NOT NULL DEFAULT TRUE,
  space_key TEXT,
  requested_by TEXT,
  retry_of BIGINT REFERENCES shared_memory_fanout_deliveries(id) ON DELETE SET NULL,
  request_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  response_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  http_status INTEGER,
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  CONSTRAINT shared_memory_fanout_deliveries_dispatch_mode_check
    CHECK (dispatch_mode IN ('invalidation', 'impact', 'publish_preview')),
  CONSTRAINT shared_memory_fanout_deliveries_status_check
    CHECK (status IN ('planned', 'pending', 'delivered', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_shared_memory_fanout_deliveries_project_created
  ON shared_memory_fanout_deliveries (project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_shared_memory_fanout_deliveries_hook_created
  ON shared_memory_fanout_deliveries (hook_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_shared_memory_fanout_deliveries_project_status
  ON shared_memory_fanout_deliveries (project_id, status, created_at DESC);
