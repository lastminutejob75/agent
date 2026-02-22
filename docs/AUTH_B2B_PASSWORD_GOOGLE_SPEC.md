# Auth B2B : email+mot de passe + Google SSO (remplacement magic link)

Spec pour passer du magic link à **email+mot de passe** (baseline) + **Se connecter avec Google** (SSO), puis retrait du magic link.

---

## Réponses pour l’expert (stratégie link Google)

**1) Un user peut-il appartenir à plusieurs tenants ?**  
**Non.** Table `tenant_users` avec **UNIQUE(email)** → 1 email = 1 tenant_id. Un utilisateur est donc rattaché à un seul client (tenant).

**2) Création de compte : invitation ou signup public ?**  
**Les deux.**  
- **Invitation** : l’admin crée un client (tenant) avec un email de contact → un `tenant_user` owner est créé ; l’admin peut aussi « Ajouter un utilisateur » (owner/member) à un tenant existant.  
- **Signup public** : POST `/api/public/onboarding` (landing « Démarrer ») crée un tenant + `tenant_user` pour l’email saisi.

**Stratégie link Google recommandée** : **A) Auto-link par email**. Comptes créés soit par admin (email maîtrisé), soit par onboarding (email saisi). Si à la connexion Google on a `email_verified` dans l’id_token et qu’un `tenant_user` existe avec le même email, on attache `google_sub` à ce user. Friction nulle et cohérent avec un B2B où les comptes sont soit invités soit auto-créés avec un email vérifié par Google.

---

## 1) Modèle de données

Sur **tenant_users** (Postgres), ajouter :

| Colonne          | Type         | Contraintes | Description |
|------------------|-------------|-------------|-------------|
| password_hash    | TEXT        | NULLABLE    | bcrypt |
| google_sub      | TEXT        | NULLABLE UNIQUE | Identifiant stable Google (sub claim) |
| google_email    | TEXT        | NULLABLE    | Email Google au moment du lien (info) |
| auth_provider   | TEXT        | NULLABLE    | `password` \| `google` \| `mixed` (optionnel) |
| email_verified  | BOOLEAN     | DEFAULT false | Optionnel, pour flow password |

- **UNIQUE(google_sub)** (déjà décrit).
- **UNIQUE(email)** existe déjà → (tenant_id, email) implicite 1 user = 1 tenant.

**Migration** : fichier type `migrations/0XX_tenant_users_password_google.sql` (ALTER TABLE tenant_users ADD COLUMN ...).

---

## 2) UX cible (écran /login)

- Bouton **« Continuer avec Google »**
- Formulaire **email + mot de passe**
- Lien **« Mot de passe oublié »**
- (Optionnel) « Créer un compte » / invitation selon le produit

Suppression à terme : demande de magic link (request-link) et toute UI associée.

---

## 3) OAuth Google (flow SPA + backend)

- **Recommandation** : Authorization Code + **PKCE** côté SPA.
- Le front redirige vers Google (avec PKCE) → Google renvoie `code` vers redirect_uri.
- Le front envoie `code` + `code_verifier` (et `redirect_uri`) au **backend**.
- Le backend échange le code contre tokens, récupère le profil (id_token), vérifie signature / aud / iss / exp (et nonce si utilisé).
- Le backend trouve ou crée l’utilisateur (auto-link par email si `tenant_user` existant avec même email + email_verified), pose la **session** (cookie HttpOnly) et renvoie `{ok: true}`.

Aucun token Google stocké côté front ; la session est gérée comme l’admin (cookie).

---

## 4) Endpoints backend (FastAPI)

| Méthode | Endpoint | Description |
|--------|----------|-------------|
| POST   | /api/auth/login | Body `email`, `password` → vérif bcrypt, pose cookie `uwi_session` (JWT tenant) |
| GET    | /api/auth/me | Lit session (cookie ou Bearer), retourne tenant_id, email, role |
| POST   | /api/auth/logout | Supprime cookie (et invalide session si besoin) |
| POST   | /api/auth/forgot-password | Body `email` → génère token reset, envoie email (lien reset) |
| POST   | /api/auth/reset-password | Body `token`, `new_password` → valide token, met à jour password_hash |
| GET    | /api/auth/google/start | Retourne `{ auth_url, code_verifier }` (PKCE) pour redirection Google |
| POST   | /api/auth/google/callback | Body `code`, `code_verifier`, `redirect_uri` → échange code, lit id_token (sub, email, email_verified), trouve/crée user, auto-link si email existant, pose cookie, retourne `{ok: true}` |

