DO $$
DECLARE
  _constraint_name TEXT;
BEGIN
  -- Drop the historical explicit-name check when present.
  IF EXISTS (
    SELECT 1
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname = 'public'
      AND t.relname = 'legacy_import_sources'
      AND c.contype = 'c'
      AND c.conname = 'legacy_import_sources_source_type_check'
  ) THEN
    ALTER TABLE public.legacy_import_sources
      DROP CONSTRAINT legacy_import_sources_source_type_check;
  END IF;

  -- Also drop any legacy source_type checks created with generated names.
  FOR _constraint_name IN
    SELECT c.conname
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname = 'public'
      AND t.relname = 'legacy_import_sources'
      AND c.contype = 'c'
      AND c.conname <> 'legacy_import_sources_source_type_check'
      AND pg_get_constraintdef(c.oid) ILIKE '%source_type%'
  LOOP
    EXECUTE format('ALTER TABLE public.legacy_import_sources DROP CONSTRAINT %I', _constraint_name);
  END LOOP;

  ALTER TABLE public.legacy_import_sources
    ADD CONSTRAINT legacy_import_sources_source_type_check
    CHECK (source_type IN ('local_dir', 'notion_root_page', 'notion_database', 'postgres_sql'));
END $$;
