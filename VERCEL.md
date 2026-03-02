# Déploiement Vercel (landing UWi)

Le **vercel.json à la racine** du repo est configuré pour builder la landing sans changer le Root Directory dans le dashboard.

## Comportement

- **installCommand** : `cd landing && npm ci` → les deps sont installées dans `landing/`
- **buildCommand** : `cd landing && npm run build` → le build Vite + prerender tourne dans `landing/`
- **outputDirectory** : `landing/dist` → Vercel sert le contenu de `landing/dist` à la racine du site

Tu peux laisser **Root Directory** vide (racine du repo). Pas besoin de le mettre à `landing`.

## Si tu préfères utiliser le dossier `landing` comme racine

1. **Vercel Dashboard** → **Settings** → **General** → **Root Directory** → **Edit** → saisir **`landing`** → **Save**.
2. Dans ce cas, c’est **landing/vercel.json** qui s’applique (le vercel.json racine est ignoré).

## Vérifications après déploiement

- **Sitemap** : https://www.uwiapp.com/sitemap.xml → doit renvoyer du XML (`<urlset>…`), pas la page d’accueil.
- **Page pilier** : https://www.uwiapp.com/secretaire-medicale-augmentee → hero + sections.
