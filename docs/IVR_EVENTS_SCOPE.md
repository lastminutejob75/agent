# ivr_events : scope par tenant (client_id = tenant_id)

## Convention

Dans les tables **ivr_events** (SQLite et PostgreSQL) et **calls** (SQLite), la colonne **`client_id`** sert de **scope tenant** pour le canal vocal (IVR).

- **`client_id` = identifiant du tenant (cabinet)** pour les événements IVR, pas l’identifiant du patient.
- Toutes les requêtes (rapports quotidiens, dashboard, get_daily_report_data, transfer_reasons, etc.) filtrent par `client_id` en passant **tenant_id** (ex. `WHERE client_id = %s` avec `tenant_id`).

## Pourquoi ce nom ?

Historique : le schéma a été nommé “client” au sens “client de la plateforme” (tenant / cabinet). Pour éviter toute confusion avec le “client” patient (contact, personne qui prend RDV), ce document fixe la convention.

## Impact

- **Rapports** : `get_daily_report_data(client_id, date)` — `client_id` = tenant_id.
- **Dashboard admin** : agrégats ivr_events avec `WHERE client_id = %s` et `tenant_id`.
- **PG** : même convention ; policies RLS sur `ivr_events` doivent utiliser la colonne `client_id` comme scope tenant (voir `docs/RLS_POLICIES.md`).

## Évolution possible

Si une migration est envisagée : renommer `client_id` en `tenant_id` dans ivr_events/calls pour aligner le vocabulaire avec le reste du multi-tenant. Non bloquant tant que la convention ci-dessus est respectée et documentée.
