# Sécurisation admin panel (plan V1 → V2 → V3)

Référence pour la barrière admin sans casser le magic link client.

---

## Identification actuelle

| Contexte | Mécanisme | Usage |
|----------|-----------|--------|
| **Admin** | `Authorization: Bearer <ADMIN_API_TOKEN>` (header) | Toutes les routes `/api/admin/*`. Token partagé (env). |
| **Client** | Magic link → JWT en localStorage → `Authorization: Bearer <JWT>` | Routes `/api/tenant/*`, `/app`. |

---

## Matrice HTTP (version clean standard)

| Code | Cas |
|------|-----|
| **401 Unauthorized** | Bearer manquant ; Bearer présent mais token invalide / expiré |
| **403 Forbidden** | Token valide, user authentifié, mais role ≠ admin |

Séparation nette : l’auth (qui es-tu ?) → 401 ; l’authz (as-tu le droit ?) → 403.

**Structure cible** (quand admin = users avec rôle) :
- `get_current_user()` : token absent → 401, token invalide/expiré → 401, sinon retourne User.
- `require_admin(user: User = Depends(get_current_user))` : si pas user → 401, si pas user.is_admin → 403, sinon return user.

Aujourd’hui : un seul token admin (ADMIN_API_TOKEN) → tout ce qui n’est pas ce token donne 401 ; 403 réservé pour plus tard.

---

## Backend : require_admin()

- **Dépendance** : `require_admin` (alias `_verify_admin`) dans `backend/routes/admin.py`.
- **Codes** :
  - **503** : aucun token admin configuré (`ADMIN_API_TOKEN` ou `ADMIN_API_TOKENS`).
  - **401** : Bearer manquant, vide, ou token invalide/expiré.
  - **403** : réservé pour usage futur (token valide mais role ≠ admin).
- **Rotation** : `ADMIN_API_TOKENS=tok1,tok2` permet plusieurs tokens valides en parallèle (sans coupure pendant la rotation).
- **Audit** : chaque accès admin est loggé (path, client IP, user-agent, `token_fp` = 8 premiers caractères du sha256 du token). Le Bearer n'est jamais loggé en clair ; l'empreinte permet de diagnostiquer une fuite sans exposer le secret.
- **CORS** : refuser `/api/admin/*` si l'en-tête `Origin` est présente et non autorisée. Les appels sans `Origin` (curl, Postman, serveur-à-serveur) passent → OK, protégés par `require_admin()`. Option plus stricte : exiger `Origin` uniquement quand la requête vient du navigateur (ex. `Sec-Fetch-Site`).
- **Allowlist IP** (optionnel) : si `ADMIN_ALLOWED_IPS` est implémentée, n'utiliser **X-Forwarded-For** (première IP) **que si `TRUST_PROXY=true`** (env), sinon risque de spoof ; sinon utiliser `request.client.host`.

Aucune route admin n’accepte le JWT client : seuls les tokens admin ouvrent l’accès.

**Tests (triple verrou)** : `test_admin_tenants_401_without_token` (401 sans token), `test_admin_tenants_401_with_invalid_token` (401 token invalide), `test_admin_tenants_with_token` (200 avec token admin). Un test 403 sera ajouté quand "token valide mais non-admin" existera (get_current_user + role).

---

## V1 — Sécurité minimale (actuel + à consolider)

1. **Admin only** : toutes les routes `/api/admin/*` utilisent `Depends(require_admin)` → 401/403 comme ci-dessus.
2. **Pas d’auto-promotion** : les clients (JWT tenant) ne peuvent pas créer de tenants ni modifier le routing ; seules les routes admin le peuvent, protégées par le token admin.
3. **Cookies** : admin utilise un Bearer en header (token en localStorage côté front). Pour le client (magic link), si passage en cookie plus tard : HttpOnly, Secure, SameSite=Lax (ou Strict).

---

## V1.5 — Anti-abus (à ajouter)

4. **Rate limiting** sur endpoints sensibles : `/api/admin/tenants`, `/api/admin/routing`, `/api/auth/request-link` (ex. par IP + par user).
5. **Idempotency key** (optionnel) : `POST /api/admin/tenants` avec clé pour éviter double création (double-clic / retry).

---

## V2 — Traçabilité

6. **Audit log** : table `admin_audit_log` (actor_user_id, actor_email, action, target_tenant_id, payload_json, created_at, ip, user_agent). Affichage dans `/admin/audit` plus tard.

---

## V3 — Enterprise (optionnel)

7. 2FA admin (TOTP / passkey).
8. Admin limité à une allowlist IP ou domaine dédié (voir `ADMIN_ALLOWED_IPS` dans `docs/AUTH_V2_ADMIN_USERS.md`).

---

## Auth admin par utilisateur (spec)

Voir **`docs/AUTH_V2_ADMIN_USERS.md`** : admin en magic link, JWT en cookie HttpOnly, `require_admin()` → 403 si non admin, migration en 2 étapes avec legacy `ADMIN_API_TOKENS` puis retrait.
