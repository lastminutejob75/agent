-- Label affiché pour la spécialité (slug stocké dans medical_specialty)
ALTER TABLE pre_onboarding_leads
  ADD COLUMN IF NOT EXISTS medical_specialty_label TEXT;

COMMENT ON COLUMN pre_onboarding_leads.medical_specialty_label IS 'Label affiché (ex: Kinésithérapeute) ; medical_specialty = slug (ex: kinesitherapeute)';
