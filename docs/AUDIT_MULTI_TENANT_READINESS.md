# Audit Multi-Tenant Readiness — UWI Agent

**Contexte :** Agent IA d'accueil et prise de RDV pour PME. Base principale **PostgreSQL** (migration depuis SQLite). Isolation multi-tenant requise par canal (vocal, WhatsApp, web).

**Dashboard clients :** Les clients (tenants) ont leur **dashboard sur uwiapp.com** (appels, RDV). Les APIs admin/dashboard doivent rester scopées par `tenant_id` pour alimenter ce frontend (ex. `GET /api/admin/tenants/{tenant_id}/dashboard`, transfer-reasons, technical-status).

**Date audit :** 2025-02

---

## Score global : **6/10** → **8/10** (post Jours 1–7)

PostgreSQL structuré pour le multi-tenant. **Jours 1–5** : résolution tenant Vocal, WhatsApp, Web ; session store web en PG ; ClientMemory en PG ; rapports `?tenant_id=` ; SQLite bloqué en multi-tenant. **Jour 6** : SQLite slots/appointments avec `tenant_id`. **Jour 7** : Depends `require_tenant_web` / `require_tenant_from_header` / `validate_tenant_id` (`backend/deps.py`) ; helper `get_tenant_display_config(tenant_id)` (business_name, transfer_phone depuis `params_json`) ; greeting vocal utilise le nom du tenant ; tests deps + config + intégration web.

---

## 1. Vérification base de données

| Point | Statut | Détail |
|-------|--------|--------|
| Table `tenants` | ✅ | Présente (SQLite `db.py` + PG `tenants_pg`). PG : `tenants`, `tenant_config`, `tenant_routing`. |
| `tenant_id` + FK sur tables métier | ✅ PG / ✅ SQLite (Jour 6) | **PG** : `slots`, `appointments` ont `tenant_id` et toutes les requêtes filtrent. **SQLite** : colonne `tenant_id` (DEFAULT 1), migration `_migrate_sqlite_add_tenant_id`, toutes les requêtes filtrent. |
| Index sur `tenant_id` | ✅ PG | Utilisés dans `slots_pg` (WHERE tenant_id = %s). Pas d’index explicite créé dans le code (à vérifier en migrations PG). |
| RLS (Row-Level Security) | ❌ | Aucune policy RLS ou équivalent dans le code. Isolation uniquement par filtre applicatif. |
| Migrations cohérentes | 🟡 | Pas de dossier migrations visible ; schéma PG décrit dans le code (tenants_pg, slots_pg, session_pg, ivr_events_pg). |

---

## 2. Résolution du tenant

| Canal | Mécanisme | Fichier | Statut |
|-------|-----------|---------|--------|
| **Vocal (Vapi)** | Numéro appelé (DID) → `tenant_routing` (channel=`vocal`, key=E.164). PG-first, fallback SQLite. | `tenant_routing.py`, `tenants_pg.pg_resolve_tenant_id` | ✅ |
| **WhatsApp** | Numéro destinataire (To) → `tenant_routing` (channel=`whatsapp`, key=E.164). `resolve_tenant_from_whatsapp(to_number)`. | `tenant_routing.py`, `routes/whatsapp.py` | ✅ |
| **Web** | Header `X-Tenant-Key` → `tenant_routing` (channel=`web`, key=api_key). `resolve_tenant_from_api_key(api_key)`. Défaut si absent ; 401 si clé invalide. | `tenant_routing.py`, `main.py` (/chat, /stream) | ✅ |

**Jour 7 :** Résolution Web centralisée via `Depends(require_tenant_web)` sur `POST /chat` (`backend/deps.py`) ; `require_tenant_from_header` et `validate_tenant_id` pour autres routes. Config affichage : `get_tenant_display_config(tenant_id)` (business_name, transfer_phone depuis `params_json`). Greeting vocal l'utilise. Tests : `test_deps.py`, `test_tenant_config.py`, `test_multitenant_web_integration.py`.

---

## 3. Isolation dans le code applicatif

| Point | Statut | Détail |
|-------|--------|--------|
| Engine reçoit un tenant explicite | ✅ | `session.tenant_id` est fixé par la route (vocal) ; engine utilise `getattr(session, "tenant_id", None)` pour scope ivr_events et `get_tenant_flags`. |
| Services (Calendar, Twilio) par tenant | 🟡 | **Calendar** : `get_calendar_adapter(session)` utilise `tenant_config.params_json` (calendar_id par tenant) ; credentials Google = **global** (`SERVICE_ACCOUNT_FILE`). **Twilio** : pas de mapping numéro → tenant vu dans le code. |
| Variables globales / singletons | 🟡 | `ENGINE` (engine global), `get_client_memory()` singleton. **Session store** : `HybridSessionStore` — sessions web en PG (`web_sessions` par `tenant_id`, `conv_id`), cache `conv_id` → `tenant_id` pour GET /stream. **ClientMemory** : `HybridClientMemory` — PG `tenant_clients` / `tenant_booking_history` quand `tenant_id` connu (ContextVar ou param). |
| Prompts paramétrés par tenant | 🟡 | **Jour 7** : `get_tenant_display_config(tenant_id)` (business_name, transfer_phone depuis `params_json`) ; greeting vocal l'utilise. Horaires et autres messages restent globaux. |