Cookie client : même politique que l’admin en cross-domain (Secure, HttpOnly, **SameSite=None** si front et API sur domaines différents). CORS : `Allow-Credentials: true`, `Allow-Origin` = origine du front (pas `*`).  
Front : `fetch(..., { credentials: "include" })`.

---

## 5) Cookies / CORS

- Même principe que l’admin : si front (Vercel) et backend (Railway) sur domaines différents → cookie **Secure=true**, **HttpOnly=true**, **SameSite=None**.
- CORS : **Access-Control-Allow-Credentials: true**, **Access-Control-Allow-Origin** = `https://ton-domaine-front` (exact, pas `*`).

---

## 6) Migration depuis magic link (sans casse)

1. Déployer **password + reset + Google** (nouveaux endpoints + colonnes).
2. Garder temporairement les routes magic link (request-link, verify) en parallèle.
3. Envoyer un email aux comptes existants type « Vous pouvez définir un mot de passe » avec lien **Mot de passe oublié** (qui mène à reset-password).
4. Après une période, **supprimer** routes + UI magic link (request-link, verify, magic_links si plus utilisé).

Sans emailing massif, « Mot de passe oublié » sert de **« Créer mon mot de passe »** pour les comptes existants (email connu).

---

## 7) Sécurité

- **id_token Google** : vérifier signature, `aud`, `iss`, `exp`, et `email_verified` si auto-link par email.
- **Rate-limit** sur `/api/auth/login` et `/api/auth/forgot-password`.
- Réponses **neutres** (pas d’énumération d’email) : ex. « Identifiants invalides » ou « Si ce compte existe, un email a été envoyé ».
- **Journaliser** connexions (succès/échec) (ex. `auth_events` ou logs).

---

## 8) Implémentation (ordre proposé)

1. **Migration** : ajout colonnes `tenant_users` (password_hash, google_sub, google_email, auth_provider, email_verified).
2. **Backend** : POST login (email+password), GET me, POST logout, POST forgot-password, POST reset-password (token à usage unique, TTL court).
3. **Backend** : GET google/start (PKCE), POST google/callback (échange code, id_token, find-or-create + auto-link, cookie).
4. **Front** : page /login avec formulaire email+mdp, bouton Google, lien « Mot de passe oublié » ; appels avec `credentials: "include"`.
5. **Front** : page /reset-password?token=... (saisie nouveau mot de passe, appel reset-password).
6. **Email** : template « Réinitialiser mon mot de passe » (lien vers front /reset-password?token=...).
7. **Migration utilisateurs** : optionnel email « Définir votre mot de passe » + lien forgot-password.
8. **Retrait** : suppression routes + UI magic link, et à terme table `magic_links` si plus utilisée.

Ce doc peut être envoyé tel quel à l’expert ou utilisé comme checklist d’implémentation.

---

## 9) Google SSO — implémentation (env + front)

### Variables d’environnement (backend)

| Variable | Description |
|----------|-------------|
| `GOOGLE_CLIENT_ID` | Client ID OAuth 2.0 (Google Cloud Console) |
| `GOOGLE_CLIENT_SECRET` | Client secret |
| `GOOGLE_REDIRECT_URI` | Ex. `https://www.uwiapp.com/auth/google/callback` (route SPA) |
| `GOOGLE_OAUTH_SCOPES` | Optionnel ; défaut `openid email profile` |
| (existants) | `JWT_SECRET` / `SESSION_SECRET`, `SESSION_COOKIE_NAME`, `COOKIE_SECURE`, `COOKIE_SAMESITE` |

**URLs prod (ce projet)** — Front : https://www.uwiapp.com | API : https://agent-production-c246.up.railway.app | Callback : https://www.uwiapp.com/auth/google/callback (à déclarer aussi dans Google Console).

### Endpoints

- **GET /api/auth/google/start**  
  Query optionnel : `redirect_uri` (sinon pris depuis `GOOGLE_REDIRECT_URI`).  
  Réponse : `{ "auth_url", "state", "code_verifier" }`. Le **code_verifier** ne doit pas circuler en URL : le front le stocke en **sessionStorage** et le renvoie dans le body du callback.

