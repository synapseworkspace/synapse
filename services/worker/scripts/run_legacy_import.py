#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
SDK_SRC = REPO_ROOT / "packages" / "synapse-sdk-py" / "src"
if str(SDK_SRC) not in sys.path:
    sys.path.insert(0, str(SDK_SRC))

from app.legacy_import import (  # noqa: E402
    NOTION_DEFAULT_BASE_URL,
    NOTION_DEFAULT_VERSION,
    LegacyImporter,
    LegacySeedOrchestrator,
    NotionApiClient,
    NotionImportConfig,
    NotionImporter,
    SUPPORTED_EXTENSIONS,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Legacy docs cold-start import into Synapse memory backfill.")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--input-dir", help="Root directory with legacy documents.")
    source_group.add_argument("--notion-root-page-id", help="Notion root page id for recursive page tree import.")
    source_group.add_argument("--notion-database-id", help="Notion database id for database query import.")

    parser.add_argument("--project-id", required=True, help="Synapse project id.")
    parser.add_argument("--api-url", default="http://localhost:8080", help="Synapse API base URL.")
    parser.add_argument("--api-key", default=None, help="Optional Synapse API key.")
    parser.add_argument("--source-system", default=None, help="source_system for backfill batches.")
    parser.add_argument("--created-by", default="legacy_import_script", help="Actor label for batch metadata.")
    parser.add_argument("--chunk-size", type=int, default=100, help="Backfill chunk size.")
    parser.add_argument("--max-records", type=int, default=None, help="Optional cap on imported records.")
    parser.add_argument("--max-chars-per-record", type=int, default=1800, help="Text trim limit per record.")
    parser.add_argument(
        "--include-ext",
        action="append",
        default=[],
        help="File extension filter (repeatable, e.g. --include-ext .pdf). Default: all supported.",
    )
    parser.add_argument("--notion-token", default=os.getenv("NOTION_TOKEN"), help="Notion integration token.")
    parser.add_argument(
        "--notion-base-url",
        default=os.getenv("NOTION_BASE_URL", NOTION_DEFAULT_BASE_URL),
        help="Notion API base URL.",
    )
    parser.add_argument(
        "--notion-version",
        default=os.getenv("NOTION_VERSION", NOTION_DEFAULT_VERSION),
        help="Notion API version header value.",
    )
    parser.add_argument("--notion-max-pages", type=int, default=200, help="Safety limit for imported Notion pages.")
    parser.add_argument("--notion-timeout-sec", type=int, default=20, help="Timeout for each Notion API request.")
    parser.add_argument("--notion-max-retries", type=int, default=3, help="Retry count for Notion API calls.")
    parser.add_argument("--dry-run", action="store_true", help="Parse and print summary without API upload.")
    parser.add_argument("--sample-limit", type=int, default=5, help="How many parsed record previews to print.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    include_ext = {value.lower() for value in args.include_ext} if args.include_ext else set(SUPPORTED_EXTENSIONS)

    source_mode = "local"
    source_descriptor = ""
    if args.input_dir:
        input_dir = Path(args.input_dir).expanduser().resolve()
        source_descriptor = str(input_dir)
        importer = LegacyImporter(
            root_dir=input_dir,
            max_chars_per_record=args.max_chars_per_record,
            include_extensions=include_ext,
        )
        result = importer.collect_records(max_records=args.max_records)
    else:
        if not args.notion_token:
            raise SystemExit("Notion mode requires --notion-token (or NOTION_TOKEN env var).")
        source_mode = "notion_root_page" if args.notion_root_page_id else "notion_database"
        source_descriptor = args.notion_root_page_id or args.notion_database_id
        notion_client = NotionApiClient(
            NotionImportConfig(
                token=args.notion_token,
                base_url=args.notion_base_url,
                notion_version=args.notion_version,
                timeout_sec=args.notion_timeout_sec,
                max_retries=args.notion_max_retries,
            )
        )
        notion_importer = NotionImporter(
            client=notion_client,
            max_chars_per_record=args.max_chars_per_record,
            max_pages=args.notion_max_pages,
        )
        if args.notion_root_page_id:
            result = notion_importer.collect_from_root_page(
                args.notion_root_page_id,
                max_records=args.max_records,
            )
        else:
            result = notion_importer.collect_from_database(
                args.notion_database_id,
                max_records=args.max_records,
            )

    source_system = args.source_system or ("notion_import" if source_mode.startswith("notion") else "legacy_import")
    seed_orchestrator = LegacySeedOrchestrator()
    seeded = seed_orchestrator.apply(
        records=list(result.records),
        source_type=source_mode,
        source_ref=source_descriptor,
        project_id=args.project_id,
        config={},
    )
    records = seeded.records
    sample = records[: max(0, int(args.sample_limit))]

    summary: dict[str, object] = {
        "status": "ok",
        "mode": "dry_run" if args.dry_run else "upload",
        "source_mode": source_mode,
        "source": source_descriptor,
        "project_id": args.project_id,
        "records_collected": len(result.records),
        "records_seeded": len(records),
        "skipped_files": result.skipped_files,
        "warnings": result.parser_warnings,
        "seed_summary": seeded.summary,
        "sample_records": sample,
    }

    if args.dry_run or not records:
        if not records:
            summary["status"] = "skipped"
            summary["reason"] = "no_records_after_seed_planning"
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    from synapse_sdk import MemoryBackfillRecord, Synapse, SynapseConfig

    synapse = Synapse(
        SynapseConfig(
            api_url=args.api_url,
            project_id=args.project_id,
            api_key=args.api_key,
        )
    )
    batch_id = synapse.backfill_memory(
        [
            MemoryBackfillRecord(
                source_id=item["source_id"],
                content=item["content"],
                entity_key=item.get("entity_key"),
                category=item.get("category"),
                metadata=item.get("metadata") or {},
            )
            for item in records
        ],
        source_system=source_system,
        created_by=args.created_by,
        chunk_size=args.chunk_size,
    )
    summary["batch_id"] = batch_id
    summary["status"] = "uploaded"
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
