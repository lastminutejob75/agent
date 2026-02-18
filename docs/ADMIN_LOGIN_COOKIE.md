# Admin : connexion par email + mot de passe (cookie)

L’admin uwiapp.com peut se connecter soit avec **email + mot de passe** (cookie HttpOnly), soit en **legacy** avec le token Bearer (`ADMIN_API_TOKEN`).

## Backend

### Variables d’environnement

| Variable | Description |
|----------|-------------|
| `ADMIN_EMAIL` | Email de l’admin (connexion cookie) |
| `ADMIN_PASSWORD_HASH` | **Recommandé en prod** : hash bcrypt du mot de passe (évite mot de passe en clair dans l’env) |
| `ADMIN_PASSWORD` | Déprécié : mot de passe en clair (accepté en dev ; en prod un warning est loggé) |
| `JWT_SECRET` ou `ADMIN_SESSION_SECRET` | Secret pour signer le cookie de session (obligatoire si login cookie) |
| `ADMIN_SESSION_EXPIRES_HOURS` | Expiration du cookie en heures (défaut **8**) |
| `ADMIN_COOKIE_SAMESITE` | `none` (API sur autre domaine, ex. Railway) ou `lax` (API sur api.uwiapp.com). Si vide : auto (none si Secure, sinon lax) |

Générer un hash bcrypt :

```bash
python -c "import bcrypt; print(bcrypt.hashpw(b'votre_mot_de_passe', bcrypt.gensalt()).decode())"
```

Routes : **POST /api/admin/auth/login**, **GET /api/admin/auth/me**, **POST /api/admin/auth/logout**. Cookie : `uwi_admin_session` (HttpOnly, Secure en prod, Path=/).

### Cookie cross-domain (architecture actuelle)

**Setup actuel :** front = **https://uwiapp.com** (Vercel), API = **Railway** (ex. `https://agent-xxx.up.railway.app`). Donc **domaines différents** → cookie cross-site.

- **En prod** : le cookie admin doit être **`SameSite=None`** et **`Secure=true`** pour que le navigateur l’envoie depuis uwiapp.com vers Railway. Définir **`ADMIN_COOKIE_SAMESITE=none`** sur Railway (ou laisser vide : le backend met déjà `none` quand `Secure=true`).
- Si un jour l’API est exposée en **api.uwiapp.com** (CNAME vers Railway) : on pourra repasser en `SameSite=Lax` et retirer la variable.

### CORS

- Le backend doit renvoyer **`Access-Control-Allow-Credentials: true`** et **`Access-Control-Allow-Origin: https://uwiapp.com`** (pas `*`). FastAPI avec `allow_credentials=True` + `allow_origins=[...]` le fait.
- Les requêtes **OPTIONS** (preflight) ne doivent pas être bloquées par le guard admin : le middleware laisse passer `method == "OPTIONS"`.
- Origines autorisées : `CORS_ORIGINS` / `ADMIN_CORS_ORIGINS`.

## Front (landing)

- **URL de connexion** : `https://uwiapp.com/admin/login`
- Appels avec `credentials: "include"` (`landing/src/lib/adminApi.js`).
- Vérifier que `VITE_UWI_API_BASE_URL` pointe vers l’API (Railway ou api.uwiapp.com).

## Checklist « ça marche du premier coup »

- [ ] **Railway** : `ADMIN_EMAIL`, `ADMIN_PASSWORD_HASH` (bcrypt), `JWT_SECRET`, et **`ADMIN_COOKIE_SAMESITE=none`** (front uwiapp.com ≠ domaine API).
- [ ] **Vercel** (uwiapp.com) : `VITE_UWI_API_BASE_URL` = URL publique du backend Railway (ex. `https://agent-xxx.up.railway.app`).
- [ ] CORS : `Allow-Credentials: true`, `Allow-Origin` = `https://uwiapp.com` (pas `*`), preflight OPTIONS non bloqué.
- [ ] Cookie avec `Path=/` ; en prod `Secure=true` + `SameSite=None`.
- [ ] Chrome DevTools → Application → Cookies (domaine = celui de Railway) : présence de `uwi_admin_session` après login.

## Vérifier en 30 secondes (smoke check)

À chaque déploiement ou après un changement CORS/cookie :

1. **DevTools → Network** (onglet réseau).
2. Sur la page **Connexion Admin**, saisir email + mot de passe puis **Se connecter**.
3. Repérer la requête **POST** vers **`/api/admin/auth/login`** :
   - **Réponse 200**.
   - Dans **Response Headers** : **`Set-Cookie`** doit contenir `uwi_admin_session=...; SameSite=None; Secure; HttpOnly` (en prod). Pas de `Domain=` (cookie host-only sur Railway).
4. Repérer ensuite la requête **GET** vers **`/api/admin/auth/me`** (appelée par le front après login) :
   - Dans **Request Headers** : **`Cookie: uwi_admin_session=...`** doit être présent.
   - **Réponse 200** avec `{ "email": "..." }`.

Si le cookie n’apparaît pas sur `/me` ou si `/me` renvoie 401, le front affiche un message explicite (voir ci-dessous) ; vérifier SameSite=None, Secure et CORS allow-credentials.

### Fallback UX si le cookie ne passe pas

Si **login** renvoie 200 mais **me()** renvoie 401 (cookie non envoyé ou rejeté), le front affiche :

> **Session non persistée.** Vérifiez SameSite=None + Secure, et CORS allow-credentials (voir docs/ADMIN_LOGIN_COOKIE.md).

Au lieu du générique « Identifiants invalides », pour éviter de perdre du temps sur un souci CORS/cookie.