---

## 4. Requêtes DB sans filtre `tenant_id` (critique)

Toutes les requêtes **PG** (slots_pg, tenants_pg, session_pg) passent par `tenant_id`. En revanche :

- **db.py (SQLite fallback)** — **Jour 6** : colonne `tenant_id` ajoutée (DEFAULT 1), toutes les requêtes (list_free_slots, find_slot_id_by_datetime, book_slot_atomic, find_booking_by_name, cancel_booking_sqlite, cleanup_old_slots) filtrent par `tenant_id`.

- **session_store_sqlite**  
  - `get(conv_id)`, `get_or_create(conv_id)` : clé = `conv_id` uniquement. Pas de `tenant_id` dans la table `sessions`. Risque de collision si `conv_id` identique pour deux tenants (rare mais possible).

- **client_memory.py**  
  - Toutes les requêtes (clients, booking_history) : **aucun tenant_id**. Une seule base `data/clients.db` pour tous les “clients” (patients). En multi-tenant, tous les tenants partageraient les mêmes données.

- **db.py get_daily_report_data**  
  - Utilise `client_id` (équivalent scope “tenant” pour les rapports IVR). Pas de colonne `tenant_id` dans `ivr_events` ; le scope est bien `client_id` (aligné tenant en vocal).

---

## 5. Config & credentials par tenant

| Élément | Statut | Détail |
|---------|--------|--------|
| Config métier (horaires, types RDV, messages) | 🟡 | `params_json` : calendar_id, business_name, transfer_phone, **horaires** (repli `OPENING_HOURS_DEFAULT`). `get_tenant_display_config(tenant_id)` ; rapports quotidiens utilisent `business_name` ; `prompts.format_transfer_callback(phone_number, horaires)`. Messages génériques = globaux. |
| Tokens OAuth / Google Calendar | 🟡 | Un seul `SERVICE_ACCOUNT_FILE` global. Par tenant : uniquement `calendar_id` (et provider) dans `params_json`. |
| Numéros Twilio / WhatsApp | ❌ | Pas de mapping numéro → tenant dans le code (sauf vocal via `tenant_routing`). |

---

## 6. Reporting & monitoring

| Point | Statut | Détail |
|-------|--------|--------|
| Rapports quotidiens scopés par tenant | ✅ | `POST /api/reports/daily?tenant_id=` optionnel. Sans `tenant_id` : boucle sur `pg_fetch_tenants`, email = `params_json.contact_email` par tenant (repli REPORT_EMAIL). Avec `tenant_id` : idem. business_name par tenant pour l'objet du mail. |
| Tracking consommation (tokens, minutes) | ❌ | Aucun tracking par tenant vu dans le code. |

---

## 🔴 Bloquants (à corriger avant production multi-tenant)

1. **backend/db.py (schéma SQLite slots/appointments)** — ✅ **Résolu (Jour 6)**  
   Tables `slots` et `appointments` ont désormais `tenant_id` (DEFAULT 1). Migration `_migrate_sqlite_add_tenant_id` pour DB existantes. Requêtes SQLite (count_free_slots, list_free_slots, find_slot_id_by_datetime, book_slot_atomic, find_booking_by_name, cancel_booking_sqlite, cleanup_old_slots) filtrent par `tenant_id`. UNIQUE(slots) = (tenant_id, date, time). *(Ancien : sans tenant_id.)* Dès que `USE_PG_SLOTS=false` ou fallback SQLite, tous les tenants partagent les mêmes créneaux et RDV.  
   **Fix :** Ajouter `tenant_id` aux tables SQLite, à toutes les requêtes (SELECT/UPDATE/INSERT/DELETE), et à l’index. Ou désactiver complètement le chemin SQLite en prod multi-tenant.

2. **backend/session_store_sqlite.py** — ✅ **Résolu (Jour 4)**  
   En prod multi-tenant avec PG : `HybridSessionStore` utilise `web_sessions` (PG) scopé `(tenant_id, conv_id)` pour le web ; cache `conv_id` → `tenant_id` pour GET /stream. Chemin SQLite bloqué par `_sqlite_guard` si `MULTI_TENANT_MODE=true`.

3. **backend/client_memory.py** — ✅ **Résolu (Jour 5)**  
   `HybridClientMemory` + `client_memory_pg` : tables PG `tenant_clients`, `tenant_booking_history` scopées par `tenant_id`. Voice et rapports passent `tenant_id` ; fallback SQLite bloqué en multi-tenant. *(Ancien : base SQLite globale sans tenant_id.)*

4. **backend/routes/whatsapp.py** — ✅ **Résolu (Jour 2)**  
   `resolve_tenant_from_whatsapp(to_number)` (numéro destinataire → `tenant_routing` channel=whatsapp) ; `tenant_id` injecté dans la session et `current_tenant_id`.

