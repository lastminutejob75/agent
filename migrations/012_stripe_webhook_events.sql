-- Idempotence webhook Stripe : ne pas retraiter le même event (Stripe peut renvoyer).
CREATE TABLE IF NOT EXISTS stripe_webhook_events (
    event_id TEXT PRIMARY KEY,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE stripe_webhook_events IS 'Events Stripe déjà traités (idempotence webhook).';
