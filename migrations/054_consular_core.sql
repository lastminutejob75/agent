-- Accueil consulaire : schéma métier et isolation par poste.
-- Le lien legacy_tenant_id permet de réutiliser temporairement l'authentification,
-- Stripe et le routage Vapi existants sans affaiblir la nouvelle isolation UUID.

CREATE TABLE IF NOT EXISTS posts (
    post_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    legacy_tenant_id BIGINT UNIQUE REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    name TEXT NOT NULL,
    country_code TEXT NOT NULL,
    host_country_code TEXT NOT NULL,
    reference_prefix TEXT NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'Africa/Algiers',
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'suspended', 'closed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS post_config (
    post_id UUID PRIMARY KEY REFERENCES posts(post_id) ON DELETE CASCADE,
    flags_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    params_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    visa_reference_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID NOT NULL REFERENCES posts(post_id) ON DELETE CASCADE,
    reference TEXT NOT NULL,
    channel TEXT NOT NULL CHECK (channel IN ('phone', 'chat', 'whatsapp')),
    lang TEXT NOT NULL CHECK (lang IN ('bg', 'fr', 'en', 'ar')),
    purpose TEXT,
    visa_category TEXT CHECK (visa_category IN ('A', 'C', 'D')),
    reclassified_from TEXT CHECK (reclassified_from IN ('A', 'C', 'D')),
    applicant_name TEXT,
    applicant_phone TEXT,
    residence TEXT,
    travel_window TEXT,
    duration_days INTEGER CHECK (duration_days IS NULL OR duration_days > 0),
    passport_ok BOOLEAN,
    host_nationality TEXT,
    fee_exempt BOOLEAN NOT NULL DEFAULT FALSE,
    is_minor BOOLEAN NOT NULL DEFAULT FALSE,
    is_first_application BOOLEAN,
    schengen_history BOOLEAN,
    previous_refusal BOOLEAN NOT NULL DEFAULT FALSE,
    status TEXT NOT NULL DEFAULT 'new'
        CHECK (status IN (
            'new', 'incomplete', 'complete', 'scheduled', 'escalated', 'closed'
        )),
    original_transcript TEXT,
    translated_transcript_fr TEXT,
    translated_transcript_bg TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    qualified_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (post_id, reference)
);

CREATE INDEX IF NOT EXISTS idx_applications_post_created
    ON applications(post_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_applications_post_status
    ON applications(post_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_applications_post_phone
    ON applications(post_id, applicant_phone);

CREATE TABLE IF NOT EXISTS application_documents (
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    doc_key TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'missing'
        CHECK (state IN ('missing', 'provided', 'waived')),
    is_blocking BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (application_id, doc_key)
);

CREATE TABLE IF NOT EXISTS application_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    actor_type TEXT NOT NULL CHECK (actor_type IN ('assistant', 'applicant', 'officer', 'system')),
    actor_id TEXT,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_application_events_timeline
    ON application_events(application_id, created_at);

CREATE TABLE IF NOT EXISTS document_requirements (
    post_id UUID NOT NULL REFERENCES posts(post_id) ON DELETE CASCADE,
    visa_category TEXT NOT NULL CHECK (visa_category IN ('A', 'C', 'D')),
    purpose TEXT NOT NULL,
    doc_key TEXT NOT NULL,
    is_blocking BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (post_id, visa_category, purpose, doc_key)
);

CREATE TABLE IF NOT EXISTS document_labels (
    doc_key TEXT NOT NULL,
    lang TEXT NOT NULL CHECK (lang IN ('bg', 'fr', 'en', 'ar')),
    label TEXT NOT NULL,
    PRIMARY KEY (doc_key, lang)
);

CREATE TABLE IF NOT EXISTS counter_slots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID NOT NULL REFERENCES posts(post_id) ON DELETE CASCADE,
    date DATE NOT NULL,
    start_time TIME NOT NULL,
    capacity INTEGER NOT NULL CHECK (capacity > 0),
    visa_category_filter TEXT CHECK (visa_category_filter IN ('A', 'C', 'D')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (post_id, date, start_time, visa_category_filter)
);

CREATE INDEX IF NOT EXISTS idx_counter_slots_post_date
    ON counter_slots(post_id, date, start_time);

CREATE OR REPLACE FUNCTION app_current_post_id() RETURNS uuid AS $$
    SELECT NULLIF(trim(current_setting('app.current_post_id', true)), '')::uuid
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION app_post_matches(candidate_post_id uuid) RETURNS boolean AS $$
    SELECT app_bypass_tenant_rls()
        OR (
            app_current_post_id() IS NOT NULL
            AND candidate_post_id = app_current_post_id()
        )
$$ LANGUAGE sql STABLE;

DO $rls$
DECLARE
    table_name text;
    scoped_tables text[] := ARRAY[
        'post_config',
        'applications',
        'document_requirements',
        'counter_slots'
    ];
BEGIN
    FOREACH table_name IN ARRAY scoped_tables LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', table_name);
        EXECUTE format(
            'DROP POLICY IF EXISTS %I ON %I',
            table_name || '_post_isolation',
            table_name
        );
        EXECUTE format(
            'CREATE POLICY %I ON %I FOR ALL '
            'USING (app_post_matches(post_id)) '
            'WITH CHECK (app_post_matches(post_id))',
            table_name || '_post_isolation',
            table_name
        );
    END LOOP;
END
$rls$;

ALTER TABLE posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE posts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS posts_post_isolation ON posts;
CREATE POLICY posts_post_isolation ON posts
    FOR ALL
    USING (
        app_post_matches(post_id)
        OR (
            legacy_tenant_id IS NOT NULL
            AND app_tenant_matches(legacy_tenant_id)
        )
    )
    WITH CHECK (
        app_post_matches(post_id)
        OR (
            legacy_tenant_id IS NOT NULL
            AND app_tenant_matches(legacy_tenant_id)
        )
    );

ALTER TABLE application_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE application_documents FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS application_documents_post_isolation ON application_documents;
CREATE POLICY application_documents_post_isolation ON application_documents
    FOR ALL
    USING (
        EXISTS (
            SELECT 1
            FROM applications
            WHERE applications.id = application_documents.application_id
              AND app_post_matches(applications.post_id)
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM applications
            WHERE applications.id = application_documents.application_id
              AND app_post_matches(applications.post_id)
        )
    );

ALTER TABLE application_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE application_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS application_events_post_isolation ON application_events;
CREATE POLICY application_events_post_isolation ON application_events
    FOR ALL
    USING (
        EXISTS (
            SELECT 1
            FROM applications
            WHERE applications.id = application_events.application_id
              AND app_post_matches(applications.post_id)
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM applications
            WHERE applications.id = application_events.application_id
              AND app_post_matches(applications.post_id)
        )
    );

COMMENT ON COLUMN posts.legacy_tenant_id IS
    'Compatibilité transitoire avec auth, Stripe et routage Vapi UWI';
COMMENT ON FUNCTION app_current_post_id() IS
    'Poste courant défini par SET LOCAL app.current_post_id';
