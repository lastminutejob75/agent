-- Déduplication v1 : updated_at + last_submitted_at pour upsert par email (new/contacted)

ALTER TABLE pre_onboarding_leads
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS last_submitted_at TIMESTAMPTZ;

UPDATE pre_onboarding_leads
SET updated_at = COALESCE(updated_at, created_at),
    last_submitted_at = COALESCE(last_submitted_at, created_at)
WHERE updated_at IS NULL OR last_submitted_at IS NULL;

ALTER TABLE pre_onboarding_leads
  ALTER COLUMN updated_at SET DEFAULT NOW(),
  ALTER COLUMN last_submitted_at SET DEFAULT NOW();
