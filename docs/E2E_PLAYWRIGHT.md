# Tests E2E Playwright

Tests end-to-end de l'app UWi (login admin + onboarding public + page publique + exports CSV).

## Vue d'ensemble

| Composant | Fichier |
|-----------|---------|
| Config | `landing/playwright.config.js` |
| Fixtures partagés | `landing/tests/e2e/fixtures/auth.js` |
| Specs | `landing/tests/e2e/*.spec.js` |
| Workflow CI | `.github/workflows/e2e-tests.yml` |

Suites disponibles :

- `admin-login.spec.js` — page de login + login valide + login invalide
- `admin-dashboard.spec.js` — dashboard admin charge (KPIs, sidebar, bannière démo)
- `admin-tenants.spec.js` — liste clients + page détail tenant
- `admin-exports.spec.js` — export CSV calls/bookings + bouton "Exporter CSV"
- `onboarding.spec.js` — wizard public `/creer-assistante` (étape 1 → 2 → retour)
- `public-page.spec.js` — page publique `/p/cabinet-dupond-demo`

## Pré-requis

Pour lancer les tests, il faut un backend **en mode démo** + un frontend Vite servis simultanément.

### En local

```bash
# Terminal 1 — backend
ADMIN_DEMO_MODE=true \
  ADMIN_EMAIL=admin@uwiapp.com \
  ADMIN_PASSWORD=adminuwi123 \
  JWT_SECRET=local-secret-min-32-bytes \
  uvicorn backend.main:app --port 8000 --reload

# Terminal 2 — frontend
cd landing
npm run dev   # http://localhost:3000

# Terminal 3 — Playwright
cd landing
npm run test:e2e          # headless, tous les tests
npm run test:e2e:ui       # mode UI interactif (recommande)
npm run test:e2e:headed   # voir le navigateur
```

Le backend en mode démo retourne un dataset mocké (pas de DB requise) et autorise le login `admin@uwiapp.com / adminuwi123`. Cf. `docs/ADMIN_DEMO_MODE.md`.

### Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `E2E_BASE_URL` | `http://localhost:3000` | URL frontend (Vite) |
| `E2E_API_BASE_URL` | `http://localhost:8000` | URL backend |
| `E2E_ADMIN_EMAIL` | `admin@uwiapp.com` | Login admin |
| `E2E_ADMIN_PASSWORD` | `adminuwi123` | Password admin |

## En CI

Le workflow `.github/workflows/e2e-tests.yml` :

1. Installe Python 3.11 + Node 20.
2. Installe les dépendances Python (`requirements.txt`) et Node (`landing/package.json`).
3. Installe les browsers Playwright (chromium uniquement).
4. Lance le backend FastAPI en mode démo (`ADMIN_DEMO_MODE=true`) sur :8000.
5. Build le frontend (`npm run build`) puis sert via `vite preview` sur :3000.
6. Attend que les 2 services répondent sur leurs ports (max 60s chacun).
7. Lance `npx playwright test --reporter=list`.
8. Upload le rapport HTML + les logs en cas d'échec.

Le job tourne sur chaque push/PR sur `main` ou `master`. Le rapport HTML est conservé 14 jours dans les artefacts GitHub.

## Architecture des tests

### Fixtures (`fixtures/auth.js`)

- `demoMeta` : vérifie au démarrage que le backend tourne en mode démo (sinon throw → tests skipped).
- `loggedInPage` : page Playwright avec un admin déjà connecté (cookie session posé).

### Pattern courant

```javascript
import { test, expect } from "./fixtures/auth.js";

test("mon test", async ({ loggedInPage: page }) => {
  await page.goto("/admin/calls");
  await expect(page.getByRole("heading", { name: /Appels/i })).toBeVisible();
});
```

### Tester l'API directement

```javascript
test("export CSV", async ({ loggedInPage: page, request }) => {
  const cookies = await page.context().cookies();
  const cookieHeader = cookies.map((c) => `${c.name}=${c.value}`).join("; ");
  const res = await request.get(`${API_BASE_URL}/api/admin/exports/calls.csv`, {
    headers: { cookie: cookieHeader },
  });
  expect(res.ok()).toBeTruthy();
});
```

## Ajouter un nouveau scénario

1. Créer `landing/tests/e2e/mon-scenario.spec.js`.
2. Importer `import { test, expect } from "./fixtures/auth.js";` (page connectée) ou `from "@playwright/test";` (page anonyme).
3. Préférer les sélecteurs accessibles : `getByRole("button", { name: /.../i })` plutôt que `locator("css")`.
4. Lancer `npm run test:e2e:ui` pour debugger interactivement.
5. Une fois stable, push : la CI le passera automatiquement.

## Stratégie de sélecteurs

Du plus stable au plus fragile :

1. `getByRole("heading", { name: /xxx/i })` — accessible et robuste.
2. `getByPlaceholder("...")` — stable si placeholder peu changé.
3. `locator("[data-testid='...']")` — à ajouter dans le code si besoin.
4. `locator("text=/regex/i")` — fallback, peut casser sur changements de copie.
5. `locator("css.classname")` — à éviter sauf cas marginal.

## Limitations connues

- **Pas de tests cross-browser** (chromium seulement). Suffit pour 95% des bugs UI. Activable via `playwright.config.js > projects` si besoin.
- **Pas de tests mobile** (viewport desktop par défaut). À ajouter si l'app évolue vers mobile-first.
- **Tests dépendants du dataset démo** : si on modifie `backend/routes/admin_demo/`, les assertions sur les valeurs précises peuvent casser. Préférer les assertions structurelles (présence d'un élément) plutôt que numériques (≥ 5 calls).
- **Onboarding wizard** : on teste seulement les 2 premières étapes. Le parcours complet (7 étapes) demande de mocker plus de state.

## Lien avec les autres docs

- `docs/ADMIN_DEMO_MODE.md` — Mode démo backend (dataset mocké).
- `docs/EXPORTS_CSV.md` — Endpoints CSV testés par `admin-exports.spec.js`.
- `docs/TESTS_BACKEND.md` — Tests unitaires Python (pytest).
