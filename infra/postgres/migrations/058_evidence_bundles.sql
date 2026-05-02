CREATE TABLE IF NOT EXISTS evidence_bundles (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  bundle_key TEXT NOT NULL,
  bundle_type TEXT NOT NULL,
  suggested_page_type TEXT,
  entity_key TEXT NOT NULL,
  bundle_status TEXT NOT NULL CHECK (bundle_status IN ('observed', 'candidate', 'ready', 'suppressed')),
  support_count INTEGER NOT NULL DEFAULT 0,
  repeated_claims INTEGER NOT NULL DEFAULT 0,
  source_diversity INTEGER NOT NULL DEFAULT 0,
  evidence_count INTEGER NOT NULL DEFAULT 0,
  first_seen_at TIMESTAMPTZ,
  last_seen_at TIMESTAMPTZ,
  latest_claim_at TIMESTAMPTZ,
  quality_score REAL NOT NULL DEFAULT 0,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(project_id, bundle_key)
);

CREATE INDEX IF NOT EXISTS idx_evidence_bundles_project_status
  ON evidence_bundles(project_id, bundle_status, last_seen_at DESC);

CREATE INDEX IF NOT EXISTS idx_evidence_bundles_project_type
  ON evidence_bundles(project_id, bundle_type, quality_score DESC);

CREATE INDEX IF NOT EXISTS idx_evidence_bundles_project_entity
  ON evidence_bundles(project_id, entity_key);

CREATE TABLE IF NOT EXISTS evidence_bundle_claim_links (
  bundle_id UUID NOT NULL REFERENCES evidence_bundles(id) ON DELETE CASCADE,
  claim_id UUID NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
  project_id TEXT NOT NULL,
  relationship TEXT NOT NULL DEFAULT 'supporting_claim',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (bundle_id, claim_id)
);

CREATE INDEX IF NOT EXISTS idx_evidence_bundle_claim_links_project
  ON evidence_bundle_claim_links(project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_evidence_bundle_claim_links_claim
  ON evidence_bundle_claim_links(claim_id);
