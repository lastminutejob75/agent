-- Créneau de rappel réservé (écran finalisation UWI)
ALTER TABLE pre_onboarding_leads
  ADD COLUMN IF NOT EXISTS callback_booking_date DATE,
  ADD COLUMN IF NOT EXISTS callback_booking_slot  VARCHAR(50);

COMMENT ON COLUMN pre_onboarding_leads.callback_booking_date IS 'Date du créneau de rappel choisi (écran finalisation)';
COMMENT ON COLUMN pre_onboarding_leads.callback_booking_slot IS 'Créneau horaire (ex: 9h00)';
