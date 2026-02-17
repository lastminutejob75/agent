-- RLS (Row-Level Security) — exemple pour multi-tenant
-- À exécuter sur la base PG après création des tables.
-- L'app doit poser : SET LOCAL app.current_tenant_id = '<tenant_id>' avant les requêtes.
-- Voir docs/RLS_POLICIES.md

-- tenant_config
ALTER TABLE tenant_config ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_config_tenant_isolation ON tenant_config
  USING (tenant_id = (current_setting('app.current_tenant_id', true)::bigint));

-- tenant_routing
ALTER TABLE tenant_routing ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_routing_tenant_isolation ON tenant_routing
  USING (tenant_id = (current_setting('app.current_tenant_id', true)::bigint));

-- tenant_users
ALTER TABLE tenant_users ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_users_tenant_isolation ON tenant_users
  USING (tenant_id = (current_setting('app.current_tenant_id', true)::bigint));

-- tenant_clients
ALTER TABLE tenant_clients ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_clients_tenant_isolation ON tenant_clients
  USING (tenant_id = (current_setting('app.current_tenant_id', true)::bigint));

-- tenant_booking_history
ALTER TABLE tenant_booking_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_booking_history_tenant_isolation ON tenant_booking_history
  USING (tenant_id = (current_setting('app.current_tenant_id', true)::bigint));

-- call_sessions
ALTER TABLE call_sessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY call_sessions_tenant_isolation ON call_sessions
  USING (tenant_id = (current_setting('app.current_tenant_id', true)::bigint));

-- call_messages
ALTER TABLE call_messages ENABLE ROW LEVEL SECURITY;
CREATE POLICY call_messages_tenant_isolation ON call_messages
  USING (tenant_id = (current_setting('app.current_tenant_id', true)::bigint));

-- call_state_checkpoints
ALTER TABLE call_state_checkpoints ENABLE ROW LEVEL SECURITY;
CREATE POLICY call_state_checkpoints_tenant_isolation ON call_state_checkpoints
  USING (tenant_id = (current_setting('app.current_tenant_id', true)::bigint));

-- web_sessions
ALTER TABLE web_sessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY web_sessions_tenant_isolation ON web_sessions
  USING (tenant_id = (current_setting('app.current_tenant_id', true)::bigint));

-- slots (si table slots en PG)
-- ALTER TABLE slots ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY slots_tenant_isolation ON slots
--   USING (tenant_id = (current_setting('app.current_tenant_id', true)::bigint));

-- appointments (si table appointments en PG)
-- ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY appointments_tenant_isolation ON appointments
--   USING (tenant_id = (current_setting('app.current_tenant_id', true)::bigint));

-- ivr_events : scope = client_id (= tenant_id pour IVR, voir docs/IVR_EVENTS_SCOPE.md)
ALTER TABLE ivr_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY ivr_events_tenant_isolation ON ivr_events
  USING (client_id = (current_setting('app.current_tenant_id', true)::int));
