ALTER TABLE gatekeeper_project_configs
  ADD COLUMN IF NOT EXISTS llm_assist_enabled BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE gatekeeper_project_configs
  ADD COLUMN IF NOT EXISTS llm_provider TEXT NOT NULL DEFAULT 'openai';

ALTER TABLE gatekeeper_project_configs
  ADD COLUMN IF NOT EXISTS llm_model TEXT NOT NULL DEFAULT 'gpt-4.1-mini';

ALTER TABLE gatekeeper_project_configs
  ADD COLUMN IF NOT EXISTS llm_score_weight REAL NOT NULL DEFAULT 0.35 CHECK (llm_score_weight >= 0 AND llm_score_weight <= 1);

ALTER TABLE gatekeeper_project_configs
  ADD COLUMN IF NOT EXISTS llm_min_confidence REAL NOT NULL DEFAULT 0.65 CHECK (llm_min_confidence >= 0 AND llm_min_confidence <= 1);

ALTER TABLE gatekeeper_project_configs
  ADD COLUMN IF NOT EXISTS llm_timeout_ms INTEGER NOT NULL DEFAULT 3500 CHECK (llm_timeout_ms >= 200 AND llm_timeout_ms <= 20000);
