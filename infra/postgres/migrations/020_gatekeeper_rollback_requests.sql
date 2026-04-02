CREATE TABLE IF NOT EXISTS gatekeeper_config_rollback_requests (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  snapshot_id UUID NOT NULL REFERENCES gatekeeper_config_snapshots(id) ON DELETE RESTRICT,
  status TEXT NOT NULL CHECK (status IN ('pending_approval', 'applied', 'rejected', 'failed')),
  requested_by TEXT NOT NULL,
  required_approvals INTEGER NOT NULL DEFAULT 1 CHECK (required_approvals >= 1 AND required_approvals <= 5),
  approvals JSONB NOT NULL DEFAULT '[]'::jsonb,
  preview JSONB NOT NULL DEFAULT '{}'::jsonb,
  note TEXT,
  rejection_reason TEXT,
  applied_by TEXT,
  applied_snapshot_id UUID REFERENCES gatekeeper_config_snapshots(id) ON DELETE SET NULL,
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_rollback_requests_project_status
  ON gatekeeper_config_rollback_requests (project_id, status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_rollback_requests_snapshot
  ON gatekeeper_config_rollback_requests (snapshot_id, created_at DESC);
