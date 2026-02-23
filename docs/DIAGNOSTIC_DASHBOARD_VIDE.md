# Dashboard vide (aucun appel, aucun RDV)

## Symptôme

- **Dashboard admin** : 0 appels, 0 RDV confirmés, 0 transferts.
- **Dashboard client** (cabinet) : idem, dernier appel / dernier RDV vides, compteurs à 0.

## Cause la plus fréquente : écriture / lecture sur des bases différentes

En production (Railway), **DATABASE_URL** est en général défini → le backend **lit** les stats depuis la table Postgres **ivr_events** pour afficher les dashboards.

Les **écritures** (chaque appel, RDV confirmé, transfert, abandon) vont :

- **toujours** en SQLite (fichier local) via `backend/db.create_ivr_event` ;
- **en Postgres** seulement si **USE_PG_EVENTS=true** (dual-write dans `backend/ivr_events_pg`).

Si **USE_PG_EVENTS** n’est pas défini ou est à `false` :

- Les événements sont enregistrés **uniquement en SQLite**.
- Le dashboard lit **Postgres** (car DATABASE_URL est défini).
- La table **ivr_events** en Postgres reste **vide** → les dashboards affichent rien.

## Correction

1. **Activer l’écriture Postgres** : dans les variables d’environnement (Railway ou `.env`), définir :
   ```bash
   USE_PG_EVENTS=true
   ```
2. **Créer la table en Postgres** si ce n’est pas déjà fait (une seule fois) :
   ```bash
   psql $DATABASE_URL -f migrations/003_postgres_ivr_events.sql
   ```
   Puis éventuellement la migration 004 pour l’idempotence :
   ```bash
   psql $DATABASE_URL -f migrations/004_ivr_events_idempotence.sql
   ```
3. **Redémarrer** l’application. Les **nouveaux** appels et RDV seront alors écrits en Postgres et visibles dans les dashboards.

## Vérification au démarrage

Si `DATABASE_URL` (ou `PG_EVENTS_URL`) est défini mais `USE_PG_EVENTS` est false, le serveur log un avertissement au démarrage :

```
⚠️ DASHBOARD: Set USE_PG_EVENTS=true so appels/RDV appear in dashboards (see .env.example)
```

Consulter les logs Railway au démarrage pour confirmer que la config est cohérente.

## Autres points à vérifier

- **DID → tenant** : le numéro appelé (DID) doit être routé vers le bon `tenant_id` (table `tenant_routing`). Sinon les événements peuvent être enregistrés sous un autre tenant.
- **call_id** : Vapi doit envoyer `message.call.id` (ou équivalent) ; sans `call_id`, certains événements (ex. `booking_confirmed`) peuvent être ignorés.

Voir aussi : `docs/DASHBOARD_STATS_VAPI_VERIFICATION.md`.
