-- Demandes de rendez-vous issues des pages publiques /p/:slug.
-- Statuts: pending, confirmed, cancelled.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public_bookings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id BIGINT REFERENCES tenants(tenant_id) ON DELETE SET NULL,
  slot_id VARCHAR(80),
  slot_label VARCHAR(140),
  patient_name VARCHAR(200) NOT NULL,
  patient_phone VARCHAR(40) NOT NULL,
  motif VARCHAR(120),
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  source VARCHAR(40) DEFAULT 'page_publique',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  confirmed_at TIMESTAMPTZ,
  cancelled_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_public_bookings_tenant_created
  ON public_bookings (tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_public_bookings_status_created
  ON public_bookings (status, created_at DESC);
