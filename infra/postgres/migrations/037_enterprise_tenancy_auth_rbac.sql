CREATE TABLE IF NOT EXISTS tenants (
  id UUID PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT,
  updated_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tenants_status ON tenants(status, created_at DESC);

CREATE TABLE IF NOT EXISTS tenant_memberships (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL,
  email TEXT,
  display_name TEXT,
  roles TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  status TEXT NOT NULL DEFAULT 'active',
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT,
  updated_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_tenant_memberships_user_status ON tenant_memberships(user_id, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_tenant_memberships_tenant_status ON tenant_memberships(tenant_id, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_tenant_memberships_roles_gin ON tenant_memberships USING GIN (roles);

CREATE TABLE IF NOT EXISTS tenant_projects (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  project_id TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'active',
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT,
  updated_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, project_id)
);

CREATE INDEX IF NOT EXISTS idx_tenant_projects_tenant_status ON tenant_projects(tenant_id, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_tenant_projects_project_status ON tenant_projects(project_id, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS auth_sessions (
  id UUID PRIMARY KEY,
  session_token_hash TEXT NOT NULL UNIQUE,
  subject TEXT NOT NULL,
  email TEXT,
  tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL,
  roles TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  auth_provider TEXT NOT NULL DEFAULT 'oidc',
  claims JSONB NOT NULL DEFAULT '{}'::jsonb,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ,
  last_seen_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_auth_sessions_subject ON auth_sessions(subject, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_tenant ON auth_sessions(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_expiry ON auth_sessions(expires_at, revoked_at);
