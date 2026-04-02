CREATE INDEX IF NOT EXISTS idx_wiki_pages_project_status_entity_lower
  ON wiki_pages (project_id, status, (lower(entity_key)));

CREATE INDEX IF NOT EXISTS idx_wiki_pages_title_trgm_lower
  ON wiki_pages USING gin (lower(title) gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_wiki_pages_slug_trgm_lower
  ON wiki_pages USING gin (lower(slug) gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_claims_project_fingerprint_updated_at
  ON claims (project_id, claim_fingerprint, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_wiki_statements_project_active_created
  ON wiki_statements (project_id, created_at DESC)
  WHERE status = 'active';
