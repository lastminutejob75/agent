-- Analytics events for public practitioner pages /p/:slug.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public_page_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id BIGINT REFERENCES tenants(tenant_id) ON DELETE SET NULL,
  slug VARCHAR(160) NOT NULL,
  event_name VARCHAR(80) NOT NULL,
  source VARCHAR(40) DEFAULT 'direct',
  slot_id VARCHAR(80),
  slot_label VARCHAR(140),
  motif VARCHAR(120),
  question VARCHAR(180),
  query VARCHAR(180),
  results_count INT,
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_public_page_events_slug_created
  ON public_page_events (slug, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_public_page_events_tenant_created
  ON public_page_events (tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_public_page_events_event_created
  ON public_page_events (event_name, created_at DESC);
