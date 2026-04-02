#!/usr/bin/env bash
set -euo pipefail

API_URL="${SYNAPSE_API_URL:-http://localhost:8080}"
EVENT_ID="11111111-1111-4111-8111-111111111111"
NOW="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

payload() {
  cat <<JSON
{
  "events": [
    {
      "id": "${EVENT_ID}",
      "schema_version": "v1",
      "project_id": "smoke_project",
      "agent_id": "smoke_agent",
      "session_id": "smoke_session",
      "event_type": "agent_message",
      "payload": {"text": "Smoke event from m1 script"},
      "observed_at": "${NOW}",
      "tags": ["smoke", "m1"]
    }
  ]
}
JSON
}

echo "Posting event first time..."
FIRST_RESP="$(curl -sS -X POST "${API_URL}/v1/events" -H "content-type: application/json" -H "Idempotency-Key: smoke-key" -d "$(payload)")"
echo "Response #1: ${FIRST_RESP}"

echo "Posting same event second time (should deduplicate by id)..."
SECOND_RESP="$(curl -sS -X POST "${API_URL}/v1/events" -H "content-type: application/json" -H "Idempotency-Key: smoke-key" -d "$(payload)")"
echo "Response #2: ${SECOND_RESP}"

echo "Smoke script done. Expect second response inserted=0." 
