CREATE TABLE IF NOT EXISTS moderation_actions (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  draft_id UUID NOT NULL REFERENCES wiki_draft_changes(id) ON DELETE CASCADE,
  claim_id UUID,
  page_id UUID REFERENCES wiki_pages(id) ON DELETE SET NULL,
  action_type TEXT NOT NULL CHECK (action_type IN ('approve', 'reject')),
  reviewed_by TEXT NOT NULL,
  decision_before TEXT,
  decision_after TEXT,
  draft_status_before TEXT,
  draft_status_after TEXT,
  note TEXT,
  reason TEXT,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  result JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_moderation_actions_project_time
  ON moderation_actions (project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_moderation_actions_draft
  ON moderation_actions (draft_id, created_at DESC);

CREATE TABLE IF NOT EXISTS gatekeeper_project_configs (
  project_id TEXT PRIMARY KEY,
  min_sources_for_golden INTEGER NOT NULL DEFAULT 3 CHECK (min_sources_for_golden >= 2),
  conflict_free_days INTEGER NOT NULL DEFAULT 7 CHECK (conflict_free_days >= 1),
  min_score_for_golden REAL NOT NULL DEFAULT 0.72 CHECK (min_score_for_golden >= 0 AND min_score_for_golden <= 1),
  operational_short_text_len INTEGER NOT NULL DEFAULT 32 CHECK (operational_short_text_len >= 8),
  operational_short_token_len INTEGER NOT NULL DEFAULT 5 CHECK (operational_short_token_len >= 1),
  updated_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

