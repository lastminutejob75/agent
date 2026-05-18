-- Tables normalisees pour la page client "Mon cabinet"
-- Compatible avec l'existant tenant_config.params_json (migration progressive)

CREATE TABLE IF NOT EXISTS tenant_profiles (
    tenant_id BIGINT PRIMARY KEY REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    practitioner_name TEXT,
    cabinet_name TEXT,
    specialty TEXT,
    phone TEXT,
    email TEXT,
    address_line TEXT,
    postal_code TEXT,
    city TEXT,
    website_url TEXT,
    languages_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    accepts_new_patients BOOLEAN NOT NULL DEFAULT TRUE,
    practitioner_photo_url TEXT,
    public_slug TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tenant_opening_hours (
    tenant_id BIGINT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    day_of_week TEXT NOT NULL,
    is_open BOOLEAN NOT NULL DEFAULT FALSE,
    morning_start TEXT,
    morning_end TEXT,
    afternoon_start TEXT,
    afternoon_end TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, day_of_week)
);

CREATE TABLE IF NOT EXISTS tenant_availability_settings (
    tenant_id BIGINT PRIMARY KEY REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    temporary_closure_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    temporary_closure_start TEXT,
    temporary_closure_end TEXT,
    temporary_closure_message TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tenant_booking_rules (
    tenant_id BIGINT PRIMARY KEY REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    default_appointment_duration_minutes INT NOT NULL DEFAULT 30,
    minimum_booking_notice_hours INT NOT NULL DEFAULT 24,
    accepts_new_patients BOOLEAN NOT NULL DEFAULT TRUE,
    appointment_reschedule_allowed BOOLEAN NOT NULL DEFAULT TRUE,
    appointment_reschedule_notice_hours INT NOT NULL DEFAULT 24,
    appointment_cancel_allowed BOOLEAN NOT NULL DEFAULT TRUE,
    appointment_cancel_notice_hours INT NOT NULL DEFAULT 24,
    emergency_instruction TEXT,
    new_patient_instruction TEXT,
    booking_notes TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tenant_appointment_reasons (
    id UUID PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    duration_minutes INT NOT NULL DEFAULT 30,
    description TEXT,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    allowed_for_new_patients BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tenant_appointment_reasons_tenant
    ON tenant_appointment_reasons (tenant_id, enabled);

CREATE TABLE IF NOT EXISTS tenant_assistant_settings (
    tenant_id BIGINT PRIMARY KEY REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    assistant_name TEXT,
    welcome_message TEXT,
    documents_to_bring TEXT,
    access_instructions TEXT,
    payment_methods TEXT,
    parking_info TEXT,
    pmr_access TEXT,
    sensitive_medical_instruction TEXT,
    escalation_instruction TEXT,
    human_handoff_instruction TEXT,
    faq_items_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
