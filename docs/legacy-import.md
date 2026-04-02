# Legacy Import (Cold Start)

`run_legacy_import.py` converts existing company documents into Synapse `memory_backfill` batches.

During import, Synapse also runs a deterministic **seed orchestrator** that enriches each record with:

- `metadata.synapse_seed_plan` (`space/page/section` hints for wiki synthesis).
- `metadata.synapse_source_provenance` (traceable source/run fingerprints).

The runner supports two source modes:

- `local` files (`--input-dir`)
- `notion` API connector (`--notion-root-page-id` or `--notion-database-id`)

## Supported formats

- `.txt`
- `.md` / `.markdown`
- `.csv`
- `.json`
- `.jsonl`
- `.xlsx` (requires `openpyxl`)
- `.pdf` (requires `pypdf`)

If optional parser dependencies are missing, `.xlsx/.pdf` files are skipped with warnings.

## Upload mode

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_legacy_import.py \
  --input-dir /path/to/legacy_docs \
  --project-id omega_demo \
  --api-url http://localhost:8080 \
  --source-system legacy_import \
  --chunk-size 100
```

## Notion API upload mode

Import a whole page tree (recursive over `child_page` blocks):

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_legacy_import.py \
  --notion-root-page-id 1f6bc5c4d0aa4fb8a55ff4bdf2e0e123 \
  --notion-token "$NOTION_TOKEN" \
  --project-id omega_demo \
  --api-url http://localhost:8080 \
  --source-system notion_import
```

Import from a Notion database:

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_legacy_import.py \
  --notion-database-id 2f74f5a9f4a344f8b61a7f39302b5e4b \
  --notion-token "$NOTION_TOKEN" \
  --project-id omega_demo \
  --api-url http://localhost:8080
```

Useful Notion flags:

- `--notion-max-pages 200` safety cap for traversal/query.
- `--notion-timeout-sec 20` and `--notion-max-retries 3` for network resilience.
- `--notion-base-url` and `--notion-version` for self-hosted/proxy or version pinning.

## Dry run mode

```bash
PYTHONPATH=services/worker python services/worker/scripts/run_legacy_import.py \
  --input-dir /path/to/legacy_docs \
  --project-id omega_demo \
  --dry-run
```

Dry run prints parser warnings, skipped files, and sample records without API upload.

Dry-run/upload summaries now include `seed_summary` with:

- `seed_records`
- `seed_pages`
- `group_mode`
- `top_pages` (highest-volume seed targets)

These fields are useful to validate cold-start structure before promoting drafts.

## Seed planning regression QA

Run deterministic seed-planning regression suite (golden fixtures for grouping/section/page targeting):

```bash
PYTHONPATH=services/worker python3 scripts/eval_legacy_seed_regression.py --summary-only
```

Dataset file: `eval/legacy_seed_cases.json`.

The regression dataset now covers:
- Notion-heavy seeding (multiple pages/records to same target page) with deterministic grouping.
- Mixed-language category + section override keys (`OPS`, `доступ`, `SUPPORT_POLICY`) and normalized override resolution.

`seed_section_overrides` keys are normalized with the same category normalization pipeline as records, so aliases/case/mixed-language keys can map to one canonical category.

For periodic source refresh orchestration (configured sources + queued scheduled runs), see [legacy-sync-orchestration.md](legacy-sync-orchestration.md).
