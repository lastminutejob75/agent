# Récap technique : uwiapp.com ↔ Agent UWI

**Architecture cible :** 1 repo (agent), 2 hébergeurs (Vercel + Railway).

> Si Vercel pointe encore sur `uwi-landing`, voir [§3 Migration](#3-migration--repo-unifié-agent-seul) pour basculer sur `agent`.

---

## Schéma global

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           UTILISATEUR FINAL                                   │
└─────────────────────────────────────────────────────────────────────────────┘
           │                                    │
           │ https://uwiapp.com                 │ Appels téléphoniques
           │ (Landing + Admin + Onboarding)     │ Webhooks Vapi/WhatsApp
           ▼                                    ▼
┌──────────────────────────────┐    ┌──────────────────────────────────────────┐
│         VERCEL               │    │              RAILWAY                     │
│  ┌────────────────────────┐  │    │  ┌────────────────────────────────────┐ │
│  │  uwiapp.com            │  │    │  │  Backend FastAPI (agent)            │ │
│  │  (SPA Vite + React)    │──┼────┼─▶│  - /api/public/onboarding          │ │
│  │                        │  │    │  │  - /api/admin/* (tenants, dashboard)│ │
│  │  Root: landing/        │  │    │  │  - /api/vapi/webhook (vocal)        │ │
│  │  Build: npm run build  │  │    │  │  - /chat, /stream (widget)          │ │
│  │  Output: dist/         │  │    │  │  - /health                         │ │
│  └────────────────────────┘  │    │  └────────────────────────────────────┘ │
└──────────────────────────────┘    │                                         │
           │                        │  Repo: agent                            │
           │                        │  Build: Dockerfile                      │
           └────────────────────────┴────────────────────────────────────────────┘
                                    │
                    REPO UNIQUE: github.com/lastminutejob75/agent
```

---

## 1. uwiapp.com (frontend)

| Élément | Détail |
|---------|--------|
| **URL** | https://uwiapp.com |
| **Hébergeur** | Vercel |
| **Repo** | `github.com/lastminutejob75/agent` |
| **Root Directory** | `landing` |
| **Stack** | Vite 5, React 18, React Router, Tailwind CSS |
| **Build** | `npm run build` → `dist/` |
| **Framework détecté** | Vite (vercel.json) |

### Routes SPA

| Route | Page | Description |
|-------|------|-------------|
| `/` | UwiLanding | Landing marketing (Hero, sections, CTA) |
| `/onboarding` | Onboarding | Formulaire création tenant |
| `/admin` | Admin | Liste tenants (token requis) |
| `/admin/tenants/:id` | AdminTenant | Détail + Statut technique |
| `/admin/tenants/:id/dashboard` | AdminTenantDashboard | Dashboard temps réel |

### Variables d'environnement (Vercel)

| Variable | Description | Exemple |
|----------|-------------|---------|
| `VITE_UWI_API_BASE_URL` | URL publique du backend Railway | `https://agent-xxx.railway.app` |

---

## 2. Backend Agent (API)

| Élément | Détail |
|---------|--------|
| **URL** | Variable (ex. `https://agent-xxx.railway.app`) |
| **Hébergeur** | Railway |
| **Repo** | `github.com/lastminutejob75/agent` |
| **Stack** | Python 3.11, FastAPI, SQLite + Postgres (optionnel) |
| **Build** | Dockerfile → conteneur |
| **Port** | 8000 (ou `PORT` env) |

### Endpoints principaux

| Endpoint | Auth | Description |
|----------|------|-------------|
| `POST /api/public/onboarding` | — | Création tenant |
| `GET /api/admin/tenants` | Bearer | Liste tenants |
| `GET /api/admin/tenants/{id}` | Bearer | Détail tenant |
| `GET /api/admin/tenants/{id}/dashboard` | Bearer | Snapshot dashboard |
| `GET /api/admin/tenants/{id}/technical-status` | Bearer | Statut DID, calendrier, agent |
| `POST /api/vapi/webhook` | — | Webhook Vapi (vocal) |
| `POST /api/whatsapp/webhook` | — | Webhook Twilio (WhatsApp) |
| `GET /health` | — | Health check |

### Variables d'environnement (Railway)

| Variable | Description |
|----------|-------------|
| `ADMIN_API_TOKEN` | Token Bearer pour `/api/admin/*` |
| `DATABASE_URL` | Postgres (tenants, ivr_events) |
| `GOOGLE_SERVICE_ACCOUNT_BASE64` | Service Account Google Calendar |
| `GOOGLE_CALENDAR_ID` | Calendrier par défaut |
| `TWILIO_*` | Twilio (WhatsApp) |
| `PORT` | Port d'écoute (défaut 8000) |

---

## 3. Migration : repo unifié (agent seul)

**Avant :** 2 repos (agent + uwi-landing), sync manuel.  
**Après :** 1 repo (agent), plus de sync.

### Étapes pour basculer Vercel sur agent

1. **Vercel** → Projet uwiapp.com → Settings → Git
2. **Disconnect** le repo uwi-landing
3. **Connect Repository** → `lastminutejob75/agent`
4. **Settings → General** :
   - **Root Directory** : `landing` (cliquer Edit, saisir `landing`)
   - **Framework Preset** : Vite (ou détecté automatiquement)
   - **Build Command** : `npm run build`
   - **Output Directory** : `dist`
5. **Environment Variables** : `VITE_UWI_API_BASE_URL` = URL Railway
6. **Redeploy**

Une fois validé : le repo `uwi-landing` peut être archivé (Settings → Archive).

---

## 3.1 Sécuriser le monorepo

### Vercel (uwiapp.com)

Avec **Root Directory = landing** :
- Vercel exécute `npm install` et `npm run build` dans `landing/`
- Le fichier `landing/vercel.json` sert de config (framework Vite, output dist)
- Vérifier dans Vercel → Build & Output :
  - Framework preset : Vite
  - Build command : `npm run build`
  - Output directory : `dist`

### Railway (backend)

Pour éviter un rebuild inutile quand seul `landing/` change :

1. **`railway.toml`** : `watchPatterns` limite les déploiements aux changements backend :
   ```
   watchPatterns = ["backend/**", "frontend/**", "requirements.txt", "Dockerfile", "railway.toml", "migrations/**"]
   ```
   *Note : si le "new builder" Railway est activé, les watch paths peuvent être ignorés ; désactiver le new builder si besoin.*

2. **`.dockerignore`** : exclut `landing/`, `node_modules`, etc. du contexte Docker → build plus rapide.

### Domaine API (optionnel, plus tard)

`api.uwiapp.com` → CNAME vers Railway pour une config plus propre.

### Archiver uwi-landing

Avant d’archiver :
- Garder le repo en read-only quelques jours
- Ou ajouter un README : `DEPRECATED: moved to lastminutejob75/agent/landing`

---

## 4. Flux de données

```
uwiapp.com (Vercel)                    Backend (Railway)
        │                                      │
        │  VITE_UWI_API_BASE_URL                │
        │  (injecté au build)                   │
        │                                      │
        ├── POST /api/public/onboarding ──────▶│  Crée tenant
        │                                      │
        ├── GET /api/admin/tenants ───────────▶│  Bearer ADMIN_API_TOKEN
        ├── GET /api/admin/tenants/:id/dashboard ▶│
        ├── GET /api/admin/tenants/:id/technical-status ▶│
        │                                      │
        │  Token admin : localStorage          │
        │  (uwi_admin_token)                   │
        └──────────────────────────────────────┘
```

---

## 5. Récapitulatif

| Composant | Repo | Hébergeur | Domaine |
|-----------|------|-----------|---------|
| Landing + Admin | agent (landing/) | Vercel | uwiapp.com |
| Backend API | agent | Railway | xxx.railway.app |

**Flux :** Push sur `agent/main` → Railway redéploie le backend, Vercel redéploie uwiapp.com.

---

## 6. Checklist migration

Voir **`docs/CHECKLIST_MIGRATION_MONOREPO.md`** pour la checklist complète (Vercel, Railway, archivage uwi-landing).

---

## 7. Commandes utiles

```bash
# Lancer le backend en local
uvicorn backend.main:app --reload

# Lancer la landing en local
cd landing && npm run dev

# Build landing
cd landing && npm run build
```
