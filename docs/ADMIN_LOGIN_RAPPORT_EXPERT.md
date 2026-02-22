# Rapport pour l’expert : Admin login (Railway FastAPI) — 401 "Identifiants invalides"

**Date :** _____________  
**Backend :** https://agent-production-c246.up.railway.app  
**Front :** __________________________  
**Objectif :** diagnostiquer 401 au POST /api/admin/auth/login (email+mdp)

---

## 0) Informations rapides (à remplir)

- **Service Railway concerné (nom du service) :** _____________
- **Dernier redeploy effectué :** oui / non — date/heure : _____________
- **Variables modifiées récemment :** oui / non — lesquelles : _____________

---

## 1) Health (backend à jour)

```bash
curl -s https://agent-production-c246.up.railway.app/health | jq
```

**Résultat :** __________________________________

---

## 2) Status admin login (vérité runtime des env vars)

```bash
curl -s https://agent-production-c246.up.railway.app/api/admin/auth/status | jq
```

**Copier/coller le JSON complet ici :**

```
PASTE_JSON_HERE
```

**Table (extrait) :**

| Champ | Valeur |
|-------|--------|
| login_configured | |
| email_set | |
| password_plain_set | |
| password_hash_set | |
| jwt_secret_set | |

**Lecture expert (très important) :**

- Si **password_hash_set = true** → le hash est prioritaire (même si ADMIN_PASSWORD est correct).
- Beaucoup de 401 viennent de : **ADMIN_PASSWORD_HASH présent mais invalide** (tronqué, guillemets, espace, mauvais format) → bcrypt.checkpw échoue → False → 401.

---

## 3) Test backend pur : POST login (capturer headers + body)

Remplacer **TON_EMAIL** / **TON_MDP** par les valeurs supposées correctes.

```bash
curl -i -s -X POST https://agent-production-c246.up.railway.app/api/admin/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"TON_EMAIL","password":"TON_MDP"}'
```

**À relever (copier/coller) :**

- **Code HTTP :** ___________
- **Body :** ______________________
- **Header set-cookie présent ?** oui / non
- **Si oui, copier la ligne set-cookie :** ______________________
- **Autres headers utiles (vary, access-control-*) :** ______________________

**Interprétation :**

- **401 ici** ⇒ problème exclusivement côté comparaison email/mdp (env vars, hash, mauvais service, pas redeploy).
- **200 ici** ⇒ le login backend marche, le problème sera ensuite cookie / CORS / SameSite / domain.

---

## 4) Si login = 200 : tester /me en réutilisant le cookie (sans front)

**Option A (recommandée) : cookie jar**

```bash
# 1) Login et stockage cookies
curl -s -c /tmp/cookies.txt -X POST https://agent-production-c246.up.railway.app/api/admin/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"TON_EMAIL","password":"TON_MDP"}' | jq

# 2) Appel /me avec cookie
curl -i -s -b /tmp/cookies.txt https://agent-production-c246.up.railway.app/api/admin/auth/me
```

**Résultat /me :**

- **Code HTTP :** ___________
- **Body :** ______________________

**Interprétation :**

- Si **/me = 200** ⇒ session OK côté backend, le souci est front (cross-domain cookies / credentials / CORS).
- Si **/me = 401** malgré cookie ⇒ cookie non posé correctement (path/domain/samesite/secure) ou token invalidé.

---

## 5) Test depuis le front (navigateur)

1. Ouvrir : **https://__________/admin/login**
2. Saisir exactement le même email+mdp.
3. Cliquer « Se connecter ».

**Dans DevTools → Network, sur la requête POST /api/admin/auth/login :**

- **Status :** ___________
- **Response body :** ______________________
- **Onglet Response Headers :**
  - set-cookie présent ? oui / non
  - access-control-allow-credentials : ______________________
  - access-control-allow-origin : ______________________
- **Onglet Request :** le front envoie bien `credentials: "include"` ? oui / non

**Si login = 200, vérifier la requête GET /api/admin/auth/me :**

- **Status :** ___________
- Si 401 : dans **Application → Cookies**, cookie `uwi_admin_session` existe ? oui / non

---

## 6) Résumé "1 écran" à envoyer à l’expert

- JSON complet de **GET /api/admin/auth/status**
- **password_hash_set** = true / false
- Résultat du **curl -i POST /login** (status + présence de set-cookie)
- Si possible : résultat de **/me avec cookie jar**
- Côté front : status POST /login, puis status GET /me, et présence du cookie dans le navigateur

---

## Notes expert (causes les plus probables selon symptômes)

**Si 401 même en curl direct — priorité :**

1. ADMIN_PASSWORD_HASH présent mais faux / mal formé (le plus fréquent)
2. Variables pas dans le bon service Railway / pas redeploy effectif
3. Email configuré différent de celui tapé (ou alias)
4. Mot de passe contient caractères invisibles / copier-coller

**Si curl login = 200 mais front échoue ensuite — alors c’est cookie/CORS :**

- `credentials: "include"` côté fetch
- `Access-Control-Allow-Credentials: true`
- `Access-Control-Allow-Origin` doit être exactement le domaine du front (pas `*`)
- Cookie `SameSite=None; Secure` si cross-domain

**Si tu me colles ici le JSON de /api/admin/auth/status + le résultat brut de curl -i sur /login, je te dis immédiatement (sans hypothèses) quel cas tu es et la correction exacte (hash prioritaire / mauvais runtime / cookie).**
