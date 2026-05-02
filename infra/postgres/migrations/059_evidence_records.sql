CREATE TABLE IF NOT EXISTS evidence_records (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  claim_id UUID REFERENCES claims(id) ON DELETE CASCADE,
  bundle_key TEXT,
  event_id TEXT,
  entity_key TEXT NOT NULL,
  category TEXT,
  source_type TEXT NOT NULL,
  source_id TEXT NOT NULL,
  source_system TEXT,
  source_shape TEXT NOT NULL,
  volatility_class TEXT NOT NULL CHECK (volatility_class IN ('ephemeral', 'session', 'durable', 'authoritative')),
  pii_level TEXT NOT NULL CHECK (pii_level IN ('none', 'possible', 'high')),
  transactionality TEXT NOT NULL CHECK (transactionality IN ('transactional', 'aggregate', 'reference', 'policy', 'unknown')),
  ingestion_classification TEXT,
  knowledge_taxonomy_class TEXT,
  normalized_target_type TEXT,
  evidence_role TEXT NOT NULL CHECK (evidence_role IN ('supporting', 'derived', 'suppressed')),
  content_excerpt TEXT,
  observed_at TIMESTAMPTZ,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (project_id, claim_id, source_type, source_id, evidence_role)
);

CREATE INDEX IF NOT EXISTS idx_evidence_records_project_observed
  ON evidence_records(project_id, observed_at DESC);

CREATE INDEX IF NOT EXISTS idx_evidence_records_project_bundle
  ON evidence_records(project_id, bundle_key, observed_at DESC);

CREATE INDEX IF NOT EXISTS idx_evidence_records_project_shape
  ON evidence_records(project_id, source_shape, volatility_class, pii_level, observed_at DESC);

CREATE INDEX IF NOT EXISTS idx_evidence_records_project_taxonomy
  ON evidence_records(project_id, knowledge_taxonomy_class, normalized_target_type, observed_at DESC);

CREATE INDEX IF NOT EXISTS idx_evidence_records_project_source
  ON evidence_records(project_id, source_system, source_type, observed_at DESC);
