-- Suspension past_due (V1) : colonnes sur tenant_billing pour éviter conso Vapi des clients qui ne paient pas.
ALTER TABLE tenant_billing
    ADD COLUMN IF NOT EXISTS is_suspended BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS suspension_reason TEXT,
    ADD COLUMN IF NOT EXISTS suspended_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS force_active_override BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS force_active_until TIMESTAMPTZ;

COMMENT ON COLUMN tenant_billing.is_suspended IS 'Si true, agent vocal ne prend plus RDV et dit phrase fixe (suspension past_due ou manuelle).';
COMMENT ON COLUMN tenant_billing.force_active_override IS 'Override admin: do not suspend even if past_due, until force_active_until.';
