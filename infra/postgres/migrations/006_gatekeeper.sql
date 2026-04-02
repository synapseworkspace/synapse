CREATE TABLE IF NOT EXISTS gatekeeper_decisions (
  claim_id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  tier TEXT NOT NULL CHECK (tier IN ('operational_memory', 'insight_candidate', 'golden_candidate')),
  score REAL NOT NULL,
  rationale TEXT NOT NULL,
  features JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_decisions_project_tier
  ON gatekeeper_decisions (project_id, tier, updated_at DESC);