5. **Web / widget** — ✅ **Résolu (Jour 3)**  
   Header `X-Tenant-Key` → `resolve_tenant_from_api_key(api_key)` ; `/chat` et `/stream` fixent `session.tenant_id` et `current_tenant_id`. Admin : `channel=web` dans `POST /api/admin/routing`. *(Ancien : aucun mécanisme identifié.)*

---

## 🟡 Risques (fonctionnel mais fragile)

1. **backend/config.py (BUSINESS_NAME, TRANSFER_PHONE, horaires)**  
   **Adressé (Jour 7 + suite)** : `get_tenant_display_config(tenant_id)` retourne business_name, transfer_phone, horaires (params_json + repli config). Greeting vocal et rapports quotidiens utilisent business_name ; `params_json.horaires` + `format_transfer_callback(phone_number, horaires)` pour message de rappel. Routes admin : `Depends(validate_tenant_id)` sur `tenant_id` path.

2. **backend/calendar_adapter.py**  
   Credentials Google communs à tous les tenants. Un seul compte de service.  
   **Amélioration :** Pour forte isolation, prévoir des credentials par tenant (ou délégation de domaine) et les charger depuis la config tenant.

3. **backend/routes/reports.py**  
   **Adressé** : Boucle sur `pg_fetch_tenants` ; email = `params_json.contact_email` par tenant (repli global). Appel avec `?tenant_id=` utilise aussi le contact_email du tenant. Données scopées par tenant (get_daily_report_data(tid), business_name par tenant).

4. **Pas de RLS en PG**  
   L’isolation repose uniquement sur les filtres applicatifs. Une requête oubliant `tenant_id` exposerait des données.  
   **Amélioration :** Ajouter des policies RLS sur les tables contenant `tenant_id` (slots, appointments, call_sessions, etc.) pour renforcer la garantie côté DB.

5. **ivr_events.client_id vs tenant_id**  
   Colonne nommée `client_id` alors qu’elle sert de scope tenant pour le vocal. Possible confusion avec “client” patient.  
   **Amélioration :** Documenter clairement que `client_id` = tenant pour IVR ; ou renommer en `tenant_id` si migration possible.

---

## 🟢 OK

- **PG : tenants, tenant_config, tenant_routing** : En place, utilisés pour le routing vocal (DID → tenant_id) et la config (flags, params).
- **PG : slots_pg / appointments** : Toutes les requêtes (list, count, book, find_booking, cancel, cleanup) filtrent par `tenant_id`.
- **PG : call_sessions (session_pg)** : Clé `(tenant_id, call_id)` ; journal/lock par tenant.
- **Résolution tenant vocal** : `resolve_tenant_id_from_vocal_call(to_number)` dans voice.py, injection dans la session puis engine.
- **Calendar adapter** : Utilise `session.tenant_id` et `tenant_config.params_json` (calendar_id, provider) par tenant.
- **Engine** : Utilise `session.tenant_id` pour scope ivr_events et `get_tenant_flags`.
- **Rapports IVR (get_daily_report_data)** : Toutes les requêtes filtrent par `client_id` (scope = 1 tenant/jour).

---

## 📋 Plan de migration (ordre recommandé)

| # | Action | Effort | Priorité |
|---|--------|--------|----------|
| 1 | Ajouter `tenant_id` aux tables SQLite `slots` et `appointments` + migrer toutes les requêtes (list_free_slots, book_slot_atomic, find_booking_by_name, cancel). | M | Critique |
| 2 | Ajouter résolution tenant pour WhatsApp (mapping numéro ou identifiant → tenant_id) et injecter tenant dans la session. | S | Critique |
| 3 | Définir résolution tenant pour le web (API key ou paramètre tenant) et l’utiliser dans les routes chat/stream. | M | Critique |
| 4 | Session store : clé ou colonne `tenant_id` (SQLite + PG si utilisé) pour isoler les sessions par tenant. | M | Critique |
| 5 | ClientMemory : introduire `tenant_id` (ou équivalent) partout pour isoler clients/patients par tenant. | L | Critique |
| 6 | Rapports quotidiens : boucle sur les tenants (ex. depuis PG), email par tenant, et scope des données par tenant. | M | ✅ Fait (contact_email par tenant, boucle pg_fetch_tenants, business_name par tenant). |
| 7 | Config métier par tenant : BUSINESS_NAME, TRANSFER_PHONE depuis tenant_config/params. | S | ✅ Fait (Jour 7 : get_tenant_display_config, params_json, greeting vocal). Horaires à étendre si besoin. |
| 8 | (Optionnel) RLS sur les tables PG avec tenant_id. | M | Renforcement |
| 9 | (Optionnel) Tracking consommation (tokens, minutes Vapi) par tenant. | M | Plus tard |

**Légende effort :** S = petit, M = moyen, L = large.

---

*Audit basé sur l’état du code (PostgreSQL comme base principale, fallback SQLite encore présent).*
