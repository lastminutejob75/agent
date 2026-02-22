-- Amplitude horaire max par jour (signal business : cabinets 7h-21h = 14h)
ALTER TABLE pre_onboarding_leads
  ADD COLUMN IF NOT EXISTS max_daily_amplitude REAL;

COMMENT ON COLUMN pre_onboarding_leads.max_daily_amplitude IS 'Amplitude max (end - start) en heures sur la semaine ; >=10h = étendue, >=12h = élevée';
