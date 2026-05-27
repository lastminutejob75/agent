# Récap audit sécurité + observabilité 2026-05

Synthèse de tous les chantiers menés pendant la session d'audit sécurité et observabilité.
Ce document liste **ce qui a été fait, où c'est, et à quoi ça sert**, pour reprendre rapidement le contexte.

Pour les détails techniques de chaque chantier, voir le doc dédié référencé dans chaque section.

---

## Vue d'ensemble

| Domaine | Statut | Doc dédiée |
|---------|--------|------------|
| Audit-log admin (RGPD) | ✅ | [`AUDIT_LOG_ADMIN.md`](AUDIT_LOG_ADMIN.md) |
| Exports CSV admin & tenant | ✅ | [`EXPORTS_CSV.md`](EXPORTS_CSV.md) |
| Tests E2E Playwright | ✅ | [`E2E_PLAYWRIGHT.md`](E2E_PLAYWRIGHT.md) |
| Observabilité (logs structurés, request_id, LogsPanel) | ✅ | [`OBSERVABILITE.md`](OBSERVABILITE.md) |
| Sentry error tracking | ✅ | [`SENTRY.md`](SENTRY.md) |
| Audit de dépendances (CVE) | ✅ | [`SECURITY_DEPENDENCIES.md`](SECURITY_DEPENDENCIES.md) |
| Pre-commit hooks | ✅ | [`PRE_COMMIT.md`](PRE_COMMIT.md) |
| Tests backend (couverture min) | ✅ | [`TESTS_BACKEND.md`](TESTS_BACKEND.md) |
| Endpoint `system/info` + UI | ✅ | (cf. ci-dessous) |
| Healthcheck enrichi | ✅ | (cf. `OBSERVABILITE.md`) |
| Rate limiting endpoints sensibles | ✅ | (cf. `ADMIN_SECURITY.md`) |
| Audit de sécurité (état des fix) | — | [`AUDIT_SECURITE_2026-05.md`](AUDIT_SECURITE_2026-05.md) |

---

## 1. Sécurité — Backend

### 1.1 Audit-log admin (`admin_audit_log`)

**Pourquoi** : tracer qui fait quoi en admin (RGPD, sécurité, debug post-incident).

**Quoi** :
- Nouvelle table `admin_audit_log` (cf. `migrations/034_admin_audit_log.sql`).
- Middleware `install_audit_middleware(app)` qui logue tous les `POST/PUT/PATCH/DELETE` sur `/api/admin/*`.
- Sanitization automatique (redaction des champs `password`, `token`, `api_key`, ...).
- Endpoint `GET /api/admin/audit-log` + UI `<AuditLogPanel />` dans Admin Monitoring.
- Cron hebdo `purge_admin_audit_log_job` qui supprime les entrées > 12 mois (RGPD), configurable via `ADMIN_AUDIT_LOG_RETENTION_DAYS`.

**Fichiers clés** :
- `backend/audit_log.py` (middleware, sanitization, purge)
- `backend/reports.py` (job planifié)
- `landing/src/admin/components/dashboard/AuditLogPanel.jsx`
- `tests/test_audit_log.py` (31 tests)

**Env vars** : `ADMIN_AUDIT_LOG_ENABLED`, `ADMIN_AUDIT_LOG_RETENTION_DAYS`.

### 1.2 Rate-limiting endpoints sensibles

**Pourquoi** : bloquer brute-force sur `/auth/login`, `/auth/magic-link`, `/onboarding/*`, `/contact`.

**Quoi** : rate-limiter in-memory (sliding window), décorateur sur les routes sensibles.

**Fichiers** : `backend/rate_limit.py`, `tests/test_rate_limit.py`.

### 1.3 Pre-onboarding HMAC tokens

**Pourquoi** : sécuriser le flow d'onboarding pré-paiement (avant qu'un tenant existe).

**Quoi** : tokens HMAC signés côté serveur, validation systématique avant chaque action.

**Fichiers** : `backend/lead_tokens.py`.

### 1.4 Vapi webhook signature

**Pourquoi** : empêcher quelqu'un d'envoyer de faux events Vapi à notre endpoint.

**Quoi** : vérification HMAC de la signature `x-vapi-signature` sur tous les webhooks Vapi.

**Env vars** : `VAPI_SIGNATURE_DISABLED` (à `true` uniquement en dev local).

### 1.5 Audit de dépendances CVE (CI)

**Pourquoi** : détecter les CVE connues sur nos deps Python/Node.

**Quoi** :
- Job CI `audit-deps-python` (pip-audit) + `audit-deps-node` (npm audit).
- Non-bloquant pour le moment (`continue-on-error: true`), à passer bloquant quand les CVE upstream sont nettoyées.

