# Vérification Admin : Operations & Quality

Ce document décrit les données affichées, les sources backend et les points à contrôler pour les pages **Operations** et **Quality** du dashboard admin.

---

## 1. Operations (`/admin/operations`)

### 1.1 Endpoint

- **GET** `/api/admin/stats/operations-snapshot?window_days=7` (7, 14 ou 30 selon le select front).

### 1.2 Blocs affichés et sources

| Bloc | Données front | Source backend | Tables |
|------|----------------|----------------|--------|
| **À risque paiement** | Coût Vapi ce mois (UTC), liste tenants past_due | `_get_billing_snapshot()` + `month_utc` | `vapi_call_usage` (SUM cost_usd ce mois), `tenant_billing` + `tenants` (billing_status IN ('past_due','unpaid')) |
| **Quota risk** | Tenants à 80%+ et 100%+ d’usage ce mois | Quota risk dans `_get_operations_snapshot()` | `vapi_call_usage` (SUM duration_sec/60 par tenant), `tenant_billing` / params pour `included_minutes` (plan_key) |
| **Suspendus** | Liste clients suspendus, boutons Lever / Forcer actif 7j | Suspensions dans snapshot | `tenant_billing` JOIN `tenants` WHERE is_suspended = TRUE |
| **Top coût** | Aujourd’hui UTC, 7 derniers jours, ce mois | Cost today/7d + billing | `vapi_call_usage` (ended_at, cost_usd), groupé par tenant_id |
| **Erreurs** | Top 10 tenants par nombre d’erreurs sur N j, total | Errors dans snapshot | `ivr_events` WHERE event = 'anti_loop_trigger', GROUP BY client_id |

### 1.3 Contrat API (réponse JSON)

- `generated_at` : timestamp UTC.
- `billing` : `cost_usd_this_month`, `month_utc`, `tenants_past_due` (tenant_id, name, billing_status, current_period_end), `top_tenants_by_cost_this_month`.
- `suspensions` : `suspended_total`, `items[]` (tenant_id, name, reason, mode, suspended_at, force_active_until).
- `cost` : `today_utc` (date_utc, total_usd, top[]), `last_7d` (window_days, total_usd, top[]). Chaque `top[]` : tenant_id, name, value (USD).
- `errors` : `window_days`, `top_tenants[]` (tenant_id, name, errors_total, last_error_at), `errors_total`.
- `quota` : `month_utc`, `over_80[]`, `over_100[]` (tenant_id, name, used_minutes, included_minutes, usage_pct).

### 1.4 Vérifications à faire

1. **Billing** : `DATABASE_URL` ou `PG_TENANTS_URL` + `PG_EVENTS_URL` pointent bien la base qui a `tenant_billing`, `tenants`, `vapi_call_usage`.
2. **Suspensions** : colonnes `tenant_billing.is_suspended`, `suspension_reason`, `suspension_mode`, `suspended_at`, `force_active_until` (migrations 013, 014).
3. **Coût** : `vapi_call_usage.ended_at` et `cost_usd` renseignés (webhook Vapi end-of-call).
4. **Quota** : `vapi_call_usage.duration_sec` et `tenant_id` renseignés ; plan / included_minutes cohérents (billing_plans ou params tenant).
5. **Erreurs** : `ivr_events.event = 'anti_loop_trigger'` et `client_id` (= tenant_id) renseigné pour que le top par client soit correct.

### 1.5 Actions front (POST)

- **Lever suspension** : `POST /api/admin/tenants/{id}/unsuspend`
- **Forcer actif 7 j** : `POST /api/admin/tenants/{id}/force-active` (body attendu selon route).

---

## 2. Quality (`/admin/quality`)

### 2.1 Endpoint

- **GET** `/api/admin/stats/quality-snapshot?window_days=7` (7, 14 ou 30).

### 2.2 Blocs affichés et sources

| Bloc | Données front | Source backend | Tables |
|------|----------------|----------------|--------|
| **KPIs globaux** | Appels, Abandons, Transferts, Anti-loop, RDV confirmés, Taux abandon | `_get_quality_snapshot()` | `ivr_events` : COUNT(DISTINCT call_id), puis COUNT par event |
| **Top 10 · Anti-loop** | Par client, count, dernier incident, lien « Voir appels » | idem | `ivr_events` WHERE event = 'anti_loop_trigger', GROUP BY client_id |
| **Top 10 · Abandons** | idem | idem | event IN ('user_abandon','abandon','hangup','user_hangup') |
| **Top 10 · Transferts** | idem | idem | event IN ('transferred_human','transferred','transfer_human','transfer') |

Mapping events → KPIs :

- **Abandons** : user_abandon, abandon, hangup, user_hangup.
- **Transferts** : transferred_human, transferred, transfer_human, transfer.
- **Anti-loop** : anti_loop_trigger.
- **RDV confirmés** : booking_confirmed.
- **Taux abandon** : abandons / calls_total * 100.

### 2.3 Contrat API

- `window_days`, `generated_at`.
- `kpis` : calls_total, abandons, transfers, anti_loop, appointments, abandon_rate_pct.
- `top` : anti_loop[], abandons[], transfers[] — chaque item : tenant_id, name, count, last_at.

### 2.4 Lien « Voir appels »

- Anti-loop → `/admin/calls?tenant_id=X&result=error&days=N` (backend : result=error ⇒ last_event = 'anti_loop_trigger').
- Abandons → `result=abandoned`.
- Transferts → `result=transfer`.

### 2.5 Vérifications à faire

1. **ivr_events** : `call_id`, `event`, `client_id`, `created_at` présents. `client_id` = tenant_id pour le top par client.
2. **Cohérence events** : les noms d’events (anti_loop_trigger, booking_confirmed, etc.) correspondent bien à ce que le pipeline vocal écrit.
3. Les lignes avec `client_id` NULL sont ignorées dans les tops (pas de « Tenant #None »).

---

## 3. Résumé des tables et env

| Donnée | Table(s) | Connexion (env) |
|--------|----------|------------------|
| Billing, past_due, suspensions | tenant_billing, tenants | DATABASE_URL / PG_TENANTS_URL |
| Coût, quota (minutes) | vapi_call_usage | DATABASE_URL / PG_EVENTS_URL |
| Erreurs, Quality KPIs, tops | ivr_events | DATABASE_URL / PG_EVENTS_URL |

En prod souvent une seule `DATABASE_URL` pour tout.

---

## 4. Modifs récentes (vérif code)

- **Operations / Quality** : les lignes avec `client_id` (tenant_id) NULL sont exclues des tops (errors et quality top), pour ne pas afficher « Tenant #None ».
