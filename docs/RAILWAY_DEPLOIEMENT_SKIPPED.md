# Railway : déploiements SKIPPED ou REMOVED

## Pourquoi tu voyais « SKIPPED — No changes to watched files »

Railway ne déployait que si certains dossiers changeaient (`backend/**`, `frontend/**`, etc.).
Les correctifs agenda modifiaient souvent **uniquement** `landing/` (front Vercel) → Railway **ignorait** le commit, même si tu pensais avoir « tout poussé ».

| Dossier modifié | Où ça part |
|-----------------|------------|
| `landing/**` | **Vercel** (uwiapp.com) |
| `backend/**` | **Railway** (API) |
| Les deux | Railway **et** Vercel |

## SKIPPED vs REMOVED

- **SKIPPED** : aucun fichier « surveillé » dans le commit (souvent landing seul).
- **REMOVED** : ancien déploiement remplacé ou supprimé (normal quand un nouveau deploy réussit).

## Depuis juin 2026

`watchPatterns` a été **retiré** de `railway.toml` : **chaque push sur `main` redéploie Railway**.

## Vérifier la version live

```bash
curl -s https://agent-production-c246.up.railway.app/health
```

Réponse attendue : `{"status":"ok","git_sha":"xxxxxxxx"}` (8 premiers caractères du commit GitHub).

Comparer avec :

```bash
git rev-parse --short=8 HEAD
```

## Forcer un redeploy manuel (dashboard)

1. [railway.app](https://railway.app) → projet **cooperative-insight**
2. Service **backend** (domaine `*.up.railway.app`)
3. **Deployments** → dernier deploy → **⋮** → **Redeploy**

## Variables « inactive »

Voir [RAILWAY_FIX_VARIABLES_INACTIVES.md](./RAILWAY_FIX_VARIABLES_INACTIVES.md).
