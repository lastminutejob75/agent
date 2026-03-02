# Déploiement Vercel (landing UWi)

Pour que le build fonctionne, le projet Vercel doit utiliser le dossier **`landing`** comme racine.

## Configuration requise

1. **Vercel Dashboard** → ton projet → **Settings** → **General**
2. **Root Directory** : cliquer sur **Edit**, saisir **`landing`**, puis **Save**.
3. Redéployer (Deployments → … → Redeploy).

Sans cela, Vercel exécute `npm install` à la racine du repo et ne trouve pas le bon `package.json` (l’app est dans `landing/`), d’où l’erreur `ENOENT package.json`.

## Vérifications après déploiement

- **Sitemap** : https://www.uwiapp.com/sitemap.xml doit renvoyer du XML (`<urlset>…`), pas la page d’accueil.
- **Page pilier** : https://www.uwiapp.com/secretaire-medicale-augmentee doit afficher le hero et les sections.
