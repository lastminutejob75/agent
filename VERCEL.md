# Déploiement Vercel (UWi)

**Source unique : repo GitHub `lastminutejob75/agent`.**  
Il n’y a plus de sync vers le repo `uwi-landing` : chaque push sur `main` déclenche le déploiement Vercel depuis **agent**.

Configuration : **Root Directory = `landing`**, et c’est **`landing/vercel.json`** qui fait foi.  
Il n’y a pas de `vercel.json` à la racine du monorepo.

## Étapes côté Vercel

1. **Vercel Dashboard** → projet uwiapp.com (ou `agent`) → **Settings** → **General**.
2. **Repository** : **`lastminutejob75/agent`** (pas `uwi-landing`).
3. **Root Directory** : **`landing`** puis **Save**.
4. Dans **Build & Output Settings** (Framework = Vite) :
   - **Build Command** : `npm run build`
   - **Output Directory** : `dist`
   - **Install Command** : `npm install`

## Vérifications après déploiement

- **Sitemap** : https://www.uwiapp.com/sitemap.xml → doit renvoyer du XML (`<urlset>…`), pas la page d’accueil.
- **Page pilier** : https://www.uwiapp.com/secretaire-medicale-augmentee → hero + sections.
