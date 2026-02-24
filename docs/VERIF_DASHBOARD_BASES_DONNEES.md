# Vérification : Dashboard client ↔ bases de données et stats Vapi

## 1. Chaîne frontend → backend

| Frontend (landing) | Backend (FastAPI) | Rôle |
|--------------------|-------------------|------|
| `api.tenantMe()` | `GET /api/tenant/me` | Profil tenant (nom, email, params) |
| `api.tenantDashboard()` | `GET /api/tenant/dashboard` | Snapshot : counters_7d, last_call, last_booking, service_status |
| `api.tenantKpis(days)` | `GET /api/tenant/kpis?days=7` | KPIs par jour + trend (graphique) |
| `api.tenantTechnicalStatus()` | `GET /api/tenant/technical-status` | Statut DID, calendrier, agent |

- **Auth** : routes tenant protégées par **cookie `uwi_session`** (JWT, typ=client_session).  
  Le frontend envoie `credentials: "include"` donc le cookie est bien envoyé vers le backend.
- **Contexte** : `AppLayout` appelle `tenantMe()` puis `tenantDashboard()` au chargement et passe `{ me, dashboard }` en contexte à l’`Outlet`.  
  `AppDashboard` utilise `dashboard?.counters_7d` (calls_total, bookings_confirmed) et les affiche (greeting, stats).

**Conclusion** : le dashboard est bien connecté aux API tenant ; les stats affichées viennent du backend.

---

## 2. Backend : sources des données

### 2.1 Dashboard snapshot (`/api/tenant/dashboard`)

- **Fichier** : `backend/routes/admin.py` → `_get_dashboard_snapshot(tenant_id, tenant_name)`.
- **Lecture** :
  - Si **`DATABASE_URL` ou `PG_EVENTS_URL`** est défini → lecture **Postgres** `ivr_events` :
    - `service_status` : dernier event (MAX(created_at)) < 15 min → online.
    - `counters_7d` : appels (COUNT DISTINCT call_id), bookings_confirmed, transferred_human + transferred, user_abandon.
    - `last_call` : dernier call_id avec outcome (booking_confirmed > transferred > user_abandon).
  - Sinon → **fallback SQLite** : même logique sur la table SQLite `ivr_events`.
- **last_booking** : si `USE_PG_SLOTS` et Postgres dispo → table `appointments` + `slots` (PG). Sinon déduit du last_call si outcome = booking_confirmed.
- **Convention** : `ivr_events.client_id = tenant_id` (une ligne = un event par tenant).

### 2.2 KPIs par jour (`/api/tenant/kpis`)

- **Fichier** : `backend/routes/admin.py` → `_get_kpis_daily(tenant_id, days)`.
- **Lecture** :
  - Si **`DATABASE_URL` ou `PG_EVENTS_URL`** → **Postgres** `ivr_events` : agrégats par jour (calls, bookings, transfers) sur la fenêtre demandée + semaine précédente pour le trend.
  - Sinon → **SQLite** `ivr_events` (même schéma).

### 2.3 Statut technique (`/api/tenant/technical-status`)

- **Fichier** : `backend/routes/admin.py` → `_get_technical_status(tenant_id)`.
- **Sources** :
  - Tenant / params / routing : **Postgres** (tenants_pg) ou config.
  - Dernier event agent : **Postgres** ou **SQLite** `ivr_events` (MAX(created_at)) pour “online / offline”.

### 2.4 Profil tenant (`/api/tenant/me`)

- **Fichier** : `backend/routes/tenant.py` → `_get_tenant_detail(tenant_id)` (admin).
- **Source** : **Postgres** (tenants_pg) en priorité, sinon fallback config/SQLite selon le projet.

**Conclusion** : les stats (appels, RDV, transferts) et le statut agent viennent bien de la base (Postgres ou SQLite) via `ivr_events` et, pour les RDV, `appointments`/`slots` en PG.

---

## 3. Écriture des events (Vapi → ivr_events)

Pour que les **stats et le dashboard ne soient pas vides**, les events doivent être **écrits** dans la même base que celle lue par le dashboard.

- **Moteur / webhook** : `backend/db.py` → `create_ivr_event(...)` :
  - Écrit toujours en **SQLite** (table `ivr_events`) si utilisée.
  - Si **`USE_PG_EVENTS=true`** : **dual-write** vers **Postgres** via `backend/ivr_events_pg.py` → `create_ivr_event_pg(client_id, call_id, event, ...)`.
- **client_id** : dans le flow vocal (Vapi), `session.client_id` est renseigné (ex. dans `backend/routes/voice.py` avec `existing_client.id` / tenant). Ce `client_id` = `tenant_id` est celui utilisé pour les requêtes dashboard (convention `ivr_events.client_id = tenant_id`).
- **Table Postgres** : créée au démarrage si `USE_PG_EVENTS=true` et `DATABASE_URL` (ou équivalent) défini → `backend/main.py` appelle `ensure_ivr_events_table()`.

**Conclusion** : Vapi (et le moteur) alimentent bien `ivr_events` (SQLite et/ou Postgres). En prod, si le dashboard lit en Postgres, il faut **USE_PG_EVENTS=true** pour que les appels/RDV apparaissent.

---

## 4. Checklist déploiement (stats visibles)

1. **Backend**
   - [ ] `DATABASE_URL` (ou `PG_EVENTS_URL`) défini pour que le dashboard **lise** `ivr_events` en Postgres.
   - [ ] **`USE_PG_EVENTS=true`** pour que les events Vapi/moteur soient **écrits** en Postgres (sinon table ivr_events vide côté PG → dashboard vide).
   - [ ] Migrations Postgres appliquées (ex. `003_postgres_ivr_events.sql`, `004_...` si présent).
   - [ ] Cookie `uwi_session` émis après login (même domaine ou CORS avec credentials) pour que les appels tenant soient authentifiés.

2. **Landing**
   - [ ] `VITE_UWI_API_BASE_URL` pointe vers le backend (ex. Railway).
   - [ ] Appels avec `credentials: "include"` (déjà le cas dans `landing/src/lib/api.js`).

3. **Vérification rapide**
   - Se connecter au dashboard client, ouvrir `/app` : le greeting doit afficher “X appels” et “Y RDV pris” si des events existent pour ce tenant en base.
   - Page Statut : “Service agent” reflète le dernier event (online si < 15 min).
   - Si tout est à 0 alors que des appels ont eu lieu : vérifier `USE_PG_EVENTS` et que les events sont bien écrits avec `client_id = tenant_id`.

---

## 5. Résumé

- **Oui** : le dashboard client est bien connecté aux bases de données et récupère les stats (Vapi / ivr_events, et appointments si PG slots).
- **Lecture** : Postgres si `DATABASE_URL` (ou `PG_EVENTS_URL`), sinon SQLite.
- **Écriture** : SQLite toujours (si utilisée) ; Postgres **uniquement si `USE_PG_EVENTS=true`**.
- En production, pour avoir les chiffres réels dans le dashboard : **`USE_PG_EVENTS=true`** et **`DATABASE_URL`** (ou équivalent) configurés, et migrations ivr_events appliquées.
