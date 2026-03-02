# Pré-render des pages publiques (Node-only, sans Chrome)

Le build utilise **vite-prerender-plugin** pour générer du HTML statique pour les 6 routes publiques. Aucun Puppeteer/Chrome : tout se fait en Node pendant `vite build`, donc **compatible Vercel** et build local.

Le **&lt;head&gt;** (title, canonical, meta description, robots, Open Graph, Twitter) est injecté par route via `getHeadForPrerender()` (source de vérité partagée avec `SeoHead.jsx`), donc pas de head “fallback” sur les pages pré-rendues.

## Routes pré-rendues

- `/`
- `/creer-assistante`
- `/contact`
- `/cgv`
- `/cgu`
- `/mentions-legales`
- `/secretaire-medicale-augmentee` (pilier SEO — secrétaire médicale augmentée)
- `/secretaire-medicale-augmentee-medecin`
- `/assistant-telephone-ia-dentiste`
- `/assistant-telephone-ia-kine`
- `/assistant-telephone-ia-sage-femme`
- `/assistant-telephone-ia-dermatologue`
- `/assistant-telephone-ia-orthophoniste`
- `/standard-telephonique-cabinet-medical`

## Comment ça marche

1. **vite.config.js** : le plugin `vitePrerenderPlugin` avec `renderTarget: '#root'` et `prerenderScript` pointant vers `src/prerender.jsx`.
2. **src/prerender.jsx** : pour chaque route, rend l’app en Node avec `react-dom/server` (renderToString) + `StaticRouter` + `HelmetProvider`, et retourne le HTML + la liste des liens à pré-rendre.
3. **Build** : `npm run build` lance Vite puis le plugin génère `dist/`, `dist/creer-assistante/index.html`, etc.
4. **Vercel** : les rewrites dans `vercel.json` envoient `/creer-assistante`, `/contact`, etc. vers le bon `.../index.html`.

## Vérification

- En local après `npm run build` : ouvrir `dist/contact/index.html` (ou une autre route) et vérifier que `<div id="root">` contient du texte lisible (titres, paragraphes).
- En prod : **View Source** sur `https://www.uwiapp.com/contact` → le HTML doit contenir le contenu de la page, pas seulement une structure vide.

## Pièges à éviter

- **`window` / `document` au top-level** : les mettre dans `useEffect` ou derrière `typeof window !== "undefined"`.
- **Scripts / analytics** qui modifient le DOM au chargement : de préférence en lazy pour ne pas perturber le rendu serveur.
