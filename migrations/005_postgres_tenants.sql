-- Postgres: tenants, tenant_config, tenant_routing
-- Migration progressive : PG-first read, SQLite fallback.
-- key = did_key (DID E.164 ou domain/widget_key)

CREATE TABLE IF NOT EXISTS tenants (
    tenant_id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'Europe/Paris',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tenant_config (
    tenant_id BIGINT PRIMARY KEY REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    flags_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    params_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tenant_routing (
    channel TEXT NOT NULL,
    key TEXT NOT NULL,
    tenant_id BIGINT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (channel, key)
);

CREATE INDEX IF NOT EXISTS idx_tenants_status ON tenants(status);
CREATE INDEX IF NOT EXISTS idx_routing_tenant ON tenant_routing(tenant_id);

-- Seed default tenant (id=1) - idempotent
INSERT INTO tenants (tenant_id, name) VALUES (1, 'DEFAULT')
ON CONFLICT (tenant_id) DO NOTHING;

INSERT INTO tenant_config (tenant_id, flags_json, params_json)
VALUES (1, '{}'::jsonb, '{}'::jsonb)
ON CONFLICT (tenant_id) DO NOTHING;

-- Reset sequence après seed manuel
SELECT setval(
    pg_get_serial_sequence('tenants', 'tenant_id'),
    GREATEST((SELECT COALESCE(MAX(tenant_id), 1) FROM tenants), 1)
);
