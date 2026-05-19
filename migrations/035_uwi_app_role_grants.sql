-- Droits du rôle applicatif uwi_app (non superuser, soumis au RLS)
-- À exécuter APRÈS création du rôle (scripts/setup_uwi_app_role.py)
-- et APRÈS migration 034 (fonctions app_*)

DO $body$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'uwi_app') THEN
    RAISE EXCEPTION 'Rôle uwi_app absent. Lancez: python scripts/setup_uwi_app_role.py';
  END IF;
END
$body$;

DO $db$
DECLARE dbname text := current_database();
BEGIN
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO uwi_app', dbname);
END
$db$;
GRANT USAGE ON SCHEMA public TO uwi_app;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO uwi_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO uwi_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO uwi_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO uwi_app;

-- Fonctions RLS (migration 034)
DO $fn$
DECLARE
  f text;
  funcs text[] := ARRAY[
    'app_current_tenant_id()',
    'app_bypass_tenant_rls()',
    'app_tenant_matches(bigint)',
    'app_client_matches(integer)'
  ];
BEGIN
  FOREACH f IN ARRAY funcs
  LOOP
    IF to_regprocedure('public.' || replace(f, '()', '')) IS NOT NULL
       OR to_regprocedure('public.' || f) IS NOT NULL THEN
      BEGIN
        EXECUTE format('GRANT EXECUTE ON FUNCTION public.%s TO uwi_app', f);
      EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'Grant function % skipped: %', f, SQLERRM;
      END;
    END IF;
  END LOOP;
END
$fn$;

COMMENT ON ROLE uwi_app IS 'Rôle applicatif UWi (Railway) — non superuser, RLS actif';
