# Dashboard admin — sources de données et multi-tenant

Document de référence : comment le dashboard admin est alimenté et ce qu’il faut vérifier quand il y a plusieurs clients (tenants).

---

## 1. Vue d’ensemble

| Page admin | Endpoint principal | Données affichées |
|------------|--------------------|-------------------|
| **Dashboard** (accueil) | `GET /api/admin/stats/dashboard-payload?window_days=30` | KPIs globaux, courbe appels, top clients (appels + coût), billing |
| **Tenants** (liste) | `GET /api/admin/tenants` | Liste des clients (PG ou SQLite) |
| **Fiche tenant** | `GET /api/admin/tenants/{id}` + `GET /api/admin/tenants/{id}/billing` | Détail client, facturation, params |
| **Appels** | `GET /api/admin/calls?tenant_id=&days=&limit=&result=` | Liste des appels (filtrable par tenant) |
| **Leads** | `GET /api/admin/leads` + `GET /api/admin/leads/count-new` | Leads pré-onboarding (badge + liste) |
| **Operations** | `GET /api/admin/stats/operations-snapshot?window_days=7` | Billing, suspensions, coût, erreurs, quota |
| **Quality** | `GET /api/admin/stats/quality-snapshot?window_days=7` | KPIs qualité + top par anti_loop / abandons / transferts |

Toutes les requêtes admin passent par **adminApi** (landing) → **VITE_UWI_API_BASE_URL** + token admin (cookie ou Bearer).

---

## 2. Sources de données backend (par type)

### 2.1 Tenants (clients)

- **Liste** : `_get_tenant_list()`  
  - **Prod** : `pg_fetch_tenants()` → table **tenants** (PG, `USE_PG_TENANTS` + `DATABASE_URL` / `PG_TENANTS_URL`).  
  - **Fallback** : SQLite `tenants` (dev local).
- **Détail** : `_get_tenant_detail(tenant_id)`  
  - **Prod** : `pg_get_tenant_full(tenant_id)` → **tenants** + **tenant_config** (params, flags).  
  - **Fallback** : SQLite.

→ Pour plusieurs clients : tous les tenants actifs/inactifs viennent de la même source (PG ou SQLite). Vérifier que **PG_TENANTS_URL** ou **DATABASE_URL** pointe bien la base qui contient la table **tenants**.

### 2.2 Appels / RDV / transferts / erreurs (KPIs globaux et par tenant)

- **Tables** : **ivr_events** (PG ou SQLite), **call_sessions** (PG pour durée).
- **Convention** : `ivr_events.client_id` = **tenant_id** (un event est rattaché à un client).
- **URL** : `DATABASE_URL` ou **PG_EVENTS_URL** (souvent la même base en prod).

Données utilisées :

- **Dashboard global** : `_get_global_stats()` → agrégats sur **ivr_events** (calls_total, appointments_total, transfers_total, errors_total, last_activity_at) + **call_sessions** (minutes) + **vapi_call_usage** (minutes / coût USD si dispo).
- **Top clients (appels)** : `_get_stats_top_tenants("calls")` → **ivr_events** groupé par `client_id`, tri par nombre d’appels.
- **Top clients (coût)** : `_get_stats_top_tenants("cost_usd")` → **vapi_call_usage** groupé par `tenant_id`.
- **Liste appels** (`/admin/calls`) : `_get_calls_list()` → **ivr_events** (+ **call_sessions** pour durée), filtrable par `tenant_id` et par `result` (rdv, transfer, abandoned, error).
- **Fiche tenant / dashboard tenant** : agrégats **ivr_events** filtrés par `client_id = tenant_id`.
- **Quality** : **ivr_events** (anti_loop, abandons, transferts) groupé par `client_id`.

→ Pour plusieurs clients : chaque event doit avoir le bon **client_id** (= tenant_id). Si les events sont écrits avec un mauvais client_id ou sans client_id, les stats par tenant et le top clients seront faux. Vérifier que le pipeline qui écrit dans **ivr_events** (voice, Vapi, etc.) envoie bien **tenant_id** → **client_id**.

### 2.3 Coût et facturation (billing)

- **Tables** : **vapi_call_usage** (minutes / coût par appel, par tenant), **tenant_billing** (Stripe, statut, période).
- **URL** : **vapi_call_usage** = `DATABASE_URL` ou **PG_EVENTS_URL** ; **tenant_billing** = `DATABASE_URL` ou **PG_TENANTS_URL**.

Données utilisées :

- **Dashboard** : `_get_billing_snapshot()` → coût total ce mois (**vapi_call_usage**), top tenants par coût ce mois, liste **tenant_billing** en `past_due` / `unpaid`.
- **Operations** : idem billing + suspensions (tenant_billing + tenants), coût today / 7j, erreurs, quota (usage vs inclus).

