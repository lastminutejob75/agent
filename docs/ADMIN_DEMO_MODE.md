# Admin — Mode démo (lecture seule)

> **TL;DR** — Active `ADMIN_DEMO_MODE=true` côté backend pour servir un dataset factice et bloquer toutes les écritures admin. Idéal pour valider l'UI/UX, faire des démos, ou développer l'admin sans Postgres ni vraies données.

---

## 1. Pourquoi ce mode

L'admin UWi consomme une vingtaine d'endpoints qui s'appuient sur **Postgres** (tenants, calls, leads, billing, quality, etc.). En local ou en staging on n'a pas toujours :

- une base Postgres avec des données réalistes,
- des comptes Stripe / Vapi / Twilio branchés,
- des appels et leads existants pour peupler les listes.

Le mode démo résout ce problème en injectant un **dataset factice cohérent** (8 cabinets, ~60 appels, 12 leads, plans tarifaires, factures, etc.) directement dans le backend. Le frontend n'a aucune modification à faire — il consomme les mêmes endpoints.

En complément, **toutes les écritures admin (POST/PUT/PATCH/DELETE) sont bloquées par un middleware** : le mode est strictement read-only, ce qui évite tout effet de bord pendant une démo.

---

## 2. Activation / désactivation

### Activer

Dans `.env` (ou `.env.local`) du backend :

```bash
ADMIN_DEMO_MODE=true
```

Valeurs reconnues : `true`, `1`, `yes`, `on` (insensible à la casse).
Tout le reste (vide, `false`, `0`) désactive le mode.

Au démarrage de FastAPI, un log warning apparaît :

```
[ADMIN_DEMO_MODE] active : les endpoints admin retournent un dataset factice
```

### Désactiver

Soit retirer la variable, soit la mettre à `false`. Redémarrer le backend.

```bash
ADMIN_DEMO_MODE=false
```

---

## 3. Architecture

### Backend (`backend/admin_demo/`)

```
backend/admin_demo/
├── __init__.py     # is_demo_mode() : lit l'env
├── dataset.py      # Dataset deterministe (seed fixe) : tenants, calls, leads...
└── router.py       # Endpoints alternatifs (memes paths que routes/admin.py)
```

- **`dataset.py`** : génère un état complet en RAM avec un seed fixe → mêmes données à chaque démarrage. 8 tenants, ~60 appels par tenant, 12 leads, factures Stripe simulées, FAQ, créneaux, etc.
- **`router.py`** : duplique les endpoints critiques de `routes/admin.py` (lecture seule), avec la **même auth** (cookie ou Bearer) via `_verify_admin`.

### Montage (priorité de matching)

Dans `backend/main.py`, le router démo est monté **avant** le router admin standard :

```python
if _is_admin_demo():
    from backend.admin_demo.router import router as _admin_demo_router
    app.include_router(_admin_demo_router)
app.include_router(admin.router)
```

FastAPI matche la première route trouvée → en mode démo, les routes communes vont au router démo, les autres tombent naturellement sur le router admin standard (auth, etc.).

### Middleware write-block (`backend/main.py`)

Une deuxième barrière intercepte toute requête write sur `/api/admin/*` :

```python
@app.middleware("http")
async def admin_demo_write_block(request, call_next):
    # GET/HEAD/OPTIONS : pass
    # /api/admin/auth/* : pass (login, logout, status, me)
    # Sinon, en mode demo : 403 avec un message explicite
```

Réponse en cas de blocage :

```json
{
  "detail": "Action desactivee en mode demo. Mettre ADMIN_DEMO_MODE=false pour reactiver.",
  "demo_mode": true
}
```

### Frontend (`landing/src/admin/`)

