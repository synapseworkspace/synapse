from __future__ import annotations

import unittest

try:
    from services.api.app.main import (
        MemoryBackfillBatchIn,
        MemoryBackfillCuratedFilterIn,
        MemoryBackfillRecordIn,
        _apply_backfill_curated_filters,
        _build_adoption_import_connectors,
        _resolve_backfill_curated_options,
    )
except Exception:  # pragma: no cover - optional API dependency path in test env
    MemoryBackfillBatchIn = None
    MemoryBackfillCuratedFilterIn = None
    MemoryBackfillRecordIn = None
    _apply_backfill_curated_filters = None
    _build_adoption_import_connectors = None
    _resolve_backfill_curated_options = None


@unittest.skipIf(
    MemoryBackfillBatchIn is None
    or MemoryBackfillCuratedFilterIn is None
    or MemoryBackfillRecordIn is None
    or _apply_backfill_curated_filters is None
    or _resolve_backfill_curated_options is None
    or _build_adoption_import_connectors is None,
    "api curated-backfill helpers unavailable",
)
class BackfillCuratedFilterTests(unittest.TestCase):
    def test_default_knowledge_lane_balanced_drops_snapshot_payload(self) -> None:
        records = [
            MemoryBackfillRecordIn(
                source_id="order_snapshot_2026_04_08_01",
                content='{"order_id":"1","status":"new","amount":"100","currency":"USD","customer":"c1","route":"r1","driver":"d1","eta":"10m","warehouse":"w1"}',
                category="event_payload",
                metadata={"namespace": "ops"},
            ),
            MemoryBackfillRecordIn(
                source_id="dispatch_escalation_policy_v2",
                content="If priority customer has blocked payment, escalate to billing owner within 15 minutes.",
                category="process",
                metadata={"namespace": "ops"},
            ),
        ]
        batch = MemoryBackfillBatchIn(
            project_id="omega_demo",
            source_system="legacy_sync:postgres_sql",
            finalize=True,
            records=records,
        )
        options = _resolve_backfill_curated_options(batch, ingest_lane="knowledge")
        self.assertTrue(bool(options["enabled"]))
        self.assertEqual(options["noise_preset"], "balanced")

        kept, summary = _apply_backfill_curated_filters(
            records,
            batch_source_system=batch.source_system,
            options=options,
        )
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].source_id, "dispatch_escalation_policy_v2")
        self.assertEqual(summary["dropped_records"], 1)
        self.assertEqual(int(summary["drop_reasons"].get("noise_preset", 0)), 1)

    def test_curated_filters_apply_source_and_namespace_constraints(self) -> None:
        records = [
            MemoryBackfillRecordIn(
                source_id="kb_1",
                content="Warehouse #1 now requires card access after 18:00.",
                category="policy",
                metadata={"source_system": "ops_kb_sync", "namespace": "support"},
            ),
            MemoryBackfillRecordIn(
                source_id="kb_2",
                content="Keep",
                category="policy",
                metadata={"source_system": "other_sync", "namespace": "support"},
            ),
            MemoryBackfillRecordIn(
                source_id="kb_3",
                content="Keep",
                category="policy",
                metadata={"source_system": "ops_kb_sync", "namespace": "finance"},
            ),
        ]
        batch = MemoryBackfillBatchIn(
            project_id="omega_demo",
            source_system="legacy_sync:postgres_sql",
            curated=MemoryBackfillCuratedFilterIn(
                enabled=True,
                source_systems=["ops_kb_sync"],
                namespaces=["support"],
                noise_preset="off",
            ),
            records=records,
        )
        options = _resolve_backfill_curated_options(batch, ingest_lane="knowledge")
        kept, summary = _apply_backfill_curated_filters(
            records,
            batch_source_system=batch.source_system,
            options=options,
        )
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].source_id, "kb_1")
        self.assertEqual(int(summary["drop_reasons"].get("source_system", 0)), 1)
        self.assertEqual(int(summary["drop_reasons"].get("namespace", 0)), 1)

    def test_curated_explicit_disable_overrides_knowledge_default(self) -> None:
        records = [
            MemoryBackfillRecordIn(
                source_id="order_snapshot_2",
                content='{"id":"2","status":"open","amount":"10","currency":"USD","customer":"c2","driver":"d2","route":"r2","eta":"8m","warehouse":"w2"}',
                category="event_payload",
                metadata={"namespace": "ops"},
            )
        ]
        batch = MemoryBackfillBatchIn(
            project_id="omega_demo",
            source_system="legacy_sync:postgres_sql",
            curated=MemoryBackfillCuratedFilterIn(enabled=False, noise_preset="strict"),
            records=records,
        )
        options = _resolve_backfill_curated_options(batch, ingest_lane="knowledge")
        self.assertFalse(bool(options["enabled"]))
        kept, summary = _apply_backfill_curated_filters(
            records,
            batch_source_system=batch.source_system,
            options=options,
        )
        self.assertEqual(len(kept), 1)
        self.assertEqual(summary["dropped_records"], 0)

    def test_adoption_import_connectors_include_curated_defaults(self) -> None:
        connectors = _build_adoption_import_connectors(source_type="postgres_sql", profile=None)
        self.assertTrue(bool(connectors))
        ops_polling = next(
            (
                item
                for item in connectors
                if item.get("profile") == "ops_kb_items" and item.get("sync_mode") == "polling"
            ),
            None,
        )
        self.assertIsNotNone(ops_polling)
        config_patch = ops_polling.get("config_patch") if isinstance(ops_polling, dict) else {}
        curated = config_patch.get("curated_import") if isinstance(config_patch, dict) else {}
        self.assertEqual(bool(curated.get("enabled")), True)
        self.assertEqual(str(curated.get("noise_preset")), "balanced")


if __name__ == "__main__":
    unittest.main()
