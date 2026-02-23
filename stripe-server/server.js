// Serveur Stripe Checkout (embedded) — clé secrète via variable d'environnement
require('dotenv').config();

const stripe = require('stripe')(process.env.STRIPE_SECRET_KEY);
const express = require('express');
const app = express();
const path = require('path');

// CORS pour que le site (landing sur 3000/5173) puisse appeler ce serveur
app.use((req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin', process.env.CORS_ORIGIN || '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.sendStatus(204);
  next();
});
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

const PORT = process.env.PORT || 4242;
// URL du front (landing) pour la redirection après paiement (embedded checkout)
const FRONTEND_URL = process.env.FRONTEND_URL || process.env.CORS_ORIGIN || 'http://localhost:5173';

app.post('/create-checkout-session', async (req, res) => {
  const priceId = process.env.STRIPE_PRICE_ID || req.body?.price_id;
  if (!priceId) {
    return res.status(400).json({ error: 'STRIPE_PRICE_ID manquant (env ou body.price_id)' });
  }

  try {
    const session = await stripe.checkout.sessions.create({
      ui_mode: 'embedded',
      line_items: [
        {
          price: priceId,
          quantity: req.body?.quantity ?? 1,
        },
      ],
      mode: 'payment',
      return_url: `${FRONTEND_URL}/checkout/return?session_id={CHECKOUT_SESSION_ID}`,
    });

    res.json({ clientSecret: session.client_secret });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

app.get('/session-status', async (req, res) => {
  const sessionId = req.query.session_id;
  if (!sessionId) {
    return res.status(400).json({ error: 'session_id requis' });
  }

  try {
    const session = await stripe.checkout.sessions.retrieve(sessionId);
    res.json({
      status: session.status,
      customer_email: session.customer_details?.email ?? null,
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`Stripe server: http://localhost:${PORT}`);
  if (!process.env.STRIPE_SECRET_KEY) {
    console.warn('ATTENTION: STRIPE_SECRET_KEY non défini (fichier .env)');
  }
});
