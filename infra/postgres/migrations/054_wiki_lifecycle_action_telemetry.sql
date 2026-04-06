CREATE TABLE IF NOT EXISTS wiki_lifecycle_action_telemetry_snapshots (
  project_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  metric_kind TEXT NOT NULL CHECK (
    metric_kind IN ('empty_scope_action_shown', 'empty_scope_action_applied')
  ),
  action_key TEXT NOT NULL,
  counter_value BIGINT NOT NULL DEFAULT 0,
  source TEXT NOT NULL DEFAULT 'web_ui',
  observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (project_id, session_id, metric_kind, action_key)
);

CREATE INDEX IF NOT EXISTS idx_wiki_lifecycle_action_telemetry_snapshots_project_updated
  ON wiki_lifecycle_action_telemetry_snapshots (project_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS wiki_lifecycle_action_telemetry_daily (
  project_id TEXT NOT NULL,
  metric_date DATE NOT NULL,
  metric_kind TEXT NOT NULL CHECK (
    metric_kind IN ('empty_scope_action_shown', 'empty_scope_action_applied')
  ),
  action_key TEXT NOT NULL,
  total_count BIGINT NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (project_id, metric_date, metric_kind, action_key)
);

CREATE INDEX IF NOT EXISTS idx_wiki_lifecycle_action_telemetry_daily_project_date
  ON wiki_lifecycle_action_telemetry_daily (project_id, metric_date DESC);

CREATE INDEX IF NOT EXISTS idx_wiki_lifecycle_action_telemetry_daily_project_metric
  ON wiki_lifecycle_action_telemetry_daily (project_id, metric_kind, metric_date DESC);
