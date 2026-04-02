from __future__ import annotations

import json
import sqlite3

from synapse_sdk import Synapse, SynapseConfig

from _memory_transport import MemoryTransport


def build_sample_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE warehouse_events (
            warehouse_id TEXT NOT NULL,
            status TEXT NOT NULL,
            observed_at TEXT NOT NULL
        )
        """
    )
    conn.executemany(
        "INSERT INTO warehouse_events (warehouse_id, status, observed_at) VALUES (?, ?, ?)",
        [
            ("warehouse_1", "closed_for_sanitation", "2026-03-31T08:00:00Z"),
            ("warehouse_1", "closed_for_sanitation", "2026-03-31T09:00:00Z"),
            ("warehouse_1", "open", "2026-03-31T12:00:00Z"),
            ("warehouse_2", "open", "2026-03-31T08:00:00Z"),
        ],
    )
    return conn


def run_demo() -> dict[str, object]:
    transport = MemoryTransport()
    synapse = Synapse(
        SynapseConfig(api_url="http://localhost:8080", project_id="cookbook_sql"),
        transport=transport,
    )

    @synapse.collect_insight(category="warehouse_policy", source_type="external_event", min_confidence=0.5)
    def evaluate_warehouse_policy(warehouse_id: str, conn: sqlite3.Connection) -> str:
        row = conn.execute(
            """
            SELECT COUNT(*)
            FROM warehouse_events
            WHERE warehouse_id = ?
              AND status = 'closed_for_sanitation'
            """,
            (warehouse_id,),
        ).fetchone()
        closed_count = int(row[0]) if row else 0
        if closed_count >= 2:
            return f"{warehouse_id} requires manual dispatch override; policy update is required due to sanitation closure pattern."
        return f"{warehouse_id} has no active closure pattern."

    conn = build_sample_db()
    summary_text = evaluate_warehouse_policy("warehouse_1", conn)
    synapse.flush()

    queued_claim_texts = [claim.claim_text for claim in transport.claims]
    return {
        "summary_text": summary_text,
        "transport": transport.summary(),
        "queued_claims": queued_claim_texts,
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
