CREATE TABLE IF NOT EXISTS wiki_uploads (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  page_id UUID REFERENCES wiki_pages(id) ON DELETE SET NULL,
  filename TEXT NOT NULL,
  content_type TEXT,
  size_bytes BIGINT NOT NULL CHECK (size_bytes >= 0),
  checksum_sha256 TEXT NOT NULL,
  storage BYTEA NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wiki_uploads_project_created_at
  ON wiki_uploads(project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_wiki_uploads_project_page_created_at
  ON wiki_uploads(project_id, page_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_wiki_uploads_project_checksum
  ON wiki_uploads(project_id, checksum_sha256);
