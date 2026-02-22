-- Numéro de téléphone pour rappel (quand wants_callback = true)
ALTER TABLE pre_onboarding_leads
  ADD COLUMN IF NOT EXISTS callback_phone TEXT;

COMMENT ON COLUMN pre_onboarding_leads.callback_phone IS 'Numéro pour rappel si wants_callback = true';
