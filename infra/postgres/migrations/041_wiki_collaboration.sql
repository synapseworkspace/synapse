CREATE TABLE IF NOT EXISTS wiki_page_comments (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  page_id UUID NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
  author TEXT NOT NULL,
  body TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  deleted_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_wiki_page_comments_project_page_time
  ON wiki_page_comments(project_id, page_id, created_at DESC);

CREATE TABLE IF NOT EXISTS wiki_page_watchers (
  page_id UUID NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
  project_id TEXT NOT NULL,
  watcher TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (page_id, watcher)
);

CREATE INDEX IF NOT EXISTS idx_wiki_page_watchers_project_watcher
  ON wiki_page_watchers(project_id, watcher);
