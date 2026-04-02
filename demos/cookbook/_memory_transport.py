from __future__ import annotations

from typing import Any


class MemoryTransport:
    """In-memory transport for cookbook demos (no API/DB required)."""

    def __init__(self) -> None:
        self.events: list[Any] = []
        self.claims: list[Any] = []
        self.backfills: list[dict[str, Any]] = []

    def send_events(self, events: list[Any], *, idempotency_key: str | None = None) -> None:
        self.events.extend(events)

    def propose_fact(self, claim: Any, *, idempotency_key: str | None = None) -> None:
        self.claims.append(claim)

    def ingest_memory_backfill(self, batch_payload: dict[str, Any], *, idempotency_key: str | None = None) -> None:
        self.backfills.append(batch_payload)

    def summary(self) -> dict[str, int]:
        return {
            "events": len(self.events),
            "claims": len(self.claims),
            "backfill_batches": len(self.backfills),
        }
