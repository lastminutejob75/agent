-- Idempotence push usage Stripe : un seul push par (tenant_id, date_utc).
CREATE TABLE IF NOT EXISTS stripe_usage_push_log (
    tenant_id BIGINT NOT NULL,
    date_utc DATE NOT NULL,
    quantity_minutes INT NOT NULL DEFAULT 0,
    stripe_usage_record_id TEXT,
    pushed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, date_utc)
);

CREATE INDEX IF NOT EXISTS idx_stripe_usage_push_log_pushed_at
    ON stripe_usage_push_log (pushed_at);

COMMENT ON TABLE stripe_usage_push_log IS 'Idempotence: one Stripe usage push per tenant per UTC day. Prevents double billing.';

-- Optionnel : colonne pour UsageRecord (metered item). Remplir via webhook subscription.updated.
ALTER TABLE tenant_billing
    ADD COLUMN IF NOT EXISTS stripe_metered_item_id TEXT;

COMMENT ON COLUMN tenant_billing.stripe_metered_item_id IS 'Stripe subscription item id (metered) for UsageRecord.create. Set from webhook subscription.updated.';
