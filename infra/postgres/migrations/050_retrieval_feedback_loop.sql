CREATE TABLE IF NOT EXISTS wiki_retrieval_feedback (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  claim_id UUID,
  page_id UUID REFERENCES wiki_pages(id) ON DELETE SET NULL,
  feedback TEXT NOT NULL CHECK (feedback IN ('positive', 'negative', 'neutral')),
  usefulness_score REAL CHECK (usefulness_score IS NULL OR (usefulness_score >= -1.0 AND usefulness_score <= 1.0)),
  query_text TEXT,
  session_id TEXT,
  source_system TEXT NOT NULL DEFAULT 'unknown',
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wiki_retrieval_feedback_project_time
  ON wiki_retrieval_feedback(project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_wiki_retrieval_feedback_project_claim_time
  ON wiki_retrieval_feedback(project_id, claim_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_wiki_retrieval_feedback_project_page_time
  ON wiki_retrieval_feedback(project_id, page_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_wiki_retrieval_feedback_project_feedback
  ON wiki_retrieval_feedback(project_id, feedback, created_at DESC);
