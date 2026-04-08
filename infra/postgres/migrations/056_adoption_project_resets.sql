CREATE TABLE IF NOT EXISTS adoption_project_resets (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  requested_by TEXT NOT NULL,
  reason TEXT,
  scopes JSONB NOT NULL DEFAULT '[]'::jsonb,
  dry_run BOOLEAN NOT NULL DEFAULT TRUE,
  status TEXT NOT NULL CHECK (status IN ('dry_run', 'completed', 'failed')),
  rows_preview JSONB NOT NULL DEFAULT '{}'::jsonb,
  rows_deleted JSONB NOT NULL DEFAULT '{}'::jsonb,
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_adoption_project_resets_project_created
  ON adoption_project_resets (project_id, created_at DESC);
