-- Diagnostic push usage : status + error_short. Retry uniquement pour failed ou absent.
ALTER TABLE stripe_usage_push_log
    ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending';

ALTER TABLE stripe_usage_push_log
    ADD COLUMN IF NOT EXISTS error_short VARCHAR(255);

-- Considérer les lignes déjà présentes comme envoyées (pas de repush).
UPDATE stripe_usage_push_log SET status = 'sent';

COMMENT ON COLUMN stripe_usage_push_log.status IS 'pending = en cours, sent = poussé, failed = erreur (retry possible).';
COMMENT ON COLUMN stripe_usage_push_log.error_short IS 'Message court erreur Stripe (255 car) pour diagnostic.';
