# Pourquoi le dashboard client ne reflète pas la réalité Vapi ?

Ce document liste les causes possibles et les vérifications pour que les appels Vapi apparaissent correctement dans le dashboard client.

---

## 1. Chaîne des données (rappel)

```
Vapi (appel entrant) 
  → Webhook POST /api/vapi/webhook (ou assistant request)
  → extract_to_number_from_vapi_payload(payload) → numéro appelé (DID)
  → resolve_tenant_id_from_vocal_call(to_number) → tenant_id
  → session.tenant_id = tenant_id
  → _persist_ivr_event(session, "call_started" | "booking_confirmed" | …) 
  → create_ivr_event(client_id=tenant_id, call_id, event, …)
  → écriture ivr_events (SQLite et/ou Postgres selon USE_PG_EVENTS)

Dashboard client (GET /api/tenant/dashboard)
  → _get_dashboard_snapshot(tenant_id du cookie JWT)
  → lecture ivr_events WHERE client_id = tenant_id
  → affichage counters_7d, last_call, service_status
```

**Convention** : dans `ivr_events`, la colonne `client_id` = **tenant_id** (le cabinet connecté au dashboard). Chaque event doit être enregistré avec le bon `tenant_id` pour apparaître sur le bon dashboard.

---

## 2. Causes possibles (pourquoi « pas connecté à la réalité »)

### A. Les events ne sont pas écrits en Postgres (dashboard lit le PG)

- **Symptôme** : le dashboard affiche 0 appels / 0 RDV alors que des appels Vapi ont bien eu lieu.
- **Cause** : le backend lit les stats depuis **Postgres** (`DATABASE_URL` ou `PG_EVENTS_URL`) mais les events ne sont écrits qu’en **SQLite** si `USE_PG_EVENTS` n’est pas activé.
- **Vérification** : au démarrage du backend, si tu vois le message  
  `⚠️ DASHBOARD: Set USE_PG_EVENTS=true so appels/RDV appear in dashboards`  
  alors les events ne sont pas écrits en Postgres et le dashboard (qui lit le PG) reste vide.
- **Action** : sur Railway (ou ton hébergement), définir **`USE_PG_EVENTS=true`**. Redéployer. Vérifier que la table `ivr_events` existe (création auto au boot si `ensure_ivr_events_table()` est appelée).

Référence : `docs/VERIF_DASHBOARD_BASES_DONNEES.md` et `backend/main.py` (warning au démarrage).

---

### B. Mauvais tenant : le numéro appelé (DID) n’est pas routé vers ce tenant

- **Symptôme** : un cabinet (tenant_id = 2) voit 0 appels alors qu’il reçoit des appels sur son numéro ; ou tous les appels apparaissent chez un seul tenant (souvent tenant_id = 1).
- **Cause** : le **routing vocal** associe le **numéro appelé (DID)** à un `tenant_id`. Si le numéro du cabinet n’est pas enregistré dans le routing (Postgres `tenant_routing` ou équivalent), `resolve_tenant_id_from_vocal_call(to_number)` renvoie le **tenant par défaut** (souvent 1). Tous les events sont alors stockés avec `client_id = 1`.
- **Vérification** :
  - En base : pour chaque tenant, il doit exister une entrée (channel = `vocal`, `did_key` = numéro au format E.164 ou normalisé) qui pointe vers ce `tenant_id`.
  - Dans les logs : en cas de numéro non routé, un log du type `[TENANT_ROUTE_MISS] to=+33... tenant_id=1 numéro non onboardé` peut apparaître.
- **Action** : s’assurer que le **numéro Vapi** (celui que les patients appellent) est bien enregistré pour ce tenant dans la table de routing (admin ou migration). Vérifier que `extract_to_number_from_vapi_payload` reçoit bien ce numéro dans le payload Vapi (structure `message.call.phoneNumber.number` ou `call.to` selon la version Vapi).

Référence : `backend/tenant_routing.py` (`resolve_tenant_id_from_vocal_call`), `backend/tenants_pg.py` (`pg_resolve_tenant_id`).

