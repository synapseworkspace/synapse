CREATE TABLE IF NOT EXISTS shared_memory_fanout_hooks (
  id BIGSERIAL PRIMARY KEY,
  project_id TEXT NOT NULL,
  name TEXT NOT NULL,
  endpoint_url TEXT NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  space_key TEXT,
  delivery_mode TEXT NOT NULL DEFAULT 'invalidation',
  headers JSONB NOT NULL DEFAULT '{}'::jsonb,
  timeout_seconds INTEGER NOT NULL DEFAULT 5,
  updated_by TEXT NOT NULL DEFAULT 'ops_admin',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT shared_memory_fanout_hooks_delivery_mode_check
    CHECK (delivery_mode IN ('invalidation', 'impact', 'publish_preview')),
  CONSTRAINT shared_memory_fanout_hooks_timeout_check
    CHECK (timeout_seconds BETWEEN 1 AND 60)
);

CREATE INDEX IF NOT EXISTS idx_shared_memory_fanout_hooks_project_enabled
  ON shared_memory_fanout_hooks (project_id, enabled, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_shared_memory_fanout_hooks_project_space
  ON shared_memory_fanout_hooks (project_id, space_key, enabled);
