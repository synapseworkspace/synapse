CREATE TABLE IF NOT EXISTS knowledge_daily_metrics (
  project_id TEXT NOT NULL,
  metric_date DATE NOT NULL,
  claims_created INTEGER NOT NULL DEFAULT 0,
  drafts_created INTEGER NOT NULL DEFAULT 0,
  drafts_approved INTEGER NOT NULL DEFAULT 0,
  drafts_rejected INTEGER NOT NULL DEFAULT 0,
  statements_added INTEGER NOT NULL DEFAULT 0,
  conflicts_opened INTEGER NOT NULL DEFAULT 0,
  conflicts_resolved INTEGER NOT NULL DEFAULT 0,
  pending_drafts INTEGER NOT NULL DEFAULT 0,
  open_conflicts INTEGER NOT NULL DEFAULT 0,
  pages_touched INTEGER NOT NULL DEFAULT 0,
  knowledge_velocity REAL NOT NULL DEFAULT 0,
  computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (project_id, metric_date)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_daily_metrics_date
  ON knowledge_daily_metrics (metric_date DESC, project_id);

CREATE TABLE IF NOT EXISTS intelligence_digests (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  digest_kind TEXT NOT NULL CHECK (digest_kind IN ('daily', 'weekly')),
  digest_date DATE NOT NULL,
  period_start TIMESTAMPTZ NOT NULL,
  period_end TIMESTAMPTZ NOT NULL,
  status TEXT NOT NULL DEFAULT 'ready' CHECK (status IN ('ready', 'sent', 'failed')),
  headline TEXT NOT NULL,
  summary_markdown TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  generated_by TEXT NOT NULL DEFAULT 'system',
  generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  sent_at TIMESTAMPTZ,
  UNIQUE (project_id, digest_kind, digest_date)
);

CREATE INDEX IF NOT EXISTS idx_intelligence_digests_project_kind_date
  ON intelligence_digests (project_id, digest_kind, digest_date DESC);

