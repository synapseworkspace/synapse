from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
import os
import re
import sys
from typing import Any
from urllib import error as url_error
from urllib import parse as url_parse
from urllib import request as url_request
from uuid import UUID, uuid4

try:
    from psycopg.types.json import Jsonb
except Exception:  # pragma: no cover - offline mode without psycopg runtime
    class Jsonb:  # type: ignore[override]
        def __init__(self, obj: Any):
            self.obj = obj

from app.legacy_import import (
    LegacyImportResult,
    LegacyImporter,
    LegacySeedOrchestrator,
    NotionApiClient,
    NotionImportConfig,
    NotionImporter,
    SQLImporter,
    SUPPORTED_EXTENSIONS,
)
try:
    from shared.legacy_profiles import (
        apply_postgres_sql_profile_defaults,
        get_postgres_sql_profile_preset,
    )
except ModuleNotFoundError:
    services_root = Path(__file__).resolve().parents[2]
    if str(services_root) not in sys.path:
        sys.path.append(str(services_root))
    from shared.legacy_profiles import (
        apply_postgres_sql_profile_defaults,
        get_postgres_sql_profile_preset,
    )


REPO_ROOT = Path(__file__).resolve().parents[3]
SDK_SRC = REPO_ROOT / "packages" / "synapse-sdk-py" / "src"
if str(SDK_SRC) not in sys.path:
    sys.path.insert(0, str(SDK_SRC))


@dataclass(slots=True)
class LegacySourceRecord:
    id: UUID
    project_id: str
    source_type: str
    source_ref: str
    enabled: bool
    sync_interval_minutes: int
    config: dict[str, Any]


@dataclass(slots=True)
class LegacySyncRunRecord:
    id: UUID
    source_id: UUID
    project_id: str
    trigger_mode: str
    requested_by: str


