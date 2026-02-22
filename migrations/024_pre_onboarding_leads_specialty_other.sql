-- Précision optionnelle quand spécialité = "Autre" (step 1)
ALTER TABLE pre_onboarding_leads
  ADD COLUMN IF NOT EXISTS specialty_other TEXT;

COMMENT ON COLUMN pre_onboarding_leads.specialty_other IS 'Précision libre si medical_specialty = Autre';
