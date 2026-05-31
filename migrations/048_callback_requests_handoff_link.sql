-- Lien entre demandes de rappel unifiées et handoffs vocaux.
ALTER TABLE callback_requests ADD COLUMN IF NOT EXISTS call_id TEXT;
ALTER TABLE callback_requests ADD COLUMN IF NOT EXISTS handoff_id BIGINT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_callback_requests_handoff_unique
  ON callback_requests (tenant_id, handoff_id)
  WHERE handoff_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_callback_requests_call_id
  ON callback_requests (tenant_id, call_id)
  WHERE call_id IS NOT NULL;