- **POST /api/auth/google/callback**  
  Body : `{ "code", "redirect_uri", "state", "code_verifier" }`.  
  Pose le cookie `uwi_session`, retourne `{ "ok": true }`.  
  Conflit (compte déjà lié à un autre Google) → **409**.

### Flow front (SPA)

1. **Bouton « Continuer avec Google »**  
   - `GET /api/auth/google/start?redirect_uri=...` (ou sans query).  
   - Stocker **code_verifier** en **sessionStorage** (clé ex. `oauth_code_verifier`).  
   - `window.location.href = response.auth_url`.

2. **Page /auth/google/callback** (après redirection Google)  
   - Lire `code` et `state` dans l’URL (`?code=...&state=...`).  
   - Récupérer **code_verifier** depuis sessionStorage, puis le supprimer.  
   - `redirect_uri` = URL courante sans query (ex. `window.location.origin + '/auth/google/callback'`).  
   - `POST /api/auth/google/callback` avec `{ code, redirect_uri, state, code_verifier }`, `credentials: "include"`.  
   - Si 200 : `GET /api/auth/me` avec `credentials: "include"`, puis redirection app.  
   - Si 409 : afficher « Ce compte est déjà lié à un autre compte Google ».

3. **CORS**  
   - `allow_credentials: true`, `allow_origins` = liste exacte (pas `*`).

---

## 10) Checklist validation / hardening (prod)

### A) redirect_uri identique partout

- Dans l’URL renvoyée par **/start** (paramètre envoyé à Google).
- Dans le body de **POST /callback** (même chaîne exacte).
- Dans **Google Console** → Authorized redirect URIs.  
Un caractère différent → `redirect_uri_mismatch`.

### B) Cookie cross-domain (Vercel ↔ Railway)

En prod, la réponse **POST /callback** doit contenir :

```http
Set-Cookie: uwi_session=<JWT>; Path=/; HttpOnly; Secure; SameSite=None
```

Variables recommandées en prod : `COOKIE_SECURE=true`, `COOKIE_SAMESITE=none`.  
Côté front : tous les appels auth avec **`credentials: "include"`**.

### C) Vérifier /me après callback

Après un callback réussi, **GET /api/auth/me** (avec le cookie) doit renvoyer **200** et le profil (id, tenant_id, email, role).

### D) Sécurité state / PKCE

- **State** : JWT signé avec **jti** (nonce) + **exp** uniquement ; pas de code_verifier dans le state (évite qu’il circule en URL / referrer).
- **code_verifier** : fourni par le backend dans la réponse **/start**, stocké côté front (sessionStorage), renvoyé dans le **body** du POST /callback.
- **Anti-replay** : chaque **jti** du state est consommé une seule fois (in-memory, TTL 10 min).

### E) CORS (FastAPI)

- `allow_credentials=True`
- `allow_origins` = liste exacte (ex. `https://www.uwiapp.com`, `http://localhost:5173`)
- `allow_methods` inclut au moins GET, POST, OPTIONS
- `allow_headers` inclut au moins `Content-Type`, `Authorization`

### F) Dev local (localhost)

Pour éviter les refus de cookie en local :  
`COOKIE_SECURE=false`, `COOKIE_SAMESITE=lax` (ex. dans un `.env.local` ou variables de dev).  
En prod : garder `COOKIE_SECURE=true`, `COOKIE_SAMESITE=none`.

### G) Cas limites UX

- **User existant sans mot de passe** : Google login OK (auto-link) ; option « Définir un mot de passe » dans le profil si mode mixte.
- **409 (compte déjà lié)** : proposer login email/mdp ou contacter le support.

---

## 11) Diagnostic cookie cross-site (Safari / Chrome)

### URLs prod (ce projet)

| Rôle | URL |
|------|-----|
| **Front** | https://www.uwiapp.com (Vercel) |
| **API** | https://agent-production-c246.up.railway.app (Railway) |

→ Config **cross-site** (domaines différents). Safari / ITP peut être plus strict (cookie accepté mais pas renvoyé sur XHR, ou comportements variables).

### Règle d’or : limiter le cross-site

- **Recommandation forte** : exposer l’API sur un **custom domain** du même eTLD+1 que le front, ex. **https://api.uwiapp.com** (CNAME vers Railway ou proxy). Même cross-origin, mais beaucoup plus fiable (Safari, cookies).
- Tant que l’API reste sur `*.up.railway.app`, considérer la config comme « cross-site à risque Safari » et valider sur Safari après chaque changement.

