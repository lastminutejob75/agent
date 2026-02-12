# Unification agent ↔ uwiapp.com

**Objectif :** Une seule source de vérité (repo `agent`), uwiapp.com déployé à jour.

---

## Situation actuelle

| Repo | Contenu | Déploie sur |
|------|---------|-------------|
| **agent** | Backend + landing/ (admin, dashboard, onboarding) | — |
| **uwi-landing** | Landing standalone | uwiapp.com (Vercel) |

---

## Option A : Sync manuel (immédiat)

Après chaque push sur `agent` :

```bash
./scripts/sync_landing_to_uwiapp.sh
# ou sans confirmation :
./scripts/sync_landing_to_uwiapp.sh -y
```

Le script copie `landing/` → `uwi-landing`, commit et push. Vercel redéploie automatiquement.

---

## Option B : Déployer uwiapp.com depuis agent (recommandé)

1. **Vercel** : Ouvrir le projet uwiapp.com
2. **Settings → General → Root Directory** : `landing`
3. **Settings → Git** : Changer le repo connecté → `lastminutejob75/agent`
4. **Build** : Framework = Vite, build command = `npm run build`, output = `dist`
5. Sauvegarder

Ensuite : plus besoin de uwi-landing. Chaque push sur `agent/main` déploie uwiapp.com.

---

## Option C : GitHub Action (sync auto) ✅ En place

Le workflow `.github/workflows/sync-landing.yml` sync automatiquement à chaque push sur `main` qui modifie `landing/**`.

```yaml
name: Sync landing to uwi-landing
on:
  push:
    branches: [main]
    paths: ['landing/**']
jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/checkout@v4
        with:
          repository: lastminutejob75/uwi-landing
          token: ${{ secrets.UWI_LANDING_PAT }}
          path: uwi-landing
      - run: |
          cp -r landing/src uwi-landing/
          cp -r landing/public uwi-landing/ 2>/dev/null || mkdir -p uwi-landing/public
          for f in index.html package.json package-lock.json vite.config.js tailwind.config.js postcss.config.js vercel.json netlify.toml; do
            [ -f "landing/$f" ] && cp "landing/$f" "uwi-landing/$f"
          done
      - run: |
          cd uwi-landing
          git config user.name "github-actions"
          git config user.email "actions@github.com"
          git add -A
          git diff --staged --quiet || (git commit -m "chore: sync from agent" && git push)
```

Prérequis : créer un PAT (Personal Access Token) avec accès au repo uwi-landing, l’ajouter dans les secrets du repo agent sous `UWI_LANDING_PAT`.

---

## Recommandation

- **Court terme :** Option A (sync manuel après chaque release)
- **Moyen terme :** Option B (un seul repo, source unique)
