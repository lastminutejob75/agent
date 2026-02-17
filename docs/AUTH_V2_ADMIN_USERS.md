# Auth V2 — Admin par utilisateur (spec)

Spec courte pour passer de l’auth admin par token partagé à l’auth admin par utilisateur (magic link + JWT), calée sur la stack actuelle : **FastAPI, Postgres, magic link**.

---

## Choix par défaut

- **Admin login** : magic link (même flux que les clients).
- **JWT** : en cookie **HttpOnly, Secure, SameSite=Lax** (meilleur UX, moins de fuite via JS).
- **require_admin()** : 403 si user non admin (après résolution du user via JWT).
- **ADMIN_API_TOKENS** : conservé en **legacy bypass** (étape 1), puis retiré (étape 2).

Un seul modèle mental d’auth (magic link) pour clients et admins.

---

## Modèle de données (décisions sans code)

### Rôle admin

- **Option A** : champ `tenant_users.is_admin` (bool).  
  - Admin global : `tenant_id = NULL` ou tenant_id “système” (ex. 0) selon convention.
- **Option B** : enum `role` étendu : `owner | viewer | admin_global`.  
  - Un même email peut être dans `tenant_users` pour un tenant (client) et avoir une ligne “admin” avec `tenant_id = NULL`.

Recommandation : **Option A** avec table dédiée ou colonne selon schéma actuel.

- **`tenant_users`** : inchangé pour les clients (tenant_id, email, role).
- **Admins** : soit une ligne avec `tenant_id = NULL` et `is_admin = true`, soit table `admin_users(id, email, created_at)` et lookup prioritaire dans `require_admin()`.

Convention retenue pour la spec : **`tenant_users.tenant_id = NULL` = admin global** (1 email = 1 tenant en v1 client ; pour admin, tenant_id NULL = accès global). Si tu préfères un tenant_id spécial (ex. 0), même logique.

### Tables (résumé)

- **tenant_users** (existant)  
  - Ajout optionnel : `is_admin BOOLEAN DEFAULT false`.  
  - Ou : garder tel quel et introduire **admin_users(email UNIQUE, created_at)** ; dans `require_admin()` : si email dans `admin_users` → admin.
- **magic_links** (existant) : réutilisé pour admin ; pour un admin, `tenant_id` peut être NULL (lien créé avec tenant_id NULL et scope=admin si tu veux distinguer).

Pas de mot de passe : tout en magic link.

---

## Endpoints (auth admin)

