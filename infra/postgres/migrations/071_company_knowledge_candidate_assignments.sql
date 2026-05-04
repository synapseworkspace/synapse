ALTER TABLE company_knowledge_candidates
  ADD COLUMN IF NOT EXISTS assignment_status TEXT NOT NULL DEFAULT 'unassigned',
  ADD COLUMN IF NOT EXISTS assignment_priority TEXT NOT NULL DEFAULT 'medium',
  ADD COLUMN IF NOT EXISTS assigned_to TEXT,
  ADD COLUMN IF NOT EXISTS assigned_team TEXT,
  ADD COLUMN IF NOT EXISTS assigned_by TEXT,
  ADD COLUMN IF NOT EXISTS assigned_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS due_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS assignment_note TEXT;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'company_knowledge_candidates_assignment_status_check'
  ) THEN
    ALTER TABLE company_knowledge_candidates
      ADD CONSTRAINT company_knowledge_candidates_assignment_status_check
      CHECK (assignment_status IN ('unassigned', 'queued', 'assigned', 'resolved'));
  END IF;
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'company_knowledge_candidates_assignment_priority_check'
  ) THEN
    ALTER TABLE company_knowledge_candidates
      ADD CONSTRAINT company_knowledge_candidates_assignment_priority_check
      CHECK (assignment_priority IN ('low', 'medium', 'high'));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_company_knowledge_candidates_assignment
  ON company_knowledge_candidates (project_id, assignment_status, assignment_priority, updated_at DESC);
