DO $$
DECLARE
  _constraint_name TEXT;
BEGIN
  SELECT c.conname
  INTO _constraint_name
  FROM pg_constraint c
  JOIN pg_class t ON t.oid = c.conrelid
  WHERE t.relname = 'legacy_import_sources'
    AND c.contype = 'c'
    AND pg_get_constraintdef(c.oid) ILIKE '%source_type IN%';

  IF _constraint_name IS NOT NULL THEN
    EXECUTE format('ALTER TABLE legacy_import_sources DROP CONSTRAINT %I', _constraint_name);
  END IF;

  ALTER TABLE legacy_import_sources
    ADD CONSTRAINT legacy_import_sources_source_type_check
    CHECK (source_type IN ('local_dir', 'notion_root_page', 'notion_database', 'postgres_sql'));
END $$;