### Ce qu’il faut vérifier (backend)

1. **Cookie** : ne **pas** set `Domain=` (host-only). Le code actuel ne set pas `domain` → OK.
2. **Réponse login / google/callback** :
   - `Set-Cookie: uwi_session=...; Path=/; HttpOnly; Secure; SameSite=None`
   - `Secure` obligatoire si `SameSite=None`.
3. **CORS** sur les réponses (au moins callback et /me) :
   - `Access-Control-Allow-Credentials: true`
   - `Access-Control-Allow-Origin` = origine exacte (pas `*`). Inclure **les deux** : `https://www.uwiapp.com` et `https://uwiapp.com` (sinon les users qui arrivent sans www ont 401).
4. **Préflight OPTIONS** : `allow_methods` doit inclure **POST** et **OPTIONS**, `allow_headers` doit inclure **Content-Type** (déjà le cas en backend).

### Diagnostic rapide (DevTools)

1. **Network** → **POST /api/auth/google/callback** (ou login) : vérifier la présence du header **Set-Cookie**.
2. **Application** → **Cookies** : si le cookie n’apparaît pas alors que Set-Cookie est présent → le navigateur l’a bloqué.
3. **GET /api/auth/me** : si callback = 200 mais /me = 401 → cookie non stocké ou non envoyé (souvent cross-site / Safari).

### Test minimal Safari

Sur Safari (macOS ou iOS) : login Google → **POST /api/auth/google/callback** = 200 → **GET /api/auth/me** = 200.  
Si callback = 200 mais /me = 401 : cookie non stocké ou non renvoyé → cas Safari/ITP typique (voir diagnostic DevTools ci‑dessus).

### Résumé

- **Config actuelle** : front www.uwiapp.com, API agent-production-c246.up.railway.app → **cross-site**, **risque Safari possible**. À valider en réel sur Safari.
- **Fix le plus fiable** : custom domain API **api.uwiapp.com** (voir plan ci‑dessous).

---

## 12) Plan concret « api.uwiapp.com » (recommandé)

**Objectif** : passer de `agent-production-c246.up.railway.app` à `api.uwiapp.com` pour rester dans le même eTLD+1 (uwiapp.com) et réduire les blocages Safari.

**Étapes :**

1. **Railway** → service backend → **Settings** → **Domains** → **Custom Domain** : ajouter `api.uwiapp.com`. Railway indique la cible CNAME.
2. **DNS** (checklist) :
   - Créer **CNAME** `api.uwiapp.com` → cible fournie par Railway (ex. `agent-production-c246.up.railway.app` ou host Railway dédié).
   - Attendre la **propagation** DNS (quelques minutes à 1 h).
   - Vérifier dans Railway : statut du domaine **Active** et certificat TLS OK.
3. **Front (Vercel)** : **Settings** → **Environment Variables** → `VITE_UWI_API_BASE_URL=https://api.uwiapp.com`, puis **redéployer** (obligatoire : Vercel n’applique pas les changements d’env à chaud).
4. **Backend (Railway)** : `CORS_ORIGINS` doit contenir `https://www.uwiapp.com,https://uwiapp.com` (rien à changer si déjà le cas).
5. **Google Console** : si tu gardes `redirect_uri=https://www.uwiapp.com/auth/google/callback`, rien à changer.

**Résultat** : même cross-origin, mais same eTLD+1 (uwiapp.com) → cookies et Safari beaucoup plus fiables.

**Bascule progressive (recommandé)**  
- **Jour 0** : créer api.uwiapp.com (Railway + DNS), tester (health, login).  
- **Jour 1** : mettre `VITE_UWI_API_BASE_URL=https://api.uwiapp.com` sur Vercel et redéployer.  
- **48–72 h** : laisser l’ancien domaine Railway répondre en parallèle (ne pas le retirer tout de suite). Ça évite les erreurs si un vieux build ou du cache pointe encore vers l’ancien host.

### Bonus : www vs non-www

- **CORS** : autoriser **les deux** origines (`https://www.uwiapp.com` et `https://uwiapp.com`) pour que ça marche quel que soit l’URL tapée.
- **Canonical** : pour éviter la duplication, le plus propre est de forcer un seul domaine (ex. 301 de `https://uwiapp.com` → `https://www.uwiapp.com`) côté Vercel/redirect. Optionnel.

