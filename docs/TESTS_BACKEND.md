# Tests unitaires backend

Documentation de la suite de tests Python (pytest) du backend FastAPI.

## Lancer les tests

```bash
# Toute la suite
python3 -m pytest

# Un seul fichier
python3 -m pytest tests/test_lead_tokens.py -v

# Un seul test
python3 -m pytest tests/test_lead_tokens.py::test_verify_token_expired -v

# Sous-ensemble par mot-cle
python3 -m pytest -k "lead_token or pre_onboarding"

# Mode rapide (sans tracebacks longues)
python3 -m pytest --tb=line -q
```

## Configuration

- Definie dans `pyproject.toml` (`[tool.pytest.ini_options]`).
- Repertoire des tests : `tests/`.
- Pattern : `test_*.py`.
- Fixture globale dans `tests/conftest.py` :
  - Force `JWT_SECRET`, `ADMIN_API_TOKEN` (eviter 503).
  - Force `ADMIN_DEMO_MODE=""` et `ENABLE_DEBUG_ENDPOINTS=""` (sinon le `.env` peut faire echouer 22 tests admin).
  - Force `VAPI_SIGNATURE_DISABLED=true` (skip verif signature Vapi pour les ~800 tests qui n'envoient pas de signature ; les tests dedies reactivent via `monkeypatch`).
  - Fixture `admin_db_sqlite` autouse pour `test_admin_*` : isole sur SQLite avec tenants 1 et 2.

## Etat de la suite

| Categorie | Tests | Statut |
|---|---:|---|
| **Audit securite 2026-05** (nouveaux) | 102 | OK |
| **Observabilite 2026-05** (`test_log_setup.py`) | 22 | OK |
| Logique metier (FAQ, Vapi, FSM, calendrier, etc.) | ~760 | OK |
| Twilio provisioning | 12 | OK |
| Total | **896 passed / 19 skipped / 0 failed** | ✅ |

Les 19 tests `skipped` restants concernent des scenarios produit non encore reactives (refactors specifiques, configs externes manquantes en CI, etc.) ; les 5 tests skipped majoritaires de la passe precedente ont ete reecrits :

- `tests/test_admin_api.py::test_get_calls_list_*` — reecrits avec mock `backend.pg_pool.pg_connection` au lieu de `psycopg.connect`. **Bug latent fixe** : `cursor_ts`/`cursor_id` non initialises dans `_get_calls_list` quand le fallback `ivr_events` etait utilise (NameError silencieux en prod).
- `tests/test_call_lock_pg.py::test_lock_*` — remplaces par 3 tests unitaires sur `_pg_lock_ok()` (fast-paths actions ne declenchent plus le lock PG, scenario change).
- `tests/test_vapi_live_transfer.py::test_maybe_start_terminal_booking_end_*` — reecrit pour valider le nouveau pattern thread daemon + scheduling end-call (au lieu de mute+say HTTP).
- `tests/test_cancel_modify_faq.py::test_cancel_rdv_pas_trouve_*` — reactive en tolerant les deux comportements valides (alternatives intermediaires OU transfert direct si agenda inaccessible).

## Tests d'audit securite (nouveaux)

Ajoutes lors de l'audit securite 2026-05. Couvrent les fixs documentes dans `docs/AUDIT_SECURITE_2026-05.md`.

### `tests/test_lead_tokens.py` (18 tests)

Tests unitaires du module `backend/lead_tokens.py` (signature HMAC pour pre-onboarding).

- Format `v1.{lead}.{exp}.{sig}` (4 parties).
- Round-trip `make_lead_token` / `verify_lead_token`.
- Edge cases : token vide, malforme, version inconnue, signature falsifiee, lead_id falsifie, expire, secret absent.
- Helpers : extraction depuis query string `?token=`, header `X-Lead-Token`, priorite query > header.
- Chaine de fallback secret : `LEAD_TOKEN_SECRET` > `JWT_SECRET` > `ADMIN_SESSION_SECRET`.
- Verifie que le token est URL-safe.

### `tests/test_pre_onboarding_security.py` (16 tests)

Tests d'integration des endpoints `/api/pre-onboarding/*` proteges par token HMAC.

- `POST /commit` retourne un `token` non vide, verifiable.
- `GET /leads/{id}/check` : 401 sans token, 403 si invalide, 410 si expire, 403 si lead_id mismatch.
- `GET /leads/{id}/email` : meme matrice.
- `POST /leads/{id}/callback-booking` : meme matrice.
- `POST /leads/{id}/create-account` : meme matrice.
- Bypass admin via `Authorization: Bearer ADMIN_API_TOKEN`.
- Token via header `X-Lead-Token` (alternative a la query).

### `tests/test_admin_security_audit.py` (9 tests)

Tests des fixs cote admin.

- `GET /api/admin/auth/status` sans auth : payload reduit (`login_configured` uniquement, pas de leak `email_set`/`password_*`/`jwt_secret_set`).
- Avec Bearer admin : payload complet expose.
- `POST /api/public/onboarding` : ne retourne JAMAIS `admin_setup_token` (regression-test).
- `OnboardingResponse` Pydantic : champ `admin_setup_token` absent du modele.
- `POST /api/admin/auth/logout` : reste public (clear cookie).
- Smoke : `/api/admin/tenants`, `/api/admin/leads`, `/api/admin/calls` → 401 sans auth.

### `tests/test_debug_endpoints_guard.py` (17 tests)

Tests du middleware `debug_endpoints_guard` (`backend/main.py`).

- `/debug/config`, `/debug/env-vars`, `/debug/force-load-credentials` : 403 sans auth.
- `/api/stats/bookings` : 403 sans auth.
- Bypass via `ENABLE_DEBUG_ENDPOINTS=true` (insensible a la casse, accepte `true|1|yes|on`).
- Bypass via `ADMIN_DEMO_MODE=true`.
- Bypass via `Authorization: Bearer ADMIN_API_TOKEN`.
- `/api/vapi/test-calendar` et `/api/vapi/test` : meme matrice (depend par endpoint).
- Verifie que `/health` et `/api/admin/*` ne sont pas affectes par le guard.

### `tests/test_public_analytics_auth.py` (7 tests)

Tests de l'auth ajoutee sur `GET /api/public/analytics/{slug}/summary`.

- 401 sans aucune auth (avant l'audit, c'etait public).
- Bypass via Bearer admin.
- Bearer invalide → 401.
- Helpers `_is_admin_authenticated` et `_tenant_owns_slug` : retournent False sans auth, True avec Bearer admin valide.

### `tests/test_vapi_security.py` (35 tests)

Tests de la signature des webhooks Vapi (`backend/vapi_security.py`).

- **Helper `verify_vapi_signature`** : modes `disabled` / `no_secret` / shared secret valide / shared secret invalide / HMAC valide / HMAC avec prefixe `sha256=` / HMAC invalide / HMAC valide pour body different / sans header → `missing` / `X-Vapi-Secret` prioritaire sur HMAC / case-insensitive / body vide.
- **`is_strict_mode()`** : parsing de `VAPI_REQUIRE_SIGNATURE` (`true/1/yes/on` → True, reste → False).
- **Integration `/api/vapi/webhook`** : mode souple sans signature → 200 + warning ; mode strict sans signature → 401 ; shared secret valide → 200 ; HMAC valide → 200 ; signature invalide → 401 ; `VAPI_SIGNATURE_DISABLED=true` override mode strict → 200.
- **Integration `/api/vapi/tool`** : meme matrice (signature obligatoire en strict, libre en souple).
- **Helper `make_test_signature`** : retourne une signature HMAC valide pour les tests, leve si pas de secret.

### `tests/test_log_setup.py` (22 tests)

Tests des logs structures (`backend/log_setup.py`). Cf. [`OBSERVABILITE.md`](./OBSERVABILITE.md).

- **`LogBuffer`** : append, maxlen, filtre par niveau (case-insensitive), clear, limit cap.
- **`request_id` contextvar** : defaut "", set/reset.
- **`JsonFormatter`** : JSON valide, champs `extra={...}`, `request_id` propage, valeurs non-serialisables stringifiees.
- **`BufferHandler`** : integration avec `logging.getLogger` (un `logger.info(extra=...)` arrive bien dans le buffer).
- **`configure_logging()`** : idempotence (pas de duplication des handlers tagges), activation `JsonFormatter` via `LOG_JSON=true`.
- **Middleware HTTP** : header `X-Request-ID` dans la reponse, reutilise le header client si fourni, log `request_end` en buffer avec `path`/`method`/`status_code`/`duration_ms`/`request_id`.
- **`GET /api/admin/logs/recent`** : 401 sans auth, OK avec Bearer admin, `limit` respecte (1-1000), `level` filtre, validation des bornes (limit=0 → 422, limit=10000 → 422).

## Ecrire un nouveau test

### Pattern de base

```python
import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def admin_headers():
    return {"Authorization": f"Bearer {os.environ.get('ADMIN_API_TOKEN', 'test-admin-token-pytest')}"}


def test_endpoint_requires_auth(client):
    r = client.get("/api/admin/tenants")
    assert r.status_code == 401


def test_endpoint_with_admin_works(client, admin_headers):
    r = client.get("/api/admin/tenants", headers=admin_headers)
    assert r.status_code != 401
```

### Mocker la DB

Pour eviter de toucher Postgres :

```python
from unittest.mock import patch

with patch("backend.routes.pre_onboarding.lead_exists", return_value=True):
    r = client.get(...)
```

### Override d'env locale a un test

```python
def test_with_flag(client, monkeypatch):
    monkeypatch.setenv("ENABLE_DEBUG_ENDPOINTS", "true")
    r = client.get("/debug/config")
    assert r.status_code == 200
```

Note : utiliser `setenv("MA_VAR", "")` plutot que `delenv("MA_VAR")` quand un module fait `load_dotenv()` a l'import (sinon la variable est rechargee depuis `.env` au premier import).

## CI

Suggestion `.github/workflows/tests.yml` (a configurer si besoin) :

```yaml
name: Tests backend

on:
  pull_request:
    paths:
      - 'backend/**'
      - 'tests/**'
      - 'pyproject.toml'

jobs:
  pytest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python -m pytest -q
        env:
          JWT_SECRET: ci-jwt-secret-32-bytes-minimum-required
          ADMIN_API_TOKEN: ci-admin-token
          ADMIN_DEMO_MODE: ""
          ENABLE_DEBUG_ENDPOINTS: ""
```

## Couverture

La CI mesure la couverture (`pytest --cov=backend`) et impose un seuil minimal via `--cov-fail-under=50`.

```bash
# En local
python -m pytest --cov=backend --cov-report=term-missing:skip-covered

# Avec seuil
python -m pytest --cov=backend --cov-fail-under=50
```

### Politique d'augmentation

Le seuil actuel de **50%** est volontairement bas pour ne pas bloquer la CI au moment de l'introduction. À mesure que la suite se développe, augmenter par paliers :

1. **50%** (actuel) — point de départ.
2. **60%** — après ajout des tests pour les modules backend critiques (`exports.py`, `health_checks.py`, etc.).
3. **70%** — quand le projet est en croissance maitrisée (~6 mois).
4. **75-80%** — objectif long terme. Pas de raison d'aller plus haut sur un projet métier (le coût marginal devient prohibitif).

À chaque PR augmentant le seuil, vérifier le rapport coverage.xml pour identifier les fichiers à couvrir en priorité (handlers HTTP, helpers de calcul, intégrations externes).

### Modules à exclure

Si un module a une couverture délibérément faible (ex: code de scaffolding, scripts CLI), le marquer dans `pyproject.toml` :

```toml
[tool.coverage.run]
omit = ["backend/scripts/**", "backend/migrations/**"]
```

## Historique

- 2026-05 : audit securite — ajout de 67 tests d'audit + neutralisation de `ADMIN_DEMO_MODE` dans `conftest.py` (a re-fait passer 22 tests admin pre-existants).
- 2026-05 : ajout du seuil minimal de couverture `--cov-fail-under=50` en CI.