**Fichier** : `.github/workflows/backend-tests.yml`, `docs/SECURITY_DEPENDENCIES.md`.

### 1.6 Pre-commit hooks

**Pourquoi** : éviter de commit des secrets / lints / gros fichiers / fichiers cassés.

**Quoi** : `pre-commit` avec ruff (lint Python), gitleaks (détection de secrets), trailing whitespace, etc.

**Fichier** : `.pre-commit-config.yaml`, `docs/PRE_COMMIT.md`.

**Activation locale** :
```bash
pip install pre-commit
pre-commit install
```

---

## 2. Observabilité

### 2.1 Logs structurés + request_id

**Pourquoi** : suivre une requête sur plusieurs lignes de log, ingérer dans Datadog/Loki/CloudWatch sans parsing custom.

**Quoi** :
- Format JSON activable via `LOG_JSON=true`.
- Chaque requête HTTP reçoit un `request_id` (UUID4 ou repris de `X-Request-ID`) propagé via `contextvars`.
- Log `request_end` à chaque fin de requête (méthode, path, status, durée).
- Ring buffer en RAM (~1000 derniers logs) exposé via `GET /api/admin/logs/recent`.

**Fichier** : `backend/log_setup.py`, doc complète dans `OBSERVABILITE.md`.

### 2.2 LogsPanel (admin UI)

**Pourquoi** : debug rapide depuis l'admin, sans SSH.

**Quoi** :
- Poll 10s (pause/play).
- Filtre par niveau + limit (50/100/200/500).
- **Recherche full-text** (msg, path, request_id, logger).
- **Groupement par `request_id`** : voir tous les logs d'une même requête.
- **Pin sur un `request_id`** : clic pour filtrer uniquement cette requête.
- **Export JSON** des logs filtrés.

**Fichier** : `landing/src/admin/components/dashboard/LogsPanel.jsx`.

### 2.3 MetricsPanel

