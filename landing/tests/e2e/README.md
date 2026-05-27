# Tests E2E Playwright — Admin UWi

Smoke tests automatisés sur la zone admin. Conçus pour tourner contre un backend
en **mode démo** (lecture seule, dataset factice) — voir
[`docs/ADMIN_DEMO_MODE.md`](../../../docs/ADMIN_DEMO_MODE.md).

## Pré-requis

1. **Backend** lancé sur `http://localhost:8000` avec :
   ```bash
   ADMIN_DEMO_MODE=true
   ADMIN_EMAIL=admin@uwiapp.com       # ou ce que tu as dans .env
   ADMIN_PASSWORD=adminuwi123
   ```

2. **Frontend** lancé sur `http://localhost:3000` :
   ```bash
   cd landing && npm run dev
   ```

3. **Navigateurs Playwright** installés :
   ```bash
   cd landing && npx playwright install chromium
   ```

## Lancement

```bash
# Mode headless (CI / vérification rapide)
npm run test:e2e

# Mode UI interactif (recommandé en dev)
npm run test:e2e:ui

# Voir le navigateur s'ouvrir
npm run test:e2e:headed
```

## Variables d'environnement

| Variable | Default | Rôle |
|---|---|---|
| `E2E_BASE_URL` | `http://localhost:3000` | URL du frontend |
| `E2E_API_BASE_URL` | `http://localhost:8000` | URL du backend |
| `E2E_ADMIN_EMAIL` | `admin@uwiapp.com` | Email login |
| `E2E_ADMIN_PASSWORD` | `adminuwi123` | Mot de passe login |

Exemple ciblant un staging :

```bash
E2E_BASE_URL=https://staging.uwiapp.com \
E2E_API_BASE_URL=https://api-staging.uwiapp.com \
E2E_ADMIN_EMAIL=admin-staging@uwiapp.com \
E2E_ADMIN_PASSWORD=secret \
npm run test:e2e
```

## Tests inclus

| Fichier | Couvre |
|---|---|
| `admin-login.spec.js` | Page login, login valide / invalide, redirection |
| `admin-dashboard.spec.js` | Dashboard chargé, KPIs, bannière démo, payload API |
| `admin-tenants.spec.js` | Liste clients, mode démo désactive création, drill-down détail |

## Architecture

- `fixtures/auth.js` — fixture Playwright partagée. Vérifie le mode démo, gère le login admin réutilisable via `loggedInPage`.
- `playwright.config.js` (à la racine `landing/`) — config principale, projet Chromium, traces sur retry, screenshots sur échec.

## Rapports

Après un run, le rapport HTML est dans `playwright-report/`. Pour l'ouvrir :

```bash
npx playwright show-report
```

## Troubleshooting

**Erreur `ADMIN_DEMO_MODE n'est pas active`**
→ Le backend doit être lancé avec `ADMIN_DEMO_MODE=true`. Le fixture vérifie via `GET /api/admin/_meta`.

**Erreur de timeout sur le login**
→ Vérifier que les identifiants `E2E_ADMIN_EMAIL` / `E2E_ADMIN_PASSWORD` correspondent à ceux du backend (`.env` du backend, variables `ADMIN_EMAIL` / `ADMIN_PASSWORD`).

**Backend injoignable**
→ Vérifier qu'il tourne sur `:8000` ou ajuster `E2E_API_BASE_URL`.

## CI

Pour intégrer dans une GitHub Action :

```yaml
- name: Install dependencies
  run: cd landing && npm ci
- name: Install Playwright browsers
  run: cd landing && npx playwright install --with-deps chromium
- name: Start backend (demo mode)
  run: |
    cd backend && ADMIN_DEMO_MODE=true python -m uvicorn main:app --port 8000 &
    sleep 5
- name: Start frontend
  run: |
    cd landing && npm run build && npm run preview -- --port 3000 &
    sleep 5
- name: Run E2E
  run: cd landing && npm run test:e2e
- uses: actions/upload-artifact@v4
  if: always()
  with:
    name: playwright-report
    path: landing/playwright-report/
```
