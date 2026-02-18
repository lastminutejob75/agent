# Prompt Cursor — Admin UWi complet

Objectif : construire un admin UWi complet (Vite 5 + React 18 + React Router 7) avec authentification admin par identifiant + mot de passe, session en cookie HttpOnly, et un back-office multi-tenant (liste/cherche/crée/supprime client + stats par tenant).

---

## CONTEXTE STACK (réel)

- **Front** : Vercel https://uwiapp.com (Vite + React)
- **Backend** : Railway (domaine différent de uwiapp.com)
- **Router** : React Router 7, routes dans `landing/src/App.jsx`
- **Fetch** : custom, PAS axios. Pour l’admin, utiliser `credentials: "include"`
- **Pas de lib toast** : afficher succès/erreurs inline

---

## BACKEND (déjà partiellement en place / à compléter si besoin)

### 1) Auth admin (cookie)

- **POST /api/admin/auth/login** `{ email, password }`
  - Vérifie email/password via env : `ADMIN_EMAIL`, `ADMIN_PASSWORD_HASH` (bcrypt). `ADMIN_PASSWORD` peut rester en fallback mais warning en prod.
  - Pose cookie HttpOnly : `uwi_admin_session` contenant un JWT avec `scope="admin"`, `iat`, `exp` (`ADMIN_SESSION_EXPIRES_HOURS` défaut 8).
  - Cookie flags :
    - `Secure=True` en prod
    - `SameSite` configurable via `ADMIN_COOKIE_SAMESITE` (none|lax|strict). Par défaut : en prod Secure=True ⇒ SameSite=none (API Railway cross-domain), sinon lax
    - **Ne pas set `domain`** : avec API sur Railway, le cookie doit rester host-only sur *.railway.app.
- **GET /api/admin/auth/me** → `{ email }` si cookie valide, sinon 401
- **POST /api/admin/auth/logout** → supprime cookie (mêmes flags que login)

### 2) Protection admin

- **require_admin** : accepte d’abord cookie JWT admin valide, sinon Bearer `ADMIN_API_TOKENS` (legacy).
- **CORS** :
  - `allow_credentials=True`
  - `allow_origins` contient `https://uwiapp.com` (pas `*`)
  - admin_cors_guard : si Origin présente et non autorisée → 403
  - **IMPORTANT** : ne jamais bloquer le preflight : si `method == OPTIONS` → laisser passer (call_next)

### 3) Tenants

- GET /api/admin/tenants, GET /api/admin/tenants/{id}
- POST /api/admin/tenants (create)
- POST /api/admin/routing `{ channel, key, tenant_id }` (guard numéro test immuable)
- **DELETE /api/admin/tenants/{tenant_id}**
  - Soft delete PG only : `pg_deactivate_tenant` (inactive)
  - Si mode SQLite fallback : retourner 501 (UI doit afficher un message clair)

---

## FRONT (structure à générer / organiser)

Créer dans `landing/src/` :

- **src/lib/adminApi.js**  
  - `adminFetch(baseUrl + path, { credentials: "include" })`  
  - expose : `me()`, `login()`, `logout()`, `listTenants()`, `getTenant(id)`, `createTenant()`, `addRouting()`, `deleteTenant(id)`

- **src/admin/AdminAuthProvider.jsx** + **useAdminAuth.js**  
  - Contexte global auth admin : `refresh()` appelle /api/admin/auth/me, `login(email, password)` → /login + refresh, `logout()` → /logout + reset state

- **src/admin/ProtectedRoute.jsx**  
  - Si loading → « Chargement… » ; si non connecté → redirect /admin/login ; sinon `<Outlet />`

- **src/admin/AdminLayout.jsx**  
  - Sidebar (Dashboard, Clients, Monitoring, Audit), topbar : email + bouton Déconnexion, `<Outlet />`

**Pages** (`src/admin/pages/`) :

- **AdminLogin.jsx** : formulaire email/password, erreurs inline, redirect après succès
- **AdminDashboard.jsx** : vue globale (nb tenants + derniers tenants)
- **AdminTenantsList.jsx** : table + recherche (nom/id) + lien « Créer un client », boutons Détail et Dashboard tenant
- **AdminTenantNew.jsx** : formulaire create tenant, redirect vers /admin/tenants/:id en succès, erreur 409 EMAIL_ALREADY_ASSIGNED
- **AdminTenantDetail.jsx** : tenant + statut technique + routings, bloc « Raccorder un numéro », bouton « Supprimer le client » (ConfirmDialog). Si 501 → message « Suppression nécessite Postgres ». Texte « (Postgres uniquement) » à côté du bouton
- **AdminTenantDashboard.jsx** : compteurs 7j + dernière activité
- **AdminMonitoring.jsx** + **AdminAuditLog.jsx** : placeholders « Bientôt disponible »
- **AdminNotFound.jsx**

**Composants** (`src/admin/components/`) : **ConfirmDialog.jsx** (modal simple sans lib)

**Routes** (`landing/src/App.jsx`) : /admin/login (public) ; le reste sous ProtectedRoute + AdminLayout : /admin, /admin/tenants, /admin/tenants/new, /admin/tenants/:id, /admin/tenants/:id/dashboard, /admin/monitoring, /admin/audit

---

## EXIGENCES

- Pas de Next.js, pas de middleware Next.
- Pas de lib toast.
- Admin API calls utilisent cookie session (credentials include).
- Gérer 401 : rediriger vers /admin/login.
- Gérer 409 EMAIL_ALREADY_ASSIGNED sur création.
- Gérer 409 TEST_NUMBER_IMMUTABLE sur routing.
- Gérer 501 sur delete tenant.
- Code clair, composants simples, UI sobre mais utilisable.

Livrer : fichiers créés/modifiés avec contenu complet, et adapter aux chemins existants (`landing/src/…`).
