# Dépannage : « Impossible de joindre le serveur »

Ce message s’affiche quand le front (landing) ne peut pas contacter le backend (API). Causes possibles : URL backend incorrecte, CORS, ou backend arrêté.

## Checklist

### 1. URL du backend (front)

Le front doit connaître l’URL de l’API au **moment du build** (variable Vite).

- **Landing (Vercel / build)** : dans les variables d’environnement du projet **landing**, définir :
  ```bash
  VITE_UWI_API_BASE_URL=https://votre-backend.up.railway.app
  ```
  (sans slash final)

- **Important** : après toute modification de `VITE_*`, **redéployer** le front (Vite lit ces variables au build, pas au runtime).

- En **local** : créer `landing/.env` avec la même variable, puis `npm run build` ou `npm run dev`.

### 2. CORS (backend)

Si le front est sur un **domaine différent** de l’API (ex. front sur `https://mon-app.vercel.app`, API sur `https://xxx.railway.app`), le backend doit autoriser l’**origine** du front.

- Sur **Railway** (ou l’hébergeur du backend), définir :
  ```bash
  CORS_ORIGINS=https://mon-app.vercel.app,https://www.uwiapp.com,https://uwiapp.com
  ```
  Une seule valeur, origines séparées par des **virgules**, **sans slash final**, **sans espace** (ou espaces après les virgules uniquement).

- **Défaut** du backend (si `CORS_ORIGINS` n’est pas défini) : prod uniquement — `https://www.uwiapp.com`, `https://uwiapp.com`. En **dev local**, définir `CORS_ORIGINS=http://localhost:5173` (ou le port de ton front).

- Si tu utilises une **preview Vercel** (ex. `https://xxx-xxx.vercel.app`), ajoute cette URL exacte dans `CORS_ORIGINS`.

### 3. Backend démarré et joignable

- Vérifier que le service backend (ex. Railway) est **démarré** et qu’il n’y a pas d’erreur au démarrage.
- Tester l’API dans un navigateur ou avec `curl` :
  ```bash
  curl -s -o /dev/null -w "%{http_code}" https://votre-backend.up.railway.app/health
  ```
  Tu dois obtenir `200` (ou une autre réponse 2xx).

### 4. Résumé

| Où | Variable / action |
|----|-------------------|
| **Front (landing)** | `VITE_UWI_API_BASE_URL` = URL complète du backend (ex. `https://xxx.railway.app`), puis **redéployer**. |
| **Backend** | `CORS_ORIGINS` = liste des origines du front (ex. `https://www.uwiapp.com`, ton domaine Vercel, `http://localhost:5173`). |
| **Backend** | Service démarré et `/health` répond 200. |

Voir aussi : [GOOGLE_SSO_SETUP.md](./GOOGLE_SSO_SETUP.md) (CORS et Google), [.env.example](../.env.example) (CORS_ORIGINS).
