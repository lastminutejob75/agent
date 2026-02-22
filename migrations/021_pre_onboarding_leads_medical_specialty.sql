-- Qualification lead : spécialité médicale (wizard step 1)

ALTER TABLE pre_onboarding_leads
  ADD COLUMN IF NOT EXISTS medical_specialty TEXT;

CREATE INDEX IF NOT EXISTS ix_pre_onboarding_leads_medical_specialty
  ON pre_onboarding_leads (medical_specialty);
