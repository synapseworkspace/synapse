CREATE TABLE IF NOT EXISTS access_policy_decisions (
  id UUID PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  subject TEXT NOT NULL,
  email TEXT,
  tenant_id TEXT,
  auth_source TEXT NOT NULL,
  session_id TEXT,
  method TEXT NOT NULL,
  path TEXT NOT NULL,
  route_action TEXT,
  project_ids TEXT[] NOT NULL DEFAULT '{}'::text[],
  decision TEXT NOT NULL CHECK (decision IN ('allow', 'deny', 'bypass')),
  deny_code TEXT,
  required_roles TEXT[] NOT NULL DEFAULT '{}'::text[],
  actor_roles TEXT[] NOT NULL DEFAULT '{}'::text[],
  rbac_mode TEXT NOT NULL,
  tenancy_mode TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_access_policy_decisions_created
  ON access_policy_decisions (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_access_policy_decisions_decision_created
  ON access_policy_decisions (decision, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_access_policy_decisions_path_method
  ON access_policy_decisions (path, method);

CREATE INDEX IF NOT EXISTS idx_access_policy_decisions_projects_gin
  ON access_policy_decisions
  USING GIN (project_ids);
