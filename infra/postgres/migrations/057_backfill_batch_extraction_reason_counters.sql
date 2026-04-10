ALTER TABLE memory_backfill_batches
  ADD COLUMN IF NOT EXISTS drop_reason_counts JSONB NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS keep_reason_counts JSONB NOT NULL DEFAULT '{}'::jsonb;

