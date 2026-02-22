-- Grand compte potentiel : 100+ appels/jour
ALTER TABLE pre_onboarding_leads
  ADD COLUMN IF NOT EXISTS is_enterprise BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE pre_onboarding_leads
SET is_enterprise = (daily_call_volume = '100+')
WHERE is_enterprise = FALSE AND daily_call_volume = '100+';

COMMENT ON COLUMN pre_onboarding_leads.is_enterprise IS 'Grand compte potentiel (daily_call_volume = 100+)';
