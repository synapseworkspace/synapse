# OpenClaw Provenance Verification

Last updated: 2026-04-02

Synapse supports audit-time verification of OpenClaw provenance signatures.

## 1) API verification endpoint

`POST /v1/openclaw/provenance/verify`

Request body:

```json
{
  "provenance": {
    "schema": "synapse.openclaw.provenance.v1",
    "integration": "openclaw",
    "mode": "signed",
    "signature_alg": "hmac-sha256",
    "signature": "....",
    "payload_sha256": "....",
    "key_id": "ops-key-2026-04"
  },
  "payload": {
    "project_id": "omega_demo",
    "entity_key": "bc_omega",
    "category": "access_policy",
    "claim_text": "Gate is card-only after 10:00",
    "source_id": "dialog-44",
    "source_type": "external_event",
    "agent_id": "openclaw_dispatcher",
    "session_id": "sess-1"
  }
}
```

Response includes:
- `verification.valid`
- `verification.reason`
- hash/signature match diagnostics.

## 2) Offline CLI verification

Use local script:

```bash
python3 scripts/verify_openclaw_provenance.py \
  --input ./provenance_sample.json
```

Or with separate files:

```bash
python3 scripts/verify_openclaw_provenance.py \
  --provenance-file ./provenance.json \
  --payload-file ./payload.json
```

To verify via API:

```bash
python3 scripts/verify_openclaw_provenance.py \
  --input ./provenance_sample.json \
  --api-url http://localhost:8080
```

CI smoke check:

```bash
python3 scripts/smoke_openclaw_provenance_verification.py
```

## 3) Secrets and key id

Signed-mode verification uses:
- `SYNAPSE_OPENCLAW_PROVENANCE_SECRET` (or `SYNAPSE_PROVENANCE_SECRET`)
- `SYNAPSE_OPENCLAW_PROVENANCE_KEY_ID` (or `SYNAPSE_PROVENANCE_KEY_ID`)

If secret is not configured, signed payloads cannot be validated (`secret_missing_for_signed_provenance`).
