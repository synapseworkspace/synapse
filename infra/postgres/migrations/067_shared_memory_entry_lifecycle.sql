ALTER TABLE shared_memory_entries
  ADD COLUMN IF NOT EXISTS superseded_by_entry_id BIGINT REFERENCES shared_memory_entries(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS lifecycle_reason TEXT;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE table_schema = 'public'
      AND table_name = 'shared_memory_entries'
      AND constraint_name = 'shared_memory_entries_status_check'
  ) THEN
    ALTER TABLE shared_memory_entries
      DROP CONSTRAINT shared_memory_entries_status_check;
  END IF;
END $$;

ALTER TABLE shared_memory_entries
  ADD CONSTRAINT shared_memory_entries_status_check
  CHECK (status IN ('active', 'superseded', 'resolved', 'expired', 'archived'));

CREATE INDEX IF NOT EXISTS idx_shared_memory_entries_status
  ON shared_memory_entries(project_id, status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_shared_memory_entries_expires_at
  ON shared_memory_entries(project_id, expires_at)
  WHERE expires_at IS NOT NULL;
