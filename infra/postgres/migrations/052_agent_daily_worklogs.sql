CREATE TABLE IF NOT EXISTS agent_daily_worklogs (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  worklog_date DATE NOT NULL,
  summary JSONB NOT NULL DEFAULT '{}'::jsonb,
  markdown TEXT NOT NULL,
  generated_by TEXT,
  generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (project_id, agent_id, worklog_date)
);

CREATE INDEX IF NOT EXISTS idx_agent_daily_worklogs_project_date
  ON agent_daily_worklogs (project_id, worklog_date DESC, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_daily_worklogs_project_agent
  ON agent_daily_worklogs (project_id, agent_id, worklog_date DESC);
