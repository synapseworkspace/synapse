ALTER TABLE claims
ADD COLUMN IF NOT EXISTS claim_fingerprint TEXT;

CREATE INDEX IF NOT EXISTS idx_claims_project_fingerprint
  ON claims (project_id, claim_fingerprint);

UPDATE claims
SET claim_fingerprint = encode(
  digest(
    lower(trim(project_id)) || '|' ||
    lower(trim(entity_key)) || '|' ||
    lower(trim(category)) || '|' ||
    lower(trim(claim_text)),
    'sha256'
  ),
  'hex'
)
WHERE claim_fingerprint IS NULL;