---

### C. Vapi n’appelle pas notre backend (ou mauvais assistant)

- **Symptôme** : aucun event (même pas `call_started`) en base pour ce tenant alors que les appels ont lieu côté Vapi.
- **Cause** : l’assistant Vapi n’est pas configuré pour appeler notre backend (URL du webhook / Server URL incorrecte), ou un autre assistant (autre compte / autre projet) reçoit les appels.
- **Vérification** : dans la console Vapi, vérifier que l’**Assistant** utilisé pour ce numéro a bien :
  - **Server URL** (ou Webhook URL) = `https://ton-backend.railway.app/api/vapi/...` (ou l’URL de ton backend),
  - et que les appels de test déclenchent bien des requêtes vers ce backend (logs Railway, ou endpoint de health/log si tu en as un).
- **Action** : corriger l’URL du serveur dans l’assistant Vapi et s’assurer que le numéro (DID) utilisé en prod est bien celui attaché à cet assistant.

---

### D. Table `ivr_events` absente ou erreurs d’écriture silencieuses

- **Symptôme** : `USE_PG_EVENTS=true` et routing OK, mais toujours rien dans le dashboard.
- **Cause** : la table Postgres `ivr_events` n’existe pas (migration non appliquée), ou les écritures échouent (contrainte, type, etc.) et l’exception est catchée (dual-write en try/except).
- **Vérification** :
  - Au démarrage : message `✅ ivr_events table ready` indique que la table a été créée ou existe déjà.
  - En base : `SELECT COUNT(*) FROM ivr_events WHERE client_id = <tenant_id>;` (remplacer par le tenant_id du cabinet connecté).
  - Consulter les logs backend lors d’un appel test : recherche de `ivr_events_pg: insert failed` ou erreurs psycopg.
- **Action** : appliquer la migration Postgres qui crée `ivr_events` (ex. `migrations/003_postgres_ivr_events.sql`). Vérifier que `ensure_ivr_events_table()` est bien exécutée au boot (voir `main.py`). Corriger les erreurs d’insertion si les logs en montrent.

Référence : `backend/ivr_events_pg.py`, `backend/main.py` (startup).

---

## 3. Checklist rapide (dashboard = réalité Vapi)

| # | Vérification | Où / comment |
|---|------------------------------|----------------------------------------------|
| 1 | `USE_PG_EVENTS=true` (si le dashboard lit en Postgres) | Variables d’environnement backend (Railway, etc.) |
| 2 | `DATABASE_URL` (ou `PG_EVENTS_URL`) défini | Idem |
| 3 | Table `ivr_events` présente en Postgres | Migration 003 ou `ensure_ivr_events_table()` au boot |
| 4 | Numéro Vapi (DID) enregistré pour ce tenant | Table de routing (channel = vocal, did_key = numéro) → bon tenant_id |
| 5 | Assistant Vapi pointe vers ce backend | Console Vapi → Assistant → Server URL = ton backend |
| 6 | Au moins un event `call_started` par appel | Logs backend pendant un appel test ; ou `SELECT * FROM ivr_events ORDER BY created_at DESC LIMIT 5` |

---

## 4. Résumé

- Le dashboard client est **branché** sur la même source que les stats : la table **`ivr_events`**, filtrée par **`client_id` = tenant_id** du compte connecté.
- Pour que ça reflète la réalité Vapi il faut :
  1. Que **chaque appel** déclenche des **écritures** dans `ivr_events` avec le **bon tenant_id** (donc bon routing du DID).
  2. Que le **même stock** soit **lu** par le dashboard (donc Postgres alimenté si le dashboard lit en Postgres → **USE_PG_EVENTS=true**).
  3. Que **Vapi** envoie bien les requêtes à **ce** backend et avec un payload d’où on extrait le bon numéro (DID).

En cas de doute, vérifier d’abord **USE_PG_EVENTS** et le **routing du numéro** (DID → tenant_id), puis que les webhooks Vapi atteignent bien le backend.
