# Décision : migration Postgres (P0 Prod)

On arrête d'étendre SQLite en production. On migre **toutes** les données runtime vers Postgres :

- tenants / tenant_config / tenant_routing
- ivr_events
- bookings (et tout ce qui sert au cancel/modify/reporting)

**Raison :** multi-tenant + ivr_events à haut débit + besoin de fiabilité + risque de verrous SQLite.

SQLite reste OK pour dev/local, mais prod = Postgres.

## Étape 1 : ivr_events (FAIT)

1. **Schéma** : `migrations/003_postgres_ivr_events.sql`
2. **Dual-write** : `USE_PG_EVENTS=true` + `DATABASE_URL` → écrit SQLite + Postgres
3. **Backfill** : `python scripts/backfill_ivr_events_to_pg.py`
4. **Export** : `DATABASE_URL=... python scripts/export_weekly_kpis.py --last-week`

## Exigences

1. **Schéma Postgres** avec `client_id` (tenant_id) + index `(client_id, created_at)`, `(client_id, call_id)`.
2. **Migration sans downtime** : dual-write (SQLite+PG) puis backfill puis read PG puis stop SQLite.
3. Tous les endpoints doivent lire `tenant_id` avant d'écrire des events.
4. Les exports KPI : `--db-pg-url` ou `DATABASE_URL` pour lire Postgres en prod.

## Livrables

- [x] migrations/003_postgres_ivr_events.sql
- [x] backend/ivr_events_pg.py (dual-write)
- [x] scripts/backfill_ivr_events_to_pg.py
- [x] export_weekly_kpis.py --db-pg-url
- [ ] feature flag `USE_PG_EVENTS=true` + rollout progressif

---

**Note :** Pas besoin de quitter Railway pour ça. Railway peut héberger Postgres managé. Le point clé est "prod = Postgres", pas "changer d'hébergeur".
