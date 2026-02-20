# Problème : connexion admin (email + mot de passe) — « Identifiants invalides »

## Contexte

- **Front** : SPA (Vite/React) hébergée sur **Vercel**. Page de login admin : `/admin/login` (formulaire email + mot de passe).
- **Backend** : **FastAPI** sur **Railway**. Routes admin sous `/api/admin/*`.
- **Auth** : après un login réussi, le backend pose un cookie HttpOnly `uwi_admin_session` (JWT) et renvoie `{ "ok": true }`. Le front enchaîne avec un `GET /api/admin/auth/me` (avec `credentials: "include"`) pour vérifier la session.

## Symptôme

L’utilisateur saisit un **email** et un **mot de passe** puis clique sur « Se connecter ».  
Le backend répond **HTTP 401** avec le détail **« Identifiants invalides »**.  
Aucune redirection vers l’admin, pas de message « Session non persistée » (donc le blocage est bien au moment du login, pas au moment d’envoi du cookie).

## Configuration backend attendue (Railway)

Le login email/mot de passe repose sur ces variables d’environnement (lues au démarrage du process) :

| Variable | Rôle |
|----------|------|
| **ADMIN_EMAIL** | Email autorisé (comparé en `.strip().lower()` à l’email envoyé dans le body). |
| **ADMIN_PASSWORD** | Mot de passe en clair (comparé à `(body.password or "").strip()`). **Ou** |
| **ADMIN_PASSWORD_HASH** | Hash bcrypt du mot de passe (prioritaire si défini). `bcrypt.checkpw(password.encode("utf-8"), ADMIN_PASSWORD_HASH.encode("utf-8"))`. |
| **JWT_SECRET** (ou **ADMIN_SESSION_SECRET**) | Secret pour signer le JWT du cookie de session. |

- Si **ADMIN_EMAIL** est vide → le backend renvoie **503** (« Admin login not configured (ADMIN_EMAIL) »), pas 401.
- Si **ADMIN_PASSWORD** et **ADMIN_PASSWORD_HASH** sont vides → **503** (« Admin login not configured (ADMIN_PASSWORD_HASH or ADMIN_PASSWORD) »).
- Donc en cas de **401**, le backend considère que le login *est* configuré, mais que la combinaison email/mot de passe ne correspond pas.

## Code côté backend (extrait)

- Chargement des variables (au chargement du module) :
  - `ADMIN_EMAIL = (os.environ.get("ADMIN_EMAIL") or "").strip().lower()`
  - `ADMIN_PASSWORD = (os.environ.get("ADMIN_PASSWORD") or "").strip()`
  - `ADMIN_PASSWORD_HASH = (os.environ.get("ADMIN_PASSWORD_HASH") or "").strip()`

- Route **POST /api/admin/auth/login** (body JSON : `email`, `password`) :
  - `email = (body.email or "").strip().lower()`
  - Rejet 401 si : `email != ADMIN_EMAIL` **ou** `not _verify_admin_password((body.password or "").strip())`

- `_verify_admin_password(password)` :
  - Si **ADMIN_PASSWORD_HASH** non vide : `bcrypt.checkpw(password.encode("utf-8"), ADMIN_PASSWORD_HASH.strip().encode("utf-8"))` (avec try/except, en cas d’exception → `False`).
  - Sinon si **ADMIN_PASSWORD** non vide : `password.strip() == ADMIN_PASSWORD`.
  - Sinon : `False`.

## Diagnostic déjà en place

- **GET /api/admin/auth/status** (sans auth) renvoie par exemple :
  - `login_configured`, `email_set`, `password_plain_set`, `password_hash_set`, `jwt_secret_set`
- Permet de vérifier si le process backend « voit » bien les variables (après redéploiement Railway).

## Hypothèses possibles

1. **Variables non prises en compte**  
   Valeurs définies dans l’interface Railway mais pas injectées au runtime (mauvais service, pas de redéploiement après ajout/modification). À croiser avec la réponse de **/api/admin/auth/status**.

2. **Valeur de mot de passe**  
   - Avec **ADMIN_PASSWORD** : espaces, caractères spéciaux ou encodage différent entre la valeur dans Railway et ce que le front envoie.  
   - Avec **ADMIN_PASSWORD_HASH** : hash bcrypt tronqué, multi-ligne, ou généré avec un mot de passe différent de celui saisi.

3. **Email**  
   Casse normalisée côté backend (`.lower()`), donc peu probable si l’email est correct ; à vérifier toutefois que **ADMIN_EMAIL** sur Railway correspond bien à l’email saisi (pas d’espace, pas de faute).

4. **Moment de chargement des variables**  
   Les variables sont lues au **démarrage** du process (au import du module). Si elles ont été ajoutées/modifiées sans redéploiement, l’instance en cours peut encore avoir les anciennes valeurs (ou vides).

## Ce qui fonctionne par ailleurs

- Connexion admin avec **Bearer ADMIN_API_TOKEN** (header `Authorization: Bearer <token>`) fonctionne : les routes admin sont accessibles avec ce token.
- Le test email (Postmark, etc.) et le reste de l’app ne sont pas bloqués par ce problème.

## Résumé pour l’expert

- **Problème** : 401 « Identifiants invalides » sur **POST /api/admin/auth/login** alors que l’utilisateur pense utiliser le bon email et le bon mot de passe.
- **Stack** : Front Vercel (SPA), Backend FastAPI Railway, auth par cookie JWT après login email/password (variables **ADMIN_EMAIL** + **ADMIN_PASSWORD** ou **ADMIN_PASSWORD_HASH**).
- **À clarifier** : pourquoi la comparaison email/mot de passe échoue alors que les variables sont censées être définies sur Railway (vérification possible via **GET /api/admin/auth/status** et redéploiement effectué après toute modification des variables).

---

## Plan de debug (intégré)

Un plan de résolution pas à pas (ordre optimal, piège priorité hash, test curl sans front, diagnostic 30 s) est décrit dans **docs/ADMIN_LOGIN_DEPANNAGE.md** (sections « Plan de debug 401 » et « Interprétation rapide »).
