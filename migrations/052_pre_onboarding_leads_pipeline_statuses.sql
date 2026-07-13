-- Aligne la contrainte PostgreSQL avec les statuts du pipeline admin.
-- `to_contact` reste accepté pour les imports/écritures historiques, même si
-- l'API le normalise actuellement vers `new`.

ALTER TABLE pre_onboarding_leads
  DROP CONSTRAINT IF EXISTS pre_onboarding_leads_status_check;

ALTER TABLE pre_onboarding_leads
  ADD CONSTRAINT pre_onboarding_leads_status_check
  CHECK (
    status IN (
      'new',
      'to_contact',
      'contacted',
      'interested',
      'demo_scheduled',
      'trial_offered',
      'trial_started',
      'converted',
      'lost',
      'later'
    )
  );
