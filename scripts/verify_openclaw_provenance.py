#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _read_json_file(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        loaded = json.load(handle)
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return loaded


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True, default=str)


def _verify(
    *,
    provenance: dict[str, Any],
    payload: dict[str, Any],
    secret: str | None,
    expected_key_id: str | None,
) -> dict[str, Any]:
    schema = str(provenance.get("schema") or "").strip()
    integration = str(provenance.get("integration") or "").strip().lower()
    mode = str(provenance.get("mode") or "").strip().lower()
    signature_alg = str(provenance.get("signature_alg") or "").strip().lower()
    provided_signature = str(provenance.get("signature") or "").strip().lower()
    provided_hash = str(provenance.get("payload_sha256") or "").strip().lower()
    key_id = str(provenance.get("key_id") or "").strip() or None

    canonical = _canonical_json(payload)
    computed_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    payload_hash_match = bool(provided_hash) and hmac.compare_digest(provided_hash, computed_hash)
    key_id_match = expected_key_id is None or key_id is None or key_id == expected_key_id

    if signature_alg == "hmac-sha256" or mode == "signed":
        if not secret:
            return {
                "valid": False,
                "reason": "secret_required_for_signed_mode",
                "schema": schema or None,
                "integration": integration or None,
                "mode": mode or "signed",
                "signature_alg": signature_alg or "hmac-sha256",
                "key_id": key_id,
                "expected_key_id": expected_key_id,
                "key_id_match": key_id_match,
                "computed_payload_sha256": computed_hash,
                "provided_payload_sha256": provided_hash or None,
                "payload_hash_match": payload_hash_match,
                "signature_match": False,
            }
        expected_signature = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        signature_match = bool(provided_signature) and hmac.compare_digest(provided_signature, expected_signature)
        valid = payload_hash_match and signature_match and key_id_match
        return {
            "valid": valid,
            "reason": "ok" if valid else ("key_id_mismatch" if not key_id_match else "signature_or_payload_mismatch"),
            "schema": schema or None,
            "integration": integration or None,
            "mode": mode or "signed",
            "signature_alg": signature_alg or "hmac-sha256",
            "key_id": key_id,
            "expected_key_id": expected_key_id,
            "key_id_match": key_id_match,
            "computed_payload_sha256": computed_hash,
            "provided_payload_sha256": provided_hash or None,
            "payload_hash_match": payload_hash_match,
            "signature_match": signature_match,
            "expected_signature": expected_signature,
        }

    expected_signature = computed_hash
    signature_match = bool(provided_signature) and hmac.compare_digest(provided_signature, expected_signature)
    valid = payload_hash_match and signature_match
    return {
        "valid": valid,
        "reason": "ok" if valid else "signature_or_payload_mismatch",
        "schema": schema or None,
        "integration": integration or None,
        "mode": mode or "digest_only",
        "signature_alg": signature_alg or "sha256",
        "key_id": key_id,
        "expected_key_id": expected_key_id,
        "key_id_match": key_id_match,
        "computed_payload_sha256": computed_hash,
        "provided_payload_sha256": provided_hash or None,
        "payload_hash_match": payload_hash_match,
        "signature_match": signature_match,
        "expected_signature": expected_signature,
    }


def _call_api(*, api_url: str, provenance: dict[str, Any], payload: dict[str, Any], timeout_sec: int) -> dict[str, Any]:
    body = json.dumps({"provenance": provenance, "payload": payload}, ensure_ascii=False).encode("utf-8")
    request = Request(
        url=f"{api_url.rstrip('/')}/v1/openclaw/provenance/verify",
        method="POST",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=max(1, timeout_sec)) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API request failed: {exc.code} {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"API request failed: {exc}") from exc

    decoded = json.loads(raw)
    if not isinstance(decoded, dict):
        raise RuntimeError("API response must be JSON object.")
    return decoded


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify OpenClaw provenance signature/hash payloads.")
    parser.add_argument("--input", help="JSON file containing {'provenance': {...}, 'payload': {...}}.")
    parser.add_argument("--provenance-file", help="JSON file with provenance object.")
    parser.add_argument("--payload-file", help="JSON file with canonical payload object.")
    parser.add_argument("--api-url", help="Optional Synapse API URL to run verification via backend endpoint.")
    parser.add_argument("--timeout-sec", type=int, default=15)
    parser.add_argument(
        "--secret",
        default=None,
        help="HMAC secret override for local verification (fallback: env SYNAPSE_OPENCLAW_PROVENANCE_SECRET|SYNAPSE_PROVENANCE_SECRET).",
    )
    parser.add_argument(
        "--expected-key-id",
        default=None,
        help="Optional expected key id override (fallback: env SYNAPSE_OPENCLAW_PROVENANCE_KEY_ID|SYNAPSE_PROVENANCE_KEY_ID).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.input:
        data = _read_json_file(args.input)
        provenance = data.get("provenance")
        payload = data.get("payload")
    else:
        if not args.provenance_file or not args.payload_file:
            raise SystemExit("--input or both --provenance-file and --payload-file are required.")
        provenance = _read_json_file(args.provenance_file)
        payload = _read_json_file(args.payload_file)

    if not isinstance(provenance, dict) or not isinstance(payload, dict):
        raise SystemExit("Input must include object fields: provenance, payload")

    if args.api_url:
        result = _call_api(
            api_url=str(args.api_url),
            provenance=provenance,
            payload=payload,
            timeout_sec=int(args.timeout_sec),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        verification = result.get("verification") if isinstance(result, dict) else None
        if not isinstance(verification, dict):
            return 1
        return 0 if bool(verification.get("valid")) else 1

    secret = args.secret
    if secret is None:
        secret = str(os.getenv("SYNAPSE_OPENCLAW_PROVENANCE_SECRET") or os.getenv("SYNAPSE_PROVENANCE_SECRET") or "").strip() or None
    expected_key_id = args.expected_key_id
    if expected_key_id is None:
        expected_key_id = (
            str(os.getenv("SYNAPSE_OPENCLAW_PROVENANCE_KEY_ID") or os.getenv("SYNAPSE_PROVENANCE_KEY_ID") or "").strip()
            or None
        )

    verification = _verify(
        provenance=provenance,
        payload=payload,
        secret=secret,
        expected_key_id=expected_key_id,
    )
    print(json.dumps({"status": "ok", "verification": verification}, ensure_ascii=False, indent=2))
    return 0 if bool(verification.get("valid")) else 1


if __name__ == "__main__":
    sys.exit(main())
