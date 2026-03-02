-- Usage de test pour tenant 1 (hier UTC).
-- Schéma vapi_call_usage : tenant_id, vapi_call_id, started_at, ended_at, duration_sec, cost_usd, cost_currency.
--
-- Exécution :
--   railway run psql $DATABASE_URL -f scripts/insert_test_usage_tenant1.sql
--   ou : psql $DATABASE_URL -f scripts/insert_test_usage_tenant1.sql
--
-- Puis lancer : POST /api/admin/jobs/push-daily-usage

-- 55 min total pour hier (15 + 20 + 20)
INSERT INTO vapi_call_usage (tenant_id, vapi_call_id, started_at, ended_at, duration_sec, cost_usd, cost_currency)
VALUES
  (1, 'test-usage-' || gen_random_uuid()::text, 
   (date_trunc('day', now() AT TIME ZONE 'utc') - interval '1 day') + interval '10:00',
   (date_trunc('day', now() AT TIME ZONE 'utc') - interval '1 day') + interval '10:15',
   900, 0.05, 'USD'),
  (1, 'test-usage-' || gen_random_uuid()::text,
   (date_trunc('day', now() AT TIME ZONE 'utc') - interval '1 day') + interval '14:00',
   (date_trunc('day', now() AT TIME ZONE 'utc') - interval '1 day') + interval '14:20',
   1200, 0.07, 'USD'),
  (1, 'test-usage-' || gen_random_uuid()::text,
   (date_trunc('day', now() AT TIME ZONE 'utc') - interval '1 day') + interval '16:00',
   (date_trunc('day', now() AT TIME ZONE 'utc') - interval '1 day') + interval '16:20',
   1200, 0.07, 'USD')
ON CONFLICT (tenant_id, vapi_call_id) DO NOTHING;

-- Vérifier : SELECT tenant_id, ended_at, duration_sec, CEIL(SUM(duration_sec)/60)::int AS minutes
-- FROM vapi_call_usage WHERE tenant_id=1 AND ended_at >= (CURRENT_DATE - 1)::timestamp AND ended_at < CURRENT_DATE::timestamp GROUP BY tenant_id, ended_at;
