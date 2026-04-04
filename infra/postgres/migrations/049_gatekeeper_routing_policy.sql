ALTER TABLE gatekeeper_project_configs
  ADD COLUMN IF NOT EXISTS routing_policy JSONB NOT NULL DEFAULT '{}'::jsonb;
