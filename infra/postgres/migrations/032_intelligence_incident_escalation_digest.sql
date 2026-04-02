ALTER TABLE intelligence_digests
  DROP CONSTRAINT IF EXISTS intelligence_digests_digest_kind_check;

ALTER TABLE intelligence_digests
  ADD CONSTRAINT intelligence_digests_digest_kind_check
  CHECK (digest_kind IN ('daily', 'weekly', 'incident_escalation_daily'));
