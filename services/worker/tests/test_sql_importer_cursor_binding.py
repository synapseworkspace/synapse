from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

from app.legacy_import import SQLImporter


class _FakeCursor:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows
        self.execute_calls: list[tuple[object, ...]] = []

    def __enter__(self) -> "_FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, *args: object) -> None:
        self.execute_calls.append(args)

    def fetchall(self) -> list[dict[str, object]]:
        return list(self._rows)


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor

    def __enter__(self) -> "_FakeConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def cursor(self) -> _FakeCursor:
        return self._cursor


class SQLImporterCursorBindingTests(unittest.TestCase):
    def test_collect_records_binds_named_cursor_placeholder_even_when_none(self) -> None:
        rows = [
            {
                "id": "1",
                "content": "Gate card required after 18:00",
                "entity_key": "customer_omega",
                "category": "access_policy",
                "observed_at": "2026-04-09T00:00:00Z",
            }
        ]
        fake_cursor = _FakeCursor(rows)
        fake_conn = _FakeConnection(fake_cursor)

        fake_psycopg = types.ModuleType("psycopg")
        fake_rows = types.ModuleType("psycopg.rows")
        fake_dict_row = object()
        fake_rows.dict_row = fake_dict_row

        def _connect(dsn: str, *, row_factory: object = None) -> _FakeConnection:
            self.assertEqual("postgresql://example.local/test", dsn)
            self.assertIs(row_factory, fake_dict_row)
            return fake_conn

        fake_psycopg.connect = _connect  # type: ignore[attr-defined]

        importer = SQLImporter(
            dsn="postgresql://example.local/test",
            query="SELECT * FROM events WHERE (%(cursor)s IS NULL OR id::text > %(cursor)s::text)",
        )

        with patch.dict(sys.modules, {"psycopg": fake_psycopg, "psycopg.rows": fake_rows}):
            result = importer.collect_records(max_records=10, cursor=None, cursor_param="cursor")

        self.assertEqual(1, len(result.records))
        self.assertEqual(1, len(fake_cursor.execute_calls))
        execute_args = fake_cursor.execute_calls[0]
        self.assertEqual(2, len(execute_args))
        self.assertEqual(
            "SELECT * FROM events WHERE (%(cursor)s IS NULL OR id::text > %(cursor)s::text)",
            execute_args[0],
        )
        self.assertEqual({"cursor": None}, execute_args[1])

    def test_collect_records_advances_cursor_from_id_when_observed_at_missing(self) -> None:
        rows = [
            {
                "id": 41,
                "content": "Policy update for access gate",
                "entity_key": "warehouse_2",
                "category": "access_policy",
            },
            {
                "id": 42,
                "content": "Policy update for access gate with escalation",
                "entity_key": "warehouse_2",
                "category": "access_policy",
            },
        ]
        fake_cursor = _FakeCursor(rows)
        fake_conn = _FakeConnection(fake_cursor)

        fake_psycopg = types.ModuleType("psycopg")
        fake_rows = types.ModuleType("psycopg.rows")
        fake_dict_row = object()
        fake_rows.dict_row = fake_dict_row

        def _connect(dsn: str, *, row_factory: object = None) -> _FakeConnection:
            self.assertEqual("postgresql://example.local/test", dsn)
            self.assertIs(row_factory, fake_dict_row)
            return fake_conn

        fake_psycopg.connect = _connect  # type: ignore[attr-defined]

        importer = SQLImporter(
            dsn="postgresql://example.local/test",
            query="SELECT * FROM events ORDER BY id ASC",
        )
        with patch.dict(sys.modules, {"psycopg": fake_psycopg, "psycopg.rows": fake_rows}):
            result = importer.collect_records(max_records=10, cursor=None, cursor_param="cursor")

        self.assertEqual(2, len(result.records))
        self.assertEqual("42", result.next_cursor)


if __name__ == "__main__":
    unittest.main()
