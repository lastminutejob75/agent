# Unification uwiapp.com ↔ agent (monorepo)

Un seul dépôt source : **agent** (https://github.com/lastminutejob75/agent.git).

## État actuel

| Repo | Contenu | Déploiement |
|------|---------|-------------|
| **agent** | Backend + landing + admin + dashboard | Railway (backend) |
| **uwi-landing** | Landing (copie) | uwiapp.com (Vercel) |

## Option 1 : uwiapp.com déploie depuis agent (recommandé)

**Une seule source de vérité.** Plus de double dépôt.

### Étapes Vercel

1. Ouvrir [Vercel Dashboard](https://vercel.com) → Projet uwiapp.com
2. **Settings** → **Git** → **Connect Git Repository**
3. Désactiver le lien avec `uwi-landing`
4. Connecter **agent** : `https://github.com/lastminutejob75/agent`
5. **Root Directory** : `landing`
6. **Build Command** : `npm run build` (défaut)
7. **Output Directory** : `dist` (défaut)
8. **Environment Variables** : `VITE_UWI_API_BASE_URL` = URL backend Railway (ex: `https://xxx.railway.app`)
9. Redéployer

→ Chaque push sur `agent/main` met à jour automatiquement uwiapp.com.

### Variable d'environnement requise

| Variable | Valeur |
|----------|--------|
| `VITE_UWI_API_BASE_URL` | URL du backend Railway (ex: `https://xxx.railway.app`) |

### Après migration

Le dépôt `uwi-landing` peut être archivé sur GitHub :
- **Settings** → **Danger Zone** → **Archive this repository**

---

## Option 2 : Sync manuel (en attendant Option 1)

Si vous gardez temporairement uwi-landing comme source de déploiement :

```bash
./scripts/sync-landing-to-uwi-landing.sh
```

Ce script copie `landing/` vers uwi-landing et pousse sur GitHub. À lancer après chaque push sur agent.

---

## Structure agent (monorepo)

```
agent/
├── backend/          # FastAPI, engine, admin API
├── landing/          # Vite SPA (uwiapp.com)
│   ├── src/
│   │   ├── pages/    # Onboarding, Admin, AdminTenant, AdminTenantDashboard
│   │   └── ...
│   ├── package.json
│   └── vercel.json
├── frontend/         # Widget chat
└── ...
```
