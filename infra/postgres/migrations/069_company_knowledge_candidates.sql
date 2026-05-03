CREATE TABLE IF NOT EXISTS company_knowledge_candidates (
  id BIGSERIAL PRIMARY KEY,
  project_id TEXT NOT NULL,
  space_key TEXT NOT NULL,
  block_id TEXT NOT NULL,
  block_type TEXT NOT NULL,
  knowledge_state TEXT NOT NULL DEFAULT 'candidate',
  state_source TEXT NOT NULL DEFAULT 'computed',
  confidence TEXT NOT NULL DEFAULT 'medium',
  summary TEXT NOT NULL,
  evidence_basis TEXT,
  target_page_type TEXT,
  target_page_slug TEXT,
  promotion_path TEXT,
  contradiction_topic TEXT,
  note TEXT,
  reviewed_by TEXT,
  reviewed_at TIMESTAMPTZ,
  canonical_page_slug TEXT,
  source_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_by TEXT NOT NULL DEFAULT 'synapse_company_compiler',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT company_knowledge_candidates_unique_scope UNIQUE (project_id, space_key, block_id),
  CONSTRAINT company_knowledge_candidates_state_check
    CHECK (knowledge_state IN ('candidate', 'reviewed', 'canonical', 'stale', 'contradicted', 'superseded')),
  CONSTRAINT company_knowledge_candidates_state_source_check
    CHECK (state_source IN ('computed', 'manual')),
  CONSTRAINT company_knowledge_candidates_confidence_check
    CHECK (confidence IN ('low', 'medium', 'high', 'unknown'))
);

CREATE INDEX IF NOT EXISTS idx_company_knowledge_candidates_project_space
  ON company_knowledge_candidates (project_id, space_key, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_company_knowledge_candidates_state
  ON company_knowledge_candidates (project_id, knowledge_state, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_company_knowledge_candidates_target_page
  ON company_knowledge_candidates (project_id, target_page_type, target_page_slug);
