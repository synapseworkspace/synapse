CREATE TABLE IF NOT EXISTS gatekeeper_calibration_queue_audit_annotations (
  id UUID PRIMARY KEY,
  event_id BIGINT NOT NULL REFERENCES gatekeeper_calibration_queue_control_events(id) ON DELETE CASCADE,
  project_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('acknowledged', 'resolved')),
  note TEXT,
  follow_up_owner TEXT,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_queue_audit_annotations_event_created
  ON gatekeeper_calibration_queue_audit_annotations (event_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_gatekeeper_queue_audit_annotations_project_created
  ON gatekeeper_calibration_queue_audit_annotations (project_id, created_at DESC);
