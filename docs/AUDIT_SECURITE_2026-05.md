# Audit sécurité — Mai 2026

> Audit statique express : endpoints non protégés, secrets en dur, hygiène. Réalisé le 2026-05-09 après la refonte du dashboard admin.

## TL;DR

- **Code applicatif** : aucun secret hardcodé détecté. Toutes les clés (Stripe, Vapi, Twilio, JWT) passent par `os.getenv` côté Python ou `import.meta.env.VITE_*` côté React.
- **Endpoints `/api/admin/*`** : 100 % protégés par `_verify_admin` (cookie OU Bearer), à 3 exceptions volontaires (`auth/login`, `auth/logout`, `auth/status`).
- **Findings sérieux** : pas dans `/api/admin/*` mais dans **endpoints publics ou pre-onboarding** — à traiter en priorité.
- **Hygiène** : 3 corrections d'hygiène immédiates appliquées dans cette passe (gitignore, anonymisation email, réduction payload `auth/status`).

---

## 1. Endpoints admin sans auth

| Endpoint | Fichier:ligne | État | Action |
|---|---|---|---|
| `POST /api/admin/auth/login` | `routes/admin.py:1489` | Volontairement public (point d'entrée) | OK |
| `GET /api/admin/auth/status` | `routes/admin.py:1473` | Public mais leak config (email/hash/jwt/token "set") | **Fix appliqué** ⤵ |
| `POST /api/admin/auth/logout` | `routes/admin.py:1531` | Public mais juste clear cookie | Acceptable — laissé public |
| `GET /api/admin/_meta` | `admin_demo/router.py:142` | Public, expose `demo_mode` + `tenants_count` | Documenté volontaire (mode démo) |

**Fix appliqué pour `auth/status`** : ne retourner que `login_configured: bool` au lieu de la liste détaillée des credentials configurés.

Tous les autres endpoints `/api/admin/*` sont protégés via `Depends(_verify_admin)` (cookie session OU Bearer token). L'auth est triple : cookie `uwi_admin_session`, ou Bearer dans `_ADMIN_VALID_TOKENS`. Pas de trou réel.

---

## 2. Endpoints sensibles hors `/api/admin/*` (priorité HIGH)

### 2.1 `POST /api/public/onboarding` (routes/admin.py:1706) — ✅ FIX APPLIQUÉ

**Risque HIGH** — pouvait renvoyer `admin_setup_token` (= `ADMIN_TOKEN`) au client public.

**Fix appliqué** :
- Champ `admin_setup_token` retiré du modèle `OnboardingResponse`.
- Les 2 retours `admin_setup_token=ADMIN_TOKEN` retirés.
- Doc API mise à jour (`docs/API_ADMIN_ONBOARDING.md`).
- Frontend non impacté (n'utilisait pas le champ).

### 2.2 `GET /api/pre-onboarding/leads/{lead_id}/email` (routes/pre_onboarding.py:270) — ✅ FIX APPLIQUÉ

**Risque HIGH** — retournait l'email d'un lead si on connaît son UUID.

**Fix appliqué** : exige désormais un token signé HMAC (`?token=...` ou header `X-Lead-Token`) ou une session admin (cookie / Bearer). Le token est émis par `POST /api/pre-onboarding/commit` lors de la création du lead. Cf. `backend/lead_tokens.py`.

### 2.3 `POST /api/pre-onboarding/leads/{lead_id}/create-account` (routes/pre_onboarding.py:413+) — ✅ FIX APPLIQUÉ

**Risque CRITIQUE** — création tenant + user + mot de passe temporaire à partir d'un seul `lead_id`.

**Fix appliqué** : même protection token signé HMAC. Bypass admin via cookie/Bearer si besoin de debug. L'endpoint est désormais inutilisable sans le token reçu lors du commit.

### 2.3 bis `POST /api/pre-onboarding/leads/{lead_id}/callback-booking` — ✅ FIX APPLIQUÉ (oubli initial)

**Risque MEDIUM (oubli de l'audit initial)** — permettait d'écraser le créneau de rappel d'un lead avec juste son UUID.

**Fix appliqué** : même mécanisme token signé HMAC.

### 2.4 `GET /api/pre-onboarding/leads/{lead_id}/check` — ✅ FIX APPLIQUÉ

**Risque LOW** — confirmait l'existence d'un lead (énumération possible).

**Fix appliqué** : token requis. Le backend log la raison d'invalidité (`expired`, `bad_signature`, etc.) sans la révéler au client (renvoi 401/403/410 générique).

### 2.4 `GET /api/pre-onboarding/config` (routes/pre_onboarding.py:47)

**Risque MEDIUM** — leak d'infos opérationnelles (`total_leads_in_db`, flags email/DB, `backend_hint`).

**Reco** : retirer en prod, ou ne renvoyer que les flags strictement nécessaires au client.

### 2.5 `GET /api/public/analytics/{slug}/summary` (routes/public_pages.py:624)

**Risque MEDIUM** — agrégats analytics par slug, sans auth. Énumérable via le sitemap (cf 2.6).

**Reco** : exiger une session praticien authentifiée, OU un token signé par tenant pour les pages publiques.

### 2.6 `GET /api/public/sitemap.xml` (routes/public_pages.py:629)

**Risque LOW** — liste jusqu'à 5000 slugs actifs. Combiné à `/analytics/{slug}/summary` permet d'énumérer l'activité de tous les cabinets.

**Reco** : conserver pour SEO, mais protéger l'analytics summary.

---

## 3. Endpoints debug / vapi sans auth — ✅ FIX APPLIQUÉ

| Endpoint | Fichier:ligne | Statut |
|---|---|---|
| `/debug/*` (~22 endpoints) | `main.py` | ✅ Middleware `debug_endpoints_guard` |
| `GET /api/stats/bookings` | `main.py:640` | ✅ Middleware `debug_endpoints_guard` |
| `GET /api/vapi/test-calendar` | `routes/voice.py:527` | ✅ `Depends(_require_admin_or_debug_flag)` |
| `GET /api/vapi/test` | `routes/voice.py:2811` | ✅ `Depends(_require_admin_or_debug_flag)` |

**Logique appliquée** :
- Bypass : `ENABLE_DEBUG_ENDPOINTS=true` (env) OU `ADMIN_DEMO_MODE=true` OU auth admin (cookie/Bearer).
- Sinon : 403 avec message explicite.

**Variables d'env** :

```bash
# Optionnel : ouvre les debug endpoints sans auth (recommande staging/dev local seulement)
ENABLE_DEBUG_ENDPOINTS=true
```

En prod, laisser vide → seuls les admins (cookie session ou Bearer) peuvent y accéder.

---

## 4. Secrets en dur

**Aucun trouvé.** Tout passe par variables d'environnement.

Quelques points d'hygiène :

| Fichier | Item | Risque | Status |
|---|---|---|---|
| `.env.example:~52` | `REPORT_EMAIL=henigoutal@gmail.com` (vraie adresse personnelle dans un exemple) | LOW (privacy) | **Fix appliqué** ⤵ |
| `.env.test-email.example` | URL Railway en clair | LOW | Laissé tel quel (URL déjà publique) |
| `landing/src/pages/AppAgenda.jsx:454` | Placeholder `uwi-bot@xxx.iam.gserviceaccount.com` | LOW (placeholder évident) | OK |
| `.gitignore` (racine) | Pas de `.env.local`, pas de `*.pem` / `*.key` | MEDIUM (préventif) | **Fix appliqué** ⤵ |

---

## 5. CORS et middlewares

| Middleware | Rôle | État |
|---|---|---|
| `CORSMiddleware` global (`main.py:53`) | `allow_credentials=True`, origines listées | OK |
| `admin_cors_guard` (`main.py:62`) | 403 si Origin non whitelistée sur `/api/admin/*` | OK (sans Origin = pas de filtrage CORS, mais auth applicative protège) |
| `admin_demo_write_block` (`main.py:87`) | 403 sur les writes en mode démo | OK |

**Note** : si `is_demo_mode()` lève une exception, le middleware `admin_demo_write_block` fait `continue` (lignes 105-106) → en cas de bug de détection démo, les writes passent. Comportement à conserver (fail-open intentionnel pour ne pas bloquer la prod), mais à monitorer si on ajoute un test sur ce middleware.

---

## 6. Cookies et tokens

- **Cookie admin** `uwi_admin_session` : signé HMAC, expiration courte (30 min). Côté `routes/admin.py:309-343`.
- **Bearer admin** : tokens listés dans `ADMIN_API_TOKEN` (env). Validés via `_ADMIN_VALID_TOKENS`.
- **JWT impersonation** (`routes/auth.py:88-135`) : protégé par secret JWT + token `impersonate`, mais **pas par session admin browser**. Si volé, accès tenant. À monitorer (logs + ttl court).

**Reco future** : rotation périodique de `ADMIN_API_TOKEN` et `JWT_SECRET`. À automatiser via secrets manager (Railway / Vercel) si ce n'est déjà fait.

---

## 7. Recommandations priorisées

### HIGH (à traiter rapidement)

1. ✅ **`POST /api/public/onboarding`** — `admin_setup_token` retiré.
2. ✅ **`POST /api/pre-onboarding/leads/{lead_id}/create-account`** — token signé HMAC.
3. ✅ **`GET /api/pre-onboarding/leads/{lead_id}/email`** — token signé HMAC.
4. ✅ **`POST /api/pre-onboarding/leads/{lead_id}/callback-booking`** — token signé HMAC (oubli initial).
5. ✅ **`/debug/*`, `/api/stats/bookings`, `/api/vapi/test-calendar`, `/api/vapi/test`** — middleware `debug_endpoints_guard` + dépendance par endpoint.

### MEDIUM

6. ✅ **`GET /api/public/analytics/{slug}/summary`** — auth tenant propriétaire OU admin requise. Frontend `AppDashboard` envoie désormais `credentials: "include"`.
7. **`GET /api/pre-onboarding/config`** — retirer ou réduire le payload. **Non corrigé** (utile en debug).
8. ✅ **Compléter `.gitignore` racine** appliqué.
9. ✅ **Vérification signature webhooks Vapi** — `backend/vapi_security.py`, mode souple par défaut, strict via `VAPI_REQUIRE_SIGNATURE=true`. Cf. [§8 — Vérification signature webhooks Vapi](#vérification-signature-webhooks-vapi-priorité-medium--fix-appliqué).
10. ✅ **Rate-limiting endpoints sensibles** — `backend/rate_limit.py` : sliding window in-memory, bloque le brute-force sur `/api/admin/auth/login` (5 tentatives / 60s par IP) et le spam sur `/api/public/onboarding` (10 / 60s). Cf. [§8 — Rate-limiting](#rate-limiting-endpoints-sensibles-priorité-medium--fix-appliqué). Le `/api/pre-onboarding/commit` avait déjà son rate-limiter dédié (`backend/pre_onboarding_rate_limit.py`).

### LOW

9. ✅ **`GET /api/admin/auth/status`** — leak config réduit appliqué.
10. ✅ **Anonymiser `REPORT_EMAIL` dans `.env.example`** appliqué.
11. ✅ **`GET /api/pre-onboarding/leads/{lead_id}/check`** — token signé HMAC.

---

## 8. Fix appliqués dans cette passe

### Hygiène

| Fichier | Modification |
|---|---|
| `.gitignore` | Ajout `.env.local`, `.env.*.local`, `*.pem`, `*.key`, `*.p12`, `*.pfx` + exceptions |
| `.env.example` | `REPORT_EMAIL` → placeholder générique |
| `backend/routes/admin.py` (`auth/status`) | Réduit payload à `login_configured: bool` (détails uniquement si auth admin) |

### Refactor produit pré-onboarding (token HMAC)

| Fichier | Modification |
|---|---|
| `backend/lead_tokens.py` (nouveau) | Helpers `make_lead_token` / `verify_lead_token` / `extract_token_from_request`. HMAC-SHA256, TTL 7 jours, secret `LEAD_TOKEN_SECRET` (fallback `JWT_SECRET`). |
| `backend/routes/pre_onboarding.py` | `commit` retourne `{ok, lead_id, token}`. Endpoints `/leads/{id}/email`, `/check`, `/callback-booking`, `/create-account` exigent désormais un token (ou bypass admin). Helper `_require_lead_token` partagé. |
| `backend/routes/admin.py` | Retrait du champ `admin_setup_token` dans `OnboardingResponse` + dans les 2 retours `public_onboarding`. |
| `docs/API_ADMIN_ONBOARDING.md` | Doc API mise à jour. |
| `landing/src/lib/api.js` | Helpers acceptent un `token` en paramètre, passé en query string. Duplication `preOnboardingLeadEmail` supprimée. |
| `landing/src/pages/CreerAssistante.jsx` | Stocke le `token` au commit dans sessionStorage + state, le passe à `UWIFinalization`. |
| `landing/src/components/UWIFinalization.jsx` | Reçoit `leadToken` en prop, le passe à `preOnboardingLeadCheck` et `preOnboardingCallbackBooking`. Si pas de token → écran d'erreur direct (lien expiré). |

### Protection des endpoints debug & analytics

| Fichier | Modification |
|---|---|
| `backend/main.py` | Middleware `debug_endpoints_guard` : bloque `/debug/*` et `/api/stats/bookings` sauf si `ENABLE_DEBUG_ENDPOINTS=true`, mode démo, ou auth admin. Helpers `_debug_endpoints_open()` et `_request_is_admin_authenticated()`. |
| `backend/routes/voice.py` | Dépendance `_require_admin_or_debug_flag` ajoutée à `GET /test-calendar` et `GET /test`. Même logique que le middleware. |
| `backend/routes/public_pages.py` | `GET /analytics/{slug}/summary` exige auth tenant propriétaire du slug OU auth admin. Helpers `_is_admin_authenticated()` et `_tenant_owns_slug()`. |
| `landing/src/pages/AppDashboard.jsx` | Fetch analytics summary avec `credentials: "include"` (cookie tenant). |

### Variable d'env à configurer

```bash
# Optionnel : si non défini, fallback sur JWT_SECRET puis ADMIN_SESSION_SECRET
LEAD_TOKEN_SECRET=<secret-aleatoire-32-chars-minimum>
```

### Backward compat

- Anciennes sessions (lead créé avant le déploiement) : pas de token en sessionStorage → `UWIFinalization` affiche l'écran "Lead introuvable, lien expiré". L'utilisateur doit recommencer le wizard. Acceptable (impact = quelques utilisateurs en cours).
- Bypass admin : un admin authentifié (cookie OU Bearer) peut appeler ces endpoints sans token → utile pour debug et pour les pages admin si elles consomment ces endpoints.

### Tests unitaires (102 tests automatisés)

Suite de tests `pytest` couvrant tous les fixs de cet audit. Voir [`docs/TESTS_BACKEND.md`](./TESTS_BACKEND.md).

| Fichier | Tests | Cible |
|---|---:|---|
| `tests/test_lead_tokens.py` | 18 | Helpers HMAC (sign/verify/edge cases) |
| `tests/test_pre_onboarding_security.py` | 16 | Endpoints `/api/pre-onboarding/*` |
| `tests/test_admin_security_audit.py` | 9 | `auth/status` réduit + leak `admin_setup_token` |
| `tests/test_debug_endpoints_guard.py` | 17 | Middleware debug + Vapi test |
| `tests/test_public_analytics_auth.py` | 7 | Auth `/api/public/analytics/{slug}/summary` |
| `tests/test_vapi_security.py` | 35 | Signature webhooks Vapi (HMAC + shared secret) |

**Lancement :**

```bash
python3 -m pytest tests/test_lead_tokens.py \
                   tests/test_pre_onboarding_security.py \
                   tests/test_admin_security_audit.py \
                   tests/test_debug_endpoints_guard.py \
                   tests/test_public_analytics_auth.py \
                   tests/test_vapi_security.py -v
# 102 passed in ~1.5s
```

**Bonus** : neutralisation de `ADMIN_DEMO_MODE` dans `tests/conftest.py` (re-fait passer 22 tests admin pré-existants).

### Vérification signature webhooks Vapi (priorité MEDIUM → ✅ FIX APPLIQUÉ)

Les endpoints `/api/vapi/webhook` et `/api/vapi/tool` étaient publics (signature TODO). Ils valident désormais l'authenticité de chaque requête à partir du secret partagé `VAPI_WEBHOOK_SECRET` (envoyé à Vapi via `server.secret`).

**Fichiers modifiés :**

| Fichier | Modification |
|---|---|
| `backend/vapi_security.py` (nouveau) | `verify_vapi_signature(body, headers) -> (ok, reason)`. Supporte les deux formats Vapi : `X-Vapi-Secret` (legacy, comparaison directe) et `X-Vapi-Signature` (HMAC-SHA256, avec/sans préfixe `sha256=`). Comparaison en temps constant via `hmac.compare_digest`. |
| `backend/routes/voice.py` (`/api/vapi/webhook`, `/api/vapi/tool`) | Lecture du body brut une seule fois, vérif signature avant le `json.loads`. En mode souple : log warning. En mode strict : `HTTPException 401`. |
| `tests/conftest.py` | Ajout `VAPI_SIGNATURE_DISABLED=true` pour neutraliser dans les ~800 tests existants (les tests dédiés réactivent via `monkeypatch`). |
| `tests/test_vapi_security.py` (nouveau) | 35 tests : modes shared secret / HMAC / sans header / disabled / mode souple vs strict / case insensitive / body différent. |
| `docs/INTEGRATION_VAPI.md` | Section [Sécurité — Vérification des webhooks](./INTEGRATION_VAPI.md#sécurité--vérification-des-webhooks-entrants). |

**Variables d'env :**

```bash
VAPI_WEBHOOK_SECRET=<secret-partage-avec-Vapi>     # déjà existant
VAPI_REQUIRE_SIGNATURE=false                       # défaut : mode souple (log warning)
# VAPI_REQUIRE_SIGNATURE=true                      # mode strict (rejet 401)
# VAPI_SIGNATURE_DISABLED=true                     # uniquement dev/CI
```

**Migration douce recommandée :**

1. **Phase 1 — Audit** (état actuel) : déployer avec `VAPI_REQUIRE_SIGNATURE=false`. Surveiller les logs `[VAPI_WEBHOOK_SIGNATURE_INVALID]` et `[VAPI_TOOL_SIGNATURE_INVALID]` pendant 3-7 jours.
2. **Phase 2 — Strict** : activer `VAPI_REQUIRE_SIGNATURE=true` une fois les logs propres.

### Rate-limiting endpoints sensibles (priorité MEDIUM → ✅ FIX APPLIQUÉ)

Les endpoints `/api/admin/auth/login` et `/api/public/onboarding` étaient sans rate-limiting → vulnérables au brute-force et au spam. Ajout d'un sliding window in-memory générique.

**Fichiers :**

| Fichier | Modification |
|---|---|
| `backend/rate_limit.py` (nouveau) | `check_rate_limit(key, request, max_attempts, window_seconds)` + `RateLimitExceeded`. Per-IP (X-Forwarded-For prioritaire). Per-process (suffisant pour brute-force defense). Désactivable via `RATE_LIMIT_ENABLED=false`. |
| `backend/routes/admin.py` (`auth/login`) | Pré-check 5 tentatives / 60s par IP → 429 + header `Retry-After` si dépassé. |
| `backend/routes/admin.py` (`public_onboarding`) | Pré-check 10 / 60s par IP. |
| `tests/test_rate_limit.py` (nouveau) | 10 tests : helper unitaire (under/over limit, isolation key/client, fenêtre glissante, X-Forwarded-For, désactivation), intégration login + onboarding. |

**Variables d'env :**

```bash
RATE_LIMIT_ENABLED=true                # master switch (defaut true)
RATE_LIMIT_LOGIN_MAX=5                 # tentatives login admin / fenetre
RATE_LIMIT_LOGIN_WINDOW_S=60           # fenetre login (s)
RATE_LIMIT_ONBOARDING_MAX=10           # /api/public/onboarding par fenetre
RATE_LIMIT_ONBOARDING_WINDOW_S=60      # fenetre onboarding (s)
```

**Limites connues :** in-memory per-process. Si scaling horizontal Railway > 1 replica, chaque worker a son propre compteur. Pour une protection forte multi-replica, passer à Redis (TODO).

### Healthcheck enrichi & observabilité (audit fiabilité)

Voir [`OBSERVABILITE.md`](./OBSERVABILITE.md) :

- `backend/log_setup.py` : logs JSON + request_id + buffer en mémoire + middleware HTTP.
- `backend/health_checks.py` + `GET /api/health` : status par service (DB, Vapi, Twilio, Stripe, Calendar, email) avec cache 30s.
- `compute_metrics()` + `GET /api/admin/logs/metrics` : KPIs/latence p50-p99/top paths/répartition niveaux, calculé sur le buffer.
- Frontend `AdminMonitoring` : `<MetricsPanel />` + `<LogsPanel />`.

### Audit-log admin (priorité MEDIUM → ✅ FIX APPLIQUÉ)

Trace toutes les actions d'écriture (POST/PUT/PATCH/DELETE) sur `/api/admin/*` dans une table dédiée. RGPD ("qui a fait quoi quand") + forensic en cas d'incident.

**Fichiers :**

| Fichier | Modification |
|---|---|
| `migrations/034_admin_audit_log.sql` (nouveau) | Table `admin_audit_log` (actor_email, method, path, payload JSONB, ip, request_id, ...) + 4 index. |
| `backend/audit_log.py` (nouveau) | `install_audit_middleware(app)`, `write_audit_entry()`, `fetch_recent_audit_entries()`. Sanitisation auto des champs sensibles (password, token, api_key, ...). Body tronqué > 4 KB, strings > 1024 chars. |
| `backend/main.py` | Installation du middleware au démarrage. |
| `backend/routes/admin.py` | Endpoint `GET /api/admin/audit-log` avec filtres (actor_email, tenant_id, method, path_prefix, limit/offset). |
| `landing/src/admin/components/dashboard/AuditLogPanel.jsx` (nouveau) | Panel UI dans `AdminMonitoring` (filtres + auto-refresh 30s + expand payload). |
| `landing/src/lib/adminApi.js` | Helper `fetchAuditLog(opts)`. |
| `tests/test_audit_log.py` (nouveau) | 31 tests : sanitisation (redaction, troncature), helpers, write/fetch (mock PG), middleware (GET non tracé, POST audité, login exclu), endpoint (auth, filtres, validation). |

**Variables d'env :**

```bash
ADMIN_AUDIT_LOG_ENABLED=true     # master switch (defaut true)
```

**Best-effort :** si Postgres est indisponible, on log uniquement (`logger.info("[ADMIN_AUDIT] ...")`) — la requête utilisateur n'est jamais bloquée.

**Routes exclues** (raison sécurité, contiennent des secrets en clair) : `/api/admin/auth/login`, `/auth/logout`, `/auth/me`, `/logs/recent`, `/logs/metrics`.

**Rétention recommandée** : 12 mois (cron de purge à mettre en place une fois la table peuplée).

### Audit dépendances (CVE) (priorité LOW → ✅ FIX APPLIQUÉ)

Voir [`SECURITY_DEPENDENCIES.md`](./SECURITY_DEPENDENCIES.md). Deux jobs CI :

- `audit-deps-python` : `pip-audit -r requirements.txt --desc`
- `audit-deps-node` : `npm audit --audit-level=high --omit=dev`

`continue-on-error: true` pour démarrer (signal sans bloquer). À durcir une fois la baseline propre.

### Pre-commit hooks (priorité LOW → ✅ FIX APPLIQUÉ)

Voir [`PRE_COMMIT.md`](./PRE_COMMIT.md). Config `.pre-commit-config.yaml` avec :

- `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-json`, `check-added-large-files`, `check-merge-conflict`, `detect-private-key`
- `ruff` (mêmes règles que la CI)
- `gitleaks` (détection de secrets dans le diff)

Installation : `pip install pre-commit && pre-commit install`.

---

## 9. Méthode

- **Endpoints admin** : grep + analyse handler par handler dans `routes/admin.py`, `routes/admin_demo/router.py`, `main.py`.
- **Secrets** : grep des patterns `sk_live`, `sk_test`, `pk_live`, `Bearer ...`, `JWT_SECRET=`, URLs `user:password@`, JWT en base64.
- **Hygiène** : revue `.env.example`, `.gitignore`, `Dockerfile`, `docker-compose.yml`.
- **Pas dans le scope** : audit dynamique (DAST), fuzzing, audit dépendances (`npm audit`, `pip-audit`).

## 10. Voir aussi

- [`ADMIN_DEMO_MODE.md`](./ADMIN_DEMO_MODE.md) — Mode démo backend (lecture seule).
- [`ADMIN_LOGIN_COOKIE.md`](./ADMIN_LOGIN_COOKIE.md) — Setup cookies SameSite=None+Secure.
- [`ADMIN_SECURITY.md`](./ADMIN_SECURITY.md) — Doc sécurité existante.
- [`AUDIT_LOG_ADMIN.md`](./AUDIT_LOG_ADMIN.md) — Audit-log admin (table, middleware, endpoint, UI).
- [`OBSERVABILITE.md`](./OBSERVABILITE.md) — Logs structurés, request_id, buffer admin.
- [`SECURITY_DEPENDENCIES.md`](./SECURITY_DEPENDENCIES.md) — Audit CVE deps (pip-audit, npm audit).
- [`PRE_COMMIT.md`](./PRE_COMMIT.md) — Hooks pre-commit (ruff, gitleaks).
- [`TESTS_BACKEND.md`](./TESTS_BACKEND.md) — Tests unitaires backend.
