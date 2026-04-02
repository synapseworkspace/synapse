CREATE TABLE IF NOT EXISTS synapse_tasks (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  status TEXT NOT NULL CHECK (status IN ('todo', 'in_progress', 'blocked', 'done', 'canceled')),
  priority TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'critical')),
  source TEXT NOT NULL DEFAULT 'human' CHECK (source IN ('agent', 'human', 'system')),
  assignee TEXT,
  entity_key TEXT,
  category TEXT,
  due_at TIMESTAMPTZ,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT,
  updated_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_synapse_tasks_project_status_updated
  ON synapse_tasks (project_id, status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_synapse_tasks_project_assignee
  ON synapse_tasks (project_id, assignee, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_synapse_tasks_project_entity
  ON synapse_tasks (project_id, entity_key, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_synapse_tasks_project_due
  ON synapse_tasks (project_id, due_at ASC);

CREATE TABLE IF NOT EXISTS synapse_task_events (
  id UUID PRIMARY KEY,
  task_id UUID NOT NULL REFERENCES synapse_tasks(id) ON DELETE CASCADE,
  project_id TEXT NOT NULL,
  event_type TEXT NOT NULL CHECK (event_type IN ('created', 'updated', 'status_changed', 'comment', 'link_added')),
  actor TEXT,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_synapse_task_events_task_time
  ON synapse_task_events (task_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_synapse_task_events_project_time
  ON synapse_task_events (project_id, created_at DESC);

CREATE TABLE IF NOT EXISTS synapse_task_links (
  id UUID PRIMARY KEY,
  task_id UUID NOT NULL REFERENCES synapse_tasks(id) ON DELETE CASCADE,
  project_id TEXT NOT NULL,
  link_type TEXT NOT NULL CHECK (link_type IN ('claim', 'draft', 'page', 'event', 'external')),
  link_ref TEXT NOT NULL,
  note TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(task_id, link_type, link_ref)
);

CREATE INDEX IF NOT EXISTS idx_synapse_task_links_task
  ON synapse_task_links (task_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_synapse_task_links_project
  ON synapse_task_links (project_id, link_type, created_at DESC);
