#!/usr/bin/env python3
from __future__ import annotations

import argparse
from hashlib import sha256
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
    LegacyImportResult,
    NotionApiClient,
    NotionImportConfig,
    NotionImporter,
    SQLImporter,
    SUPPORTED_EXTENSIONS,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Legacy docs cold-start import into Synapse memory backfill.")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--input-dir", help="Root directory with legacy documents.")
    source_group.add_argument("--notion-root-page-id", help="Notion root page id for recursive page tree import.")
    source_group.add_argument("--notion-database-id", help="Notion database id for database query import.")
    source_group.add_argument("--sql-query", help="SQL query for direct memory import (PostgreSQL).")
    source_group.add_argument("--sql-query-file", help="Path to file containing SQL query for import.")

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
    parser.add_argument("--sql-dsn", default=None, help="PostgreSQL DSN for SQL import mode.")
    parser.add_argument("--sql-dsn-env", default="LEGACY_SQL_DSN", help="Env var used for SQL DSN when --sql-dsn is omitted.")
    parser.add_argument(
        "--sql-source-ref",
        default=None,
        help="Logical source reference for SQL mode (used in provenance; default: query fingerprint).",
    )
    parser.add_argument(
        "--sql-query-params-json",
        default=None,
        help='JSON object with SQL query params (e.g. \'{"tenant_id":"acme"}\').',
    )
    parser.add_argument(
        "--sql-mapping-json",
        default=None,
        help="JSON mapping for SQL columns -> Synapse fields.",
    )
    parser.add_argument("--sql-mapping-file", default=None, help="Path to JSON file with SQL mapping config.")
    parser.add_argument("--sql-source-id-prefix", default=None, help="Optional prefix for generated source_id values.")
    parser.add_argument("--sql-cursor", default=None, help="Optional cursor value for incremental SQL query.")
    parser.add_argument("--sql-cursor-param", default="cursor", help="Named SQL parameter for cursor placeholder.")
    parser.add_argument("--sql-cursor-column", default=None, help="Column used to calculate next cursor value.")
    parser.add_argument(
        "--sql-source-connector",
        default="postgres_sql",
        help="Metadata connector label for SQL source records.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Parse and print summary without API upload.")
    parser.add_argument("--sample-limit", type=int, default=5, help="How many parsed record previews to print.")
    return parser.parse_args()


def _load_json_object(raw: str | None, *, field_name: str) -> dict[str, object]:
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{field_name} must be valid JSON object: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SystemExit(f"{field_name} must decode to a JSON object")
    return parsed


def _load_json_object_from_file(path_raw: str | None, *, field_name: str) -> dict[str, object]:
    path_text = str(path_raw or "").strip()
    if not path_text:
        return {}
    path = Path(path_text).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise SystemExit(f"{field_name} file does not exist: {path}")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{field_name} file must contain valid JSON object: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SystemExit(f"{field_name} file must contain JSON object")
    return parsed


def main() -> None:
    args = parse_args()
    include_ext = {value.lower() for value in args.include_ext} if args.include_ext else set(SUPPORTED_EXTENSIONS)

    source_mode = "local"
    source_descriptor = ""
    sql_next_cursor: str | None = None
    if args.input_dir:
        input_dir = Path(args.input_dir).expanduser().resolve()
        source_descriptor = str(input_dir)
        importer = LegacyImporter(
            root_dir=input_dir,
            max_chars_per_record=args.max_chars_per_record,
            include_extensions=include_ext,
        )
        result = importer.collect_records(max_records=args.max_records)
    elif args.sql_query or args.sql_query_file:
        source_mode = "postgres_sql"
        sql_query = str(args.sql_query or "").strip()
        if args.sql_query_file:
            sql_query_path = Path(str(args.sql_query_file)).expanduser().resolve()
            if not sql_query_path.exists() or not sql_query_path.is_file():
                raise SystemExit(f"--sql-query-file does not exist: {sql_query_path}")
            sql_query = sql_query_path.read_text(encoding="utf-8").strip()
        if not sql_query:
            raise SystemExit("SQL mode requires non-empty --sql-query or --sql-query-file contents")

        dsn = str(args.sql_dsn or "").strip()
        if not dsn:
            dsn_env = str(args.sql_dsn_env or "").strip() or "LEGACY_SQL_DSN"
            dsn = str(os.getenv(dsn_env) or "").strip()
        if not dsn:
            raise SystemExit("SQL mode requires --sql-dsn or env var from --sql-dsn-env")

        query_params = _load_json_object(args.sql_query_params_json, field_name="--sql-query-params-json")
        mapping = _load_json_object(args.sql_mapping_json, field_name="--sql-mapping-json")
        mapping_from_file = _load_json_object_from_file(args.sql_mapping_file, field_name="--sql-mapping-file")
        if mapping_from_file:
            mapping = {**mapping_from_file, **mapping}

        sql_importer = SQLImporter(
            dsn=dsn,
            query=sql_query,
            query_params=query_params,
            mapping=mapping,
            max_chars_per_record=args.max_chars_per_record,
            source_connector=args.sql_source_connector,
            source_id_prefix=args.sql_source_id_prefix,
        )
        sql_result = sql_importer.collect_records(
            max_records=args.max_records,
            cursor=args.sql_cursor,
            cursor_param=args.sql_cursor_param,
            cursor_column=args.sql_cursor_column,
        )
        sql_next_cursor = sql_result.next_cursor
        result = LegacyImportResult(
            records=list(sql_result.records),
            skipped_files=[],
            parser_warnings=list(sql_result.parser_warnings),
        )
        source_descriptor = (
            str(args.sql_source_ref).strip()
            if str(args.sql_source_ref or "").strip()
            else f"postgres_sql:{sha256(sql_query.encode('utf-8')).hexdigest()[:16]}"
        )
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

    if args.source_system:
        source_system = args.source_system
    elif source_mode.startswith("notion"):
        source_system = "notion_import"
    elif source_mode == "postgres_sql":
        source_system = "postgres_sql_import"
    else:
        source_system = "legacy_import"
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
    if sql_next_cursor is not None:
        summary["next_cursor"] = sql_next_cursor

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
                observed_at=item.get("observed_at"),
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
