from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from app.legacy_sync import LegacySyncEngine


class _FakeHttpResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> "_FakeHttpResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class MemoryApiConnectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = LegacySyncEngine(api_url="http://localhost:8080")

    @patch("services.worker.app.legacy_sync.url_request.urlopen")
    def test_collect_memory_api_maps_records_and_cursor(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _FakeHttpResponse(
            {
                "items": [
                    {
                        "id": "m-1",
                        "text": "Dispatch rule changed for BC Omega",
                        "updated_at": "2026-04-08T09:00:00Z",
                        "entity": {"id": "bc_omega"},
                        "type": "policy",
                        "meta": {"source": "ops"},
                    }
                ],
                "next_cursor": "cursor-2",
            }
        )
        result, source_patch = self.engine._collect_memory_api(
            config={
                "api_url": "https://memory.company/v1/items",
                "api_method": "GET",
                "api_records_path": "items",
                "api_pagination_cursor_path": "next_cursor",
                "api_limit": 100,
                "api_mapping": {
                    "source_id": "id",
                    "content": "text",
                    "observed_at": "updated_at",
                    "entity_key": "entity.id",
                    "category": "type",
                    "metadata": "meta",
                },
            },
            source_ref="memory_api_prod",
            max_records=1,
            max_chars=500,
        )
        self.assertEqual(len(result.records), 1)
        row = result.records[0]
        self.assertEqual(row.get("source_id"), "m-1")
        self.assertEqual(row.get("entity_key"), "bc_omega")
        self.assertEqual(row.get("category"), "policy")
        self.assertEqual(row.get("metadata"), {"source": "ops", "memory_api_raw_keys": ["entity", "id", "meta", "text", "type", "updated_at"]})
        self.assertEqual(source_patch.get("api_cursor"), "cursor-2")

    @patch("services.worker.app.legacy_sync.url_request.urlopen")
    def test_collect_memory_api_raises_when_records_path_is_not_list(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _FakeHttpResponse({"items": {"id": "x"}})
        with self.assertRaises(RuntimeError):
            self.engine._collect_memory_api(
                config={
                    "api_url": "https://memory.company/v1/items",
                    "api_records_path": "items",
                    "api_mapping": {"content": "text"},
                },
                source_ref="memory_api_prod",
                max_records=1,
                max_chars=500,
            )


if __name__ == "__main__":
    unittest.main()
