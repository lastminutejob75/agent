# RLS (Row-Level Security) PostgreSQL — multi-tenant

Renforcement de l’isolation : même une requête sans filtre applicatif ne doit pas voir les données d’un autre tenant.

## Principe

1. **Activer RLS** sur les tables contenant `tenant_id` (ou `client_id` pour ivr_events).
2. **Policies** : n’autoriser que les lignes où `tenant_id = current_setting('app.current_tenant_id', true)::int` (ou équivalent).
3. **Application** : au début de chaque requête / transaction, exécuter `SET LOCAL app.current_tenant_id = '<tenant_id>'` (ou via un pool avec session variable).

## Tables concernées

| Table | Colonne scope | Remarque |
|-------|----------------|----------|
| tenant_config | tenant_id | FK tenants |
| tenant_routing | tenant_id | |
| tenant_users | tenant_id | |
| tenant_clients | tenant_id | |
| tenant_booking_history | tenant_id | |
| call_sessions | tenant_id | session_pg |
| call_messages | tenant_id | |
| call_state_checkpoints | tenant_id | |
| web_sessions | tenant_id | |
| slots | tenant_id | slots_pg |
| appointments | tenant_id | |
| ivr_events | **client_id** | = tenant_id pour IVR (voir docs/IVR_EVENTS_SCOPE.md) |

Les tables **tenants** (liste des tenants) ne sont pas protégées par RLS de la même façon : l’accès “liste” peut rester contrôlé en applicatif (admin uniquement).

## Script SQL d’exemple (à adapter à votre schéma)

À exécuter après création des tables, sur la base PG utilisée (DATABASE_URL / PG_TENANTS_URL / PG_EVENTS_URL selon les tables).

```sql
-- Variable de session (à poser côté app avant les requêtes)
-- SET app.current_tenant_id = '1';

-- Exemple : table tenant_config
ALTER TABLE tenant_config ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_config_tenant_isolation ON tenant_config
  USING (tenant_id = (current_setting('app.current_tenant_id', true)::int));

-- Exemple : table web_sessions
ALTER TABLE web_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY web_sessions_tenant_isolation ON web_sessions
  USING (tenant_id = (current_setting('app.current_tenant_id', true)::bigint));

-- Exemple : ivr_events (scope = client_id = tenant_id)
ALTER TABLE ivr_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY ivr_events_tenant_isolation ON ivr_events
  USING (client_id = (current_setting('app.current_tenant_id', true)::int));

-- Répéter pour : tenant_routing, tenant_clients, tenant_booking_history,
-- call_sessions, call_messages, call_state_checkpoints, slots, appointments.
-- Policy FOR ALL (SELECT, INSERT, UPDATE, DELETE) si besoin, ou séparer.
```

## Côté application (intégré)

L’app pose `app.current_tenant_id` via `backend.pg_tenant_context.set_tenant_id_on_connection(conn, tenant_id)` juste après chaque `psycopg.connect()` dans les modules tenant-scopés : `tenants_pg`, `session_pg`, `client_memory_pg`, `ivr_events_pg` (client_id = tenant). Aucune policy RLS n’est active tant que le script SQL des policies n’est pas exécuté sur la base.

Pour que RLS soit efficace après activation des policies, chaque requête doit être exécutée dans un contexte où `app.current_tenant_id` est défini :

- **Option A** : au début de chaque handler (FastAPI) qui a déjà le `tenant_id`, ouvrir une connexion puis `SET LOCAL app.current_tenant_id = '<tenant_id>'` avant tout accès DB.
- **Option B** : middleware ou dépendance qui pose la variable sur la connexion du pool (si le pool est par-request).
- **Option C** : garder les filtres applicatifs actuels et utiliser RLS comme filet de sécurité (variable posée à chaque requête depuis le tenant_id de la session).

Sans mise en place de cette variable, les policies bloqueront tout accès (ou il faudra des policies pour le rôle “superuser” / migration qui bypass RLS).

## Fichier de migration

Un fichier unique `migrations/001_rls_policies.sql` peut regrouper les `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` et les `CREATE POLICY` pour toutes les tables listées ci-dessus, à exécuter manuellement ou via un outil de migrations (ex. Flyway, golang-migrate, ou script custom).
