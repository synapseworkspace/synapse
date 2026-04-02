CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS events (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  agent_id TEXT,
  session_id TEXT,
  event_type TEXT NOT NULL,
  payload JSONB NOT NULL,
  observed_at TIMESTAMPTZ NOT NULL,
  received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_project_time ON events(project_id, observed_at DESC);

CREATE TABLE IF NOT EXISTS claims (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  entity_key TEXT NOT NULL,
  category TEXT NOT NULL,
  claim_text TEXT NOT NULL,
  confidence REAL,
  status TEXT NOT NULL DEFAULT 'draft',
  valid_from TIMESTAMPTZ,
  valid_to TIMESTAMPTZ,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_claims_project_entity ON claims(project_id, entity_key);

CREATE TABLE IF NOT EXISTS claim_proposals (
  claim_id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  claim_payload JSONB NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_claim_proposals_project ON claim_proposals(project_id, created_at DESC);