class LegacySyncEngine:
    """Periodic orchestration for legacy import sources (local, Notion, SQL polling, SQL WAL/CDC)."""

    def __init__(
        self,
        *,
        api_url: str = "http://localhost:8080",
        api_key: str | None = None,
        default_requested_by: str = "legacy_sync_scheduler",
    ) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.default_requested_by = default_requested_by

    def enqueue_due_sources(
        self,
        conn,
        *,
        project_ids: list[str] | None = None,
        limit: int = 20,
        requested_by: str | None = None,
    ) -> dict[str, Any]:
        picked = self._pick_due_sources(conn, project_ids=project_ids, limit=limit)
        queued: list[str] = []
        actor = (requested_by or self.default_requested_by).strip() or self.default_requested_by
        for source in picked:
            run_id = uuid4()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO legacy_import_sync_runs (
                      id,
                      source_id,
                      project_id,
                      status,
                      trigger_mode,
                      requested_by,
                      summary,
                      created_at,
                      updated_at
                    )
                    VALUES (%s, %s, %s, 'queued', 'scheduled', %s, '{}'::jsonb, NOW(), NOW())
                    """,
                    (run_id, source.id, source.project_id, actor),
                )
                cur.execute(
                    """
                    UPDATE legacy_import_sources
                    SET next_run_at = NOW() + (%s::text || ' minutes')::interval,
                        updated_by = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (source.sync_interval_minutes, actor, source.id),
                )
            queued.append(str(run_id))
        return {
            "status": "ok",
            "picked_sources": len(picked),
            "queued_runs": len(queued),
            "run_ids": queued,
        }

    def process_queued_runs(
        self,
        conn,
        *,
        project_ids: list[str] | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        claimed = self._claim_queued_runs(conn, project_ids=project_ids, limit=limit)
        completed = 0
        failed = 0
        skipped = 0
        results: list[dict[str, Any]] = []
        for run, source in claimed:
            try:
                run_result = self._execute_run(conn, run=run, source=source)
                status = str(run_result.get("status") or "completed")
                if status == "completed":
                    completed += 1
                elif status == "skipped":
                    skipped += 1
                else:
                    failed += 1
                results.append(
                    {
                        "run_id": str(run.id),
                        "source_id": str(source.id),
                        "project_id": source.project_id,
                        **run_result,
                    }
                )
            except Exception as exc:
                failed += 1
                self._mark_run_failed(conn, run_id=run.id, source_id=source.id, error_message=str(exc))
                results.append(
                    {
                        "run_id": str(run.id),
                        "source_id": str(source.id),
                        "project_id": source.project_id,
                        "status": "failed",
                        "error": str(exc)[:300],
                    }
                )
        return {
            "status": "ok",
            "picked": len(claimed),
            "completed": completed,
            "skipped": skipped,
            "failed": failed,
            "results": results,
        }

    def discover_projects(self, conn, *, limit: int = 500) -> list[str]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT project_id
                FROM legacy_import_sources
                WHERE project_id IS NOT NULL
                  AND project_id <> ''
                GROUP BY project_id
                ORDER BY MAX(updated_at) DESC
                LIMIT %s
                """,
                (max(1, int(limit)),),
            )
            rows = cur.fetchall()
        return [str(row[0]) for row in rows]

    @staticmethod
    def compute_record_delta(records: list[dict[str, Any]], known_fingerprints: set[str]) -> dict[str, Any]:
        known = {item.strip().lower() for item in known_fingerprints if item and item.strip()}
        seen_in_run: set[str] = set()
        new_records: list[dict[str, Any]] = []
        duplicates_known = 0
        duplicates_run = 0
        all_fingerprints: set[str] = set()

        for record in records:
            content = str(record.get("content") or "").strip()
            if not content:
                continue
            fingerprint = sha256(content.encode("utf-8")).hexdigest()
            all_fingerprints.add(fingerprint)
            metadata = dict(record.get("metadata") or {})
            metadata["sync_content_fingerprint"] = fingerprint
            record["metadata"] = metadata

            if fingerprint in seen_in_run:
                duplicates_run += 1
                continue
            seen_in_run.add(fingerprint)
            if fingerprint in known:
                duplicates_known += 1
                continue
            new_records.append(record)

        return {
            "new_records": new_records,
            "new_count": len(new_records),
            "duplicates_known": duplicates_known,
            "duplicates_run": duplicates_run,
            "all_fingerprints": sorted(all_fingerprints),
        }

    def _pick_due_sources(
        self,
        conn,
        *,
        project_ids: list[str] | None,
        limit: int,
    ) -> list[LegacySourceRecord]:
        limit = max(1, int(limit))
        with conn.cursor() as cur:
            if project_ids:
                cur.execute(
                    """
                    SELECT
                      id,
                      project_id,
                      source_type,
                      source_ref,
                      enabled,
                      sync_interval_minutes,
                      config
                    FROM legacy_import_sources
                    WHERE enabled = TRUE
                      AND next_run_at <= NOW()
                      AND project_id = ANY(%s)
                    ORDER BY next_run_at ASC
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                    """,
                    (project_ids, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT
                      id,
                      project_id,
                      source_type,
                      source_ref,
                      enabled,
                      sync_interval_minutes,
                      config
                    FROM legacy_import_sources
                    WHERE enabled = TRUE
                      AND next_run_at <= NOW()
                    ORDER BY next_run_at ASC
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                    """,
                    (limit,),
                )
            rows = cur.fetchall()
        return [self._source_from_row(row) for row in rows]

    def _claim_queued_runs(
        self,
        conn,
        *,
        project_ids: list[str] | None,
        limit: int,
    ) -> list[tuple[LegacySyncRunRecord, LegacySourceRecord]]:
        limit = max(1, int(limit))
        with conn.cursor() as cur:
            if project_ids:
                cur.execute(
                    """
                    WITH picked AS (
                      SELECT r.id
                      FROM legacy_import_sync_runs r
                      JOIN legacy_import_sources s ON s.id = r.source_id
                      WHERE r.status = 'queued'
                        AND s.project_id = ANY(%s)
                      ORDER BY r.created_at ASC
                      FOR UPDATE SKIP LOCKED
                      LIMIT %s
                    )
                    UPDATE legacy_import_sync_runs r
                    SET status = 'running',
                        started_at = NOW(),
                        error_message = NULL,
                        updated_at = NOW()
                    FROM picked
                    WHERE r.id = picked.id
                    RETURNING r.id, r.source_id, r.project_id, r.trigger_mode, COALESCE(r.requested_by, 'scheduler')
                    """,
                    (project_ids, limit),
                )
            else:
                cur.execute(
                    """
                    WITH picked AS (
                      SELECT r.id
                      FROM legacy_import_sync_runs r
                      WHERE r.status = 'queued'
                      ORDER BY r.created_at ASC
                      FOR UPDATE SKIP LOCKED
                      LIMIT %s
                    )
                    UPDATE legacy_import_sync_runs r
                    SET status = 'running',
                        started_at = NOW(),
                        error_message = NULL,
                        updated_at = NOW()
                    FROM picked
                    WHERE r.id = picked.id
                    RETURNING r.id, r.source_id, r.project_id, r.trigger_mode, COALESCE(r.requested_by, 'scheduler')
                    """,
                    (limit,),
                )
            run_rows = cur.fetchall()

            if not run_rows:
                return []
            source_ids = [row[1] for row in run_rows]
            cur.execute(
                """
                SELECT
                  id,
                  project_id,
                  source_type,
                  source_ref,
                  enabled,
                  sync_interval_minutes,
                  config
                FROM legacy_import_sources
                WHERE id = ANY(%s)
                """,
                (source_ids,),
            )
            source_rows = cur.fetchall()

        source_map = {row[0]: self._source_from_row(row) for row in source_rows}
        claimed: list[tuple[LegacySyncRunRecord, LegacySourceRecord]] = []
        for row in run_rows:
            source = source_map.get(row[1])
            if source is None:
                continue
            run = LegacySyncRunRecord(
                id=row[0],
                source_id=row[1],
                project_id=str(row[2]),
                trigger_mode=str(row[3]),
                requested_by=str(row[4]),
            )
            claimed.append((run, source))
        return claimed

    def _execute_run(
        self,
        conn,
        *,
        run: LegacySyncRunRecord,
        source: LegacySourceRecord,
    ) -> dict[str, Any]:
        config = source.config or {}
        max_records = max(1, int(config.get("max_records", 5000)))
        source_system = str(config.get("source_system") or f"legacy_sync:{source.source_type}")
        chunk_size = max(1, int(config.get("chunk_size", 100)))
        created_by = run.requested_by or self.default_requested_by
        curated_import = config.get("curated_import") if isinstance(config.get("curated_import"), dict) else None

        collected, source_state_patch = self._collect_records(source=source, max_records=max_records)
        records = list(collected.records)
        fingerprints_known = self._load_known_fingerprints(conn, source_id=source.id, records=records)
        delta = self.compute_record_delta(records, fingerprints_known)
        new_records = list(delta["new_records"])
        all_fingerprints = list(delta["all_fingerprints"])

        self._upsert_fingerprints(
            conn,
            source_id=source.id,
            run_id=run.id,
            fingerprints=all_fingerprints,
        )

        summary: dict[str, Any] = {
            "records_collected": len(records),
            "records_new": len(new_records),
            "duplicates_known": int(delta["duplicates_known"]),
            "duplicates_in_run": int(delta["duplicates_run"]),
            "warnings": collected.parser_warnings,
            "skipped_files": collected.skipped_files,
            "source_type": source.source_type,
            "source_ref": source.source_ref,
        }
        if source.source_type == "postgres_sql":
            summary["sync_mode"] = str(config.get("sql_sync_mode") or "polling").strip().lower() or "polling"
        if source_state_patch:
            self._patch_source_config(
                conn,
                source_id=source.id,
                config_patch=source_state_patch,
                updated_by=created_by,
            )
            summary["source_state_patch"] = source_state_patch

        if not new_records:
            self._mark_run_skipped(
                conn,
                run_id=run.id,
                source_id=source.id,
                summary=summary,
            )
            return {
                "status": "skipped",
                "records_collected": len(records),
                "records_uploaded": 0,
                "duplicates_known": int(delta["duplicates_known"]),
            }

        seeded = LegacySeedOrchestrator().apply(
            records=new_records,
            source_type=source.source_type,
            source_ref=source.source_ref,
            project_id=source.project_id,
            source_id=str(source.id),
            run_id=str(run.id),
            config=config,
        )
        seeded_records = list(seeded.records)
        summary["seed_summary"] = seeded.summary
        summary["records_seeded"] = len(seeded_records)

        if not seeded_records:
            self._mark_run_skipped(
                conn,
                run_id=run.id,
                source_id=source.id,
                summary=summary,
            )
            return {
                "status": "skipped",
                "records_collected": len(records),
                "records_uploaded": 0,
                "duplicates_known": int(delta["duplicates_known"]),
            }

        batch_id = self._upload_records(
            project_id=source.project_id,
            records=seeded_records,
            source_system=source_system,
            chunk_size=chunk_size,
            created_by=created_by,
            batch_id=str(run.id),
            curated_import=curated_import,
        )
        summary["batch_id"] = batch_id
        summary["source_system"] = source_system
        if isinstance(curated_import, dict):
            summary["curated_import"] = curated_import
        self._mark_run_completed(
            conn,
            run_id=run.id,
            source_id=source.id,
            records_collected=len(records),
            records_uploaded=len(seeded_records),
            skipped_files_count=len(collected.skipped_files),
            warnings_count=len(collected.parser_warnings),
            batch_id=batch_id,
            summary=summary,
        )
        return {
            "status": "completed",
            "records_collected": len(records),
            "records_uploaded": len(seeded_records),
            "batch_id": batch_id,
        }

    def _collect_records(
        self,
        *,
        source: LegacySourceRecord,
        max_records: int,
    ) -> tuple[LegacyImportResult, dict[str, Any]]:
        config = source.config or {}
        max_chars = max(200, int(config.get("max_chars_per_record", 1800)))
        if source.source_type == "local_dir":
            include_ext_raw = config.get("include_extensions")
            include_ext = set(SUPPORTED_EXTENSIONS)
            if isinstance(include_ext_raw, list):
                parsed = {str(item).strip().lower() for item in include_ext_raw if str(item).strip()}
                if parsed:
                    include_ext = parsed
            importer = LegacyImporter(
                root_dir=Path(source.source_ref).expanduser().resolve(),
                max_chars_per_record=max_chars,
                include_extensions=include_ext,
            )
            return importer.collect_records(max_records=max_records), {}

        if source.source_type in {"notion_root_page", "notion_database"}:
            notion_token = self._resolve_notion_token(config)
            if not notion_token:
                raise RuntimeError("missing Notion token for source; set config.notion_token or config.notion_token_env")
            notion_config = NotionImportConfig(
                token=notion_token,
                base_url=str(config.get("notion_base_url") or os.getenv("NOTION_BASE_URL") or "https://api.notion.com"),
                notion_version=str(config.get("notion_version") or os.getenv("NOTION_VERSION") or "2022-06-28"),
                timeout_sec=max(1, int(config.get("notion_timeout_sec", 20))),
                max_retries=max(0, int(config.get("notion_max_retries", 3))),
            )
            notion_importer = NotionImporter(
                client=NotionApiClient(notion_config),
                max_chars_per_record=max_chars,
                max_pages=max(1, int(config.get("notion_max_pages", 200))),
            )
            if source.source_type == "notion_root_page":
                return notion_importer.collect_from_root_page(source.source_ref, max_records=max_records), {}
            return notion_importer.collect_from_database(source.source_ref, max_records=max_records), {}

        if source.source_type == "memory_api":
            result, source_patch = self._collect_memory_api(
                config=config,
                source_ref=source.source_ref,
                max_records=max_records,
                max_chars=max_chars,
            )
            return result, source_patch

        if source.source_type == "postgres_sql":
            resolved_config, profile_meta = apply_postgres_sql_profile_defaults(config, source_ref=source.source_ref)
            dsn = self._resolve_sql_dsn(resolved_config)
            sync_mode = str(resolved_config.get("sql_sync_mode") or "polling").strip().lower() or "polling"
            state_patch: dict[str, Any] = {}
            if profile_meta.get("profile"):
                state_patch["sql_profile"] = str(profile_meta.get("profile"))
                if bool(profile_meta.get("profile_inferred")):
                    state_patch["sql_profile_inferred"] = True
            if sync_mode in {"polling", "query"}:
                result, source_patch = self._collect_postgres_sql_polling(
                    dsn=dsn,
                    config=resolved_config,
                    max_records=max_records,
                    max_chars=max_chars,
                    source_ref=source.source_ref,
                )
                if source_patch:
                    state_patch.update(source_patch)
                return result, state_patch
            if sync_mode in {"wal", "wal_cdc", "cdc"}:
                result, source_patch = self._collect_postgres_sql_wal_cdc(
                    dsn=dsn,
                    config=resolved_config,
                    max_records=max_records,
                    max_chars=max_chars,
                    source_ref=source.source_ref,
                )
                if source_patch:
                    state_patch.update(source_patch)
                return result, state_patch
            raise RuntimeError(
                f"unsupported sql_sync_mode for postgres_sql source: {sync_mode} (supported: polling|wal_cdc)"
            )

        raise RuntimeError(f"unsupported source_type: {source.source_type}")

    @staticmethod
    def _extract_path_value(payload: Any, path: str) -> Any:
        current = payload
        for segment in [part for part in str(path or "").split(".") if part]:
            if isinstance(current, dict):
                current = current.get(segment)
            else:
                return None
        return current

    def _collect_memory_api(
        self,
        *,
        config: dict[str, Any],
        source_ref: str,
        max_records: int,
        max_chars: int,
    ) -> tuple[LegacyImportResult, dict[str, Any]]:
        api_url = str(config.get("api_url") or source_ref or "").strip()
        if not api_url:
            raise RuntimeError("missing memory_api url (config.api_url or source_ref)")
        api_method = str(config.get("api_method") or "GET").strip().upper() or "GET"
        if api_method not in {"GET", "POST"}:
            raise RuntimeError("memory_api api_method must be GET or POST")
        timeout_sec = max(1, int(config.get("api_timeout_sec", 20)))
        limit = max(1, int(config.get("api_limit", 1000)))
        limit = min(limit, max_records)
        cursor = str(config.get("api_cursor") or "").strip() or None
        cursor_param = str(config.get("api_cursor_param") or "cursor").strip() or "cursor"
        limit_param = str(config.get("api_limit_param") or "limit").strip() or "limit"
        records_path = str(config.get("api_records_path") or "items").strip() or "items"
        next_cursor_path = str(config.get("api_pagination_cursor_path") or "next_cursor").strip() or "next_cursor"
        headers_config = config.get("api_headers") if isinstance(config.get("api_headers"), dict) else {}
        headers: dict[str, str] = {"Accept": "application/json"}
        for key, value in headers_config.items():
            name = str(key or "").strip()
            if not name:
                continue
            header_value = str(value or "")
            if header_value.startswith("$env:"):
                env_name = header_value[5:].strip()
                header_value = str(os.getenv(env_name) or "").strip()
            elif header_value.startswith("env:"):
                env_name = header_value[4:].strip()
                header_value = str(os.getenv(env_name) or "").strip()
            headers[name] = header_value

        mapping = config.get("api_mapping") if isinstance(config.get("api_mapping"), dict) else {}
        source_id_path = str(mapping.get("source_id") or "id").strip() or "id"
        content_path = str(mapping.get("content") or "content").strip() or "content"
        observed_at_path = str(mapping.get("observed_at") or "observed_at").strip() or "observed_at"
        entity_key_path = str(mapping.get("entity_key") or "entity_key").strip() or "entity_key"
        category_path = str(mapping.get("category") or "category").strip() or "category"
        metadata_path = str(mapping.get("metadata") or "metadata").strip() or "metadata"
        parser_warnings: list[str] = []
        records: list[dict[str, Any]] = []
        page_number = 0
        source_patch: dict[str, Any] = {}

        while len(records) < max_records:
            page_number += 1
            query = {limit_param: str(limit)}
            if cursor:
                query[cursor_param] = cursor
            parsed = url_parse.urlsplit(api_url)
            existing_query = dict(url_parse.parse_qsl(parsed.query, keep_blank_values=True))
            existing_query.update(query)
            target_url = url_parse.urlunsplit(
                (parsed.scheme, parsed.netloc, parsed.path, url_parse.urlencode(existing_query), parsed.fragment)
            )
            body_bytes: bytes | None = None
            if api_method == "POST":
                body_bytes = json.dumps(existing_query).encode("utf-8")
                headers["Content-Type"] = "application/json"
            req = url_request.Request(url=target_url, method=api_method, headers=headers, data=body_bytes)
            try:
                with url_request.urlopen(req, timeout=timeout_sec) as response:
                    payload_raw = response.read().decode("utf-8", errors="replace")
            except url_error.HTTPError as exc:
                raise RuntimeError(f"memory_api http error {exc.code}") from exc
            except url_error.URLError as exc:
                raise RuntimeError(f"memory_api request failed: {exc}") from exc

            try:
                payload = json.loads(payload_raw)
            except json.JSONDecodeError as exc:
                raise RuntimeError("memory_api response is not valid JSON") from exc

            if isinstance(payload, list):
                rows = payload
                next_cursor = None
            else:
                rows = self._extract_path_value(payload, records_path)
                next_cursor = self._extract_path_value(payload, next_cursor_path)
            if not isinstance(rows, list):
                raise RuntimeError(f"memory_api records_path `{records_path}` did not resolve to a list")

            for raw_row in rows:
                if len(records) >= max_records:
                    break
                if not isinstance(raw_row, dict):
                    parser_warnings.append("memory_api row skipped: non-object payload")
                    continue
                content = str(self._extract_path_value(raw_row, content_path) or "").strip()
                if not content:
                    continue
                if len(content) > max_chars:
                    content = f"{content[:max_chars].rstrip()}..."
                source_id = str(self._extract_path_value(raw_row, source_id_path) or "").strip()
                if not source_id:
                    source_id = f"memory_api:{sha256(content.encode('utf-8')).hexdigest()[:16]}"
                metadata = self._extract_path_value(raw_row, metadata_path)
                metadata_obj = dict(metadata) if isinstance(metadata, dict) else {}
                metadata_obj.setdefault("memory_api_raw_keys", sorted(raw_row.keys()))
                observed_at = str(self._extract_path_value(raw_row, observed_at_path) or "").strip() or None
                entity_key = str(self._extract_path_value(raw_row, entity_key_path) or "").strip() or None
                category = str(self._extract_path_value(raw_row, category_path) or "").strip() or None
                records.append(
                    {
                        "source_id": source_id,
                        "content": content,
                        "observed_at": observed_at,
                        "entity_key": entity_key,
                        "category": category,
                        "metadata": metadata_obj,
                    }
                )

            if not rows or not next_cursor:
                cursor = None
                break
            cursor = str(next_cursor).strip() or None
            if cursor is None:
                break
        if cursor is not None:
            source_patch["api_cursor"] = cursor
        source_patch["api_last_success_at"] = datetime.now(UTC).isoformat()
        return LegacyImportResult(records=records, skipped_files=[], parser_warnings=parser_warnings), source_patch

    def _resolve_notion_token(self, config: dict[str, Any]) -> str | None:
        token = str(config.get("notion_token") or "").strip()
        if token:
            return token
        env_name = str(config.get("notion_token_env") or "NOTION_TOKEN").strip()
        return str(os.getenv(env_name) or "").strip() or None

    def _resolve_sql_dsn(self, config: dict[str, Any]) -> str:
        dsn = str(config.get("sql_dsn") or "").strip()
        if not dsn:
            dsn_env = str(config.get("sql_dsn_env") or "LEGACY_SQL_DSN").strip() or "LEGACY_SQL_DSN"
            dsn = str(os.getenv(dsn_env) or "").strip()
        if not dsn:
            raise RuntimeError("missing SQL DSN for postgres_sql source (config.sql_dsn or config.sql_dsn_env)")
        return dsn

    def _collect_postgres_sql_polling(
        self,
        *,
        dsn: str,
        config: dict[str, Any],
        max_records: int,
        max_chars: int,
        source_ref: str,
    ) -> tuple[LegacyImportResult, dict[str, Any]]:
        query = str(config.get("sql_query") or "").strip()
        query_file = str(config.get("sql_query_file") or "").strip()
        if not query and query_file:
            query_path = Path(query_file).expanduser().resolve()
            if not query_path.exists() or not query_path.is_file():
                raise RuntimeError(f"sql_query_file does not exist: {query_path}")
            query = query_path.read_text(encoding="utf-8").strip()
        sql_mapping = config.get("sql_mapping") if isinstance(config.get("sql_mapping"), dict) else {}
        profile_plan_warnings: list[str] = []
        state_patch: dict[str, Any] = {}

        if not query:
            profile_plan = self._build_postgres_sql_profile_polling_plan(
                dsn=dsn,
                config=config,
                source_ref=source_ref,
                max_records=max_records,
            )
            query = str(profile_plan.get("query") or "").strip()
            plan_mapping = profile_plan.get("sql_mapping") if isinstance(profile_plan.get("sql_mapping"), dict) else {}
            if plan_mapping:
                merged_mapping = dict(plan_mapping)
                merged_mapping.update(sql_mapping)
                sql_mapping = merged_mapping
            planned_cursor_column = str(profile_plan.get("cursor_column") or "").strip()
            if planned_cursor_column and not str(config.get("sql_cursor_column") or "").strip():
                config = dict(config)
                config["sql_cursor_column"] = planned_cursor_column
            planned_cursor_param = str(profile_plan.get("cursor_param") or "").strip()
            if planned_cursor_param and not str(config.get("sql_cursor_param") or "").strip():
                config = dict(config)
                config["sql_cursor_param"] = planned_cursor_param
            if profile_plan.get("state_patch"):
                state_patch.update(dict(profile_plan["state_patch"]))
            warnings = profile_plan.get("warnings")
            if isinstance(warnings, list):
                profile_plan_warnings = [str(item) for item in warnings if str(item).strip()]

        if not query:
            raise RuntimeError(
                "missing SQL query for postgres_sql source; set config.sql_query/config.sql_query_file or enable a known sql_profile"
            )

        sql_query_params = config.get("sql_query_params") if isinstance(config.get("sql_query_params"), dict) else {}
        cursor_key = str(config.get("sql_cursor_state_key") or "sql_last_cursor").strip() or "sql_last_cursor"
        cursor_start = str(config.get("sql_cursor_start") or "").strip()
        cursor_value_raw = config.get(cursor_key)
        cursor_value = str(cursor_value_raw).strip() if cursor_value_raw is not None else ""
        if not cursor_value:
            cursor_value = cursor_start
        cursor_param = str(config.get("sql_cursor_param") or "cursor").strip() or "cursor"
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", cursor_param):
            warnings.append(f"sql_cursor_param `{cursor_param}` is invalid; fallback to `cursor`")
            cursor_param = "cursor"
        cursor_column = str(config.get("sql_cursor_column") or "").strip() or None
        importer = SQLImporter(
            dsn=dsn,
            query=query,
            query_params=sql_query_params,
            mapping=sql_mapping,
            max_chars_per_record=max_chars,
            source_connector=str(config.get("sql_source_connector") or "postgres_sql"),
            source_id_prefix=str(config.get("sql_source_id_prefix") or ""),
        )
        sql_result = importer.collect_records(
            max_records=max_records,
            cursor=cursor_value or None,
            cursor_param=cursor_param,
            cursor_column=cursor_column,
        )
        parser_warnings = list(profile_plan_warnings)
        parser_warnings.extend(list(sql_result.parser_warnings))
        next_cursor = str(sql_result.next_cursor or "").strip()
        if next_cursor and next_cursor != cursor_value:
            state_patch[cursor_key] = next_cursor
            state_patch["sql_last_synced_at"] = datetime.now(UTC).isoformat()
        return (
            LegacyImportResult(
                records=list(sql_result.records),
                skipped_files=[],
                parser_warnings=parser_warnings,
            ),
            state_patch,
        )

    def _build_postgres_sql_profile_polling_plan(
        self,
        *,
        dsn: str,
        config: dict[str, Any],
        source_ref: str,
        max_records: int,
    ) -> dict[str, Any]:
        profile = str(config.get("sql_profile") or "").strip()
        preset = get_postgres_sql_profile_preset(profile)
        if not preset:
            return {"query": "", "sql_mapping": {}, "warnings": [], "state_patch": {}}

        table_candidates: list[str] = []
        for item in (
            config.get("sql_profile_table"),
            preset.get("default_table"),
            *(preset.get("table_candidates") or []),
        ):
            text = str(item or "").strip()
            if text and text not in table_candidates:
                table_candidates.append(text)
        if not table_candidates:
            raise RuntimeError(
                f"postgres_sql profile `{profile}` has no table candidates; set config.sql_profile_table explicitly"
            )

        resolved = self._resolve_existing_sql_table(dsn=dsn, candidates=table_candidates)
        if resolved is None:
            tried = ", ".join(table_candidates)
            raise RuntimeError(
                f"postgres_sql profile `{profile}` could not resolve table (tried: {tried}); set config.sql_profile_table"
            )

        schema = str(resolved["schema"])
        table = str(resolved["table"])
        columns = list(resolved["columns"])
        column_types = dict(resolved["column_types"])
        column_lookup = {str(item).strip().lower(): str(item).strip() for item in columns if str(item).strip()}

        mapping = config.get("sql_mapping") if isinstance(config.get("sql_mapping"), dict) else {}
        merged_mapping = dict(mapping)
        source_id_field = self._pick_existing_column(column_lookup, preset.get("source_id_fields"))
        entity_key_field = self._pick_existing_column(column_lookup, preset.get("entity_key_fields"))
        category_field = self._pick_existing_column(column_lookup, preset.get("category_fields"))
        observed_at_field = self._pick_existing_column(column_lookup, preset.get("observed_at_fields"))
        content_fields = self._pick_existing_columns(column_lookup, preset.get("content_fields"))
        metadata_fields = self._pick_existing_columns(column_lookup, preset.get("metadata_fields"))

        if source_id_field and not str(merged_mapping.get("source_id_field") or "").strip():
            merged_mapping["source_id_field"] = source_id_field
        if entity_key_field and not str(merged_mapping.get("entity_key_field") or "").strip():
            merged_mapping["entity_key_field"] = entity_key_field
        if category_field and not str(merged_mapping.get("category_field") or "").strip():
            merged_mapping["category_field"] = category_field
        if observed_at_field and not str(merged_mapping.get("observed_at_field") or "").strip():
            merged_mapping["observed_at_field"] = observed_at_field
        if content_fields and not (
            isinstance(merged_mapping.get("content_fields"), list) and merged_mapping.get("content_fields")
        ):
            merged_mapping["content_fields"] = content_fields
        if metadata_fields and not (
            isinstance(merged_mapping.get("metadata_fields"), list) and merged_mapping.get("metadata_fields")
        ):
            merged_mapping["metadata_fields"] = metadata_fields

        warnings: list[str] = []
        cursor_column_requested = str(config.get("sql_cursor_column") or "").strip()
        cursor_column = ""
        if cursor_column_requested:
            cursor_column = column_lookup.get(cursor_column_requested.lower(), "")
            if not cursor_column:
                warnings.append(
                    f"sql_cursor_column `{cursor_column_requested}` not found in `{schema}.{table}`; fallback strategy applied"
                )
        if not cursor_column:
            cursor_column = observed_at_field or source_id_field
        if not cursor_column and columns:
            cursor_column = columns[0]

        cursor_param = str(config.get("sql_cursor_param") or "cursor").strip() or "cursor"
        order_column = cursor_column or source_id_field or (columns[0] if columns else "")
        if not order_column:
            raise RuntimeError(f"postgres_sql profile `{profile}` resolved empty column list for `{schema}.{table}`")

        raw_limit = config.get("sql_profile_limit", config.get("sql_limit", max_records))
        limit_value = max(1, min(50000, int(raw_limit or max_records)))
        table_expr = self._quote_qualified_table(schema=schema, table=table)
        order_expr = self._quote_sql_identifier(order_column)

        where_clause = ""
        if cursor_column:
            cursor_expr = self._quote_sql_identifier(cursor_column)
            cursor_dtype = str(column_types.get(cursor_column.lower()) or "").lower()
            cursor_cast = self._cursor_param_cast(cursor_dtype)
            if cursor_cast:
                where_clause = (
                    f"WHERE (%({cursor_param})s{cursor_cast} IS NULL OR {cursor_expr} > %({cursor_param})s{cursor_cast})"
                )
            else:
                where_clause = (
                    f"WHERE (%({cursor_param})s::text IS NULL OR {cursor_expr}::text > %({cursor_param})s::text)"
                )

        query = f"SELECT * FROM {table_expr} {where_clause} ORDER BY {order_expr} ASC LIMIT {limit_value}"
        state_patch: dict[str, Any] = {
            "sql_profile": profile,
            "sql_profile_resolved_table": f"{schema}.{table}",
            "sql_profile_resolved_at": datetime.now(UTC).isoformat(),
        }
        if cursor_column:
            state_patch["sql_cursor_column"] = cursor_column
        if not str(config.get("sql_profile_table") or "").strip():
            state_patch["sql_profile_table"] = f"{schema}.{table}"
        if not str(config.get("sql_source_id_prefix") or "").strip():
            state_patch["sql_source_id_prefix"] = str(preset.get("default_source_id_prefix") or source_ref or profile)

        return {
            "query": query,
            "sql_mapping": merged_mapping,
            "cursor_column": cursor_column,
            "cursor_param": cursor_param,
            "warnings": warnings,
            "state_patch": state_patch,
        }

    def _resolve_existing_sql_table(self, *, dsn: str, candidates: list[str]) -> dict[str, Any] | None:
        try:
            import psycopg
        except ModuleNotFoundError as exc:
            raise RuntimeError("psycopg runtime dependency is missing for postgres_sql profile resolution") from exc

        for candidate in candidates:
            parsed = self._parse_table_candidate(candidate)
            if parsed is None:
                continue
            schema_name, table_name = parsed
            with psycopg.connect(dsn) as conn:
                with conn.cursor() as cur:
                    if schema_name:
                        cur.execute(
                            """
                            SELECT table_schema, table_name, column_name, data_type, ordinal_position
                            FROM information_schema.columns
                            WHERE table_schema = %s
                              AND table_name = %s
                            ORDER BY ordinal_position ASC
                            """,
                            (schema_name, table_name),
                        )
                    else:
                        cur.execute(
                            """
                            SELECT table_schema, table_name, column_name, data_type, ordinal_position
                            FROM information_schema.columns
                            WHERE table_name = %s
                              AND table_schema IN (CURRENT_SCHEMA(), 'public')
                            ORDER BY CASE
                                WHEN table_schema = CURRENT_SCHEMA() THEN 0
                                WHEN table_schema = 'public' THEN 1
                                ELSE 2
                              END,
                              ordinal_position ASC
                            """,
                            (table_name,),
                        )
                    rows = cur.fetchall() or []
            if not rows:
                continue
            selected_schema = str(rows[0][0]).strip()
            selected_table = str(rows[0][1]).strip()
            columns: list[str] = []
            column_types: dict[str, str] = {}
            for row in rows:
                row_schema = str(row[0]).strip()
                row_table = str(row[1]).strip()
                if row_schema != selected_schema or row_table != selected_table:
                    continue
                column_name = str(row[2]).strip()
                if not column_name:
                    continue
                columns.append(column_name)
                column_types[column_name.lower()] = str(row[3] or "").strip().lower()
            if columns:
                return {
                    "schema": selected_schema,
                    "table": selected_table,
                    "columns": columns,
                    "column_types": column_types,
                }
        return None

    @staticmethod
    def _parse_table_candidate(value: str) -> tuple[str | None, str] | None:
        text = str(value or "").strip()
        if not text:
            return None
        parts = text.split(".")
        if len(parts) == 1:
            table = parts[0].strip()
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
                return None
            return None, table
        if len(parts) == 2:
            schema = parts[0].strip()
            table = parts[1].strip()
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema):
                return None
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
                return None
            return schema, table
        return None

    @staticmethod
    def _pick_existing_column(column_lookup: dict[str, str], candidates: Any) -> str:
        if not isinstance(candidates, list):
            return ""
        for item in candidates:
            token = str(item or "").strip().lower()
            if not token:
                continue
            resolved = column_lookup.get(token)
            if resolved:
                return resolved
        return ""

    @staticmethod
    def _pick_existing_columns(column_lookup: dict[str, str], candidates: Any) -> list[str]:
        if not isinstance(candidates, list):
            return []
        out: list[str] = []
        seen: set[str] = set()
        for item in candidates:
            token = str(item or "").strip().lower()
            if not token:
                continue
            resolved = column_lookup.get(token)
            if not resolved:
                continue
            dedup = resolved.lower()
            if dedup in seen:
                continue
            seen.add(dedup)
            out.append(resolved)
        return out

    @staticmethod
    def _quote_sql_identifier(identifier: str) -> str:
        text = str(identifier or "").strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", text):
            raise RuntimeError(f"unsafe SQL identifier `{identifier}`")
        return f'"{text}"'

    def _quote_qualified_table(self, *, schema: str, table: str) -> str:
        return f"{self._quote_sql_identifier(schema)}.{self._quote_sql_identifier(table)}"

    @staticmethod
    def _cursor_param_cast(data_type: str) -> str:
        normalized = str(data_type or "").strip().lower()
        if not normalized:
            return ""
        if "timestamp" in normalized:
            return "::timestamptz"
        if normalized == "date":
            return "::date"
        if normalized in {"smallint", "integer", "bigint"}:
            return "::bigint"
        if normalized in {"numeric", "decimal", "real", "double precision"}:
            return "::numeric"
        return ""

    def _collect_postgres_sql_wal_cdc(
        self,
        *,
        dsn: str,
        config: dict[str, Any],
        max_records: int,
        max_chars: int,
        source_ref: str,
    ) -> tuple[LegacyImportResult, dict[str, Any]]:
        try:
            import psycopg
        except ModuleNotFoundError as exc:
            raise RuntimeError("psycopg runtime dependency is missing for postgres_sql wal_cdc mode") from exc

        slot = str(config.get("wal_slot") or "").strip()
        if not slot:
            raise RuntimeError("missing wal_slot for postgres_sql wal_cdc mode")
        plugin = str(config.get("wal_plugin") or "test_decoding").strip() or "test_decoding"
        parser_mode = str(config.get("wal_parser_mode") or plugin).strip().lower() or "test_decoding"
        if parser_mode not in {"test_decoding", "wal2json"}:
            raise RuntimeError("wal_parser_mode must be test_decoding or wal2json")
        allow_create_slot = bool(config.get("wal_create_slot_if_missing", False))
        acknowledge = bool(config.get("wal_acknowledge", True))
        read_limit = max(1, min(max_records, int(config.get("wal_max_changes", max_records))))
        function_name = "pg_logical_slot_get_changes" if acknowledge else "pg_logical_slot_peek_changes"
        cursor_key = str(config.get("wal_cursor_state_key") or "sql_last_lsn").strip() or "sql_last_lsn"

        options_dict = config.get("wal_options") if isinstance(config.get("wal_options"), dict) else {}
        option_pairs: list[str] = []
        for key in sorted(options_dict.keys()):
            norm_key = str(key).strip()
            if not norm_key:
                continue
            value = str(options_dict[key]).strip()
            if not value:
                continue
            option_pairs.extend([norm_key, value])

        table_allowlist = self._normalize_string_set(config.get("wal_table_allowlist"))
        operation_allowlist = self._normalize_string_set(config.get("wal_operation_allowlist"))
        if not operation_allowlist:
            operation_allowlist = {"insert", "update", "delete"}
        content_fields = self._normalize_string_list(
            config.get("wal_content_fields"),
            default=["content", "note", "text", "message", "summary", "body", "payload"],
        )
        include_raw = bool(config.get("wal_include_raw", False))
        source_id_field = str(config.get("wal_source_id_field") or "source_id").strip() or "source_id"
        entity_key_field = str(config.get("wal_entity_key_field") or "entity_key").strip() or "entity_key"
        category_field = str(config.get("wal_category_field") or "category").strip() or "category"
        observed_at_field = str(config.get("wal_observed_at_field") or "observed_at").strip() or "observed_at"
        source_id_prefix = str(config.get("wal_source_id_prefix") or config.get("sql_source_id_prefix") or source_ref).strip()
        source_id_prefix = source_id_prefix or "wal"

        warning_messages: list[str] = []
        records: list[dict[str, Any]] = []
        last_lsn = str(config.get(cursor_key) or config.get("sql_last_lsn") or config.get("wal_start_lsn") or "").strip()

        with psycopg.connect(dsn, autocommit=True) as db_conn:
            with db_conn.cursor() as cur:
                cur.execute("SELECT slot_name, plugin FROM pg_replication_slots WHERE slot_name = %s LIMIT 1", (slot,))
                slot_row = cur.fetchone()
                if slot_row is None:
                    if not allow_create_slot:
                        raise RuntimeError(
                            "replication slot not found for wal_cdc mode; set wal_create_slot_if_missing=true or create slot manually"
                        )
                    cur.execute("SELECT slot_name FROM pg_create_logical_replication_slot(%s, %s)", (slot, plugin))

                placeholders = ["%s", "NULL", "%s"]
                params: list[Any] = [slot, read_limit]
                if option_pairs:
                    placeholders.extend(["%s"] * len(option_pairs))
                    params.extend(option_pairs)
                sql = f"SELECT lsn::text, xid::text, data FROM {function_name}({', '.join(placeholders)})"
                cur.execute(sql, tuple(params))
                change_rows = cur.fetchall() or []

        for row_index, row in enumerate(change_rows, start=1):
            lsn_value = str(row[0] or "").strip()
            xid_value = str(row[1] or "").strip() if row[1] is not None else ""
            payload = str(row[2] or "")
            if not lsn_value or not payload.strip():
                continue
            last_lsn = lsn_value
            parsed = self._parse_wal_payload(payload, parser_mode=parser_mode, warning_messages=warning_messages)
            for change_index, item in enumerate(parsed, start=1):
                operation = str(item.get("operation") or "").strip().lower()
                if operation_allowlist and operation not in operation_allowlist:
                    continue
                table = str(item.get("table") or "").strip().lower()
                if table_allowlist and table and table not in table_allowlist:
                    continue
                fields = item.get("fields") if isinstance(item.get("fields"), dict) else {}
                normalized_fields = {str(k).strip().lower(): v for k, v in fields.items() if str(k).strip()}

                content = self._pick_first_non_empty_value(normalized_fields, content_fields)
                if not content:
                    continue
                if len(content) > max_chars:
                    content = f"{content[:max_chars]}...(truncated)"

                source_id = self._pick_first_non_empty_value(normalized_fields, [source_id_field.lower()])
                if not source_id:
                    source_id = f"{source_id_prefix}:{lsn_value}:{row_index}:{change_index}"
                entity_key = self._pick_first_non_empty_value(normalized_fields, [entity_key_field.lower(), "entity", "entityid"])
                category = self._pick_first_non_empty_value(normalized_fields, [category_field.lower(), "type", "kind"])
                observed_at = self._pick_first_non_empty_value(
                    normalized_fields,
                    [observed_at_field.lower(), "updated_at", "created_at", "timestamp", "ts"],
                )

                metadata: dict[str, Any] = {
                    "wal_cdc": True,
                    "wal_slot": slot,
                    "wal_plugin": plugin,
                    "wal_parser_mode": parser_mode,
                    "wal_lsn": lsn_value,
                    "wal_xid": xid_value,
                    "wal_operation": operation,
                    "wal_table": table,
                }
                if include_raw:
                    metadata["wal_raw_payload"] = payload
                metadata_fields = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
                if metadata_fields:
                    metadata["wal_metadata"] = metadata_fields

                records.append(
                    {
                        "source_id": source_id,
                        "content": content,
                        "observed_at": observed_at or None,
                        "entity_key": entity_key or None,
                        "category": category or None,
                        "metadata": metadata,
                    }
                )
                if len(records) >= max_records:
                    break
            if len(records) >= max_records:
                break

        state_patch: dict[str, Any] = {}
        if last_lsn:
            previous_cursor = str(config.get(cursor_key) or "").strip()
            if last_lsn != previous_cursor:
                state_patch[cursor_key] = last_lsn
                state_patch["sql_last_synced_at"] = datetime.now(UTC).isoformat()
        return (
            LegacyImportResult(
                records=records,
                skipped_files=[],
                parser_warnings=warning_messages,
            ),
            state_patch,
        )

    @staticmethod
    def _normalize_string_set(value: Any) -> set[str]:
        if not isinstance(value, list):
            return set()
        return {
            str(item).strip().lower()
            for item in value
            if str(item).strip()
        }

    @staticmethod
    def _normalize_string_list(value: Any, *, default: list[str]) -> list[str]:
        if isinstance(value, list):
            parsed = [str(item).strip().lower() for item in value if str(item).strip()]
            if parsed:
                return parsed
        return [item.strip().lower() for item in default if item.strip()]

    @staticmethod
    def _pick_first_non_empty_value(fields: dict[str, Any], keys: list[str]) -> str:
        for key in keys:
            lookup = str(key).strip().lower()
            if not lookup:
                continue
            value = fields.get(lookup)
            if value is None:
                continue
            text = str(value).strip()
            if text and text.lower() != "null":
                return text
        return ""

    def _parse_wal_payload(
        self,
        payload: str,
        *,
        parser_mode: str,
        warning_messages: list[str],
    ) -> list[dict[str, Any]]:
        if parser_mode == "wal2json":
            return self._parse_wal2json_payload(payload, warning_messages=warning_messages)
        return self._parse_test_decoding_payload(payload, warning_messages=warning_messages)

    def _parse_wal2json_payload(self, payload: str, *, warning_messages: list[str]) -> list[dict[str, Any]]:
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            warning_messages.append("wal2json payload parse failed (invalid JSON)")
            return []
        if not isinstance(parsed, dict):
            warning_messages.append("wal2json payload parse failed (expected object)")
            return []

        changes = parsed.get("change")
        if not isinstance(changes, list):
            if all(key in parsed for key in ("kind", "table")):
                changes = [parsed]
            else:
                return []

        records: list[dict[str, Any]] = []
        for item in changes:
            if not isinstance(item, dict):
                continue
            schema = str(item.get("schema") or "").strip()
            table_name = str(item.get("table") or "").strip()
            table = ".".join(part for part in (schema, table_name) if part)
            operation = str(item.get("kind") or item.get("action") or "").strip().lower()

            fields: dict[str, Any] = {}
            column_names = item.get("columnnames")
            column_values = item.get("columnvalues")
            if isinstance(column_names, list) and isinstance(column_values, list):
                for index, column in enumerate(column_names):
                    key = str(column).strip().lower()
                    if not key:
                        continue
                    value = column_values[index] if index < len(column_values) else None
                    fields[key] = value
            old_keys = item.get("oldkeys")
            if isinstance(old_keys, dict):
                key_names = old_keys.get("keynames")
                key_values = old_keys.get("keyvalues")
                if isinstance(key_names, list) and isinstance(key_values, list):
                    for index, column in enumerate(key_names):
                        key = str(column).strip().lower()
                        if not key:
                            continue
                        value = key_values[index] if index < len(key_values) else None
                        fields.setdefault(key, value)

            records.append(
                {
                    "operation": self._normalize_wal_operation(operation),
                    "table": table.lower(),
                    "fields": fields,
                    "metadata": {},
                }
            )
        return records

    def _parse_test_decoding_payload(self, payload: str, *, warning_messages: list[str]) -> list[dict[str, Any]]:
        pattern = re.compile(r"^table\s+([^.]+)\.([^:]+):\s+([A-Z]+):\s*(.*)$", re.IGNORECASE)
        match = pattern.match(payload.strip())
        if not match:
            warning_messages.append("test_decoding payload parse failed (pattern mismatch)")
            return []
        schema = match.group(1).strip().lower()
        table = match.group(2).strip().lower()
        operation = self._normalize_wal_operation(match.group(3).strip().lower())
        body = match.group(4)

        fields: dict[str, Any] = {}
        field_pattern = re.compile(r"([A-Za-z0-9_]+)\[[^\]]+\]:(?:'((?:''|[^'])*)'|(\S+))")
        for raw_key, quoted, plain in field_pattern.findall(body):
            key = str(raw_key).strip().lower()
            if not key:
                continue
            if quoted != "":
                value = quoted.replace("''", "'")
            else:
                text = str(plain).strip()
                value = None if text.lower() in {"null", "<null>"} else text
            fields[key] = value

        return [
            {
                "operation": operation,
                "table": f"{schema}.{table}",
                "fields": fields,
                "metadata": {},
            }
        ]

    @staticmethod
    def _normalize_wal_operation(value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized in {"insert", "update", "delete"}:
            return normalized
        if normalized in {"truncate"}:
            return normalized
        return "update"

    def _load_known_fingerprints(self, conn, *, source_id: UUID, records: list[dict[str, Any]]) -> set[str]:
        fingerprints = {
            sha256(str(item.get("content") or "").strip().encode("utf-8")).hexdigest()
            for item in records
            if str(item.get("content") or "").strip()
        }
        if not fingerprints:
            return set()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT content_fingerprint
                FROM legacy_import_source_fingerprints
                WHERE source_id = %s
                  AND content_fingerprint = ANY(%s)
                """,
                (source_id, list(fingerprints)),
            )
            rows = cur.fetchall()
        return {str(row[0]).strip().lower() for row in rows if row and row[0]}

    def _upsert_fingerprints(self, conn, *, source_id: UUID, run_id: UUID, fingerprints: list[str]) -> None:
        if not fingerprints:
            return
        with conn.cursor() as cur:
            for fingerprint in fingerprints:
                cur.execute(
                    """
                    INSERT INTO legacy_import_source_fingerprints (
                      source_id,
                      content_fingerprint,
                      first_seen_at,
                      last_seen_at,
                      seen_count,
                      last_run_id
                    )
                    VALUES (%s, %s, NOW(), NOW(), 1, %s)
                    ON CONFLICT (source_id, content_fingerprint)
                    DO UPDATE SET
                      last_seen_at = NOW(),
                      seen_count = legacy_import_source_fingerprints.seen_count + 1,
                      last_run_id = EXCLUDED.last_run_id
                    """,
                    (source_id, fingerprint, run_id),
                )

    def _upload_records(
        self,
        *,
        project_id: str,
        records: list[dict[str, Any]],
        source_system: str,
        chunk_size: int,
        created_by: str,
        batch_id: str,
        curated_import: dict[str, Any] | None = None,
    ) -> str:
        try:
            from synapse_sdk import MemoryBackfillRecord, Synapse, SynapseConfig
        except ModuleNotFoundError as exc:
            raise RuntimeError("synapse_sdk runtime dependency is missing for legacy sync upload") from exc

        synapse = Synapse(
            SynapseConfig(
                api_url=self.api_url,
                project_id=project_id,
                api_key=self.api_key,
            )
        )
        run_batch_id = synapse.backfill_memory(
            [
                MemoryBackfillRecord(
                    source_id=str(item["source_id"]),
                    content=str(item["content"]),
                    observed_at=item.get("observed_at"),
                    entity_key=item.get("entity_key"),
                    category=item.get("category"),
                    metadata=dict(item.get("metadata") or {}),
                )
                for item in records
            ],
            batch_id=batch_id,
            source_system=source_system,
            created_by=created_by,
            chunk_size=chunk_size,
            curated_enabled=(curated_import or {}).get("enabled"),
            curated_source_systems=(curated_import or {}).get("source_systems"),
            curated_namespaces=(curated_import or {}).get("namespaces"),
            noise_preset=(curated_import or {}).get("noise_preset"),
            curated_drop_event_like=(curated_import or {}).get("drop_event_like"),
        )
        return str(run_batch_id)

    def _mark_run_completed(
        self,
        conn,
        *,
        run_id: UUID,
        source_id: UUID,
        records_collected: int,
        records_uploaded: int,
        skipped_files_count: int,
        warnings_count: int,
        batch_id: str,
        summary: dict[str, Any],
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE legacy_import_sync_runs
                SET status = 'completed',
                    records_collected = %s,
                    records_uploaded = %s,
                    skipped_files_count = %s,
                    warnings_count = %s,
                    batch_id = %s,
                    summary = %s,
                    error_message = NULL,
                    finished_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (
                    records_collected,
                    records_uploaded,
                    skipped_files_count,
                    warnings_count,
                    UUID(str(batch_id)),
                    Jsonb(summary),
                    run_id,
                ),
            )
            cur.execute(
                """
                UPDATE legacy_import_sources
                SET last_run_at = NOW(),
                    last_success_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (source_id,),
            )

    def _mark_run_skipped(self, conn, *, run_id: UUID, source_id: UUID, summary: dict[str, Any]) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE legacy_import_sync_runs
                SET status = 'skipped',
                    records_collected = %s,
                    records_uploaded = 0,
                    skipped_files_count = %s,
                    warnings_count = %s,
                    summary = %s,
                    error_message = NULL,
                    finished_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (
                    int(summary.get("records_collected", 0)),
                    len(summary.get("skipped_files") or []),
                    len(summary.get("warnings") or []),
                    Jsonb(summary),
                    run_id,
                ),
            )
            cur.execute(
                """
                UPDATE legacy_import_sources
                SET last_run_at = NOW(),
                    last_success_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (source_id,),
            )

    def _mark_run_failed(self, conn, *, run_id: UUID, source_id: UUID, error_message: str) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE legacy_import_sync_runs
                SET status = 'failed',
                    error_message = %s,
                    finished_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (error_message[:4000], run_id),
            )
            cur.execute(
                """
                UPDATE legacy_import_sources
                SET last_run_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (source_id,),
            )

    def _patch_source_config(self, conn, *, source_id: UUID, config_patch: dict[str, Any], updated_by: str) -> None:
        if not config_patch:
            return
        patch = {str(key): value for key, value in config_patch.items() if str(key).strip()}
        if not patch:
            return
        actor = (updated_by or self.default_requested_by).strip() or self.default_requested_by
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE legacy_import_sources
                SET config = COALESCE(config, '{}'::jsonb) || %s,
                    updated_by = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (Jsonb(patch), actor, source_id),
            )

    def _source_from_row(self, row: tuple[Any, ...]) -> LegacySourceRecord:
        config = row[6] if isinstance(row[6], dict) else {}
        return LegacySourceRecord(
            id=row[0],
            project_id=str(row[1]),
            source_type=str(row[2]),
            source_ref=str(row[3]),
            enabled=bool(row[4]),
            sync_interval_minutes=max(1, int(row[5] or 1440)),
            config=config,
        )
