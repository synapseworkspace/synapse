CREATE TABLE IF NOT EXISTS legacy_import_sources (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  source_type TEXT NOT NULL CHECK (source_type IN ('local_dir', 'notion_root_page', 'notion_database')),
  source_ref TEXT NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  sync_interval_minutes INTEGER NOT NULL DEFAULT 1440 CHECK (sync_interval_minutes >= 15 AND sync_interval_minutes <= 10080),
  next_run_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_run_at TIMESTAMPTZ,
  last_success_at TIMESTAMPTZ,
  config JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT,
  updated_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (project_id, source_type, source_ref)
);

CREATE INDEX IF NOT EXISTS idx_legacy_import_sources_due
  ON legacy_import_sources (enabled, next_run_at ASC, project_id);

CREATE TABLE IF NOT EXISTS legacy_import_sync_runs (
  id UUID PRIMARY KEY,
  source_id UUID NOT NULL REFERENCES legacy_import_sources(id) ON DELETE CASCADE,
  project_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed', 'skipped')),
  trigger_mode TEXT NOT NULL CHECK (trigger_mode IN ('scheduled', 'manual')),
  requested_by TEXT,
  records_collected INTEGER NOT NULL DEFAULT 0,
  records_uploaded INTEGER NOT NULL DEFAULT 0,
  skipped_files_count INTEGER NOT NULL DEFAULT 0,
  warnings_count INTEGER NOT NULL DEFAULT 0,
  batch_id UUID,
  error_message TEXT,
  summary JSONB NOT NULL DEFAULT '{}'::jsonb,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_legacy_import_sync_runs_source_time
  ON legacy_import_sync_runs (source_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_legacy_import_sync_runs_status_time
  ON legacy_import_sync_runs (status, created_at ASC);

CREATE TABLE IF NOT EXISTS legacy_import_source_fingerprints (
  source_id UUID NOT NULL REFERENCES legacy_import_sources(id) ON DELETE CASCADE,
  content_fingerprint TEXT NOT NULL,
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  seen_count INTEGER NOT NULL DEFAULT 1,
  last_run_id UUID,
  PRIMARY KEY (source_id, content_fingerprint)
);

CREATE INDEX IF NOT EXISTS idx_legacy_import_source_fingerprints_last_seen
  ON legacy_import_source_fingerprints (source_id, last_seen_at DESC);