### Sessions après bascule (attendu)

Les cookies sont **host-only** : celui posé sur `agent-production-c246.up.railway.app` n’est pas envoyé vers `api.uwiapp.com`, et inversement. Donc **après bascule de domaine API**, les utilisateurs qui avaient une session ouverte devront **se reconnecter** (login mot de passe ou Google). C’est normal.  
➡️ Prévoir côté UX un message type **« Session expirée, veuillez vous reconnecter »** quand `/me` renvoie 401.

### À la bascule api.uwiapp.com : checklist

**Front**  
- **landing/.env.example** : `VITE_UWI_API_BASE_URL=https://api.uwiapp.com` (déjà fait dans le repo).  
- **Vercel** : **Settings** → **Environment Variables** → `VITE_UWI_API_BASE_URL=https://api.uwiapp.com`, puis **redéployer** (obligatoire). Pas d’« allowed origins » à toucher pour cette variable.

**Backend (Railway)**  
- **CORS_ORIGINS** : garder `https://www.uwiapp.com,https://uwiapp.com`.  
- **Domains** : ajouter **api.uwiapp.com** ; **ne pas retirer** `agent-production-c246.up.railway.app` pendant **48–72 h** pour que les deux répondent (évite erreurs cache / vieux build). Ensuite tu peux optionnellement retirer l’ancien domaine.

### Validation rapide une fois api.uwiapp.com actif

À exécuter pour confirmer que la prod répond bien sur le nouveau domaine. Remplace `api.uwiapp.com` si ton host est différent, et `EMAIL` / `Secret#2026` par des identifiants de test.

**1. Health**

```bash
curl -s https://api.uwiapp.com/health | head -1
```

**2. CORS preflight (OPTIONS)**

```bash
curl -s -X OPTIONS https://api.uwiapp.com/api/auth/me \
  -H "Origin: https://www.uwiapp.com" -H "Access-Control-Request-Method: GET" -I
```

**Attendu** : `Access-Control-Allow-Origin: https://www.uwiapp.com`, `Access-Control-Allow-Credentials: true`, et **Vary: Origin** (ou `vary: Origin`). Si Vary: Origin est absent derrière un proxy, risque de mauvaise réponse mise en cache.

**3. Login + cookie + /me (duo qui prouve que le cookie est accepté et que /me voit la session)**

```bash
# Login + stockage du cookie
curl -i -c /tmp/uwi_cookies.txt -X POST https://api.uwiapp.com/api/auth/login \
  -H "Origin: https://www.uwiapp.com" \
  -H "Content-Type: application/json" \
  -d '{"email":"EMAIL","password":"Secret#2026"}'

# /me avec cookie
curl -i -b /tmp/uwi_cookies.txt https://api.uwiapp.com/api/auth/me \
  -H "Origin: https://www.uwiapp.com"
```

**Attendu** : POST login → **200** et header **Set-Cookie: uwi_session=...**. GET /me → **200** et body JSON (id, tenant_id, email, role). Si /me retourne 200 ici, cookie + JWT + CORS sont cohérents côté API. Vérifier aussi **Vary: Origin** sur la réponse /me si tu as un cache/proxy.

**4. Test navigateur**

- Aller sur https://www.uwiapp.com/login → « Continuer avec Google » ou login email+mdp → après redirection, le dashboard (/app) doit s’afficher.
- **Network** : tous les appels API doivent partir vers **api.uwiapp.com** (aucun vers `*.railway.app`). Si tu vois encore l’ancien domaine, une lib utilise peut‑être un endpoint hardcodé → vérifier que tout passe par `getApiUrl()` / `VITE_UWI_API_BASE_URL`.
- **Application → Cookies** : ouvrir DevTools → **Application** (ou Storage) → **Cookies** → **https://api.uwiapp.com**. Vérifier la présence de **uwi_session** et ses attributs : **HttpOnly**, **Secure**, **SameSite=None**. S’assurer que le cookie est bien attaché à **https://api.uwiapp.com** (domaine de l’API) et **pas** à https://www.uwiapp.com (front) — c’est normal : cookie host-only côté API.

---

## 13) Six micro-points (éviter “ça marche sur Chrome mais pas ailleurs”)

### 1) CORS : Vary: Origin

