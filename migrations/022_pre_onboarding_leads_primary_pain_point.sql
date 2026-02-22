-- Mini-diagnostic : point de douleur principal (wizard)

ALTER TABLE pre_onboarding_leads
  ADD COLUMN IF NOT EXISTS primary_pain_point TEXT;

CREATE INDEX IF NOT EXISTS ix_pre_onboarding_leads_primary_pain_point
  ON pre_onboarding_leads (primary_pain_point);
