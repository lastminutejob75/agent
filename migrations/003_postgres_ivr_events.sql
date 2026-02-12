-- Postgres: ivr_events (reporting KPI)
-- client_id = tenant_id en vocal (scope)
-- Index pour reporting hebdo rapide
-- created_at TIMESTAMPTZ pour index + comparaisons
-- Contrainte unique pour idempotence (dual-write retry, backfill rejoué)

CREATE TABLE IF NOT EXISTS ivr_events (
    id BIGSERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL,
    call_id TEXT NOT NULL DEFAULT '',
    event TEXT NOT NULL,
    context TEXT,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_ivr_events_dedup UNIQUE (client_id, call_id, event, created_at)
);

CREATE INDEX IF NOT EXISTS idx_ivr_events_client_created
    ON ivr_events (client_id, created_at);

CREATE INDEX IF NOT EXISTS idx_ivr_events_client_call
    ON ivr_events (client_id, call_id)
    WHERE call_id IS NOT NULL AND call_id != '';

CREATE INDEX IF NOT EXISTS idx_ivr_events_client_event_created
    ON ivr_events (client_id, event, created_at);

-- Commentaire : client_id = tenant_id en vocal (scope multi-tenant)
