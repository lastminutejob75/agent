# Installation Stripe sur uwiapp.com

Ce guide permet d’activer le paiement Stripe (Checkout embedded) sur **uwiapp.com** : landing (Vercel) + serveur Stripe (à déployer).

---

## Ce qui est déjà en place

- **Landing** : routes `/checkout` et `/checkout/return`, composants React avec `@stripe/react-stripe-js` et `@stripe/stripe-js`. Lien « Paiement » dans le footer vers `/checkout`.
- **stripe-server** : serveur Express (Node) qui crée les sessions Checkout et expose `GET /session-status`. Utilise `STRIPE_PRICE_ID` par défaut (ou `price_id` dans le body).

---

## 1. Créer un produit et un prix dans Stripe

1. [Stripe Dashboard](https://dashboard.stripe.com) → **Produits** → **Ajouter un produit** (nom, description, prix unique ou récurrent).
2. Après création, récupérer l’ID du **prix** (`price_...`) dans l’onglet Prix du produit.

---

## 2. Déployer stripe-server (prod)

Le front uwiapp.com appelle un **backend Stripe** pour créer la session. Ce backend doit être hébergé (Railway, Render, etc.).

### Option A : Railway

1. Créer un nouveau service depuis le repo **agent** (ou un repo qui contient `stripe-server/`).
2. **Root Directory** : `stripe-server`.
3. **Build** : `npm install` (ou laisser Railway le détecter).
4. **Start** : `npm start` (ou `node server.js`).
5. **Variables d’environnement** (Railway → Variables) :

   | Variable | Valeur (prod uwiapp.com) |
   |----------|---------------------------|
   | `STRIPE_SECRET_KEY` | `sk_live_...` (ou `sk_test_...` pour tester) |
   | `STRIPE_PRICE_ID` | `price_...` (ID du prix créé à l’étape 1) |
   | `FRONTEND_URL` | `https://www.uwiapp.com` |
   | `CORS_ORIGIN` | `https://www.uwiapp.com,https://uwiapp.com` |
   | `PORT` | Laisser Railway définir (souvent 4242 ou `PORT` fourni) |

6. Déployer, puis noter l’URL du service (ex. `https://uwi-stripe.railway.app`).

### Option B : Render / autre

Même principe : projet Node, root = `stripe-server`, commande de start = `npm start`, et les mêmes variables d’environnement (surtout `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID`, `FRONTEND_URL`, `CORS_ORIGIN`).

---

## 3. Configurer la landing (Vercel) pour uwiapp.com

Dans **Vercel** → projet uwiapp.com → **Settings** → **Environment Variables** :

| Variable | Valeur (prod) |
|----------|----------------|
| `VITE_STRIPE_PUBLISHABLE_KEY` | `pk_live_...` (ou `pk_test_...`) — clé **publique** Stripe |
| `VITE_STRIPE_API_URL` | URL du serveur Stripe (ex. `https://uwi-stripe.railway.app`) |

**Important** : après toute modification des variables, faire un **Redeploy** du projet (Vercel n’applique pas les changements d’env à chaud).

---

## 4. Vérification

1. Aller sur **https://www.uwiapp.com** → footer → **Paiement** (ou ouvrir directement `https://www.uwiapp.com/checkout`).
2. La page « Paiement sécurisé » doit afficher le formulaire Stripe Embedded Checkout (et non « Clé Stripe non configurée »).
3. Tester un paiement avec une carte de test Stripe (ex. `4242 4242 4242 4242`).
4. Après paiement, la redirection doit aller sur `https://www.uwiapp.com/checkout/return?session_id=...` avec le message de remerciement.

---

## 5. Résumé des URLs

| Rôle | Valeur |
|------|--------|
| Landing (front) | https://www.uwiapp.com (Vercel) |
| Page checkout | https://www.uwiapp.com/checkout |
| Page retour | https://www.uwiapp.com/checkout/return |
| API Stripe (stripe-server) | À définir (ex. https://uwi-stripe.railway.app) |

---

## 6. Paiement avec un prix précis (optionnel)

Pour envoyer l’utilisateur vers un prix spécifique :  
`https://www.uwiapp.com/checkout?price_id=price_xxxxx`  
Si `price_id` est absent, le serveur utilise la variable d’environnement `STRIPE_PRICE_ID`.

---

## Références

- **Fondation billing (plans, webhooks, admin)** : `docs/STRIPE_FOUNDATION.md`
- **Serveur Stripe (endpoints, config locale)** : `stripe-server/README.md`
