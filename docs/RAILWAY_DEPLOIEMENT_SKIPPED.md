# Railway : déploiements SKIPPED ou REMOVED

## Pourquoi presque tout était SKIPPED (« No changes to watched files »)

Deux causes cumulées :

1. **Dashboard Railway** : le service backend avait des « Watch Paths » limités (souvent `backend/**` seul).
2. **Retirer `watchPatterns` du `railway.toml`** ne vide pas le dashboard : sans valeur dans le fichier, Railway **réutilise** les chemins du dashboard → les commits qui ne touchent que `landing/` ou `tests/` étaient **ignorés**.

Ton travail n’était pas perdu sur GitHub : il n’était **pas déployé** sur l’API Railway.

## Où va ton code (monorepo)

| Dossier | Plateforme | URL |
|---------|------------|-----|
| `landing/**` | **Vercel** | https://www.uwiapp.com |
| `backend/**`, `migrations/**`, etc. | **Railway** | API `*.up.railway.app` |

Un commit **landing seul** doit quand même apparaître sur **Vercel** (pas Railway). Vérifie les déploiements Vercel du projet `agent`.

## Correction (juin 2026)

`railway.toml` et `railway.json` définissent une liste **explicite** de `watchPatterns` (backend, landing, tests, CI, …) pour **écraser** le dashboard à chaque deploy.

## À faire une fois sur Railway (dashboard)

1. [railway.app](https://railway.app) → projet **cooperative-insight**
2. Service **backend** (celui qui a l’URL `agent-production-….up.railway.app`)
3. **Settings** → section **Build** → **Watch Paths** / **Root Directory**
4. **Vide complètement** le champ Watch Paths (laisse vide) **ou** mets une seule ligne `**` si le champ est obligatoire
5. **Root Directory** doit rester `/` (racine du repo), pas un sous-dossier
6. **Deployments** → **Deploy latest commit** (ou Redeploy) pour forcer la version actuelle

La config dans le repo (`railway.toml`) prime sur le dashboard **pour chaque nouveau deploy**, mais vider le dashboard évite les surprises.

## SKIPPED vs REMOVED

- **SKIPPED** : Railway a décidé que le commit ne modifiait aucun fichier « surveillé ».
- **REMOVED** : ancien déploiement remplacé (souvent normal quand un autre deploy réussit ensuite).

## Vérifier que la prod API est à jour

```bash
curl -s https://agent-production-c246.up.railway.app/health
```

Tu dois voir `git_sha` avec les **8 premiers caractères** du dernier commit GitHub :

```bash
git rev-parse --short=8 HEAD
```

Si les deux diffèrent, l’API tourne encore sur une vieille version → **Redeploy** manuel (étape 6 ci-dessus).

## Forcer un redeploy immédiat (CLI)

```bash
cd /chemin/vers/agent
npx railway login
npx railway link   # projet cooperative-insight + service backend
npx railway up
```

## Variables « inactive »

Voir [RAILWAY_FIX_VARIABLES_INACTIVES.md](./RAILWAY_FIX_VARIABLES_INACTIVES.md).
