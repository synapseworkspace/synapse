from __future__ import annotations

import unittest

from services.worker.app.legacy_sync import LegacySyncEngine


class _TestLegacySyncEngine(LegacySyncEngine):
    def __init__(self, *, column_type: str) -> None:
        super().__init__(api_url="http://api:8080")
        self._column_type = column_type

    def _resolve_existing_sql_table(self, *, dsn: str, candidates: list[str]):  # type: ignore[override]
        return {
            "schema": "public",
            "table": "ops_kb_items",
            "columns": ["id", "updated_at", "content", "category", "entity_key", "metadata"],
            "column_types": {
                "id": "text",
                "updated_at": self._column_type,
                "content": "text",
                "category": "text",
                "entity_key": "text",
                "metadata": "jsonb",
            },
        }


class SQLProfileQueryCastTests(unittest.TestCase):
    def test_profile_polling_query_types_both_cursor_sides_when_cast_available(self) -> None:
        engine = _TestLegacySyncEngine(column_type="timestamp with time zone")
        plan = engine._build_postgres_sql_profile_polling_plan(
            dsn="postgresql://example",
            config={"sql_profile": "ops_kb_items", "sql_cursor_column": "updated_at"},
            source_ref="postgres_sql:ops_kb_items",
            max_records=5000,
        )
        query = str(plan.get("query") or "")
        self.assertIn("(%(cursor)s::timestamptz IS NULL OR \"updated_at\" > %(cursor)s::timestamptz)", query)

    def test_profile_polling_query_falls_back_to_text_cast_for_unknown_cursor_type(self) -> None:
        engine = _TestLegacySyncEngine(column_type="jsonb")
        plan = engine._build_postgres_sql_profile_polling_plan(
            dsn="postgresql://example",
            config={"sql_profile": "ops_kb_items", "sql_cursor_column": "updated_at"},
            source_ref="postgres_sql:ops_kb_items",
            max_records=5000,
        )
        query = str(plan.get("query") or "")
        self.assertIn("(%(cursor)s::text IS NULL OR \"updated_at\"::text > %(cursor)s::text)", query)


if __name__ == "__main__":
    unittest.main()

