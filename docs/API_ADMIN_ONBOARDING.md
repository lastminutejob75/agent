# API Admin / Onboarding (uwiapp.com → agent)

API pour centraliser onboarding + dashboard admin (Vite SPA → FastAPI backend).

## Variables d'environnement

| Variable | Description |
|----------|-------------|
| `ADMIN_API_TOKEN` | Token Bearer pour protéger `/api/admin/*`. **Obligatoire** en prod. |
| `DATABASE_URL` | Postgres (tenants + ivr_events). Si absent, fallback SQLite. |

## Endpoints

### Public (sans auth)

#### `POST /api/public/onboarding`

Crée un tenant + config. Utilisé par le formulaire onboarding sur uwiapp.com.

**Body:**
```json
{
  "company_name": "Cabinet Dupont",
  "email": "contact@cabinet.fr",
  "calendar_provider": "google|none",
  "calendar_id": "xxx@group.calendar.google.com",
  "sector": "optionnel"
}
```

**Response:**
```json
{
  "tenant_id": 2,
  "message": "Onboarding créé. Vous pouvez configurer le tenant depuis l'admin.",
  "admin_setup_token": null
}
```

---

### Admin (Bearer `ADMIN_API_TOKEN`)

Toutes les routes `/api/admin/*` exigent :
```
Authorization: Bearer <ADMIN_API_TOKEN>
```

#### `GET /api/admin/tenants`

Liste des tenants.  
`?include_inactive=true` pour inclure les inactifs.

#### `GET /api/admin/tenants/{tenant_id}`

Détail tenant : flags, params, routing.

#### `PATCH /api/admin/tenants/{tenant_id}/flags`

Met à jour les flags (merge).  
Body: `{"flags": {"ENABLE_LLM_ASSIST_START": false}}`

#### `PATCH /api/admin/tenants/{tenant_id}/params`

Met à jour params (merge).  
Champs autorisés : `calendar_provider`, `calendar_id`, `contact_email`.

#### `POST /api/admin/routing`

Ajoute une route DID → tenant.  
Body: `{"channel": "vocal", "key": "+33123456789", "tenant_id": 1}`

#### `GET /api/admin/kpis/weekly`

KPIs hebdo.  
Params: `tenant_id`, `start` (YYYY-MM-DD), `end` (YYYY-MM-DD).

#### `GET /api/admin/rgpd`

RGPD : consent_obtained, consent_rate.  
Params: `tenant_id`, `start`, `end`.

---

#### `GET /api/admin/tenants/{tenant_id}/dashboard`

Snapshot dashboard pour un tenant.

**Response:**
```json
{
  "tenant_id": 12,
  "tenant_name": "Cabinet Dupont",
  "service_status": {
    "status": "online",
    "reason": null,
    "checked_at": "2026-02-12T18:20:00Z"
  },
  "last_call": {
    "call_id": "abc123",
    "created_at": "2026-02-12T17:55:10Z",
    "name": null,
    "motif": null,
    "slot_label": null,
    "outcome": "booking_confirmed"
  },
  "last_booking": {
    "created_at": "2026-02-12T17:55:40Z",
    "name": "Marie Martin",
    "slot_label": "2026-02-17 14:00",
    "source": "postgres"
  },
  "counters_7d": {
    "calls_total": 42,
    "bookings_confirmed": 14,
    "transfers": 9,
    "abandons": 3
  }
}
```

- `service_status`: online si dernier event < 15 min
- `last_call`: dernier call (7j), outcome prioritaire (booking_confirmed > transferred_human > user_abandon)
- `last_booking`: depuis appointments PG si dispo, sinon ivr_events
- `counters_7d`: agrégats ivr_events

---

## Front (uwi-landing)

- `VITE_UWI_API_BASE_URL` : URL de l'API agent (ex: `https://xxx.railway.app`)
- Token admin : saisi dans l'UI, stocké en localStorage (`uwi_admin_token`)
