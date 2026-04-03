CREATE TABLE IF NOT EXISTS source_ownership_policies (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  domain TEXT NOT NULL CHECK (domain IN ('runtime_memory', 'ops_kb_static', 'synapse_wiki')),
  write_master TEXT NOT NULL,
  allowed_source_systems JSONB NOT NULL DEFAULT '[]'::jsonb,
  enforcement_mode TEXT NOT NULL DEFAULT 'enforce'
    CHECK (enforcement_mode IN ('off', 'advisory', 'enforce')),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (project_id, domain)
);

CREATE INDEX IF NOT EXISTS idx_source_ownership_policies_project
  ON source_ownership_policies (project_id, domain);
