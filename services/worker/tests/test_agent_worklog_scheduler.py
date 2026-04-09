from __future__ import annotations

import types
import unittest
from unittest.mock import patch

from services.worker.scripts.run_agent_worklog_scheduler import _dedupe, _discover_agent_projects
from services.worker.scripts.run_worker_loop import build_jobs


class AgentWorklogSchedulerTests(unittest.TestCase):
    def test_dedupe_normalizes_whitespace_and_order(self) -> None:
        values = [" omega_demo ", "beta", "omega_demo", "", "  ", "beta", "gamma"]
        self.assertEqual(_dedupe(values), ["omega_demo", "beta", "gamma"])

    def test_discover_projects_graceful_when_db_unavailable(self) -> None:
        with patch("services.worker.scripts.run_agent_worklog_scheduler._get_conn", side_effect=RuntimeError("db_down")):
            self.assertEqual(_discover_agent_projects(limit=20), [])

    def test_worker_loop_includes_agent_worklog_job_when_enabled(self) -> None:
        args = types.SimpleNamespace(
            enable_wiki_synthesis=True,
            synthesis_extract_limit=200,
            synthesis_limit=100,
            synthesis_interval_sec=15,
            enable_legacy_sync=False,
            legacy_sync_enqueue_limit=50,
            legacy_sync_process_limit=50,
            legacy_sync_api_url="http://api:8080",
            legacy_sync_api_key="",
            legacy_sync_requested_by="legacy_sync_scheduler",
            legacy_sync_all_projects=True,
            enable_intelligence=False,
            intelligence_delivery_limit=200,
            intelligence_interval_sec=600,
            enable_auto_publish=False,
            auto_publish_limit_per_project=50,
            auto_publish_reviewed_by="synapse_autopublisher",
            enable_agent_worklogs=True,
            agent_worklogs_discover_limit=500,
            agent_worklogs_days_back=1,
            agent_worklogs_max_agents=500,
            agent_worklogs_max_logs_per_agent_page=14,
            agent_worklogs_generated_by="agent_worklog_scheduler",
            agent_worklogs_include_retired=False,
            agent_worklogs_respect_schedule=True,
            enable_agent_worklogs_realtime=True,
            agent_worklogs_realtime_interval_sec=300,
            agent_worklogs_realtime_lookback_minutes=15,
            agent_worklogs_interval_sec=86400,
        )
        jobs = build_jobs(args)
        names = [job.name for job in jobs]
        self.assertIn("agent_worklog_scheduler", names)
        self.assertIn("agent_worklog_realtime", names)

    def test_worker_loop_skips_agent_worklog_job_when_disabled(self) -> None:
        args = types.SimpleNamespace(
            enable_wiki_synthesis=True,
            synthesis_extract_limit=200,
            synthesis_limit=100,
            synthesis_interval_sec=15,
            enable_legacy_sync=False,
            legacy_sync_enqueue_limit=50,
            legacy_sync_process_limit=50,
            legacy_sync_api_url="http://api:8080",
            legacy_sync_api_key="",
            legacy_sync_requested_by="legacy_sync_scheduler",
            legacy_sync_all_projects=True,
            enable_intelligence=False,
            intelligence_delivery_limit=200,
            intelligence_interval_sec=600,
            enable_auto_publish=False,
            auto_publish_limit_per_project=50,
            auto_publish_reviewed_by="synapse_autopublisher",
            enable_agent_worklogs=False,
            agent_worklogs_discover_limit=500,
            agent_worklogs_days_back=1,
            agent_worklogs_max_agents=500,
            agent_worklogs_max_logs_per_agent_page=14,
            agent_worklogs_generated_by="agent_worklog_scheduler",
            agent_worklogs_include_retired=False,
            agent_worklogs_respect_schedule=True,
            enable_agent_worklogs_realtime=False,
            agent_worklogs_realtime_interval_sec=300,
            agent_worklogs_realtime_lookback_minutes=15,
            agent_worklogs_interval_sec=86400,
        )
        jobs = build_jobs(args)
        names = [job.name for job in jobs]
        self.assertNotIn("agent_worklog_scheduler", names)

    def test_worker_loop_can_disable_wiki_synthesis(self) -> None:
        args = types.SimpleNamespace(
            enable_wiki_synthesis=False,
            synthesis_extract_limit=200,
            synthesis_limit=100,
            synthesis_interval_sec=15,
            enable_legacy_sync=False,
            legacy_sync_enqueue_limit=50,
            legacy_sync_process_limit=50,
            legacy_sync_api_url="http://api:8080",
            legacy_sync_api_key="",
            legacy_sync_requested_by="legacy_sync_scheduler",
            legacy_sync_all_projects=True,
            enable_intelligence=False,
            intelligence_delivery_limit=200,
            intelligence_interval_sec=600,
            enable_auto_publish=False,
            auto_publish_limit_per_project=50,
            auto_publish_reviewed_by="synapse_autopublisher",
            enable_agent_worklogs=False,
            agent_worklogs_discover_limit=500,
            agent_worklogs_days_back=1,
            agent_worklogs_max_agents=500,
            agent_worklogs_max_logs_per_agent_page=14,
            agent_worklogs_generated_by="agent_worklog_scheduler",
            agent_worklogs_include_retired=False,
            agent_worklogs_respect_schedule=True,
            enable_agent_worklogs_realtime=False,
            agent_worklogs_realtime_interval_sec=300,
            agent_worklogs_realtime_lookback_minutes=15,
            agent_worklogs_interval_sec=86400,
        )
        jobs = build_jobs(args)
        names = [job.name for job in jobs]
        self.assertNotIn("wiki_synthesis", names)


if __name__ == "__main__":
    unittest.main()
