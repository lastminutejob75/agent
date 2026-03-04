-- Journal de notes (JSON array) et date de relance pour la fiche lead admin
ALTER TABLE pre_onboarding_leads
  ADD COLUMN IF NOT EXISTS notes_log JSONB DEFAULT '[]',
  ADD COLUMN IF NOT EXISTS follow_up_at TIMESTAMPTZ;

COMMENT ON COLUMN pre_onboarding_leads.notes_log IS 'Journal chronologique [{text, created_at, action?}]';
COMMENT ON COLUMN pre_onboarding_leads.follow_up_at IS 'Date de relance planifiée';
