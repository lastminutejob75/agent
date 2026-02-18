# Sources pour les stats admin (dashboard global)

**En production (Railway)** : toutes les tables sont en **Postgres** (ivr_events, call_sessions, tenants, appointments). Les endpoints `/api/admin/stats/*` interrogent Postgres en priorité ; le fallback SQLite ne sert qu’en dev local si PG n’est pas configuré.

**Convention client_id = tenant_id** : dans `ivr_events` la colonne s’appelle `client_id` mais elle contient le **tenant_id** (même entité). Le code stats utilise un résolver `_ivr_client_id(tenant_id)` pour centraliser cette convention (évolution future possible : migration `client_id` → `tenant_id` ou vue SQL).

**Minutes** : approximation `updated_at - started_at` (call_sessions), **clamp ≥ 0** et **plafond 6h par session** pour éviter les outliers (sessions ouvertes / bug).

## Réponses aux 2 points

### 1) Durée d’appel

- **Il n’y a pas** de champ `duration_sec` ni `duration_ms` dans `call_sessions` ni dans `ivr_events`.
- **call_sessions** (PG) a : `started_at`, `updated_at`. On peut approcher une durée par `EXTRACT(EPOCH FROM (updated_at - started_at))` (temps entre début et dernière mise à jour), mais ce n’est pas une “durée d’appel” fiable (session peut rester ouverte).
- **Rapports** : la table `interactions` (reports) a `duration_ms`, mais c’est un autre flux.
- **Conclusion** : pour la V1 du dashboard global, **minutes_total** est dérivé de `call_sessions` (PG) quand dispo : `SUM(EXTRACT(EPOCH FROM (updated_at - started_at))/60)` sur la fenêtre, sinon **0** (ou on n’expose pas la métrique tant qu’on ne persiste pas une vraie durée de fin d’appel).

### 2) Abandon / answered / transferred

- Tout est dérivé des **ivr_events** via le champ **event** (pas de statut “answered” explicite dans call_sessions pour l’agrégat global).
- **Convention** :
  - **transfers** : `event IN ('transfer', 'transferred', 'transfer_human', 'transferred_human')`
  - **abandons** : `event IN ('abandon', 'hangup', 'user_hangup', 'user_abandon')`
  - **bookings (RDV)** : `event = 'booking_confirmed'`
  - **calls_total** : `COUNT(DISTINCT call_id)` dans ivr_events (call_id non vide)
- **call_sessions** a `last_state` (ex. TRANSFERRED, CONFIRMED) et `status` ('active') ; utile pour détail par call, pas pour les agrégats globaux cross-tenant (les agrégats existants utilisent ivr_events avec `client_id` = tenant_id).

## Tables utilisées (Postgres sur Railway)

| Table | Rôle |
|-------|------|
| **ivr_events** | client_id (= tenant_id), call_id, event, created_at → calls_total, transfers, abandons, bookings, timeseries |
| **call_sessions** | tenant_id, call_id, started_at, updated_at → minutes_total (approximation) |
| **tenants** | tenants_total, tenants_active (status = 'active') |
| **appointments** | appointments_total (si USE_PG_SLOTS) |

Variables d’environnement Railway : `DATABASE_URL` (ou `PG_EVENTS_URL` pour ivr_events), `PG_SLOTS_URL` pour appointments si distinct.

## Drill-down tenant (dashboard détaillé)

Mêmes sources (Postgres en priorité), filtrées par `client_id` (ivr_events) et `tenant_id` (call_sessions) :

- **GET /api/admin/stats/tenants/{tenant_id}?window_days=7|30** : KPIs (calls_total, calls_abandoned, calls_answered = total − abandoned, minutes_total, appointments_total, transfers_total, errors_total, last_activity_at).
- **GET /api/admin/stats/tenants/{tenant_id}/timeseries?metric=calls|appointments|minutes&days=** : série par jour, même shape que le global.
- **GET /api/admin/tenants/{tenant_id}/activity?limit=50** : timeline des derniers events (date, call_id, event, meta) pour “preuve physique”.
