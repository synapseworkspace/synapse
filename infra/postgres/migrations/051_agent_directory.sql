CREATE TABLE IF NOT EXISTS agent_directory_profiles (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  display_name TEXT NOT NULL,
  team TEXT,
  role TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'idle', 'paused', 'offline', 'retired')),
  responsibilities JSONB NOT NULL DEFAULT '[]'::jsonb,
  tools JSONB NOT NULL DEFAULT '[]'::jsonb,
  data_sources JSONB NOT NULL DEFAULT '[]'::jsonb,
  limits JSONB NOT NULL DEFAULT '[]'::jsonb,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT,
  updated_by TEXT,
  last_seen_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (project_id, agent_id)
);

CREATE INDEX IF NOT EXISTS idx_agent_directory_profiles_project_status
  ON agent_directory_profiles (project_id, status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_directory_profiles_project_team
  ON agent_directory_profiles (project_id, team, role);
