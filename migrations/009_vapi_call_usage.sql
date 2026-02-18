-- Vapi = source de vérité pour conso (durée, coût). UWi = source de vérité fonctionnel (RDV, events).
-- Table remplie par webhook end-of-call-report + optionnel sync périodique Vapi API.

CREATE TABLE IF NOT EXISTS vapi_call_usage (
    tenant_id INT NOT NULL,
    vapi_call_id TEXT NOT NULL,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    duration_sec NUMERIC(12, 2),
    cost_usd NUMERIC(12, 6),
    cost_currency TEXT NOT NULL DEFAULT 'USD',
    costs_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, vapi_call_id)
);

CREATE INDEX IF NOT EXISTS idx_vapi_call_usage_tenant_ended
    ON vapi_call_usage (tenant_id, ended_at DESC);

CREATE INDEX IF NOT EXISTS idx_vapi_call_usage_ended
    ON vapi_call_usage (ended_at DESC);

COMMENT ON TABLE vapi_call_usage IS 'Conso Vapi par appel (webhook end-of-call-report). duration_sec / cost_usd = source de vérité pour billing.';