- **`DemoModeProvider.jsx`** — Provider React qui interroge `GET /api/admin/_meta` au montage (endpoint public, pas d'auth) et expose le hook `useDemoMode()` :

  ```jsx
  const { isDemoMode, datasetLabel, tenantsCount } = useDemoMode();
  ```

- **`AdminLayout.jsx`** affiche un bandeau et un badge si `isDemoMode` est `true`.

- **Helper `demoDisabled(isDemoMode, label)`** (dans `DemoModeProvider.jsx`) — produit `disabled` + `title` pour désactiver les boutons d'écriture avec un tooltip explicite :

  ```jsx
  <button {...demoDisabled(isDemoMode, "Annuler abonnement")} onClick={...}>
    Annuler abonnement
  </button>
  ```

  Désactivé proprement dans : `AdminBillingSection`, `AdminOperations`, `AdminTenantsList` (Créer client), `AdminTenantPage` (Voir comme client), `TenantCreationWizard`, `AdminLeadDetail` (write actions).

---

## 4. Endpoint méta (`/api/admin/_meta`)

**GET `/api/admin/_meta`** — public, pas d'auth requise. Le frontend l'utilise pour détecter le mode au montage.

```json
{
  "demo_mode": true,
  "tenants_count": 8,
  "dataset_label": "Dataset factice (8 cabinets, 60+ appels, 12 leads)"
}
```

En mode normal :

```json
{
  "demo_mode": false,
  "tenants_count": null,
  "dataset_label": null
}
```

---

## 5. Endpoints couverts (lecture seule)

| Catégorie | Endpoint | Rôle |
|-----------|----------|------|
| Méta | `GET /api/admin/_meta` | Détection mode démo |
| Tenants | `GET /api/admin/tenants` | Liste basique |
|  | `GET /api/admin/tenants/enriched` | Liste avec KPIs (page principale) |
|  | `GET /api/admin/tenants/{id}` | Détail tenant |
|  | `GET /api/admin/tenants/{id}/dashboard` | Vue dashboard |
|  | `GET /api/admin/tenants/{id}/technical-status` | Vapi/Stripe/Twilio status |
|  | `GET /api/admin/tenants/{id}/billing` | Facturation détail |
|  | `GET /api/admin/tenants/{id}/usage` | Minutes consommées |
|  | `GET /api/admin/tenants/{id}/quota` | Plan + dépassement |
|  | `GET /api/admin/tenants/{id}/billing/invoices` | Factures Stripe |
|  | `GET /api/admin/tenants/{id}/activity` | Activité récente |
|  | `GET /api/admin/tenants/{id}/faq` | FAQ tenant |
| Calls | `GET /api/admin/calls` | Liste appels (tous tenants) |
|  | `GET /api/admin/tenants/{id}/calls/{call_id}` | Détail appel + transcript |
| Leads | `GET /api/admin/leads` | Liste leads |
|  | `GET /api/admin/leads/count-new` | Compteur nouveaux |
|  | `GET /api/admin/leads/{id}` | Détail lead + journal |
| Stats | `GET /api/admin/stats/global` | KPIs globaux |
|  | `GET /api/admin/stats/dashboard-payload` | Payload complet du dashboard |
|  | `GET /api/admin/stats/billing-snapshot` | Snapshot revenue |
|  | `GET /api/admin/stats/platform-health` | Santé plateforme |
|  | `GET /api/admin/stats/operations-snapshot` | Risques opérationnels |
|  | `GET /api/admin/stats/quality-snapshot` | Métriques qualité (anti-loop, abandons, transferts) |
| Billing | `GET /api/admin/billing/overview` | Vue billing globale |
|  | `GET /api/admin/billing/plans` | Catalogue de plans |
| Provisioning | `GET /api/admin/twilio/numbers` | Numéros Twilio dispos (wizard création) |

> **Note** : tous les endpoints non listés ici (write notamment) tombent sur le router admin standard et sont **bloqués 403 par le middleware** en mode démo.

---

## 6. Authentification en mode démo

L'auth fonctionne normalement : il faut toujours se connecter avec un compte admin.

Identifiants par défaut (configurables via `.env`) :

```bash
ADMIN_EMAIL=admin@uwiapp.com
ADMIN_PASSWORD=adminuwi123
ADMIN_API_TOKEN=...   # optionnel, pour requêtes Bearer
```

Endpoints autorisés sans blocage write-block :

- `POST /api/admin/auth/login`
- `POST /api/admin/auth/logout`
- `GET /api/admin/auth/status`
- `GET /api/admin/auth/me`

---

## 7. Limitations connues

1. **Données figées** : le dataset est régénéré à chaque démarrage avec le même seed → mêmes IDs, mêmes appels, mêmes leads. Si l'on veut faire « bouger » les chiffres, il faut redémarrer.
2. **Pas de persistence** : ajouter un lead, modifier un tenant → impossible (write bloqué). Côté UI, les boutons concernés sont désactivés avec un tooltip.
3. **Pas de Vapi / Stripe / Twilio réels** : tous les IDs externes sont factices (`vapi-demo-xxx`, `cus_demo_xxx`, `+331866523xx`).
4. **Pas de webhooks** : les webhooks Stripe / Vapi ne sont pas simulés. Le mode démo ne couvre que la lecture/visualisation, pas le cycle de vie réel.
5. **Performance** : tout est en RAM, pas de pagination sur le dataset complet → suffisant pour 8 tenants, à revoir si on veut 1000+.

---

## 8. Cas d'usage typiques

### Local frontend-only (sans Postgres)

Idéal pour un dev frontend qui veut iterér sur l'UI sans setup backend complet :

```bash
# .env backend
ADMIN_DEMO_MODE=true

# Lancer backend (sqlite local + dataset démo)
cd backend && python -m uvicorn main:app --reload --port 8000

# Lancer frontend
cd landing && npm run dev
```

### Démo client / pitch

Activer en staging pour montrer l'admin avec des données réalistes sans risque de fuite de données réelles ou de modification accidentelle.

### Tests E2E

Le mode démo est aussi pratique pour Playwright : dataset déterministe, pas de seed à faire, pas de cleanup. Voir `docs/E2E_PLAYWRIGHT.md` (à venir).

---

## 9. FAQ

**Q : Le bandeau démo apparaît mais je veux le cacher pour une démo.**
R : Le bandeau est rendu dans `AdminLayout.jsx` conditionnellement sur `isDemoMode`. Pour le masquer, soit désactiver le mode, soit cacher temporairement en commentant le bloc dans le layout.

**Q : Je veux ajouter un nouveau tenant fictif.**
R : Modifier `backend/admin_demo/dataset.py` (constantes `TENANTS_SEED` ou la fonction `_generate_tenants`). Redémarrer le backend.

**Q : Comment tester un endpoint write sans désactiver le mode démo ?**
R : Pas possible — c'est volontaire. Désactiver `ADMIN_DEMO_MODE` et brancher une vraie DB.

**Q : Le mode démo fonctionne-t-il en production ?**
R : Techniquement oui, mais **fortement déconseillé**. Le mode est conçu pour staging/dev. En prod, il masquerait toutes les vraies données et bloquerait les actions admin.

---

## 10. Voir aussi

- `backend/admin_demo/dataset.py` — Source de vérité pour le contenu du dataset.
- `backend/admin_demo/router.py` — Mapping endpoint ↔ donnée mock.
- `backend/main.py` (lignes 87–161) — Middleware write-block + montage du router.
- `landing/src/admin/DemoModeProvider.jsx` — Hook React + helper `demoDisabled`.
- `docs/ADMIN_LOGIN_COOKIE.md` — Setup auth (cookies SameSite).
