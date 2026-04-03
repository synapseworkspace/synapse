ALTER TABLE gatekeeper_project_configs
  ADD COLUMN IF NOT EXISTS publish_mode_default TEXT NOT NULL DEFAULT 'human_required'
    CHECK (publish_mode_default IN ('human_required', 'conditional', 'auto_publish'));

ALTER TABLE gatekeeper_project_configs
  ADD COLUMN IF NOT EXISTS publish_mode_by_category JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE gatekeeper_project_configs
  ADD COLUMN IF NOT EXISTS auto_publish_min_score REAL NOT NULL DEFAULT 0.9
    CHECK (auto_publish_min_score >= 0 AND auto_publish_min_score <= 1);

ALTER TABLE gatekeeper_project_configs
  ADD COLUMN IF NOT EXISTS auto_publish_min_sources INTEGER NOT NULL DEFAULT 3
    CHECK (auto_publish_min_sources >= 1);

ALTER TABLE gatekeeper_project_configs
  ADD COLUMN IF NOT EXISTS auto_publish_require_golden BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE gatekeeper_project_configs
  ADD COLUMN IF NOT EXISTS auto_publish_allow_conflicts BOOLEAN NOT NULL DEFAULT FALSE;
