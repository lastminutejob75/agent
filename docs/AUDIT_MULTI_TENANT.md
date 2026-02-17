# Audit Multi-Tenant Readiness — UWI Agent

**Contexte :** Agent IA d'accueil et prise de RDV pour PME. Base principale **PostgreSQL** (migration depuis SQLite). Isolation par tenant requise.

**Date :** 2026-02

---

## Score global : **6,5 / 10**

Côté PostgreSQL (tenants, routing, slots, sessions, config) le multi-tenant est bien avancé. Les **bloquants** restants concernent le **fallback SQLite** (slots/appointments sans `tenant_id`), quelques requêtes/rapports et la **config globale** (prompts, credentials Google, Twilio).

---

## 1. Vérification base de données

### ✅ Une table `tenants` existe
- **PG :** `tenants_pg.py` — table `tenants` (tenant_id, name, timezone, status).
- **SQLite :** `db.py` — `_ensure_tenants_tables()` crée `tenants` + `tenant_config` + `tenant_routing`.

### 🟡 Tables métier et `tenant_id` / FK
- **PG (slots_pg, tenants_pg) :** `slots`, `appointments`, `tenant_config`, `tenant_routing` ont `tenant_id` et sont utilisés avec filtre tenant. Pas de FK explicite vers `tenants` dans tous les schémas (à vérifier en base).
- **SQLite (db.py) :** `slots` et `appointments` **n'ont pas** de colonne `tenant_id` (schéma dans `init_db()`). En fallback SQLite, **aucune isolation** par tenant pour créneaux/RDV.

### ✅ Index sur `tenant_id` (PG)
- `slots_pg` : requêtes avec `WHERE tenant_id = %s`.
- `tenant_routing` : index `(channel, key)` pour la résolution.

### ❌ RLS (Row-Level Security)
- Aucune policy RLS PostgreSQL détectée dans le code. L’isolation repose uniquement sur le filtre `tenant_id` dans les requêtes.

### 🟡 Migrations
- Pas de dossier de migrations versionnées type Alembic. Évolutions via `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE` dans le code (db.py, tenants_pg, etc.). Risque de dérive schéma entre environnements.

---

## 2. Résolution du tenant

### ✅ Mécanisme par canal
- **Vocal (Vapi) :** `tenant_routing.py` — `resolve_tenant_id_from_vocal_call(to_number, channel="vocal")`. Numéro appelé (DID) → `tenant_routing` (PG ou SQLite). Extraction du DID depuis le payload Vapi (`extract_to_number_from_vapi_payload`).
- **Web / autres canaux :** Pas de résolution explicite “Web” dans l’audit ; le tenant peut être déduit d’une session ou d’un header (à confirmer pour widget/API key).

### 🟡 Injection du tenant
- Pas de `Depends()` FastAPI sur un “tenant courant”. Le `resolved_tenant_id` est calculé dans chaque route (ex. `voice.py`) puis passé à `_get_or_resume_voice_session(tenant_id, call_id)` et aux services. Pas de ContextVar central.

### ✅ Routes / webhooks
- Voice : résolution DID → tenant avant traitement ; session et engine reçoivent `tenant_id`. Tool Vapi idem.

---

## 3. Isolation dans le code applicatif

### ✅ Engine / session et tenant
- `session.tenant_id` est renseigné partout après résolution. `tools_booking.get_slots_for_display(session=session)` et `calendar_adapter.get_calendar_adapter(session)` utilisent `session.tenant_id` (ou défaut 1).

### 🟡 Services et credentials
- **Google Calendar :** `calendar_adapter.get_calendar_adapter(session)` → `params_json` par tenant (`calendar_id`, `calendar_provider`). **Credentials :** un seul `SERVICE_ACCOUNT_FILE` global ; pas de credentials par tenant (un seul compte de service qui accède à plusieurs calendriers).
- **Twilio / WhatsApp :** Pas de mapping “numéro → tenant” côté code audité ; le routing vocal est par DID. À valider si Twilio est bien “un numéro par tenant” et que le lien DID ↔ tenant est cohérent.

### 🟡 Globals / singletons
- `ENGINE` global (`engine.py`), `_slots_cache` dans `tools_booking` (cache par `tenant_id` dans `by_tenant`). Pas de fuite évidente entre tenants si le cache est bien indexé par tenant.
- Config globale : `config.BUSINESS_NAME`, `config.TRANSFER_PHONE`, etc. — non scopés tenant (voir §5).

