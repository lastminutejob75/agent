-- suspension_mode: hard (phrase fixe, zero LLM) | soft (message poli, FAQ-only later). past_due = always hard; manual = can choose soft.
ALTER TABLE tenant_billing
    ADD COLUMN IF NOT EXISTS suspension_mode TEXT DEFAULT 'hard';

COMMENT ON COLUMN tenant_billing.suspension_mode IS 'hard = blocage total (MSG_VOCAL_SUSPENDED); soft = message poli sans RDV (manual only).';
