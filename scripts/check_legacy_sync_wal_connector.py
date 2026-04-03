#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
WORKER_SRC = ROOT_DIR / "services" / "worker"
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))


def main() -> int:
    from app.legacy_sync import LegacySyncEngine

    engine = LegacySyncEngine()

    warnings: list[str] = []
    test_decoding_payload = (
        "table public.ops_kb_items: INSERT: "
        "id[text]:'42' note[text]:'Ramp broken at warehouse 2' "
        "entity_key[text]:'warehouse_2' category[text]:'operations' "
        "updated_at[timestamp without time zone]:'2026-04-03T09:10:11Z'"
    )
    parsed_test_decoding = engine._parse_wal_payload(
        test_decoding_payload,
        parser_mode="test_decoding",
        warning_messages=warnings,
    )
    assert len(parsed_test_decoding) == 1, parsed_test_decoding
    td = parsed_test_decoding[0]
    assert td["operation"] == "insert", td
    assert td["table"] == "public.ops_kb_items", td
    assert td["fields"]["entity_key"] == "warehouse_2", td
    assert td["fields"]["note"] == "Ramp broken at warehouse 2", td

    wal2json_payload = json.dumps(
        {
            "change": [
                {
                    "kind": "update",
                    "schema": "public",
                    "table": "memory_items",
                    "columnnames": ["id", "content", "entity_key", "category", "updated_at"],
                    "columnvalues": [
                        "abc-1",
                        "Customer X prefers Slack",
                        "customer_x",
                        "customer_preferences",
                        "2026-04-03T10:20:30Z",
                    ],
                }
            ]
        }
    )
    parsed_wal2json = engine._parse_wal_payload(
        wal2json_payload,
        parser_mode="wal2json",
        warning_messages=warnings,
    )
    assert len(parsed_wal2json) == 1, parsed_wal2json
    wj = parsed_wal2json[0]
    assert wj["operation"] == "update", wj
    assert wj["table"] == "public.memory_items", wj
    assert wj["fields"]["content"] == "Customer X prefers Slack", wj

    fields = wj["fields"]
    content = engine._pick_first_non_empty_value(fields, ["content", "note"])
    entity_key = engine._pick_first_non_empty_value(fields, ["entity_key"])
    category = engine._pick_first_non_empty_value(fields, ["category"])
    observed_at = engine._pick_first_non_empty_value(fields, ["observed_at", "updated_at"])

    assert content == "Customer X prefers Slack", content
    assert entity_key == "customer_x", entity_key
    assert category == "customer_preferences", category
    assert observed_at == "2026-04-03T10:20:30Z", observed_at
    assert not warnings, warnings

    print(
        json.dumps(
            {
                "status": "ok",
                "checks": {
                    "test_decoding": True,
                    "wal2json": True,
                    "field_mapping": True,
                },
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
