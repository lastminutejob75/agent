# Setup UWI — Dashboard Admin connecté aux données et Vapi

Document de référence pour construire un dashboard admin connecté au backend UWI et aux données Vapi.

---

## 1. Architecture

```
┌─────────────────┐     HTTPS      ┌──────────────────────┐     Postgres
│  Dashboard      │ ──────────────▶│  Backend FastAPI     │ ◀─────────────
│  (React/Vite)   │   /api/admin/* │  (Railway)           │   DATABASE_URL
└─────────────────┘                └──────────────────────┘
         │                                    │
         │                                    │ Webhook
         │                                    ▼
         │                           ┌──────────────────────┐
         │                           │  Vapi (voice AI)     │
         │                           │  status-update,      │
         │                           │  transcript,         │
         │                           │  end-of-call-report  │
         │                           └──────────────────────┘
         │
         └── VITE_UWI_API_BASE_URL = https://xxx.up.railway.app
```

---

## 2. Variables d'environnement

### Backend (Railway)

| Variable | Obligatoire | Description |
|----------|-------------|-------------|
| `DATABASE_URL` | Oui | Postgres (tenants, events, billing, vapi_call_usage) |
| `PG_TENANTS_URL` | Non | Fallback si différent de DATABASE_URL |
| `PG_EVENTS_URL` | Non | Fallback pour ivr_events, vapi_calls |
| `PG_SLOTS_URL` | Non | Fallback pour slots/appointments |
| `ADMIN_API_TOKEN` | Oui* | Token Bearer pour auth admin (legacy) |
| `ADMIN_EMAIL` | Oui* | Email admin (login cookie) |
| `ADMIN_PASSWORD_HASH` | Oui* | bcrypt hash du mot de passe |
| `JWT_SECRET` | Oui | Secret pour JWT session admin |
| `CORS_ORIGINS` | Oui | Origines autorisées (ex: `https://www.uwiapp.com,http://localhost:5173`) |
| `ADMIN_CORS_ORIGINS` | Non | Liste stricte pour /api/admin/* (sinon = CORS_ORIGINS) |
| `VAPI_PUBLIC_BACKEND_URL` | Oui | URL backend pour webhook Vapi (ex: https://xxx.railway.app) |
| `VAPI_ASSISTANT_ID` | Non | ID assistant Vapi (optionnel) |

*Au moins `ADMIN_API_TOKEN` OU (`ADMIN_EMAIL` + `ADMIN_PASSWORD_HASH`)

### Frontend (Vercel / .env)

| Variable | Obligatoire | Description |
|----------|-------------|-------------|
| `VITE_UWI_API_BASE_URL` | Oui | URL du backend (ex: `https://xxx.up.railway.app`) |
| `VITE_SITE_URL` | Non | URL du site (ex: `https://www.uwiapp.com`) |

---

## 3. Authentification Admin

Deux méthodes :

1. **Bearer token** : `Authorization: Bearer <ADMIN_API_TOKEN>`
   - Stocker dans `localStorage.uwi_admin_token`
   - Utilisé par le client adminApi

2. **Cookie session** : login email/mot de passe → cookie `uwi_admin_session` (JWT)
   - `POST /api/admin/auth/login` avec `{ email, password }`
   - `GET /api/admin/auth/me` pour vérifier la session

Toutes les requêtes admin doivent inclure :
- Soit `Authorization: Bearer <token>`
- Soit le cookie `uwi_admin_session` (avec `credentials: "include"`)

---

## 4. API Admin — Endpoints principaux

Base URL : `{VITE_UWI_API_BASE_URL}`

### Auth
| Méthode | Path | Description |
|---------|------|--------------|
| POST | `/api/admin/auth/login` | `{ email, password }` → cookie |
| GET | `/api/admin/auth/me` | Vérifie session / token |
| POST | `/api/admin/auth/logout` | Déconnexion |

### Tenants (clients)
| Méthode | Path | Description |
|---------|------|-------------|
| GET | `/api/admin/tenants` | Liste tous les tenants |
| GET | `/api/admin/tenants/{id}` | Détail tenant (flags, params, routing) |
| GET | `/api/admin/tenants/{id}/dashboard` | Snapshot dashboard (service_status, last_call, last_booking, counters_7d) |
| GET | `/api/admin/tenants/{id}/activity` | Timeline events (limit) |
| PATCH | `/api/admin/tenants/{id}/flags` | `{ flags: { ENABLE_LLM_ASSIST_START: true } }` |
| PATCH | `/api/admin/tenants/{id}/params` | `{ params: { calendar_id: "..." } }` |

### Stats globales (dashboard principal)
| Méthode | Path | Description |
|---------|------|-------------|
| GET | `/api/admin/stats/dashboard-payload?window_days=30` | **Payload unique** : global + timeseries + topTenantsCalls + topTenantsCost + billing |
| GET | `/api/admin/stats/global?window_days=30` | KPIs globaux |
| GET | `/api/admin/stats/timeseries?metric=calls&days=30` | Série temporelle |
| GET | `/api/admin/stats/top-tenants?metric=calls&window_days=30&limit=10` | Top tenants |
| GET | `/api/admin/stats/billing-snapshot` | Coût Vapi ce mois, tenants past_due |

### Stats par tenant
| Méthode | Path | Description |
|---------|------|-------------|
| GET | `/api/admin/stats/tenants/{id}?window_days=7` | KPIs tenant (calls, abandons, RDV, transferts, minutes) |
| GET | `/api/admin/stats/tenants/{id}/timeseries?metric=calls&days=7` | Série temporelle tenant |

### Appels (Vapi)
| Méthode | Path | Description |
|---------|------|-------------|
| GET | `/api/admin/calls?tenant_id=&days=7&limit=50&result=` | Liste appels (result=rdv\|transfer\|abandoned\|error) |
| GET | `/api/admin/tenants/{id}/calls/{call_id}` | Détail appel (events, duration, result) |

### Billing / Stripe
| Méthode | Path | Description |
|---------|------|-------------|
| GET | `/api/admin/tenants/{id}/billing` | Stripe customer, subscription |
| GET | `/api/admin/tenants/{id}/usage?month=2026-02` | Usage Vapi (minutes, cost_usd) |
| GET | `/api/admin/tenants/{id}/quota?month=2026-02` | Quota (used, included, remaining) |
| GET | `/api/admin/billing/plans` | Plans (free, starter, growth, pro) |

---

## 5. Structures de données

### dashboard-payload (GET /api/admin/stats/dashboard-payload)
```json
{
  "global": {
    "calls_total": 42,
    "appointments_total": 12,
    "transfers_total": 5,
    "tenants_active": 3,
    "tenants_total": 3,
    "cost_usd_total": 12.50,
    "minutes_total": 120,
    "errors_total": 0,
    "last_activity_at": "2026-02-23T14:30:00Z"
  },
  "timeseries": {
    "metric": "calls",
    "days": 30,
    "points": [{"date": "2026-02-01", "value": 5}, ...]
  },
  "topTenantsCalls": {
    "metric": "calls",
    "window_days": 30,
    "items": [{"tenant_id": 1, "name": "Cabinet Dupont", "value": 25}, ...]
  },
  "topTenantsCost": {
    "metric": "cost_usd",
    "items": [{"tenant_id": 1, "name": "Cabinet Dupont", "value": 8.50}, ...]
  },
  "billing": {
    "cost_usd_this_month": 45.20,
    "top_tenants_by_cost_this_month": [{"tenant_id": 1, "name": "...", "value": 20.5}],
    "tenants_past_due_count": 0,
    "tenants_past_due": [],
    "tenant_ids_past_due": []
  }
}
```

### Tenant dashboard (GET /api/admin/tenants/{id}/dashboard)
```json
{
  "tenant_id": 1,
  "tenant_name": "Cabinet Dupont",
  "service_status": {"status": "online", "reason": null, "checked_at": "..."},
  "last_call": {
    "call_id": "vapi_xxx",
    "created_at": "...",
    "outcome": "booking_confirmed",
    "name": null,
    "motif": null,
    "slot_label": null
  },
  "last_booking": {
    "created_at": "...",
    "name": "Jean Dupont",
    "slot_label": "2026-02-23 10:00",
    "source": "postgres"
  },
  "counters_7d": {
    "calls_total": 15,
    "bookings_confirmed": 4,
    "transfers": 2,
    "abandons": 1
  },
  "transfer_reasons": {
    "top_transferred": [{"reason": "hors_sujet", "count": 3}],
    "top_prevented": []
  }
}
```

### Liste appels (GET /api/admin/calls)
```json
{
  "items": [
    {
      "call_id": "vapi_xxx",
      "tenant_id": 1,
      "tenant_name": "Cabinet Dupont",
      "started_at": "2026-02-23T10:00:00Z",
      "last_event_at": "2026-02-23T10:05:30Z",
      "duration_min": 5,
      "result": "booking_confirmed",
      "outcome": "booking_confirmed"
    }
  ],
  "next_cursor": "base64...",
  "days": 7
}
```

### Détail appel (GET /api/admin/tenants/{id}/calls/{call_id})
```json
{
  "call_id": "vapi_xxx",
  "tenant_id": 1,
  "started_at": "2026-02-23T10:00:00Z",
  "last_event_at": "2026-02-23T10:05:30Z",
  "duration_min": 5,
  "result": "booking_confirmed",
  "events": [
    {"created_at": "...", "event": "booking_confirmed", "meta": null}
  ]
}
```

---

## 6. Tables Postgres (données Vapi)

| Table | Description |
|-------|-------------|
| `ivr_events` | Events conversationnels (client_id=tenant_id, call_id, event, created_at) |
| `vapi_calls` | Cycle de vie appel (status: ringing, in-progress, ended) — webhook status-update |
| `call_transcripts` | Transcription (role, transcript, is_final) — webhook transcript |
| `vapi_call_usage` | Durée + coût par appel — webhook end-of-call-report |
| `call_sessions` | Sessions vocales (tenant_id, call_id, started_at, updated_at) |
| `tenants` | Clients (tenant_id, name, timezone, status) |
| `tenant_config` | flags_json, params_json |
| `tenant_routing` | DID → tenant_id (channel, key, tenant_id) |
| `tenant_billing` | Stripe (stripe_customer_id, stripe_metered_item_id, billing_status) |

### Events ivr_events (exemples)
- `booking_confirmed` — RDV confirmé
- `transferred_human`, `transferred` — Transfert
- `user_abandon`, `abandon` — Abandon
- `anti_loop_trigger` — Erreur / boucle

---

## 7. Client API (frontend)

```javascript
// adminApi.js — pattern
const base = import.meta.env.VITE_UWI_API_BASE_URL;
const token = localStorage.getItem("uwi_admin_token") || "";

const res = await fetch(`${base}/api/admin/stats/dashboard-payload?window_days=30`, {
  method: "GET",
  headers: {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  },
  credentials: "include", // cookie
});
const data = await res.json();
if (!res.ok) throw new Error(data.detail || "Request failed");
```

---

## 8. CORS

Le backend refuse `/api/admin/*` si `Origin` est présente et non autorisée.

- **CORS_ORIGINS** : liste séparée par virgules (ex: `https://www.uwiapp.com,http://localhost:5173`)
- **ADMIN_CORS_ORIGINS** : override pour admin (optionnel)

Erreur 403 "Origin not allowed" → ajouter l’URL du front dans CORS_ORIGINS sur Railway.

---

## 9. Vapi Webhook

Le backend reçoit les webhooks Vapi sur `POST /api/vapi/webhook`.

Types de messages persistés :
- **status-update** → `vapi_calls` (ringing, in-progress, ended)
- **transcript** → `call_transcripts`
- **end-of-call-report** → `vapi_call_usage` (duration_sec, cost_usd)

Configurer dans Vapi Dashboard :
- Server URL = `{VAPI_PUBLIC_BACKEND_URL}/api/vapi/webhook`

---

## 10. Fichiers de référence

| Fichier | Rôle |
|---------|------|
| `landing/src/lib/adminApi.js` | Client API admin (méthodes) |
| `landing/src/admin/pages/AdminDashboard.jsx` | Dashboard global |
| `landing/src/admin/pages/AdminTenantDashboard.jsx` | Dashboard par tenant |
| `backend/routes/admin.py` | Routes admin |
| `backend/vapi_calls_pg.py` | Persistance vapi_calls, call_transcripts |
| `migrations/009_vapi_call_usage.sql` | Schéma vapi_call_usage |
| `migrations/028_vapi_calls_and_transcripts.sql` | Schéma vapi_calls, call_transcripts |

---

## 11. Checklist déploiement

- [ ] `DATABASE_URL` configuré (Postgres Railway)
- [ ] Migrations exécutées (001 à 030)
- [ ] `ADMIN_API_TOKEN` ou `ADMIN_EMAIL` + `ADMIN_PASSWORD_HASH`
- [ ] `JWT_SECRET` défini
- [ ] `CORS_ORIGINS` inclut l’URL du front
- [ ] `VAPI_PUBLIC_BACKEND_URL` = URL backend (webhook Vapi)
- [ ] Front : `VITE_UWI_API_BASE_URL` = URL backend