### 🟡 Prompts / LLM
- Prompts dans `prompts.py` ; pas de paramétrage par tenant (nom du cabinet, horaires, types de RDV). `tenant_config.params_json` peut contenir des infos métier mais n’est pas utilisé pour personnaliser les textes prompts dans l’audit.

---

## 4. Requêtes DB

### ✅ Requêtes PG
- **slots_pg :** Toutes les requêtes (list, count, book, find_booking, cancel, cleanup) filtrent par `tenant_id`.
- **tenants_pg :** Lecture `tenant_config` / `tenant_routing` par `tenant_id` ou `(channel, key)`.
- **session_pg (call_sessions) :** Clé `(tenant_id, call_id)` ; pas de requête sans tenant.

### 🔴 Requêtes sans filtre `tenant_id` (critique)
- **SQLite (db.py) :**
  - `list_free_slots` (SQLite path) : `SELECT id, date, time FROM slots WHERE is_booked=0 AND date >= ?` — **aucun tenant_id** (et la table n’a pas la colonne).
  - `count_free_slots` (SQLite) : idem.
  - `cleanup_old_slots` : `DELETE FROM slots WHERE date < ?` / `SELECT COUNT(*) FROM slots WHERE date >= ?` — global.
  - `book_slot_atomic` (SQLite path) : `UPDATE slots SET is_booked=1 WHERE id=?` et `INSERT INTO appointments (slot_id, ...)` — **pas de tenant_id** (colonnes absentes).
  - `find_booking_by_name` (SQLite) : lecture appointments/slots par slot_id sans filtre tenant.
  - `cancel_booking_sqlite` : idem.
- **ivr_events (SQLite et PG) :** Utilisent `client_id` ; dans ce produit **client_id = tenant_id** (ex. admin.py utilise `tenant_id` comme `client_id` pour ivr_events). Donc pas de fuite si toujours cohérent.

### 🟡 Rapports / KPIs
- `db.get_daily_kpis(client_id, date_str)` : filtre par `client_id` (équivalent tenant). Si appelé avec le bon `client_id` par tenant, OK. À confirmer que tous les appelants (cron, admin) passent bien le bon identifiant tenant.

---

## 5. Config & credentials par tenant

### 🟡 Config métier
- **Par tenant (PG) :** `tenant_config.params_json` (ex. `calendar_provider`, `calendar_id`, `contact_email`). `tenant_config.flags_json` pour feature flags.
- **Global (config.py) :** `BUSINESS_NAME`, `TRANSFER_PHONE`, `CABINET_*`, horaires, FAQ, etc. — **non par tenant**.

### 🟡 OAuth / Google
- Un seul `SERVICE_ACCOUNT_FILE` (ou équivalent) ; calendriers différenciés par `calendar_id` par tenant. Modèle “un service account, N calendriers” acceptable si les calendriers sont bien isolés par client.

### 🟡 Twilio / WhatsApp
- Numéros et credentials Twilio non audités en détail ; le routing vocal (DID → tenant) est en place. À valider : un numéro Twilio par tenant ou un mapping explicite.

---

## 6. Reporting & monitoring

### 🟡 Rapports quotidiens
- `reports.py` et KPIs dans `db.py` : scopés par `client_id` (tenant). Pas de boucle “pour chaque tenant” dans l’audit ; à confirmer que le cron / job appelle bien les rapports **par tenant** et non en global.

### 🟡 Consommation (tokens LLM, minutes Vapi)
- Pas de tracking par tenant visible dans le code audité.

---

## Synthèse des problèmes

### 🔴 Bloquants (à corriger avant production multi-tenant)

1. **SQLite slots/appointments sans tenant_id**  
   - **Fichiers :** `backend/db.py` (init_db, list_free_slots, cleanup_old_slots, book_slot_atomic, find_booking_by_name, cancel_booking_sqlite).  
   - **Problème :** En fallback SQLite, tous les tenants partagent les mêmes slots et RDV.  
   - **Fix :** Ajouter `tenant_id` aux tables SQLite `slots` et `appointments`, index, et **toutes** les requêtes SQLite (SELECT/UPDATE/INSERT/DELETE) doivent filtrer ou fournir `tenant_id`. Migration des données existantes si besoin.

