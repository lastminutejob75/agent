-- V2 : contexte patient (événements, métriques, résumés IA) + questionnaires structurés.
-- Adapté au modèle UWI existant : tenant_id INTEGER, patient_phone TEXT (cabinet_clients).

-- ===== Événements patient (source métriques + timeline) =====
CREATE TABLE IF NOT EXISTS patient_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER NOT NULL,
    patient_phone TEXT NOT NULL,
    type TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    statut TEXT,
    motif TEXT,
    payload_json JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_patient_events_lookup
    ON patient_events(tenant_id, patient_phone, occurred_at DESC);

-- ===== Notes (extension V2 — table existante conservée côté SQLite) =====
-- patient_notes déjà gérée par db.py ; pas de DDL ici.

-- ===== Métriques calculées (déterministe) =====
CREATE TABLE IF NOT EXISTS patient_metrics (
    tenant_id INTEGER NOT NULL,
    patient_phone TEXT NOT NULL,
    nb_rdv INT DEFAULT 0,
    nb_no_shows INT DEFAULT 0,
    nb_annul_tardive INT DEFAULT 0,
    taux_assiduite INT,
    score_fiabilite INT,
    dernier_rdv TIMESTAMPTZ,
    prochain_rdv TIMESTAMPTZ,
    recence_jours INT,
    motifs_top_json JSONB DEFAULT '[]',
    updated_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (tenant_id, patient_phone)
);

-- ===== Résumés IA de fiche =====
CREATE TABLE IF NOT EXISTS patient_summaries (
    tenant_id INTEGER NOT NULL,
    patient_phone TEXT NOT NULL,
    sections_json JSONB NOT NULL DEFAULT '{}',
    inputs_hash TEXT NOT NULL,
    model TEXT,
    is_health BOOLEAN NOT NULL DEFAULT false,
    generated_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (tenant_id, patient_phone)
);

-- ===== Questionnaires V2 =====
CREATE TABLE IF NOT EXISTS questionnaire_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    description TEXT,
    sections_json JSONB NOT NULL DEFAULT '[]',
    is_default BOOLEAN NOT NULL DEFAULT false,
    is_health BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_questionnaire_templates_tenant
    ON questionnaire_templates(tenant_id, type);

CREATE TABLE IF NOT EXISTS questionnaire_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER NOT NULL,
    patient_phone TEXT NOT NULL,
    appointment_id TEXT,
    template_id UUID REFERENCES questionnaire_templates(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    sent_by_user_id TEXT,
    sent_to_email TEXT,
    sent_to_phone TEXT,
    secure_token_hash TEXT NOT NULL,
    token_used BOOLEAN NOT NULL DEFAULT false,
    expires_at TIMESTAMPTZ,
    opened_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    integrated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_questionnaire_requests_patient
    ON questionnaire_requests(tenant_id, patient_phone, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_questionnaire_requests_token_hash
    ON questionnaire_requests(secure_token_hash);

CREATE TABLE IF NOT EXISTS questionnaire_responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER NOT NULL,
    questionnaire_request_id UUID NOT NULL REFERENCES questionnaire_requests(id) ON DELETE CASCADE,
    patient_phone TEXT NOT NULL,
    answers_json JSONB NOT NULL DEFAULT '{}',
    ai_summary TEXT,
    structured_summary_json JSONB DEFAULT '{}',
    consent_given BOOLEAN NOT NULL DEFAULT false,
    is_health BOOLEAN NOT NULL DEFAULT false,
    submitted_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_questionnaire_responses_patient
    ON questionnaire_responses(tenant_id, patient_phone, submitted_at DESC);

CREATE TABLE IF NOT EXISTS patient_documents_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER NOT NULL,
    patient_phone TEXT NOT NULL,
    questionnaire_response_id UUID REFERENCES questionnaire_responses(id) ON DELETE SET NULL,
    filename TEXT NOT NULL,
    storage_key TEXT NOT NULL,
    mime_type TEXT,
    is_health BOOLEAN NOT NULL DEFAULT false,
    uploaded_by TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