| Méthode | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/admin/request-link` | Body `{ "email": "..." }`. Si email dans allowlist admin → crée magic_link (tenant_id NULL ou scope admin), envoie email. Sinon 200 { ok: true } (pas d’enumeration). |
| GET | `/api/auth/admin/verify?token=...` | Vérifie token, marque used. Émet **JWT** (payload : sub=email, role=admin, pas de tenant_id ou tenant_id=null). Réponse : **Set-Cookie** (HttpOnly, Secure, SameSite=Lax) + redirect vers `/admin` ou JSON { ok, redirect }. |
| POST | `/api/auth/admin/logout` | Invalide cookie (Clear-Set-Cookie ou token blacklist optionnel). |

Côté client (navigateur) : après verify, toutes les requêtes vers `/api/admin/*` envoient le cookie ; plus besoin de mettre le JWT dans localStorage pour l’admin.

---

## Backend : get_current_user + require_admin

- **get_current_user(request)**  
  - Lit le JWT depuis le **cookie** (nom fixe, ex. `session` ou `admin_session`).  
  - Si header `Authorization: Bearer <token>` présent (legacy), l’utiliser en secours.  
  - Token absent / invalide / expiré → 401.  
  - Sinon décode et retourne un objet **User** (email, role, tenant_id optionnel, is_admin dérivé).

- **require_admin(user: User = Depends(get_current_user))**  
  - Si pas de user → déjà 401 par get_current_user.  
  - Si `user.is_admin` faux → **403 Forbidden**.  
  - Sinon → continuer (optionnel : retourner user pour audit).

- **Legacy (étape 1)** : si `ADMIN_API_TOKENS` est configuré et que la requête contient un Bearer qui matche un de ces tokens, traiter comme admin (bypass get_current_user pour cette requête). Log audit avec `token_fp` comme aujourd’hui.  
- **Étape 2** : retirer le bypass ; seuls les JWT (cookie) admin ouvrent l’accès.

---

## CORS et réseau

- **CORS** : `/api/admin/*` déjà limité aux origines autorisées (`ADMIN_CORS_ORIGINS` ou fallback `CORS_ORIGINS`). À conserver.
- **Allowlist IP (optionnel)** : variable `ADMIN_ALLOWED_IPS` (liste d’IP ou CIDR). Si définie, les requêtes vers `/api/admin/*` dont l’IP client n’est pas dans la liste → 403. À ajouter en middleware ou dans `require_admin()`. Peut rester désactivé (variable vide) en prod si non nécessaire.

---

## Migration en 2 étapes

### Étape 1 — Double mode (legacy + users)

1. Ajouter table ou colonne pour marquer les admins (ex. `admin_users` ou `tenant_users.is_admin` + lignes tenant_id NULL).
2. Implémenter `POST /api/auth/admin/request-link`, `GET /api/auth/admin/verify` (cookie HttpOnly), `POST /api/auth/admin/logout`.
3. Introduire `get_current_user()` qui lit JWT depuis cookie (et éventuellement Bearer).
4. Modifier `require_admin()` :  
   - d’abord : si Bearer ∈ ADMIN_API_TOKENS → OK (legacy) ;  
   - sinon : appeler get_current_user → si pas user 401, si user et non admin 403, sinon OK.
5. Front admin : page login (email) → redirect après verify vers `/admin` ; appels API sans mettre de token en localStorage (cookie seul).
6. Tests : 401 sans cookie ni token ; 403 avec JWT client (non admin) ; 200 avec JWT admin ; 200 avec legacy Bearer.

### Étape 2 — Retrait legacy

1. Supprimer la branche “Bearer ∈ ADMIN_API_TOKENS” dans `require_admin()`.
2. Retirer (ou déprécier) `ADMIN_API_TOKEN` / `ADMIN_API_TOKENS` de la doc et du déploiement.
3. Tests : plus de 401/200 avec Bearer admin ; uniquement cookie JWT admin pour accès admin.

---

## Tests à prévoir

- **Auth admin**  
  - `request-link` avec email non admin → 200 { ok: true }, pas d’email.  
  - `request-link` avec email admin → 200, magic link créé (mock email).  
  - `verify` token invalide/expiré → 400.  
  - `verify` token valide → Set-Cookie présent, redirect ou JSON ok.
- **require_admin**  
  - Requête sans cookie ni Bearer → 401.  
  - Requête avec JWT client (tenant_id non null, is_admin false) → 403.  
  - Requête avec JWT admin (is_admin true) → 200.  
  - (Étape 1) Requête avec Bearer ∈ ADMIN_API_TOKENS → 200.  
  - (Étape 2) Bearer legacy retiré → 401 pour Bearer seul sans cookie admin.
- **CORS** : requête `/api/admin/*` avec Origin non autorisée → 403.  
- **IP allowlist** (si implémenté) : IP hors liste → 403.

---

## Résumé

| Élément | Décision |
|--------|----------|
| Login admin | Magic link (comme client) |
| JWT admin | Cookie HttpOnly, Secure, SameSite=Lax |
| Qui est admin ? | `admin_users` ou `tenant_users` avec tenant_id NULL + is_admin |
| require_admin() | 403 si user non admin |
| Legacy | ADMIN_API_TOKENS accepté en étape 1, retiré en étape 2 |
| CORS / IP | Déjà CORS admin ; allowlist IP optionnelle (ADMIN_ALLOWED_IPS) |

Cette spec peut servir de base pour les tâches “Auth V2 admin” dans le backlog sans modifier le comportement client actuel.
