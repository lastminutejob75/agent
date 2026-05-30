-- RLS tenant isolation — tables contexte patient V2 (042)
-- Même modèle que 034_rls_tenant_isolation.sql (app.current_tenant_id / app.bypass_tenant_rls).

DO $rls$
DECLARE
  t text;
  tables text[] := ARRAY[
    'patient_events',
    'patient_metrics',
    'patient_summaries',
    'questionnaire_templates',
    'questionnaire_requests',
    'questionnaire_responses',
    'patient_documents_v2'
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
