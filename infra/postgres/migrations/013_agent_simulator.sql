CREATE TABLE IF NOT EXISTS agent_simulator_runs (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
  mode TEXT NOT NULL CHECK (mode IN ('policy_replay')),
  created_by TEXT NOT NULL DEFAULT 'system',
  config JSONB NOT NULL DEFAULT '{}'::jsonb,
  result JSONB NOT NULL DEFAULT '{}'::jsonb,
  sessions_scanned INTEGER NOT NULL DEFAULT 0,
  findings_total INTEGER NOT NULL DEFAULT 0,
  error_message TEXT,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_simulator_runs_project_time
  ON agent_simulator_runs (project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_simulator_runs_project_status
  ON agent_simulator_runs (project_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS agent_simulator_findings (
  id UUID PRIMARY KEY,
  run_id UUID NOT NULL REFERENCES agent_simulator_runs(id) ON DELETE CASCADE,
  project_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  policy_id TEXT NOT NULL,
  entity_key TEXT,
  category TEXT,
  impact_kind TEXT NOT NULL,
  severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
  impact_score REAL NOT NULL,
  rationale TEXT NOT NULL,
  evidence_excerpt TEXT,
  session_first_seen TIMESTAMPTZ,
  session_last_seen TIMESTAMPTZ,
  session_event_count INTEGER NOT NULL DEFAULT 0,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_simulator_findings_run_score
  ON agent_simulator_findings (run_id, impact_score DESC, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_simulator_findings_project_severity
  ON agent_simulator_findings (project_id, severity, created_at DESC);
