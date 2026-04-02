CREATE TABLE IF NOT EXISTS memory_backfill_batches (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  source_system TEXT NOT NULL,
  agent_id TEXT,
  session_id TEXT,
  status TEXT NOT NULL CHECK (status IN ('collecting', 'ready', 'processing', 'completed', 'failed')),
  total_items INTEGER NOT NULL DEFAULT 0,
  inserted_events INTEGER NOT NULL DEFAULT 0,
  processed_events INTEGER NOT NULL DEFAULT 0,
  generated_claims INTEGER NOT NULL DEFAULT 0,
  cursor TEXT,
  created_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memory_backfill_batches_project_status
  ON memory_backfill_batches (project_id, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS event_pipeline_state (
  event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  pipeline TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('processing', 'completed', 'failed')),
  last_error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (event_id, pipeline)
);

CREATE INDEX IF NOT EXISTS idx_event_pipeline_state_pipeline_status
  ON event_pipeline_state (pipeline, status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_events_project_type_time
  ON events (project_id, event_type, observed_at DESC);

