#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import hmac
import json
import subprocess
import tempfile
from pathlib import Path


def _canonical(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True, default=str)


def _run_cli(input_file: Path, *, secret: str | None, expected_key_id: str | None) -> tuple[int, dict[str, object] | None]:
    cmd = ["python3", "scripts/verify_openclaw_provenance.py", "--input", str(input_file)]
    if secret is not None:
        cmd.extend(["--secret", secret])
    if expected_key_id is not None:
        cmd.extend(["--expected-key-id", expected_key_id])
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    parsed: dict[str, object] | None = None
    stdout = proc.stdout.strip()
    if stdout:
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            parsed = None
    return proc.returncode, parsed


def main() -> int:
    payload = {
        "project_id": "smoke_openclaw",
        "entity_key": "bc_omega",
        "category": "access_policy",
        "claim_text": "Gate is card-only after 10:00",
        "source_id": "dialog-44",
        "source_type": "external_event",
        "agent_id": "openclaw_dispatcher",
        "session_id": "sess-1",
    }
    canonical = _canonical(payload)
    secret = "smoke-secret"
    key_id = "smoke-key"
    payload_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    signature = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()

    signed_provenance = {
        "schema": "synapse.openclaw.provenance.v1",
        "integration": "openclaw",
        "mode": "signed",
        "signature_alg": "hmac-sha256",
        "signature": signature,
        "payload_sha256": payload_hash,
        "key_id": key_id,
    }
    digest_provenance = {
        "schema": "synapse.openclaw.provenance.v1",
        "integration": "openclaw",
        "mode": "digest_only",
        "signature_alg": "sha256",
        "signature": payload_hash,
        "payload_sha256": payload_hash,
    }

    with tempfile.TemporaryDirectory(prefix="synapse-prov-smoke-") as tmp_dir:
        tmp_path = Path(tmp_dir)

        signed_file = tmp_path / "signed.json"
        signed_file.write_text(json.dumps({"provenance": signed_provenance, "payload": payload}), encoding="utf-8")
        rc_signed, out_signed = _run_cli(signed_file, secret=secret, expected_key_id=key_id)
        if rc_signed != 0 or not isinstance(out_signed, dict):
            return 1
        verification_signed = out_signed.get("verification")
        if not isinstance(verification_signed, dict) or not bool(verification_signed.get("valid")):
            return 1

        digest_file = tmp_path / "digest.json"
        digest_file.write_text(json.dumps({"provenance": digest_provenance, "payload": payload}), encoding="utf-8")
        rc_digest, out_digest = _run_cli(digest_file, secret=None, expected_key_id=None)
        if rc_digest != 0 or not isinstance(out_digest, dict):
            return 1
        verification_digest = out_digest.get("verification")
        if not isinstance(verification_digest, dict) or not bool(verification_digest.get("valid")):
            return 1

        tampered_payload = dict(payload)
        tampered_payload["claim_text"] = "Tampered payload"
        tampered_file = tmp_path / "tampered.json"
        tampered_file.write_text(
            json.dumps({"provenance": signed_provenance, "payload": tampered_payload}),
            encoding="utf-8",
        )
        rc_tampered, out_tampered = _run_cli(tampered_file, secret=secret, expected_key_id=key_id)
        if rc_tampered == 0:
            return 1
        if isinstance(out_tampered, dict):
            verification_tampered = out_tampered.get("verification")
            if isinstance(verification_tampered, dict) and bool(verification_tampered.get("valid")):
                return 1

    print(json.dumps({"status": "ok", "checks": ["signed", "digest_only", "tamper_detected"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
