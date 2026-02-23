# Serveur Stripe Checkout (embedded)

API Express pour créer une session Stripe Checkout en mode embedded et consulter son statut.

## Configuration

1. Un fichier `.env` est déjà présent avec des placeholders. **Remplace** dans `stripe-server/.env` :
   - `sk_test_REMPLACER` → ta clé secrète Stripe (Dashboard Stripe > Clés API)
   - `price_REMPLACER` → l’ID d’un prix (Stripe > Produits > créer un prix, puis copier l’ID `price_...`)
2. Optionnel : `PORT` (défaut 4242), `FRONTEND_URL` (défaut http://localhost:5173), `CORS_ORIGIN`

Dans **landing/.env**, remplace `pk_test_REMPLACER` par ta clé publique Stripe (`pk_test_...`).

## Lancement

```bash
cd stripe-server
npm install
npm start
```

## Endpoints

- **POST /create-checkout-session**  
  Body optionnel : `{ "price_id": "price_...", "quantity": 1 }`  
  Réponse : `{ "clientSecret": "..." }`

- **GET /session-status?session_id=...**  
  Réponse : `{ "status": "complete", "customer_email": "..." }`

## Frontend

Depuis ton app (React, etc.), appelle `POST /create-checkout-session` pour obtenir `clientSecret`, puis utilise le composant Stripe Embedded Checkout avec ce `clientSecret`. Après paiement, vérifie le statut avec `GET /session-status?session_id=...`.
