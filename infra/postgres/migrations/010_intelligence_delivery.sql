CREATE TABLE IF NOT EXISTS intelligence_delivery_targets (
  id UUID PRIMARY KEY,
  project_id TEXT NOT NULL,
  channel TEXT NOT NULL CHECK (channel IN ('slack_webhook', 'email_smtp')),
  target TEXT NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  config JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT,
  updated_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (project_id, channel, target)
);

CREATE INDEX IF NOT EXISTS idx_intelligence_delivery_targets_project
  ON intelligence_delivery_targets (project_id, enabled, updated_at DESC);

CREATE TABLE IF NOT EXISTS intelligence_delivery_attempts (
  id UUID PRIMARY KEY,
  digest_id UUID NOT NULL REFERENCES intelligence_digests(id) ON DELETE CASCADE,
  project_id TEXT NOT NULL,
  channel TEXT NOT NULL,
  target TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('sent', 'failed', 'skipped')),
  provider_message_id TEXT,
  error_message TEXT,
  response_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  attempted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_intelligence_delivery_attempts_digest
  ON intelligence_delivery_attempts (digest_id, attempted_at DESC);

CREATE INDEX IF NOT EXISTS idx_intelligence_delivery_attempts_project
  ON intelligence_delivery_attempts (project_id, attempted_at DESC);

