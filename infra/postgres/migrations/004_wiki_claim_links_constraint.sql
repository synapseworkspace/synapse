DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'wiki_claim_links'::regclass
      AND conname = 'wiki_claim_links_insertion_status_check'
      AND pg_get_constraintdef(oid) LIKE '%new_page%'
  ) THEN
    ALTER TABLE wiki_claim_links
    DROP CONSTRAINT IF EXISTS wiki_claim_links_insertion_status_check;

    ALTER TABLE wiki_claim_links
    ADD CONSTRAINT wiki_claim_links_insertion_status_check CHECK (
      insertion_status IN (
        'new_page',
        'new_section',
        'new_statement',
        'reinforcement',
        'duplicate_ignored',
        'conflict',
        'rejected'
      )
    );
  END IF;
END $$;
