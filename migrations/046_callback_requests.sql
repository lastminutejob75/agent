-- Demandes de rappel depuis la page publique.
CREATE TABLE IF NOT EXISTS callback_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id BIGINT REFERENCES tenants(tenant_id) ON DELETE SET NULL,
  appointment_source TEXT,
  appointment_id TEXT,
  patient_id BIGINT,
  name TEXT,
  phone TEXT NOT NULL,
  email TEXT,
  reason TEXT NOT NULL DEFAULT 'other',
  message TEXT,
  source TEXT NOT NULL DEFAULT 'public_page',
  status TEXT NOT NULL DEFAULT 'new',
  unmatched BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  handled_at TIMESTAMPTZ,
  handled_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_callback_requests_tenant_created
  ON callback_requests (tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_callback_requests_status
  ON callback_requests (tenant_id, status, created_at DESC);
