# Déploiement Vercel (landing UWi)

Configuration simple et unique : **Root Directory = `landing`**, et c’est **`landing/vercel.json`** qui fait foi.  
Il n’y a plus de `vercel.json` à la racine du repo.

## Étapes côté Vercel

1. **Vercel Dashboard** → ton projet → **Settings** → **General**.
2. Dans **Root Directory**, saisir **`landing`** puis **Save**.
3. Dans **Build & Output Settings** (Framework = Vite, overrides activés) vérifier :
   - **Build Command** : `npm run build`
   - **Output Directory** : `dist`
   - **Install Command** : `npm install`

Vercel exécutera donc le build dans `landing/` avec les commandes standard Vite, en utilisant `landing/vercel.json` pour les rewrites (sitemap, robots, routes pré-rendues…).

## Vérifications après déploiement

- **Sitemap** : https://www.uwiapp.com/sitemap.xml → doit renvoyer du XML (`<urlset>…`), pas la page d’accueil.
- **Page pilier** : https://www.uwiapp.com/secretaire-medicale-augmentee → hero + sections.