2. **Requêtes SQLite slots sans filtre tenant**  
   - **Fichier :** `backend/db.py` (list_free_slots, count_free_slots, cleanup_old_slots, find_slot_id_by_datetime, book_slot_atomic SQLite path, find_booking_by_name SQLite, cancel_booking_sqlite).  
   - **Fix :** Une fois `tenant_id` ajouté au schéma, ajouter `WHERE tenant_id = ?` (et passer `tenant_id` partout).

3. **Pas de RLS en PostgreSQL**  
   - **Risque :** Une requête oubliée ou un bug peut exposer des données d’un autre tenant.  
   - **Fix :** Envisager des policies RLS sur les tables contenant `tenant_id` (slots, appointments, call_sessions, etc.) avec `current_setting('app.tenant_id')` ou équivalent, et définir ce contexte en début de requête par connexion/transaction.

### 🟡 Risques (fonctionnel mais fragile)

4. **Config globale (BUSINESS_NAME, TRANSFER_PHONE, horaires)**  
   - **Fichier :** `backend/config.py`.  
   - **Fix :** Déplacer vers `tenant_config.params_json` (ou table dédiée) et charger par tenant dans les routes / engine.

5. **Prompts non paramétrés par tenant**  
   - **Fichier :** `backend/prompts.py`.  
   - **Fix :** Variables type `{business_name}`, `{transfer_phone}` alimentées depuis la config tenant au moment de l’appel.

6. **Credentials Google un seul service account**  
   - Acceptable si un service account par environnement accède à N calendriers. Pour isolation forte (un compte par client), prévoir credentials par tenant (stockage sécurisé + chargement par tenant).

7. **Rapports / cron non bouclés par tenant**  
   - **Fichiers :** `backend/reports.py`, jobs cron.  
   - **Fix :** S’assurer que les rapports quotidiens sont générés et envoyés **par tenant** (liste des tenants actifs, puis une exécution par tenant).

8. **Session store SQLite (si utilisé)**  
   - **Fichier :** `backend/session_store_sqlite.py`.  
   - **Risque :** Clé de session uniquement par `conv_id` peut mélanger des sessions de tenants différents si conv_id n’est pas unique globalement.  
   - **Fix :** Clé `(tenant_id, conv_id)` ou équivalent, et vérifier que tous les chemins passent par le même store avec tenant.

### 🟢 OK

- Table `tenants` et config par tenant (PG + SQLite pour config/routing).
- Résolution tenant vocal par DID (PG-first, SQLite fallback).
- Routes voice / tool Vapi : résolution tenant systématique, session et engine avec `tenant_id`.
- PG slots/appointments : toutes les opérations avec `tenant_id`.
- PG call_sessions : clé (tenant_id, call_id).
- Calendar adapter : choix du calendrier par tenant (params_json) ; credentials globales assumées.
- Cache slots dans tools_booking : indexé par `tenant_id` (`by_tenant`).
- ivr_events : scope par `client_id` (tenants utilisent `client_id` = tenant_id).

---

## Plan de migration (ordre recommandé)

| # | Action | Effort | Priorité |
|---|--------|--------|----------|
| 1 | Ajouter `tenant_id` aux tables SQLite `slots` et `appointments` + migration données | M | Critique |
| 2 | Filtrer toutes les requêtes SQLite slots/appointments par `tenant_id` | M | Critique |
| 3 | Vérifier / corriger session_store_sqlite : clé incluant tenant_id si utilisé | S | Haute |
| 4 | Documenter ou implémenter le flux rapports quotidiens par tenant | S | Haute |
| 5 | Déplacer BUSINESS_NAME, TRANSFER_PHONE (et si besoin horaires) vers config tenant | M | Moyenne |
| 6 | Paramétrer les prompts par tenant (nom cabinet, transfert, etc.) | M | Moyenne |
| 7 | Évaluer RLS PostgreSQL sur tables avec tenant_id | L | Moyenne |
| 8 | Migrations versionnées (ex. Alembic) pour schéma PG + SQLite | L | Basse |
| 9 | Tracking consommation (LLM, Vapi) par tenant | M | Basse |

**Légende effort :** S = petit, M = moyen, L = large.

---

*Audit basé sur l’état du code à la date indiquée ; base principale PostgreSQL, fallback SQLite partiel.*
