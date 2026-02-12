-- Audit events auth (RGPD, debug "je reçois pas l'email")
CREATE TABLE IF NOT EXISTS auth_events (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT REFERENCES tenants(tenant_id) ON DELETE SET NULL,  -- NULL si email inconnu
    email TEXT NOT NULL,
    event TEXT NOT NULL,
    context TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_auth_events_created ON auth_events(created_at);
CREATE INDEX IF NOT EXISTS idx_auth_events_event ON auth_events(event);
