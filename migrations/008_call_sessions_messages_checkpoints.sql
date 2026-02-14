-- P0 Option B: Journal + checkpoints pour persistance sessions vocales (dual-write Phase 1)
-- Tables: call_sessions, call_messages, call_state_checkpoints
-- Aucun secret dans state_json

-- A) call_sessions
CREATE TABLE IF NOT EXISTS call_sessions (
    tenant_id INT NOT NULL,
    call_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_state TEXT NOT NULL DEFAULT 'START',
    last_seq INT NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant_id, call_id)
);

CREATE INDEX IF NOT EXISTS idx_call_sessions_tenant_updated
    ON call_sessions (tenant_id, updated_at DESC);

-- B) call_messages
CREATE TABLE IF NOT EXISTS call_messages (
    tenant_id INT NOT NULL,
    call_id TEXT NOT NULL,
    seq INT NOT NULL,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, call_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_call_messages_tenant_call_ts
    ON call_messages (tenant_id, call_id, ts);

-- C) call_state_checkpoints
CREATE TABLE IF NOT EXISTS call_state_checkpoints (
    tenant_id INT NOT NULL,
    call_id TEXT NOT NULL,
    seq INT NOT NULL,
    state_json JSONB NOT NULL,
    ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, call_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_call_state_checkpoints_tenant_call_ts
    ON call_state_checkpoints (tenant_id, call_id, ts DESC);

-- Trigger: auto-update updated_at sur call_sessions (PostgreSQL 11+)
CREATE OR REPLACE FUNCTION call_sessions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_call_sessions_updated_at ON call_sessions;
CREATE TRIGGER trg_call_sessions_updated_at
    BEFORE UPDATE ON call_sessions
    FOR EACH ROW
    EXECUTE PROCEDURE call_sessions_updated_at();
