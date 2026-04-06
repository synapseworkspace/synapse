CREATE TABLE IF NOT EXISTS wiki_space_policy_audit (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  space_key TEXT NOT NULL,
  changed_by TEXT NOT NULL,
  before_policy JSONB NOT NULL DEFAULT '{}'::jsonb,
  after_policy JSONB NOT NULL DEFAULT '{}'::jsonb,
  changed_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
  reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wiki_space_policy_audit_project_space_created
  ON wiki_space_policy_audit (project_id, space_key, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_wiki_space_policy_audit_project_created
  ON wiki_space_policy_audit (project_id, created_at DESC);
