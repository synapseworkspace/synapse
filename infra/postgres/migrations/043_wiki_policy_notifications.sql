CREATE TABLE IF NOT EXISTS wiki_space_policies (
  project_id TEXT NOT NULL,
  space_key TEXT NOT NULL,
  write_mode TEXT NOT NULL CHECK (write_mode IN ('open', 'owners_only')) DEFAULT 'open',
  comment_mode TEXT NOT NULL CHECK (comment_mode IN ('open', 'owners_only')) DEFAULT 'open',
  review_assignment_required BOOLEAN NOT NULL DEFAULT FALSE,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (project_id, space_key)
);

CREATE TABLE IF NOT EXISTS wiki_space_owners (
  project_id TEXT NOT NULL,
  space_key TEXT NOT NULL,
  owner TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'owner',
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (project_id, space_key, owner)
);

CREATE INDEX IF NOT EXISTS idx_wiki_space_owners_project_owner
  ON wiki_space_owners(project_id, owner);

CREATE TABLE IF NOT EXISTS wiki_page_owners (
  project_id TEXT NOT NULL,
  page_id UUID NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
  owner TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'editor',
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (page_id, owner)
);

CREATE INDEX IF NOT EXISTS idx_wiki_page_owners_project_owner
  ON wiki_page_owners(project_id, owner);

CREATE TABLE IF NOT EXISTS wiki_notifications (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  recipient TEXT NOT NULL,
  actor TEXT,
  kind TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT,
  link TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  status TEXT NOT NULL CHECK (status IN ('unread', 'read')) DEFAULT 'unread',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  read_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_wiki_notifications_recipient_status
  ON wiki_notifications(project_id, recipient, status, created_at DESC);
