-- RLS multi-tenant (données médicales) — idempotent
-- L'app pose SET LOCAL app.current_tenant_id avant les requêtes (backend/pg_tenant_context.py).
-- L'admin cross-tenant pose SET LOCAL app.bypass_tenant_rls = 'on' après authentification admin.
-- En prod : utiliser un rôle PostgreSQL non superuser (ex. uwi_app) pour que RLS s'applique.

CREATE OR REPLACE FUNCTION app_current_tenant_id() RETURNS bigint AS $$
  SELECT NULLIF(trim(current_setting('app.current_tenant_id', true)), '')::bigint
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION app_bypass_tenant_rls() RETURNS boolean AS $$
  SELECT coalesce(nullif(trim(current_setting('app.bypass_tenant_rls', true)), ''), 'off') = 'on'
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION app_tenant_matches(p_tenant_id bigint) RETURNS boolean AS $$
  SELECT app_bypass_tenant_rls()
      OR (app_current_tenant_id() IS NOT NULL AND p_tenant_id = app_current_tenant_id())
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION app_client_matches(p_client_id integer) RETURNS boolean AS $$
  SELECT app_bypass_tenant_rls()
      OR (app_current_tenant_id() IS NOT NULL AND p_client_id = app_current_tenant_id()::integer)
$$ LANGUAGE sql STABLE;

-- Macro procédurale : active RLS + policy sur une table (tenant_id bigint)
DO $rls$
DECLARE
  t text;
  tables text[] := ARRAY[
    'tenant_config',
    'tenant_routing',
    'tenant_users',
    'tenant_clients',
    'tenant_booking_history',
    'tenant_profiles',
    'tenant_opening_hours',
    'tenant_availability_settings',
    'tenant_booking_rules',
    'tenant_appointment_reasons',
    'tenant_assistant_settings',
    'tenant_billing',
    'call_sessions',
    'call_messages',
    'call_state_checkpoints',
    'vapi_calls',
    'call_transcripts',
    'vapi_call_usage',
    'slots',
    'appointments'
  ];
BEGIN
  FOREACH t IN ARRAY tables
  LOOP
    IF to_regclass('public.' || t) IS NOT NULL THEN
      EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
      EXECUTE format('DROP POLICY IF EXISTS %I ON %I', t || '_tenant_isolation', t);
      EXECUTE format(
        'CREATE POLICY %I ON %I FOR ALL '
        'USING (app_tenant_matches(tenant_id)) '
        'WITH CHECK (app_tenant_matches(tenant_id))',
        t || '_tenant_isolation',
        t
      );
    END IF;
  END LOOP;
END
$rls$;

-- ivr_events : scope = client_id (= tenant_id)
DO $ivr$
BEGIN
  IF to_regclass('public.ivr_events') IS NOT NULL THEN
    ALTER TABLE ivr_events ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS ivr_events_tenant_isolation ON ivr_events;
    CREATE POLICY ivr_events_tenant_isolation ON ivr_events
      FOR ALL
      USING (app_client_matches(client_id))
      WITH CHECK (app_client_matches(client_id));
  END IF;
END
$ivr$;

COMMENT ON FUNCTION app_current_tenant_id() IS 'Tenant courant (SET LOCAL app.current_tenant_id)';
COMMENT ON FUNCTION app_bypass_tenant_rls() IS 'Bypass RLS pour routes admin authentifiées uniquement';
