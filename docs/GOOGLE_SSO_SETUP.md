# Configuration Google SSO (Connexion Google)

Ce document décrit la checklist pour que « Continuer avec Google » fonctionne (frontend landing + backend API).

## Flux en bref

1. L’utilisateur clique sur **Continuer avec Google** → le front appelle `GET /api/auth/google/start?redirect_uri=...`.
2. Le backend renvoie `auth_url`, `state`, `code_verifier`. Le front stocke `code_verifier` en sessionStorage et redirige vers Google.
3. Google redirige vers `redirect_uri` (votre page callback) avec `?code=...&state=...`.
4. La page callback envoie `POST /api/auth/google/callback` avec `{ code, state, redirect_uri, code_verifier }`.
5. Le backend échange le code contre les tokens, vérifie l’email, crée ou lie le compte, pose le cookie `uwi_session`, renvoie 200.
6. Le front redirige vers `/app`.

## Checklist

### 1. Backend (variables d’environnement)

Sur l’instance qui sert l’API (ex. Railway) :

| Variable | Obligatoire | Description |
|----------|-------------|-------------|
| `GOOGLE_CLIENT_ID` | Oui | ID client OAuth 2.0 (Google Cloud Console) |
| `GOOGLE_CLIENT_SECRET` | Oui | Secret client OAuth 2.0 |
| `JWT_SECRET` (ou `SESSION_SECRET`) | Oui | Secret pour signer le state OAuth et les sessions |
| `GOOGLE_REDIRECT_URI` | Optionnel | URI de redirection par défaut si le front n’en envoie pas |

Si `GOOGLE_CLIENT_ID` ou `JWT_SECRET` manquent, `GET /api/auth/google/start` renvoie **503** (« Google SSO not configured »).

### 2. Google Cloud Console

1. **APIs & Services** → **Credentials** → créer ou modifier un client OAuth 2.0 (type « Web application »).
2. **Authorized redirect URIs** : ajouter **exactement** l’URL de la page callback, **sans slash final** :
   - Prod : `https://www.uwiapp.com/auth/google/callback`
   - Dev : `http://localhost:5173/auth/google/callback` (ou le port de votre front)
3. **Authorized JavaScript origins** : ajouter l’origine du front (ex. `https://www.uwiapp.com`, `http://localhost:5173`).

Si l’URI de redirection ne correspond pas exactement (protocole, domaine, chemin, slash final), Google renvoie `redirect_uri_mismatch` et l’utilisateur voit une erreur sur la page callback.

### 3. Frontend (landing)

Dans le projet **landing** (build Vite), fichier `.env` ou variables d’environnement du déploiement :

| Variable | Description |
|----------|-------------|
| `VITE_UWI_API_BASE_URL` | URL de base de l’API (ex. `https://api.uwiapp.com`). **Obligatoire** si le front et l’API ne sont pas sur le même domaine. |
| `VITE_GOOGLE_REDIRECT_URI` | URI de redirection après Google. **Recommandé en prod** pour éviter les écarts (ex. `https://www.uwiapp.com/auth/google/callback`). Sinon le front utilise `window.location.origin + '/auth/google/callback'`. |

Sans `VITE_UWI_API_BASE_URL`, les appels partent vers le même domaine que le front (souvent 404 si l’API est ailleurs).

### 4. CORS (backend)

Si le front est sur un domaine différent de l’API (ex. front sur `www.uwiapp.com`, API sur `api.uwiapp.com`), le backend doit autoriser l’origine du front :

- Variable d’environnement ou config utilisée par le middleware CORS (ex. `CORS_ORIGINS=https://www.uwiapp.com`).
- Les requêtes vers `/api/auth/google/start` et `/api/auth/google/callback` doivent être envoyées avec `credentials: "include"` (déjà le cas dans le code).

Si CORS bloque la requête, le navigateur affiche une erreur réseau et le front peut afficher « Impossible de joindre l’API (CORS ou URL backend incorrecte) ».

### 5. Cookie de session (cross-origin)

Quand le front et l’API sont sur des domaines différents :

- Le backend doit poser le cookie avec `SameSite=None` et `Secure=true` pour qu’il soit envoyé sur les requêtes cross-site suivantes (ex. `GET /api/tenant/me`).
- Par défaut dans ce projet : `COOKIE_SAMESITE=none` et `COOKIE_SECURE=true`. Vérifier que ces valeurs sont cohérentes avec votre déploiement.

## Erreurs fréquentes

| Symptôme | Cause probable | Action |
|----------|----------------|--------|
| « Backend non configuré : définir VITE_UWI_API_BASE_URL » | Variable front manquante | Définir `VITE_UWI_API_BASE_URL` dans le build du front. |
| « Google SSO désactivé côté serveur » (503) | `GOOGLE_CLIENT_ID` ou `JWT_SECRET` manquant côté API | Configurer les variables d’environnement du backend. |
| « Impossible de joindre l’API (CORS ou URL backend incorrecte) » | CORS ou mauvaise URL API | Vérifier `CORS_ORIGINS` et que l’URL backend est correcte. |
| « Google a refusé l’accès : redirect_uri_mismatch » | URI non autorisée dans Google Console | Ajouter l’URI exacte (sans slash final) dans Authorized redirect URIs. |
| « Session perdue (onglet fermé ou autre domaine) » | `code_verifier` absent au retour de Google | Revenir à la page de login et cliquer à nouveau sur Google (même domaine, pas d’ouverture du lien dans un nouvel onglet). |
| « Ce compte est déjà lié à un autre Google » (409) | Un autre compte Google est déjà lié à cet email côté BDD | Gérer en support ou en déliant le compte dans l’admin. |

## Vérification rapide

1. **Démarrage** : depuis la page de login, cliquer sur « Continuer avec Google ».  
   - Si une erreur s’affiche immédiatement : problème de config front (API_URL, redirect_uri) ou backend (503) / CORS.  
   - Si la redirection vers Google fonctionne : front et `/api/auth/google/start` sont OK.

2. **Retour Google** : après avoir choisi le compte Google, vous êtes renvoyés sur `/auth/google/callback`.  
   - Si erreur « redirect_uri_mismatch » ou « Paramètres OAuth manquants » : Google ou état (state/code) invalide.  
   - Si « Session perdue » : `code_verifier` manquant (même domaine / pas de nouvel onglet).  
   - Si 503/409/403 : voir le tableau ci-dessus.

3. **Backend** : consulter les logs du serveur lors de `GET /api/auth/google/start` et `POST /api/auth/google/callback` pour les réponses 4xx/5xx et les messages d’erreur.
