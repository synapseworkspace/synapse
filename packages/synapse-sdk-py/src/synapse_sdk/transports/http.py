from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
import random
import time
from typing import Any, Sequence

import requests

from synapse_sdk.errors import SynapseTransportError
from synapse_sdk.types import Claim, ObservationEvent, RetryConfig


class HttpTransport:
    def __init__(
        self,
        api_url: str,
        api_key: str | None = None,
        *,
        retry: RetryConfig | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.retry = retry or RetryConfig()
        self.session = session or requests.Session()

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "HttpTransport":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def send_events(self, events: Sequence[ObservationEvent], *, idempotency_key: str | None = None) -> None:
        self._post_json(
            "/v1/events",
            {"events": [asdict(e) for e in events]},
            idempotency_key=idempotency_key,
        )

    def propose_fact(self, claim: Claim, *, idempotency_key: str | None = None) -> None:
        self._post_json(
            "/v1/facts/proposals",
            {"claim": asdict(claim)},
            idempotency_key=idempotency_key,
        )

    def ingest_memory_backfill(
        self,
        batch_payload: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> None:
        self._post_json(
            "/v1/backfill/memory",
            batch_payload,
            idempotency_key=idempotency_key,
        )

    def _post_json(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> None:
        self.request_json(path, method="POST", payload=payload, idempotency_key=idempotency_key)

    def request_json(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        method_upper = method.upper()
        attempt = 0
        while True:
            try:
                response = self.session.request(
                    method_upper,
                    f"{self.api_url}{path}",
                    json=payload if method_upper != "GET" else None,
                    params=params,
                    headers=self._headers(idempotency_key),
                    timeout=self.retry.timeout_seconds,
                )
            except requests.RequestException as exc:
                error = SynapseTransportError(
                    "Synapse API request failed due to network error",
                    retryable=True,
                )
                if not self._should_retry(attempt, error):
                    raise error from exc
                self._sleep_before_retry(attempt, retry_after_seconds=None)
                attempt += 1
                continue

            if 200 <= response.status_code < 300:
                if not response.text:
                    return {}
                try:
                    decoded = response.json()
                except ValueError:
                    return {}
                if isinstance(decoded, dict):
                    return decoded
                return {"data": decoded}

            retryable = response.status_code in self.retry.retryable_status_codes
            response_body = response.text[:2000] if response.text else None
            error = SynapseTransportError(
                f"Synapse API request failed with status {response.status_code}",
                retryable=retryable,
                status_code=response.status_code,
                response_body=response_body,
            )
            if not self._should_retry(attempt, error):
                raise error

            self._sleep_before_retry(attempt, retry_after_seconds=self._parse_retry_after(response))
            attempt += 1

    def _should_retry(self, attempt: int, error: SynapseTransportError) -> bool:
        return error.retryable and attempt < self.retry.max_retries

    def _sleep_before_retry(self, attempt: int, *, retry_after_seconds: float | None) -> None:
        exp_delay = min(self.retry.max_delay_seconds, self.retry.base_delay_seconds * (2**attempt))
        jitter_amplitude = max(0.0, exp_delay * self.retry.jitter_ratio)
        jitter = random.uniform(-jitter_amplitude, jitter_amplitude) if jitter_amplitude > 0 else 0.0
        delay = max(0.0, exp_delay + jitter)
        if retry_after_seconds is not None:
            delay = max(delay, retry_after_seconds)
        time.sleep(delay)

    def _parse_retry_after(self, response: requests.Response) -> float | None:
        raw_value = response.headers.get("Retry-After")
        if not raw_value:
            return None
        stripped = raw_value.strip()
        if stripped.isdigit():
            return float(max(0, int(stripped)))
        try:
            retry_dt = parsedate_to_datetime(stripped)
        except (TypeError, ValueError):
            return None
        if retry_dt.tzinfo is None:
            retry_dt = retry_dt.replace(tzinfo=UTC)
        return max(0.0, (retry_dt - datetime.now(UTC)).total_seconds())

    def _headers(self, idempotency_key: str | None = None) -> dict[str, str]:
        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["authorization"] = f"Bearer {self.api_key}"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers
