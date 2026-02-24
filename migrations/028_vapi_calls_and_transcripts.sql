-- Vapi webhook: persistance status-update (cycle de vie appel) + transcript (parole user/assistant)
-- Permet dashboard admin + client: appels en cours, durée live, transcription, raison fin, KPI.

-- A) vapi_calls : une ligne par appel, mise à jour à chaque status-update
CREATE TABLE IF NOT EXISTS vapi_calls (
    tenant_id INT NOT NULL,
    call_id TEXT NOT NULL,
    customer_number TEXT,
    assistant_id TEXT,
    phone_number_id TEXT,
    status TEXT NOT NULL DEFAULT 'unknown',
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    ended_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, call_id)
);

CREATE INDEX IF NOT EXISTS idx_vapi_calls_tenant_updated
    ON vapi_calls (tenant_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_vapi_calls_tenant_status
    ON vapi_calls (tenant_id, status) WHERE status IN ('ringing', 'in-progress');

COMMENT ON TABLE vapi_calls IS 'Cycle de vie appel Vapi (status-update). Jointure avec vapi_call_usage pour durée/coût final.';

-- B) call_transcripts : lignes de transcription (user / assistant), final ou intermédiaire
CREATE TABLE IF NOT EXISTS call_transcripts (
    id BIGSERIAL PRIMARY KEY,
    tenant_id INT NOT NULL,
    call_id TEXT NOT NULL,
    role TEXT NOT NULL,
    transcript TEXT NOT NULL,
    is_final BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_call_transcripts_tenant_call
    ON call_transcripts (tenant_id, call_id, created_at);

COMMENT ON TABLE call_transcripts IS 'Transcription Vapi (message type=transcript). Pour détail appel et analyse.';
