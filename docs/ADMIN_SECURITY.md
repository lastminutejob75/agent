# Sécurisation admin panel (plan V1 → V2 → V3)

Référence pour la barrière admin sans casser le magic link client.

---

## Identification actuelle

| Contexte | Mécanisme | Usage |
|----------|-----------|--------|
| **Admin** | `Authorization: Bearer <ADMIN_API_TOKEN>` (header) | Toutes les routes `/api/admin/*`. Token partagé (env). |
| **Client** | Magic link → JWT en localStorage → `Authorization: Bearer <JWT>` | Routes `/api/tenant/*`, `/app`. |

Un client qui envoie son JWT sur une route admin reçoit **403 Forbidden** (pas 401), car le backend distingue "pas de token" (401) et "token présent mais pas admin" (403).

---

## Backend : require_admin()

- **Dépendance** : `require_admin` (alias `_verify_admin`) dans `backend/routes/admin.py`.
- **Codes** :
  - **503** : `ADMIN_API_TOKEN` non défini (config manquante).
  - **401** : pas de Bearer ou Bearer vide → "Missing admin credentials".
  - **403** : Bearer présent mais différent de `ADMIN_API_TOKEN` (ex. JWT client) → "Forbidden: admin access required".

Aucune route admin n’accepte le JWT client : seul le token admin ouvre l’accès.

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
8. Admin limité à une allowlist IP ou domaine dédié.
