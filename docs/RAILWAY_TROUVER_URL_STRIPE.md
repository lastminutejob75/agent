# Trouver l’URL du stripe-server sur Railway

## Étape 1 : Ouvre ton projet

1. Va sur **https://railway.app**
2. Connecte-toi
3. Clique sur ton projet (ex. **agent** ou **agent-accueil-pme**)

---

## Étape 2 : Liste des services

Sur la page du projet, tu vois une **liste de cartes** (chaque carte = un service) :
- Backend / agent (API FastAPI)
- Postgres (base de données)
- **Stripe** ou **stripe-server** (si déployé)

**Si tu ne vois que 2 services (backend + Postgres)** → stripe-server n’est pas déployé. Voir « Ajouter stripe-server » plus bas.

---

## Étape 3 : Clique sur le service Stripe

Clique sur la carte du service **Stripe** / **stripe-server**.

---

## Étape 4 : Onglet Settings

En haut, tu as des onglets : **Deployments**, **Metrics**, **Settings**, etc.

Clique sur **Settings**.

---

## Étape 5 : Section Networking

Dans Settings, descends jusqu’à la section **Networking** (ou **Domains**).

Tu dois voir :
- **Public Networking** ou **Domains**
- Un bouton **Generate Domain** ou une URL déjà affichée

Si une URL est déjà là (ex. `https://xxx.up.railway.app`) → **c’est ta VITE_STRIPE_API_URL**.

Si tu vois **Generate Domain** → clique dessus pour créer l’URL.

---

## Si tu n’as pas de service Stripe

Si tu ne vois que le backend + Postgres :

1. Dans ton projet Railway → **+ New** (ou **Add Service**)
2. **Deploy from GitHub repo** → choisis le repo **agent**
3. Dans les paramètres du nouveau service :
   - **Root Directory** : `stripe-server`
   - **Build Command** : `npm install`
   - **Start Command** : `npm start`
4. **Variables** : ajoute `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID`, `FRONTEND_URL`, `CORS_ORIGIN`
5. **Deploy** → une fois déployé, va dans **Settings** → **Networking** → **Generate Domain**
6. Copie l’URL → c’est ta `VITE_STRIPE_API_URL`

---

## Résumé du chemin

```
Railway → Ton projet → Service Stripe → Settings → Networking → URL
```
