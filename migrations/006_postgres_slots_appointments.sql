-- Postgres: slots + appointments par tenant
-- start_ts remplace (date, time) pour filtres matin/après-midi trivial
-- Isolation multi-tenant (tenant_id)

CREATE TABLE IF NOT EXISTS slots (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    start_ts TIMESTAMPTZ NOT NULL,
    is_booked BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, start_ts)
);

CREATE INDEX IF NOT EXISTS idx_slots_tenant_start ON slots(tenant_id, start_ts);
CREATE INDEX IF NOT EXISTS idx_slots_tenant_free ON slots(tenant_id, is_booked, start_ts)
    WHERE is_booked = FALSE;

CREATE TABLE IF NOT EXISTS appointments (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    slot_id BIGINT NOT NULL REFERENCES slots(id) ON DELETE RESTRICT,
    name TEXT NOT NULL,
    contact TEXT NOT NULL,
    contact_type TEXT NOT NULL,
    motif TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, slot_id)
);

CREATE INDEX IF NOT EXISTS idx_appt_tenant_created ON appointments(tenant_id, created_at);
CREATE INDEX IF NOT EXISTS idx_appt_tenant_name ON appointments(tenant_id, name);
CREATE INDEX IF NOT EXISTS idx_appt_slot ON appointments(slot_id);
