-- Billing Stripe par tenant (agnostique prix). Sync via webhooks + admin.
CREATE TABLE IF NOT EXISTS tenant_billing (
    tenant_id BIGINT PRIMARY KEY REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    billing_status TEXT,
    plan_key TEXT,
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    trial_ends_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tenant_billing_stripe_customer
    ON tenant_billing (stripe_customer_id) WHERE stripe_customer_id IS NOT NULL;

COMMENT ON TABLE tenant_billing IS 'Stripe billing state per tenant (customer, subscription, status). No prices; sync via webhooks.';
