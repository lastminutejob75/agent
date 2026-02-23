# Vérification Google Connect (SSO)

## 1. Flow implémenté

| Étape | Front (landing) | Backend |
|-------|------------------|---------|
| 1 | Page `/login` : bouton « Continuer avec Google » (`GoogleLoginButton.jsx`) | — |
| 2 | `GET /api/auth/google/start?redirect_uri=...` avec `credentials: "include"` | Retourne `{ auth_url, state, code_verifier }` |
| 3 | Stocke `code_verifier` en sessionStorage, redirige vers `auth_url` (Google) | — |
| 4 | Google redirige vers `/auth/google/callback?code=...&state=...` | — |
| 5 | `AuthGoogleCallback.jsx` : lit code, state, code_verifier → `POST /api/auth/google/callback` avec body `{ code, redirect_uri, state, code_verifier }`, `credentials: "include"` | Échange code → tokens, vérifie id_token, trouve/crée user, pose cookie `uwi_session`, retourne `{ ok: true }` |
| 6 | Redirection `window.location.replace("/app")` | — |

- **PKCE** : code_verifier/code_challenge utilisés (backend génère, front envoie redirect_uri + code_verifier au callback).
- **State** : JWT signé (jti + exp), anti-replay côté backend.
- **redirect_uri** : doit être **identique** entre front (env), GET /start, POST /callback et **Google Console**.

---

## 2. Variables à vérifier

### Backend (Railway / .env)

| Variable | Rôle |
|----------|------|
| `GOOGLE_CLIENT_ID` | Client ID OAuth 2.0 (Google Cloud Console) |
| `GOOGLE_CLIENT_SECRET` | Client secret |
| `GOOGLE_REDIRECT_URI` | Ex. `https://www.uwiapp.com/auth/google/callback` |
| `JWT_SECRET` | Signe le state et la session (obligatoire pour Google SSO) |
| `COOKIE_SECURE` | `true` en prod |
| `COOKIE_SAMESITE` | `none` en prod (front et API domaines différents) |

Si `GOOGLE_CLIENT_ID` ou `GOOGLE_CLIENT_SECRET` sont vides → **503** sur `/api/auth/google/start` (« Google SSO not configured »).

### Front (Vercel / landing/.env)

| Variable | Rôle |
|----------|------|
| `VITE_UWI_API_BASE_URL` | URL de l’API (ex. `https://api.uwiapp.com`) |
| `VITE_GOOGLE_REDIRECT_URI` | **Même valeur** que `GOOGLE_REDIRECT_URI` du backend (ex. `https://www.uwiapp.com/auth/google/callback`) |

Défaut front : si `VITE_GOOGLE_REDIRECT_URI` absent → `window.location.origin + '/auth/google/callback'` (OK en dev, en prod doit matcher Google Console).

---

## 3. Google Cloud Console

- **APIs & Services** → **Credentials** → OAuth 2.0 Client ID (type « Web application »).
- **Authorized redirect URIs** : ajouter **exactement** :
  - `https://www.uwiapp.com/auth/google/callback`
  - (si tu utilises aussi le domaine sans www) `https://uwiapp.com/auth/google/callback`
  - En dev : `http://localhost:5173/auth/google/callback` (ou le port utilisé).
- Un caractère en trop ou en moins → erreur Google `redirect_uri_mismatch`.

---

## 4. CORS (backend)

- `allow_credentials=True`
- `allow_origins` doit contenir l’origine du front (ex. `https://www.uwiapp.com`, `https://uwiapp.com`, `http://localhost:5173`).

Déjà configuré dans `main.py` via `CORS_ORIGINS`.

---

## 5. Checklist rapide

- [ ] Backend : `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `JWT_SECRET` définis.
- [ ] Front : `VITE_GOOGLE_REDIRECT_URI` = même valeur que `GOOGLE_REDIRECT_URI` (prod).
- [ ] Google Console : redirect URI ajouté et identique (https, pas de slash final sauf si utilisé).
- [ ] Cookie : en prod `COOKIE_SECURE=true`, `COOKIE_SAMESITE=none`.
- [ ] Après callback réussi : `GET /api/auth/me` avec `credentials: "include"` doit renvoyer 200 et le profil.

---

## 6. Erreurs fréquentes

| Symptôme | Cause probable |
|----------|-----------------|
| 503 sur /start | `GOOGLE_CLIENT_ID` ou `JWT_SECRET` manquant |
| Google « redirect_uri_mismatch » | URI dans Google Console ≠ celle envoyée (front/backend) |
| Cookie non reçu après callback | CORS sans `credentials`, ou `SameSite`/Secure incorrect, ou domaine API ≠ front |
| 409 après callback | Compte déjà lié à un autre Google (email déjà utilisé avec un autre sub) |
| 403 « Email non vérifié » | `email_verified` faux dans id_token Google |

---

## 7. Fichiers concernés

- **Front** : `landing/src/lib/authConfig.js`, `landing/src/components/GoogleLoginButton.jsx`, `landing/src/pages/AuthGoogleCallback.jsx`, `landing/src/pages/Login.jsx`
- **Backend** : `backend/routes/auth.py` (GET `/google/start`, POST `/google/callback`)
- **Spec** : `docs/AUTH_B2B_PASSWORD_GOOGLE_SPEC.md`
