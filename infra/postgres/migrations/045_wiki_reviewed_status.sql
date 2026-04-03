DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'wiki_pages_status_check'
      AND conrelid = 'wiki_pages'::regclass
  ) THEN
    ALTER TABLE wiki_pages
      DROP CONSTRAINT wiki_pages_status_check;
  END IF;
END $$;

ALTER TABLE wiki_pages
  ADD CONSTRAINT wiki_pages_status_check
  CHECK (status IN ('draft', 'reviewed', 'published', 'archived'));
