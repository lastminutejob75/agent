# Checklist mise en service Auth P0 (Magic Link + JWT)

Ordre exact, sans downtime.

---

## Go-live prod (checklist courte)

### 1) Railway Postgres

Appliquer la migration 007 (pas en dry-run) :

```bash
make migrate-railway
```

Vérifier :

```sql
SELECT COUNT(*) FROM tenant_users;
SELECT COUNT(*) FROM magic_links;
```

### 2) Variables Railway (obligatoires)

| Variable | Valeur |
|----------|--------|
| `JWT_SECRET` | 32+ chars random |
| `APP_BASE_URL` | `https://uwiapp.com` |
| `POSTMARK_SERVER_TOKEN` | Token Postmark |
| `POSTMARK_FROM_EMAIL` | Sender validé Postmark |

Puis redeploy backend.

### 3) Vercel env var

`VITE_UWI_API_BASE_URL=https://<backend-railway>.railway.app`

Redeploy front.

---

## Tests prod indispensables (5 min)

**A) Email Postmark**

- Va sur `/login`
- Mets un email présent dans `tenant_users`
- Vérifie : email reçu, lien fonctionne, `/app` charge

Si l'email n'arrive pas : sender non validé, From incorrect, token mauvais, spam/policy.

**B) CORS**

Console navigateur : pas de "CORS blocked", "Mixed content", 401 sur `/api/tenant/*` avec token stocké.

---

## 1. Migration Postgres (détail)

Exécuter en ordre :

```bash
# 007 : tenant_users + magic_links
make migrate-railway
# ou : railway run python3 scripts/run_migration.py 007

# 008 : auth_events (audit RGPD)
railway run python3 scripts/run_migration.py 008
```

Vérifier :

```sql
SELECT COUNT(*) FROM tenant_users;
SELECT COUNT(*) FROM magic_links;
SELECT COUNT(*) FROM auth_events;
```

---

## 2. Variables Railway (backend)

| Variable | Obligatoire | Description |
|----------|-------------|-------------|
| `JWT_SECRET` | ✅ | 32+ chars random |
| `APP_BASE_URL` | ✅ | `https://uwiapp.com` |
| `POSTMARK_SERVER_TOKEN` | ✅ | Token Postmark |
| `POSTMARK_FROM_EMAIL` | ✅ | Sender validé Postmark |
| `MAGICLINK_TTL_MINUTES` | | Défaut 15 |
| `ENABLE_MAGICLINK_DEBUG` | | `true` = renvoie debug_login_url (dev only) |
| `CORS_ORIGINS` | | Défaut `https://uwiapp.com,https://www.uwiapp.com` |

Redéployer le backend après modification.

---

## 3. Front Vercel

| Variable | Description |
|----------|-------------|
| `VITE_UWI_API_BASE_URL` | `https://<backend-railway>.railway.app` (sans /api) |

Redéployer la landing.

---

## 4. Onboarding anciens clients (P0)

Tenants créés *avant* la migration 007 n'ont pas de `tenant_user`.

**Option 1 — SQL direct** (le plus rapide) :

```sql
INSERT INTO tenant_users (tenant_id, email, role)
VALUES (12, 'contact@client.com', 'owner')
ON CONFLICT (email) DO NOTHING;
```

Répéter une ligne par client.

**Option 2 — Script Python** (depuis contact_email dans tenant_config) :

```sql
INSERT INTO tenant_users (tenant_id, email, role)
SELECT t.tenant_id, (tc.params_json->>'contact_email'), 'owner'
FROM tenants t
JOIN tenant_config tc ON tc.tenant_id = t.tenant_id
WHERE tc.params_json->>'contact_email' IS NOT NULL
  AND (tc.params_json->>'contact_email') != ''
ON CONFLICT (email) DO NOTHING;
```

**Option 3 — Endpoint admin** (POST /api/admin/tenants/{id}/users) :

```bash
curl -X POST "https://<backend>/api/admin/tenants/12/users" \
  -H "Authorization: Bearer $ADMIN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email":"contact@client.com","role":"owner"}'
```

Idempotent (même tenant → 200). 409 si email déjà sur un autre tenant.

**Option 4 — Backfill Python** :

```bash
make backfill-tenant-users
# ou
railway run python3 scripts/backfill_tenant_users.py
```

---

## 9. Endpoint admin add user

`POST /api/admin/tenants/{tenant_id}/users` avec Bearer ADMIN_API_TOKEN.

Body : `{ "email": "contact@client.com", "role": "owner" }` (role ∈ owner|member).

Réponse : `{ "ok": true, "tenant_id": 12, "email": "...", "role": "owner", "created": true }`

- Idempotent : email déjà sur ce tenant → 200, `created: false`
- 409 : email déjà sur un autre tenant

---

## 5. Tests prod (10 min)

| Test | Attendu |
|------|---------|
| `/login` avec email existant | Email reçu (Postmark) |
| Clic lien → `/auth/callback` | Redirection `/app` |
| `/app/settings` : change `calendar_provider` | Valeur persistée après reload |
| `/login` avec email inconnu | Message neutre, aucun leak |

### A) Email Postmark

Si l'email n'arrive pas : sender non validé, From incorrect, token mauvais, spam.

### B) CORS

Console navigateur : pas de "CORS blocked", "Mixed content", ni 401 sur `/api/tenant/*` avec token stocké.

---

## 6. Hardening (déjà en place)

- **Rate limit** : 5 req/min par IP+email sur `POST /api/auth/request-link`
- **Audit events** : `auth_magic_link_requested`, `_sent`, `_verified`, `_failed`, `auth_rate_limited` dans `auth_events`
- **Message anti-enumération** : "Si un compte existe pour cet email, vous recevrez un lien de connexion."

---

## 7. CORS

Backend accepte `https://uwiapp.com`, `https://www.uwiapp.com`, `http://localhost:5173`.

CORS_ORIGINS peut être surchargé si besoin.

---

## 8. RGPD côté client (/app/rgpd)

Une fois connecté, le client accède à `/app/rgpd` :

- **consent_rate 7j** : taux de consentement sur les 7 derniers jours
- **Derniers consent_obtained** : call_id, date, version (affiche "v1" si format `2026-02-12_v1`)

Données issues de `ivr_events` (event = `consent_obtained`).  
Endpoint : `GET /api/tenant/rgpd` (protégé JWT).

### Version consentement (P1)

`config.CONSENT_VERSION = "2026-02-12_v1"`  
Context persisté : `{"consent_version": "2026-02-12_v1", "channel": "vocal"}`  
Persisté au premier message utilisateur vocal (consentement implicite).

### Idempotence consent_obtained

1 seul `consent_obtained` par call_id (évite doublons sur retry webhook).  
Check `consent_obtained_exists(client_id, call_id)` avant insert.
