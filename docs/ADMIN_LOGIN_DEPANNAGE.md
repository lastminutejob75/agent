# Admin : je n’arrive pas à me connecter

## 0. Vérifier que le backend voit bien les variables

**GET** (dans le navigateur ou avec curl) :

```
https://TON-BACKEND.railway.app/api/admin/auth/status
```

Réponse attendue si tout est OK :

```json
{
  "login_configured": true,
  "email_set": true,
  "password_plain_set": true,
  "password_hash_set": false,
  "jwt_secret_set": true
}
```

- Si **login_configured** est **false** : une des variables manque ou est vide → voir §1.
- Si **email_set** ou **password_plain_set** / **password_hash_set** est **false** : la variable correspondante n’est pas lue par le backend (vérifier le nom exact, pas d’espace, redéployer après modification).

**Interprétation rapide (expert)**  
Si tu as 401 (pas 503), normalement `email_set` et au moins un des deux `password_*` sont true.  
👉 **Si `password_hash_set: true`** et tu n’es pas 100 % sûr du hash : **vide ADMIN_PASSWORD_HASH** et garde uniquement **ADMIN_PASSWORD** le temps de valider le flow. Le backend donne **priorité au hash** : si ADMIN_PASSWORD_HASH est défini (même invalide), c’est lui qui est utilisé et un hash mal formé → bcrypt échoue → 401.

---

## Plan de debug 401 (ordre optimal)

1. **GET /api/admin/auth/status** (direct vers Railway, pas via Vercel) :
   ```bash
   curl -s https://TON_BACKEND_RAILWAY_DOMAIN/api/admin/auth/status | jq
   ```
   Noter `password_hash_set` / `password_plain_set` / `email_set`.

2. **Si `password_hash_set: true`** → supprimer ou vider **ADMIN_PASSWORD_HASH**, ne laisser que **ADMIN_PASSWORD** (mot de passe clair) pour valider.

3. **Variables sur le bon service** : dans Railway, vérifier que ADMIN_EMAIL / ADMIN_PASSWORD sont bien sur **le service FastAPI qui sert le domaine** (pas un autre service). Puis **Redeploy / restart** (les env sont lues au chargement du module).

4. **Mot de passe propre** : mettre temporairement **ADMIN_PASSWORD** = `UwiAdmin#2026!` (sans espace ni caractère invisible) et **ADMIN_EMAIL** = ton email exact (ex. `admin@uwi.test` ou ton vrai email sans alias). Redeploy.

5. **Test sans front** (isoler Vercel) :
   ```bash
   curl -i https://TON_BACKEND_RAILWAY_DOMAIN/api/admin/auth/login \
     -H 'Content-Type: application/json' \
     -d '{"email":"TON_EMAIL","password":"TON_MDP"}'
   ```
   - **401** → problème 100 % côté env / vérif password (pas CORS, pas cookies).
   - **200** avec `{"ok":true}` → le front envoie autre chose (champ, trimming, encodage).

6. **Piège priorité hash** : si tu as **ADMIN_PASSWORD** ET **ADMIN_PASSWORD_HASH** et que le hash est faux ou d’un autre mot de passe → 401 même avec le bon mot de passe clair. Ne garder qu’un des deux le temps de stabiliser.

7. Une fois le login OK en curl puis depuis le front : (optionnel) régénérer un bcrypt propre (`$2b$12$...`), mettre **ADMIN_PASSWORD_HASH**, supprimer **ADMIN_PASSWORD**.

**Diagnostic en 30 s** : envoyer la sortie JSON de `GET /api/admin/auth/status` + indiquer si `password_hash_set` est true → on en déduit la cause la plus probable.

---

## 1. « Identifiants invalides » (401 au login)

Le backend compare **email** (en minuscules) et **mot de passe** avec les variables Railway.

**Sur Railway (Variables du service API) :**

| Variable | À mettre |
|----------|----------|
| **ADMIN_EMAIL** | L’email que tu saisis (ex. `hello@uwiapp.com`). Le backend le met en minuscules ; pas d’espace avant/après. |
| **ADMIN_PASSWORD** | Le mot de passe **exact** que tu entres (sans espace en trop). **Ou** |
| **ADMIN_PASSWORD_HASH** | Hash bcrypt **complet** du mot de passe (une seule ligne, commençant par `$2b$` ou `$2a$`). Ne mets **pas** ADMIN_PASSWORD en même temps. |
| **JWT_SECRET** | Doit être défini. Utilisé pour le cookie de session. |

**Générer un hash bcrypt (pour ADMIN_PASSWORD_HASH) :**

```bash
python3 -c "import bcrypt; print(bcrypt.hashpw(b'TonMotDePasse', bcrypt.gensalt()).decode())"
```

Copie **toute** la sortie (une seule ligne) dans **ADMIN_PASSWORD_HASH** sur Railway. Aucun espace ni saut de ligne avant/après.

- Si tu utilises **ADMIN_PASSWORD** : la valeur doit être **strictement** celle que tu tapes dans le formulaire (pas de guillemets dans la valeur Railway).
- Après toute modification : **redéployer** le service sur Railway, puis revérifier **/api/admin/auth/status**.

---

## 2. « Session non persistée » (login OK puis échec sur /me)

Le login renvoie 200 mais l’appel suivant (`/api/admin/auth/me`) renvoie 401 car le **cookie n’est pas renvoyé** par le navigateur (cross-domain).

**Sur Railway :**

- **ADMIN_COOKIE_SAMESITE** = `none` (obligatoire quand le front est sur un autre domaine que l’API, ex. front sur Vercel, API sur Railway).
- **CORS_ORIGINS** doit contenir **exactement** l’URL d’origine de ta page admin (sans slash final), par ex. :
  - `https://uwiapp.com`
  - ou `https://ton-projet.vercel.app` si tu accèdes à l’admin depuis ce domaine.

Redéployer après modification.

---

## 3. Erreur 403 sur le login

L’origine de la page (ex. `https://ton-projet.vercel.app`) n’est pas autorisée pour les routes admin.

**Sur Railway :**

- **CORS_ORIGINS** = liste d’origines séparées par des virgules, ex. :  
  `https://uwiapp.com,https://www.uwiapp.com,https://ton-projet.vercel.app`
- Ou **ADMIN_CORS_ORIGINS** = même liste si tu veux une config dédiée à l’admin.

Redéployer après modification.

---

## Vérification rapide (DevTools)

1. Ouvre **F12 → Network**.
2. Saisis email + mot de passe puis **Se connecter**.
3. Regarde la requête **POST** vers **`/api/admin/auth/login`** :
   - **200** → identifiants OK ; regarde ensuite la requête **GET** vers **`/api/admin/auth/me`** (si 401 → problème cookie / CORS, voir §2 et §3).
   - **401** → identifiants refusés → voir §1.
   - **403** → origine non autorisée → voir §3.
   - **503** → ADMIN_EMAIL ou ADMIN_PASSWORD/HASH ou JWT_SECRET manquant → voir §1.

Voir aussi **docs/ADMIN_LOGIN_COOKIE.md** pour le détail cookie / CORS.
