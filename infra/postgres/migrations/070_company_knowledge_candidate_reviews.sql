CREATE TABLE IF NOT EXISTS company_knowledge_candidate_reviews (
  id BIGSERIAL PRIMARY KEY,
  candidate_id BIGINT NOT NULL REFERENCES company_knowledge_candidates(id) ON DELETE CASCADE,
  project_id TEXT NOT NULL,
  action_kind TEXT NOT NULL,
  knowledge_state_before TEXT,
  knowledge_state_after TEXT,
  note TEXT,
  contradiction_decision TEXT,
  preferred_source_label TEXT,
  resolution_note TEXT,
  promote_to_wiki BOOLEAN NOT NULL DEFAULT FALSE,
  wiki_page_slug TEXT,
  reviewed_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_company_knowledge_candidate_reviews_candidate
  ON company_knowledge_candidate_reviews (candidate_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_company_knowledge_candidate_reviews_project
  ON company_knowledge_candidate_reviews (project_id, created_at DESC);
