from __future__ import annotations

import unittest

from services.shared.legacy_profiles import list_legacy_mapper_templates, list_legacy_sync_runner_contracts


class LegacyMapperContractsTests(unittest.TestCase):
    def test_mapper_templates_include_profiles_and_modes(self) -> None:
        templates = list_legacy_mapper_templates(source_type="postgres_sql")
        self.assertTrue(len(templates) >= 4)
        keys = {str(item.get("template_key")) for item in templates}
        self.assertIn("postgres_sql.ops_kb_items.polling", keys)
        self.assertIn("postgres_sql.ops_kb_items.wal_cdc", keys)
        self.assertIn("postgres_sql.memory_items.polling", keys)
        self.assertIn("postgres_sql.memory_items.wal_cdc", keys)

    def test_mapper_templates_can_filter_profile(self) -> None:
        templates = list_legacy_mapper_templates(source_type="postgres_sql", profile="ops_kb_items")
        self.assertTrue(templates)
        self.assertTrue(all(str(item.get("profile")) == "ops_kb_items" for item in templates))

    def test_sync_contracts_expose_polling_and_cdc(self) -> None:
        contracts = list_legacy_sync_runner_contracts(source_type="postgres_sql")
        keys = {str(item.get("contract_key")) for item in contracts}
        self.assertIn("postgres_sql.polling", keys)
        self.assertIn("postgres_sql.wal_cdc", keys)

    def test_sync_contracts_include_scheduler_script(self) -> None:
        contracts = list_legacy_sync_runner_contracts(source_type="postgres_sql", profile="memory_items")
        self.assertTrue(contracts)
        polling = next((item for item in contracts if item.get("sync_mode") == "polling"), None)
        self.assertIsNotNone(polling)
        assert polling is not None
        runner = polling.get("runner") if isinstance(polling.get("runner"), dict) else {}
        self.assertTrue(str(runner.get("scheduler_script") or "").startswith("python services/worker/scripts/"))
        profile_hints = polling.get("profile_hints") if isinstance(polling.get("profile_hints"), list) else []
        self.assertEqual(profile_hints, ["memory_items"])


if __name__ == "__main__":
    unittest.main()
