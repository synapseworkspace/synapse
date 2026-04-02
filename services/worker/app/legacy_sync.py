from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
import os
import sys
from typing import Any
from uuid import UUID, uuid4

try:
    from psycopg.types.json import Jsonb
except Exception:  # pragma: no cover - offline mode without psycopg runtime
    class Jsonb:  # type: ignore[override]
        def __init__(self, obj: Any):
            self.obj = obj

from app.legacy_import import (
    LegacyImporter,
    LegacySeedOrchestrator,
    NotionApiClient,
    NotionImportConfig,
    NotionImporter,
    SUPPORTED_EXTENSIONS,
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
    """Periodic orchestration for legacy import sources (local + Notion)."""

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

        collected = self._collect_records(source=source, max_records=max_records)
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
        )
        summary["batch_id"] = batch_id
        summary["source_system"] = source_system
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

    def _collect_records(self, *, source: LegacySourceRecord, max_records: int):
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
            return importer.collect_records(max_records=max_records)

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
            return notion_importer.collect_from_root_page(source.source_ref, max_records=max_records)
        if source.source_type == "notion_database":
            return notion_importer.collect_from_database(source.source_ref, max_records=max_records)
        raise RuntimeError(f"unsupported source_type: {source.source_type}")

    def _resolve_notion_token(self, config: dict[str, Any]) -> str | None:
        token = str(config.get("notion_token") or "").strip()
        if token:
            return token
        env_name = str(config.get("notion_token_env") or "NOTION_TOKEN").strip()
        return str(os.getenv(env_name) or "").strip() or None

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

    def _source_from_row(self, row: tuple[Any, ...]) -> LegacySourceRecord:
        config = row[6] if isinstance(row[6], dict) else {}
        return LegacySourceRecord(
            id=row[0],
            project_id=str(row[1]),
            source_type=str(row[2]),
            source_ref=str(row[3]),
            enabled=bool(row[4]),
            sync_interval_minutes=max(15, int(row[5] or 1440)),
            config=config,
        )
