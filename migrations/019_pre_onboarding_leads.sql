-- Table leads pré-onboarding (wizard "Créer votre assistante")
-- Index pour dashboard: status + created_at, daily_call_volume

CREATE TABLE IF NOT EXISTS pre_onboarding_leads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  email TEXT NOT NULL,
  daily_call_volume TEXT NOT NULL,
  assistant_name TEXT NOT NULL,
  voice_gender TEXT NOT NULL,
  opening_hours JSONB NOT NULL DEFAULT '{}',
  wants_callback BOOLEAN NOT NULL DEFAULT FALSE,
  source TEXT NOT NULL DEFAULT 'landing_cta',
  status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'contacted', 'converted', 'lost')),
  notes TEXT,
  tenant_id BIGINT REFERENCES tenants(tenant_id),
  contacted_at TIMESTAMPTZ,
  converted_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_pre_onboarding_leads_status_created_at
  ON pre_onboarding_leads (status, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_pre_onboarding_leads_daily_call_volume
  ON pre_onboarding_leads (daily_call_volume);

CREATE INDEX IF NOT EXISTS ix_pre_onboarding_leads_email
  ON pre_onboarding_leads (email);
