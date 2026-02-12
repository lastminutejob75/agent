# API Auth Magic Link (P0)

Authentification client tenant via Magic Link + JWT.

## Variables d'environnement

| Variable | Description |
|----------|-------------|
| `JWT_SECRET` | Secret HMAC pour JWT (obligatoire) |
| `APP_BASE_URL` | URL base (ex: https://uwiapp.com) pour construire le lien |
| `POSTMARK_SERVER_TOKEN` | Token Postmark pour envoi email |
| `POSTMARK_FROM_EMAIL` | Email expéditeur (ou `EMAIL_FROM`) |
| `MAGICLINK_TTL_MINUTES` | TTL du lien (défaut: 15) |
| `ENABLE_MAGICLINK_DEBUG` | Si `true`, renvoie `debug_login_url` dans la réponse |

## Endpoints

### `POST /api/auth/request-link`

Demande un magic link. **Toujours 200** (anti user enumeration).

**Body:** `{ "email": "user@example.com" }`

**Réponse:** `{ "ok": true }`  
Si `ENABLE_MAGICLINK_DEBUG=true`: `{ "ok": true, "debug_login_url": "https://..." }`

### `GET /api/auth/verify?token=...`

Vérifie le token magic link, marque used, retourne JWT.

**Réponse:** `{ "access_token": "...", "tenant_id": 1, "tenant_name": "...", "email": "...", "expires_in": 604800 }`

Erreurs: 400 (token invalide/expiré), 503 (JWT_SECRET manquant).

## Endpoints tenant (protégés JWT)

Header: `Authorization: Bearer <access_token>`

| Endpoint | Description |
|----------|-------------|
| `GET /api/tenant/me` | Profil (tenant_id, tenant_name, email, role) |
| `GET /api/tenant/dashboard` | Snapshot dashboard |
| `GET /api/tenant/technical-status` | Statut DID, routing, calendar |
| `PATCH /api/tenant/params` | Met à jour params (whitelist) |

## Tables Postgres

- `tenant_users` : (tenant_id, email UNIQUE, role)
- `magic_links` : (token_hash PK, tenant_id, email, expires_at, used_at)

**Exécution via CLI :**
```bash
# Railway (DATABASE_URL injecté automatiquement)
railway run make migrate

# Ou directement
railway run python3 scripts/run_migration.py 007

# Local (DATABASE_URL ou PG_TENANTS_URL dans .env)
make migrate
```

## Flux

1. Onboarding crée `tenant_users` avec `contact_email` (owner)
2. Client va sur `/login`, entre son email
3. `POST /api/auth/request-link` → si email connu: crée token, envoie email Postmark
4. Client clique le lien → `GET /api/auth/verify?token=...` → JWT
5. Front stocke JWT dans `localStorage` (`uwi_tenant_token`)
6. Appels `/api/tenant/*` avec `Authorization: Bearer <JWT>`
