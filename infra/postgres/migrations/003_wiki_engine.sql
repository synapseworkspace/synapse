CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS wiki_pages (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  page_type TEXT NOT NULL,
  title TEXT NOT NULL,
  slug TEXT NOT NULL,
  entity_key TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('draft', 'published', 'archived')),
  current_version INTEGER NOT NULL DEFAULT 0,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(project_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_wiki_pages_project_entity
  ON wiki_pages(project_id, entity_key);

CREATE INDEX IF NOT EXISTS idx_wiki_pages_project_status
  ON wiki_pages(project_id, status);

CREATE TABLE IF NOT EXISTS wiki_page_aliases (
  page_id UUID NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
  alias_text TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (page_id, alias_text)
);

CREATE INDEX IF NOT EXISTS idx_wiki_page_aliases_trgm
  ON wiki_page_aliases USING gin (alias_text gin_trgm_ops);

CREATE TABLE IF NOT EXISTS wiki_page_versions (
  id UUID PRIMARY KEY,
  page_id UUID NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
  version INTEGER NOT NULL,
  markdown TEXT NOT NULL,
  ast_json JSONB NOT NULL DEFAULT '[]'::jsonb,
  source TEXT NOT NULL CHECK (source IN ('agent', 'human', 'system')),
  created_by TEXT,
  change_summary TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(page_id, version)
);

CREATE TABLE IF NOT EXISTS wiki_sections (
  page_id UUID NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
  section_key TEXT NOT NULL,
  heading TEXT NOT NULL,
  order_index INTEGER NOT NULL DEFAULT 0,
  statement_count INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (page_id, section_key)
);

CREATE TABLE IF NOT EXISTS wiki_statements (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  page_id UUID NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
  section_key TEXT NOT NULL,
  statement_text TEXT NOT NULL,
  normalized_text TEXT NOT NULL,
  claim_fingerprint TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('active', 'superseded')),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  valid_from TIMESTAMPTZ,
  valid_to TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wiki_statements_project_page
  ON wiki_statements(project_id, page_id);

CREATE INDEX IF NOT EXISTS idx_wiki_statements_fingerprint
  ON wiki_statements(project_id, claim_fingerprint);

CREATE INDEX IF NOT EXISTS idx_wiki_statements_text_trgm
  ON wiki_statements USING gin (normalized_text gin_trgm_ops);

CREATE TABLE IF NOT EXISTS wiki_claim_links (
  claim_id UUID NOT NULL,
  page_id UUID NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
  section_key TEXT NOT NULL,
  insertion_status TEXT NOT NULL CHECK (
    insertion_status IN ('new_statement', 'reinforcement', 'duplicate_ignored', 'conflict', 'rejected')
  ),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (claim_id, page_id, section_key)
);

CREATE TABLE IF NOT EXISTS wiki_conflicts (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  claim_id UUID NOT NULL,
  page_id UUID,
  conflicting_statement_id UUID REFERENCES wiki_statements(id) ON DELETE SET NULL,
  conflict_type TEXT NOT NULL,
  resolution_status TEXT NOT NULL CHECK (resolution_status IN ('open', 'resolved', 'dismissed')),
  details JSONB NOT NULL DEFAULT '{}'::jsonb,
  resolved_by TEXT,
  resolved_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wiki_conflicts_project_status
  ON wiki_conflicts(project_id, resolution_status, created_at DESC);

CREATE TABLE IF NOT EXISTS wiki_draft_changes (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  claim_id UUID NOT NULL,
  page_id UUID REFERENCES wiki_pages(id) ON DELETE SET NULL,
  section_key TEXT,
  decision TEXT NOT NULL CHECK (
    decision IN (
      'new_page',
      'new_section',
      'new_statement',
      'reinforcement',
      'duplicate_ignored',
      'conflict'
    )
  ),
  markdown_patch TEXT NOT NULL,
  semantic_diff JSONB NOT NULL DEFAULT '{}'::jsonb,
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  confidence REAL NOT NULL,
  rationale TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('pending_review', 'blocked_conflict', 'approved', 'rejected')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(claim_id)
);

CREATE INDEX IF NOT EXISTS idx_wiki_draft_changes_project_status
  ON wiki_draft_changes(project_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS knowledge_snapshots (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  published_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by TEXT,
  note TEXT
);

CREATE INDEX IF NOT EXISTS idx_knowledge_snapshots_project_time
  ON knowledge_snapshots(project_id, published_at DESC);

CREATE TABLE IF NOT EXISTS knowledge_snapshot_pages (
  snapshot_id UUID NOT NULL REFERENCES knowledge_snapshots(id) ON DELETE CASCADE,
  page_id UUID NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
  page_version INTEGER NOT NULL,
  PRIMARY KEY (snapshot_id, page_id)
);
