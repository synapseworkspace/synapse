DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'claims_valid_window_check'
  ) THEN
    ALTER TABLE claims
    ADD CONSTRAINT claims_valid_window_check
    CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_from <= valid_to)
    NOT VALID;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'wiki_statements_valid_window_check'
  ) THEN
    ALTER TABLE wiki_statements
    ADD CONSTRAINT wiki_statements_valid_window_check
    CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_from <= valid_to)
    NOT VALID;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_claims_project_valid_window
  ON claims (project_id, status, valid_from, valid_to);

CREATE INDEX IF NOT EXISTS idx_wiki_statements_project_valid_window
  ON wiki_statements (project_id, status, valid_from, valid_to);