**Pourquoi** : KPIs HTTP agrégés (RPM, latence p50/p95, taux d'erreur) sans outil externe.

**Quoi** : calcul à la volée depuis le buffer de logs.

**Fichier** : `landing/src/admin/components/dashboard/MetricsPanel.jsx`.

### 2.4 Healthcheck enrichi `/api/health`

**Pourquoi** : monitoring externe (UptimeRobot, etc.) doit savoir si le backend ET les services critiques sont up.

**Quoi** :
- Checks parallèles : Postgres, Vapi, Stripe, Twilio.
- Mise en cache (60s) pour ne pas marteler les APIs externes.
- Status `ok` / `degraded` / `down` selon résultats.

**Fichier** : `backend/health_checks.py`.

### 2.5 Endpoint `/api/admin/system/info` + UI

**Pourquoi** : voir version, git SHA, env, uptime, présence des secrets depuis l'admin (debug en prod).

**Quoi** :
- Endpoint qui retourne : git SHA/branche, Python/Node versions, platform, uptime, env vars filtrées (whitelist + flags de présence).
- UI `<SystemInfoPanel />` dans Admin Monitoring.

**Fichiers** : `backend/system_info.py`, `landing/src/admin/components/dashboard/SystemInfoPanel.jsx`.

### 2.6 Sentry (optionnel)

**Pourquoi** : alertes auto en prod sur exceptions non gérées et logs `ERROR`.

**Quoi** :
- Initialisation conditionnelle (no-op si `SENTRY_DSN` absent).
- Capture exceptions + logs `ERROR` (via `LoggingIntegration`).
- Breadcrumbs des logs `INFO` précédents (contexte).
- `send_default_pii=False` (RGPD).

**Fichiers** : `backend/sentry_setup.py`, `docs/SENTRY.md`.

**Env vars** : `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `SENTRY_TRACES_SAMPLE_RATE`, `SENTRY_RELEASE`.

---

## 3. Exports CSV

**Pourquoi** : les utilisateurs (admin + tenant) doivent pouvoir exporter leurs données dans Excel.

**Quoi** :
- Endpoints admin : `GET /api/admin/exports/calls.csv`, `GET /api/admin/exports/bookings.csv`.
- Endpoints tenant : `GET /api/tenant/exports/calls.csv`, `GET /api/tenant/exports/bookings.csv`.
- Format CSV avec BOM UTF-8 + `;` comme délimiteur (compatible Excel FR).
- Streaming (`StreamingResponse`) → pas de buffering en mémoire.
- UI : composant réutilisable `<ExportCsvButton />`.

**Fichiers** :
- `backend/exports.py` (logique commune)
- `backend/routes/admin.py` + `backend/routes/tenant.py` (endpoints)
- `landing/src/admin/components/ui/ExportCsvButton.jsx`
- `tests/test_exports.py` (20 tests)

**Doc** : `docs/EXPORTS_CSV.md`.

---

## 4. Tests & qualité

### 4.1 Tests E2E Playwright

**Pourquoi** : tester le parcours utilisateur complet (page publique, onboarding, exports admin).

**Quoi** :
- `landing/tests/e2e/public-page.spec.js` : page publique praticien.
- `landing/tests/e2e/onboarding.spec.js` : wizard d'onboarding.
- `landing/tests/e2e/admin-exports.spec.js` : exports CSV admin.
- Workflow CI `.github/workflows/e2e-tests.yml` : backend en demo mode + frontend buildé + Playwright.

**Doc** : `docs/E2E_PLAYWRIGHT.md`.

### 4.2 Couverture min backend

**Pourquoi** : empêcher la couverture de chuter sans s'en rendre compte.

**Quoi** : `pytest --cov-fail-under=50` dans la CI. À augmenter progressivement.

**Fichier** : `.github/workflows/backend-tests.yml`, `docs/TESTS_BACKEND.md`.

### 4.3 Linting CI (ruff)

**Pourquoi** : éviter le code mort, les imports inutilisés, les bugs évidents.

**Quoi** : job CI ruff sur `backend/` et `tests/`. Config dans `pyproject.toml`.

---

## 5. Variables d'environnement ajoutées

Toutes documentées dans `.env.example`.

| Variable | Défaut | Rôle |
|----------|--------|------|
| `LOG_LEVEL` | `INFO` | Niveau de log racine |
| `LOG_JSON` | `false` | Format JSON pour ingestion externe |
| `LOG_BUFFER_ENABLED` | `true` | Active le ring buffer admin |
| `LOG_BUFFER_SIZE` | `1000` | Taille du ring buffer |
| `ADMIN_DEMO_MODE` | `false` | Bloque les writes admin (mode démo / staging) |
| `ADMIN_AUDIT_LOG_ENABLED` | `true` | Active le middleware audit-log |
| `ADMIN_AUDIT_LOG_RETENTION_DAYS` | `365` | Durée de rétention RGPD |
| `VAPI_SIGNATURE_DISABLED` | `false` | Désactive la vérif HMAC Vapi (dev local uniquement) |
| `SENTRY_DSN` | (vide) | Active Sentry |
| `SENTRY_ENVIRONMENT` | auto-détecté | `production` / `staging` / `development` |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.0` | Taux d'échantillonnage perf monitoring |
| `SENTRY_RELEASE` | git sha | Version envoyée à Sentry |

---

## 6. Migrations DB ajoutées

| Migration | Rôle |
|-----------|------|
| `034_admin_audit_log.sql` | Table `admin_audit_log` + indexes (RGPD) |

---

## 7. Points en suspens

### 7.1 Tests skipped (~19) — non investigués

Bloqué par un souci local Python 3.9 (`TypeError: Unable to evaluate type annotation 'int | None'`). La CI tourne en Python 3.11, donc ces tests s'exécutent bien en CI. Investigation reportée.

**À faire** : `pip install eval_type_backport` dans le venv local, puis `pytest -rs` pour voir les vraies raisons des skips.

### 7.2 Audits CI bloquants

Pour l'instant les jobs `audit-deps-python` et `audit-deps-node` ont `continue-on-error: true`. À retirer une fois les CVE upstream nettoyées.

### 7.3 Sentry frontend

Pas configuré. Pour ajouter `@sentry/react`, voir la section "Bonus" de `docs/SENTRY.md`.

### 7.4 Coverage > 50%

Le seuil actuel est conservatif. À augmenter progressivement vers 70-80%.

---

## 8. Pour reprendre rapidement

Si tu reviens dessus dans X semaines, voici l'ordre de lecture recommandé :

1. **Ce doc** (vue d'ensemble)
2. [`AUDIT_SECURITE_2026-05.md`](AUDIT_SECURITE_2026-05.md) — état des recommandations sécu (qu'est-ce qui est fixé, qu'est-ce qu'il reste)
3. [`OBSERVABILITE.md`](OBSERVABILITE.md) — comment debug en prod (logs, request_id, LogsPanel)
4. [`AUDIT_LOG_ADMIN.md`](AUDIT_LOG_ADMIN.md) — la table `admin_audit_log` et son usage
5. Les autres docs au besoin (cf. tableau en haut)

Toutes les nouvelles fonctionnalités ont :
- Une doc dédiée dans `docs/`
- Des tests dans `tests/`
- Des variables d'env documentées dans `.env.example`
- Un panel UI dans Admin Monitoring (quand pertinent)
