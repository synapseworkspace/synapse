CREATE TABLE IF NOT EXISTS wiki_page_review_assignments (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  page_id UUID NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
  assignee TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'reviewer',
  status TEXT NOT NULL CHECK (status IN ('open', 'resolved')) DEFAULT 'open',
  note TEXT,
  due_at TIMESTAMPTZ,
  created_by TEXT NOT NULL,
  resolved_by TEXT,
  resolution_note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_wiki_page_review_assignments_project_page_status
  ON wiki_page_review_assignments(project_id, page_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_wiki_page_review_assignments_project_assignee_status
  ON wiki_page_review_assignments(project_id, assignee, status, created_at DESC);
