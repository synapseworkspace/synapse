CREATE TABLE IF NOT EXISTS shared_memory_entries (
  id BIGSERIAL PRIMARY KEY,
  project_id TEXT NOT NULL,
  visibility_tier TEXT NOT NULL DEFAULT 'reviewed_team',
  status TEXT NOT NULL DEFAULT 'active',
  space_key TEXT,
  owner_agent_id TEXT,
  role_scope TEXT,
  team_scope TEXT,
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  content TEXT,
  entity_key TEXT,
  page_slug TEXT,
  delta_kind TEXT NOT NULL DEFAULT 'knowledge_change',
  action_hint TEXT,
  importance TEXT NOT NULL DEFAULT 'medium',
  source_kind TEXT NOT NULL DEFAULT 'agent_note',
  source_ref TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL DEFAULT 'ops_admin',
  updated_by TEXT NOT NULL DEFAULT 'ops_admin',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT shared_memory_entries_visibility_tier_check
    CHECK (visibility_tier IN ('reviewed_team', 'draft_private')),
  CONSTRAINT shared_memory_entries_status_check
    CHECK (status IN ('active', 'archived')),
  CONSTRAINT shared_memory_entries_importance_check
    CHECK (importance IN ('low', 'medium', 'high'))
);

CREATE INDEX IF NOT EXISTS idx_shared_memory_entries_project_tier_status
  ON shared_memory_entries (project_id, visibility_tier, status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_shared_memory_entries_project_space
  ON shared_memory_entries (project_id, space_key, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_shared_memory_entries_project_owner
  ON shared_memory_entries (project_id, owner_agent_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_shared_memory_entries_project_team_role
  ON shared_memory_entries (project_id, team_scope, role_scope, updated_at DESC);
