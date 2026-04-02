from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
import threading
import time
from typing import Any, Literal

from fastapi import HTTPException
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

IDEMPOTENCY_TTL_SECONDS = int(os.getenv("IDEMPOTENCY_TTL_SECONDS", "86400"))
IDEMPOTENCY_IN_PROGRESS_WAIT_SECONDS = float(os.getenv("IDEMPOTENCY_IN_PROGRESS_WAIT_SECONDS", "5.0"))
IDEMPOTENCY_POLL_INTERVAL_SECONDS = float(os.getenv("IDEMPOTENCY_POLL_INTERVAL_SECONDS", "0.1"))
IDEMPOTENCY_CLEANUP_INTERVAL_SECONDS = float(os.getenv("IDEMPOTENCY_CLEANUP_INTERVAL_SECONDS", "60.0"))
IDEMPOTENCY_CLEANUP_BATCH_SIZE = int(os.getenv("IDEMPOTENCY_CLEANUP_BATCH_SIZE", "1000"))

_cleanup_lock = threading.Lock()
_last_cleanup_at_monotonic = 0.0


@dataclass
class IdempotencyDecision:
    mode: Literal["process", "replay"]
    response_code: int | None = None
    response_body: dict[str, Any] | None = None


def maybe_cleanup_expired_requests(conn: Connection) -> int:
    global _last_cleanup_at_monotonic
    now = time.monotonic()
    if now - _last_cleanup_at_monotonic < IDEMPOTENCY_CLEANUP_INTERVAL_SECONDS:
        return 0

    with _cleanup_lock:
        now = time.monotonic()
        if now - _last_cleanup_at_monotonic < IDEMPOTENCY_CLEANUP_INTERVAL_SECONDS:
            return 0

        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM idempotency_requests
                WHERE (endpoint, idempotency_key) IN (
                  SELECT endpoint, idempotency_key
                  FROM idempotency_requests
                  WHERE expires_at <= NOW()
                  ORDER BY expires_at
                  LIMIT %s
                )
                """,
                (IDEMPOTENCY_CLEANUP_BATCH_SIZE,),
            )
            deleted = cur.rowcount
        _last_cleanup_at_monotonic = now
        return deleted


def cleanup_expired_requests_now(conn: Connection, *, batch_size: int = IDEMPOTENCY_CLEANUP_BATCH_SIZE) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM idempotency_requests
            WHERE (endpoint, idempotency_key) IN (
              SELECT endpoint, idempotency_key
              FROM idempotency_requests
              WHERE expires_at <= NOW()
              ORDER BY expires_at
              LIMIT %s
            )
            """,
            (batch_size,),
        )
        return cur.rowcount


def acquire_request_slot(
    conn: Connection,
    *,
    endpoint: str,
    idempotency_key: str | None,
    request_payload: dict[str, Any],
) -> IdempotencyDecision:
    if not idempotency_key:
        return IdempotencyDecision(mode="process")

    request_hash = _compute_request_hash(request_payload)
    expires_at = datetime.now(UTC) + timedelta(seconds=IDEMPOTENCY_TTL_SECONDS)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO idempotency_requests (
              endpoint, idempotency_key, request_hash, status, expires_at
            )
            VALUES (%s, %s, %s, 'processing', %s)
            ON CONFLICT (endpoint, idempotency_key) DO NOTHING
            RETURNING endpoint
            """,
            (endpoint, idempotency_key, request_hash, expires_at),
        )
        created = cur.fetchone()
        if created:
            return IdempotencyDecision(mode="process")

    deadline = time.monotonic() + IDEMPOTENCY_IN_PROGRESS_WAIT_SECONDS

    while True:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT request_hash, status, response_code, response_body, expires_at
                FROM idempotency_requests
                WHERE endpoint = %s AND idempotency_key = %s
                """,
                (endpoint, idempotency_key),
            )
            row = cur.fetchone()

        if row is None:
            # Rare race (cleanup or manual deletion). Try to claim slot again.
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO idempotency_requests (
                      endpoint, idempotency_key, request_hash, status, expires_at
                    )
                    VALUES (%s, %s, %s, 'processing', %s)
                    ON CONFLICT (endpoint, idempotency_key) DO NOTHING
                    RETURNING endpoint
                    """,
                    (endpoint, idempotency_key, request_hash, expires_at),
                )
                if cur.fetchone():
                    return IdempotencyDecision(mode="process")
            continue

        if row["expires_at"] <= datetime.now(UTC):
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE idempotency_requests
                    SET request_hash = %s,
                        status = 'processing',
                        response_code = NULL,
                        response_body = NULL,
                        last_error = NULL,
                        created_at = NOW(),
                        updated_at = NOW(),
                        expires_at = %s
                    WHERE endpoint = %s
                      AND idempotency_key = %s
                      AND expires_at <= NOW()
                    """,
                    (request_hash, expires_at, endpoint, idempotency_key),
                )
                if cur.rowcount == 1:
                    return IdempotencyDecision(mode="process")
            continue

        if row["request_hash"] != request_hash:
            raise HTTPException(
                status_code=409,
                detail="Idempotency key was already used with a different request payload.",
            )

        if row["status"] == "completed":
            body = row["response_body"]
            return IdempotencyDecision(
                mode="replay",
                response_code=row["response_code"] or 200,
                response_body=body if isinstance(body, dict) else {},
            )

        if row["status"] == "failed":
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE idempotency_requests
                    SET status = 'processing',
                        response_code = NULL,
                        response_body = NULL,
                        last_error = NULL,
                        updated_at = NOW()
                    WHERE endpoint = %s
                      AND idempotency_key = %s
                      AND request_hash = %s
                      AND status = 'failed'
                    """,
                    (endpoint, idempotency_key, request_hash),
                )
                if cur.rowcount == 1:
                    return IdempotencyDecision(mode="process")
            continue

        if time.monotonic() >= deadline:
            raise HTTPException(
                status_code=409,
                detail="Request with this idempotency key is currently in progress.",
                headers={"Retry-After": "1"},
            )

        time.sleep(max(0.01, IDEMPOTENCY_POLL_INTERVAL_SECONDS))


def mark_request_completed(
    conn: Connection,
    *,
    endpoint: str,
    idempotency_key: str | None,
    status_code: int,
    response_body: dict[str, Any],
) -> None:
    if not idempotency_key:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE idempotency_requests
            SET status = 'completed',
                response_code = %s,
                response_body = %s,
                updated_at = NOW()
            WHERE endpoint = %s
              AND idempotency_key = %s
            """,
            (status_code, Jsonb(response_body), endpoint, idempotency_key),
        )


def mark_request_failed(
    conn: Connection,
    *,
    endpoint: str,
    idempotency_key: str | None,
    error_message: str,
) -> None:
    if not idempotency_key:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE idempotency_requests
            SET status = 'failed',
                last_error = %s,
                updated_at = NOW()
            WHERE endpoint = %s
              AND idempotency_key = %s
            """,
            (error_message[:1000], endpoint, idempotency_key),
        )


def _compute_request_hash(payload: dict[str, Any]) -> str:
    canonical_payload = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