→ Pour plusieurs clients : **vapi_call_usage** doit avoir **tenant_id** correct par ligne. **tenant_billing** a une ligne par tenant (créée à la souscription / sync webhook). Vérifier que chaque client actif a bien une ligne **tenant_billing** si tu utilises Stripe, et que **vapi_call_usage** est bien rempli par tenant (webhook Vapi ou job).

### 2.4 Leads (pré-onboarding)

- **Table** : **pre_onboarding_leads** (PG).
- **URL** : `DATABASE_URL` ou **PG_TENANTS_URL** (via `leads_pg`).

Données utilisées :

- **Badge sidebar** : `GET /api/admin/leads/count-new` → `COUNT(*) WHERE status = 'new'`.
- **Liste leads** : `GET /api/admin/leads?status=&enterprise=` → liste avec filtres.
- **Détail lead** : `GET /api/admin/leads/{id}`.

→ Les leads ne sont pas liés à un tenant tant qu’ils ne sont pas convertis. Pas de risque de mélange multi-tenant pour les leads.

### 2.5 Appointments (RDV)

- **Optionnel** : si **USE_PG_SLOTS** et table **appointments** (PG), `_get_global_stats()` peut utiliser **appointments** pour `appointments_total` à la place de **ivr_events** (booking_confirmed).
- Sinon : **appointments_total** = comptage des events **booking_confirmed** dans **ivr_events**.

→ En multi-tenant, si tu utilises **appointments**, il faut un critère tenant (ex. `tenant_id` ou lien avec un tenant). Sinon les RDV sont déjà “par appel” donc par client_id dans ivr_events.

---

## 3. Points critiques pour plusieurs clients

1. **ivr_events.client_id**  
   Doit être rempli avec le **tenant_id** à chaque event (call_started, booking_confirmed, etc.). Si c’est vide ou identique pour tous, le dashboard global sera correct mais les tops “par client” et les filtres par tenant seront faux.

2. **vapi_call_usage.tenant_id**  
   Chaque ligne = un appel d’un tenant. Utilisé pour coût global, top coût par client, billing. Si absent ou erroné, le coût par client et le billing snapshot seront faux.

3. **tenant_billing**  
   Une ligne par tenant qui a (ou a eu) un abonnement Stripe. Les pages Operations / Billing s’appuient dessus pour past_due et infos Stripe. Vérifier que la création / mise à jour (webhook, création client) associe bien la bonne ligne au bon **tenant_id**.

4. **Tenants (liste)**  
   Vérifier que **tenants** (PG ou SQLite) contient bien tous les clients et que **USE_PG_TENANTS** + **PG_TENANTS_URL** (ou **DATABASE_URL**) sont cohérents en prod.

5. **Un seul “payload” dashboard**  
   `dashboard-payload` fait un seul appel et agrège tout côté backend. Pas de N+1 par tenant pour l’accueil. Les pages détaillées (fiche tenant, appels, operations, quality) font des appels ciblés (par tenant_id ou snapshot global).

---

## 4. Résumé des tables et variables d’environnement

| Donnée | Table(s) | Env (connexion) |
|--------|----------|------------------|
| Liste / détail tenants | tenants, tenant_config | USE_PG_TENANTS, PG_TENANTS_URL, DATABASE_URL |
| Appels, RDV, transferts, erreurs | ivr_events, call_sessions | PG_EVENTS_URL, DATABASE_URL |
| Coût Vapi, minutes | vapi_call_usage | PG_EVENTS_URL, DATABASE_URL |
| Billing Stripe, past_due | tenant_billing, tenants | PG_TENANTS_URL, DATABASE_URL |
| Leads | pre_onboarding_leads | PG_TENANTS_URL, DATABASE_URL (leads_pg) |
| Appointments (optionnel) | appointments | USE_PG_SLOTS, PG_SLOTS_URL, DATABASE_URL |

En prod (Railway), souvent **DATABASE_URL** unique pour tout ; en split possible : **PG_EVENTS_URL** (events + vapi_call_usage) et **PG_TENANTS_URL** (tenants, tenant_billing, leads).

---

## 5. Ce qui est déjà “multi-tenant safe”

- Dashboard : agrégats globaux + top par **client_id** / **tenant_id**.
- Liste appels : filtre **tenant_id** optionnel.
- Fiche tenant : tout est filtré par **tenant_id**.
- Billing snapshot : jointure **tenant_billing** ↔ **tenants**, listes past_due et top coût par **tenant_id**.
- Leads : indépendants des tenants (pas de mélange).

La condition pour que tout reste cohérent avec plusieurs clients est que **ivr_events** et **vapi_call_usage** soient bien remplis avec le bon **tenant_id** / **client_id** à la source (Vapi, engine, etc.).
