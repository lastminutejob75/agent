# Checklist variables Vercel — Landing UWi

À configurer dans **Vercel** → ton projet (uwiapp.com) → **Settings** → **Environment Variables**.

**Prérequis** : le projet Vercel doit être connecté au repo **agent** avec **Root Directory** = `landing` (voir docs/VERCEL_UWIAPP_DEPLOY.md).

---

## Obligatoires (sans ça le site ne fonctionne pas)

| Variable | Valeur | Description |
|----------|--------|-------------|
| `VITE_UWI_API_BASE_URL` | `https://agent-production-c246.up.railway.app` | URL du backend API (Railway). **Sans slash final.** |
| `VITE_SITE_URL` | `https://www.uwiapp.com` | URL du site (SEO, canonical). |
| `VITE_GOOGLE_REDIRECT_URI` | `https://www.uwiapp.com/auth/google/callback` | Si tu utilises « Continuer avec Google ». Doit correspondre à Google Console. |

---

## Optionnelles

| Variable | Valeur | Description |
|----------|--------|-------------|
| `VITE_UWI_APP_URL` | `https://uwiapp.com` | Si le dashboard client est sur un autre domaine. |
| `VITE_STRIPE_PUBLISHABLE_KEY` | `pk_live_xxx` ou `pk_test_xxx` | Pour la page /checkout (Stripe). |
| `VITE_STRIPE_API_URL` | `https://agent-production-c246.up.railway.app` | Même URL que le backend — le checkout est dans Agent, pas stripe-server. Pas besoin de déployer stripe-server. |
| `VITE_ADMIN_UI_ENABLED` | `true` | Pour afficher les liens admin (si masqués par défaut). |

---

## VITE_STRIPE_API_URL = même URL que le backend

Le checkout Stripe (`/create-checkout-session`) est géré par le **backend Agent**. Donc :

**VITE_STRIPE_API_URL** = même valeur que **VITE_UWI_API_BASE_URL** = `https://agent-production-c246.up.railway.app`

Pas besoin de déployer stripe-server.

---

## Étapes dans Vercel

1. Va sur **https://vercel.com** → ton projet (landing / uwiapp).
2. **Settings** → **Environment Variables**.
3. Pour chaque variable :
   - **Key** = nom (ex. `VITE_UWI_API_BASE_URL`)
   - **Value** = valeur (ex. `https://agent-production-c246.up.railway.app`)
   - **Environments** = cocher Production (et Preview si tu veux les mêmes en preview).
4. **Save**.
5. **Deployments** → **Redeploy** (les variables VITE_* sont lues au build, un redéploiement est obligatoire).

---

## Liste complète des variables (référencement, Google, etc.)

| Variable | Obligatoire | Valeur | Rôle |
|----------|-------------|--------|------|
| `VITE_UWI_API_BASE_URL` | Oui | `https://agent-production-c246.up.railway.app` | Backend API |
| `VITE_SITE_URL` | Oui | `https://www.uwiapp.com` | **SEO** : canonical, og:url, meta |
| `VITE_GOOGLE_REDIRECT_URI` | Oui (si Google SSO) | `https://www.uwiapp.com/auth/google/callback` | Connexion Google |
| `VITE_STRIPE_API_URL` | Si /checkout | `https://agent-production-c246.up.railway.app` | Checkout Stripe |
| `VITE_STRIPE_PUBLISHABLE_KEY` | Si /checkout | `pk_live_xxx` ou `pk_test_xxx` | Clé publique Stripe |
| `VITE_UWI_APP_URL` | Non | `https://uwiapp.com` | Si dashboard client sur autre domaine |
| `VITE_ADMIN_UI_ENABLED` | Non | `true` | Afficher liens admin |

**Référencement** : `VITE_SITE_URL` sert au canonical, Open Graph et Twitter cards. La meta `google-site-verification` est dans `index.html` (pas de variable).

**Google Analytics** : pas dans le code actuel. Si tu veux GA4, il faudrait ajouter le script + une variable `VITE_GA_MEASUREMENT_ID`.

---

## Valeurs minimales pour démarrer

```
VITE_UWI_API_BASE_URL=https://agent-production-c246.up.railway.app
VITE_SITE_URL=https://www.uwiapp.com
VITE_GOOGLE_REDIRECT_URI=https://www.uwiapp.com/auth/google/callback
VITE_STRIPE_API_URL=https://agent-production-c246.up.railway.app
```

---

## Vérification

Après redéploiement :

- `/admin/login` → le diagnostic doit afficher l'API configurée.
- Login admin (email/mdp ou token) doit fonctionner.
- Si « Backend non configuré » → `VITE_UWI_API_BASE_URL` manquant ou build sans redéploiement.