Si l’API passe derrière un cache/proxy, les réponses qui varient selon `Access-Control-Allow-Origin` doivent inclure **Vary: Origin**, sinon un cache peut renvoyer une réponse avec le mauvais `Allow-Origin`.  
Le middleware CORS Starlette/FastAPI le gère en général quand `allow_credentials=True`. **À vérifier** dans les headers de réponse (POST /callback, GET /me) : si absent derrière un proxy, l’ajouter (middleware ou proxy).

### 2) HTTPS only côté front

- Pas de **mixed content** (tout en HTTPS sur www.uwiapp.com).
- En prod, la landing ne doit **pas** tourner sur un preview **http://...** (sinon les cookies `Secure` ne se posent pas). Vercel previews en HTTPS par défaut → OK si tu n’exposes pas d’URL http en prod.

### 3) Cookie homogène sur login password

Même politique de cookie sur **POST /api/auth/login** (email+mdp) que sur **POST /api/auth/google/callback** :  
`Set-Cookie: uwi_session=...; Path=/; HttpOnly; Secure; SameSite=None; Max-Age=...`  
À vérifier une fois : réponse **POST /api/auth/login** → header **Set-Cookie** identique (pas de différence qui ferait que l’un pose le cookie et l’autre non).

### 4) Safari : test navigation privée + iOS

Le test minimal (callback 200 puis /me 200) doit être fait sur :
- **Safari macOS** (normal),
- **Safari navigation privée** (souvent plus strict),
- **Safari iOS** si possible (souvent le pire).  
Si tu ne peux pas tester iOS, le passage à **api.uwiapp.com** réduira une bonne partie du risque.

### 5) Google redirect_uri : rester sur le front

**Bonne pratique** : `redirect_uri` pointe vers le **front** (ex. `https://www.uwiapp.com/auth/google/callback`), pas vers l’API. C’est déjà le cas dans la spec → évite des soucis CORS et UX.

### 6) Vérification finale (headers réels)

Pour confirmer que tout est “cookie + CORS compliant”, vérifier (sans valeurs sensibles) les headers de :
- **POST /api/auth/google/callback** (réponse 200) : `Set-Cookie`, `Access-Control-Allow-Credentials: true`, `Access-Control-Allow-Origin` (exact), `Vary: Origin` si proxy/cache.
- **GET /api/auth/me** juste après : même CORS ; le cookie doit être envoyé par le navigateur (Request headers : `Cookie: uwi_session=...`).

---

## Checklist finale avant prod (forgot / reset)

### A) URL dans l’email : encodage

Le lien de reset est construit avec `urllib.parse.urlencode({"email": email, "token": token})` pour éviter les caractères spéciaux (+, /, etc.) dans la query string.

### B) ResetPassword.jsx : pas de token dans l’URL

Après lecture des paramètres `email` et `token` depuis l’URL, la page appelle `window.history.replaceState({}, "", "/reset-password")` pour ne pas laisser le token dans l’historique / screenshots.

### C) Cookie cross-site

Si l’API est encore sur `*.railway.app`, le reset peut réussir mais `/me` échouer sur Safari. Une fois sur **api.uwiapp.com**, le comportement est plus stable.

### D) Rate limiting (auth)

- **POST /api/auth/forgot-password** : 5 requêtes/min par IP, 3/min par email (429 si dépassement).
- **POST /api/auth/reset-password** : 10 requêtes/min par IP.
- **POST /api/auth/login** : 10 requêtes/min par IP.

Implémentation : `backend/auth_rate_limit.py` (in-memory TTL 60 s). Pour multi-instances, prévoir Redis plus tard.

---

## Tests curl « vérité terrain »

Remplacer `EMAIL`, `TOKEN`, `Secret#2026!!` et l’URL si besoin.

**Forgot (toujours 200, anti-enumération) :**
```bash
curl -i -X POST https://api.uwiapp.com/api/auth/forgot-password \
  -H "Content-Type: application/json" \
  -d '{"email":"EMAIL"}'
```

**Reset puis /me avec cookie :**
```bash
curl -i -c /tmp/uwi_cookies.txt -X POST https://api.uwiapp.com/api/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{"email":"EMAIL","token":"TOKEN","new_password":"Secret#2026!!"}'

curl -i -b /tmp/uwi_cookies.txt https://api.uwiapp.com/api/auth/me
```

Attendu : 200 sur reset, puis 200 sur /me avec le profil.
