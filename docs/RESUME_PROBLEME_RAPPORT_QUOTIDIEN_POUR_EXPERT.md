# Résumé — Problème rapport quotidien (email) pour expert

## Contexte

- **Objectif** : envoyer un email quotidien (stats des appels IVR : RDV pris, transferts, abandons) à une adresse admin (henigoutal@gmail.com).
- **Stack** : Backend FastAPI sur **Railway**. Endpoint **POST /api/reports/daily** protégé par header `X-Report-Secret`. Génération du rapport (DB + template HTML) puis envoi SMTP (Gmail).
- **Déclenchement** : appel manuel (curl) ou job GitHub Actions à 19h Paris.

---

## Ce qui fonctionne

- **GET /health** sur Railway répond en **HTTP 200** en quelques secondes (app bien en ligne).
- **Secret** : avec le bon `X-Report-Secret`, l’app accepte la requête (pas de 403).
- **Config** : en local, toutes les variables sont définies (REPORT_EMAIL, SMTP_EMAIL, SMTP_PASSWORD, etc.) et `make check-report-env` est OK.
- **Code** : la logique de rapport (génération + envoi SMTP) est testée en unitaire et fonctionne.

---

## Ce qui ne fonctionne pas (côté client)

- **POST /api/reports/daily** : depuis une machine cliente (curl depuis un Mac), la requête **ne reçoit jamais de réponse** → **HTTP_CODE:000** (timeout côté client) même avec `--max-time 60` ou 90 secondes.
- Donc : pas de réponse HTTP (ni 200, ni 500, ni body). Le client coupe après son timeout.
- Pourtant **GET /health** sur la même URL de base répond bien.

---

## Hypothèses envisagées

1. **Cold start Railway** : le premier appel après inactivité serait très long. → Test : appeler d’abord /health pour « réveiller » l’app, puis immédiatement POST /reports/daily. Résultat : toujours 000 sur le POST après 90 s.
2. **Timeout dans notre code** : on a ajouté un timeout de 25 s dans l’endpoint (exécution du rapport dans un thread avec `future.result(timeout=25)`). → Déploiement fait, mais le client reçoit toujours 000. Soit le nouveau code n’est pas pris en compte, soit la réponse n’atteint jamais le client.
3. **Proxy / load balancer Railway** : une couche devant l’app pourrait couper les requêtes longues (ex. timeout à 30 s) sans que notre code ne soit en cause. La réponse 200/202 partirait du serveur mais serait perdue avant d’arriver au client.
4. **Blocage côté serveur** : une des étapes (accès DB, `get_client_memory()`, `get_daily_report_data()`, connexion SMTP depuis Railway) pourrait bloquer indéfiniment ou très longtemps (ex. résolution DNS SMTP, pare-feu sortant). Dans ce cas notre timeout de 25 s aurait dû renvoyer une réponse ; si le client voit encore 000, soit le déploiement avec timeout n’est pas actif, soit la réponse est perdue en chemin.

---

## Solution actuelle (côté code)

- L’endpoint a été modifié pour **répondre immédiatement en HTTP 202 Accepted** et lancer la génération + envoi du rapport dans un **thread en arrière-plan**.
- Le client (curl ou GitHub Actions) reçoit donc une réponse en moins d’une seconde, avec un body du type :  
  `{"status": "accepted", "message": "Rapport en cours de génération et envoi. Consulter les logs Railway pour le résultat."}`
- Ainsi, plus de **HTTP 000** côté client. Le succès réel de l’envoi d’email doit être vérifié dans les **logs Railway** (ex. `report_daily background result:` ou `report_sent`) et dans la boîte mail.

---

## Points à faire vérifier par un expert

1. **Railway**  
   - Y a-t-il un **timeout de requête** (proxy / load balancer) inférieur à 60–90 s qui couperait les réponses longues ?  
   - Le **dernier déploiement** correspond-il bien au commit qui contient le timeout 25 s puis la réponse 202 + background ?

2. **Réseau / SMTP depuis Railway**  
   - Connexion sortante vers **smtp.gmail.com:587** : autorisée ? Pas de blocage pare-feu / sécurité qui ferait planter ou attendre indéfiniment la connexion SMTP ?

3. **Comportement observé**  
   - GET /health → 200 rapide.  
   - POST /api/reports/daily (avec bon secret) → aucune réponse reçue par le client (000) avant la mise en place du 202 + background.  
   - Après passage au 202 + background : le client doit recevoir 202 rapidement ; à confirmer après déploiement.

4. **Variables d’environnement**  
   - Sur Railway, les variables REPORT_EMAIL, SMTP_EMAIL, SMTP_PASSWORD, SMTP_HOST, SMTP_PORT sont-elles bien définies pour le service qui exécute le backend ? (En local elles sont présentes et le check `make check-report-env` est OK.)

---

## Plan d'attaque expert (pour trancher définitivement)

### 1) Vérif immédiate : le 202 + background est-il bien déployé ?

Depuis le Mac :
```bash
curl -sv -X POST "https://agent-production-c246.up.railway.app/api/reports/daily" \
  -H "X-Report-Secret: MonRapportSecret2025" \
  --max-time 15
```

**À voir :** `HTTP/2 202` (ou `HTTP/1.1 202`) + body `{"status":"accepted"...}`.

Si encore **HTTP_CODE:000** : soit le nouveau build n’est pas servi, soit mauvaise URL/service, soit réseau local.  
**Action :** dans Railway, ouvrir les logs juste avant de relancer le curl. Une ligne **"report_daily accepted, running in background"** doit apparaître à l’entrée. Si elle n’existe pas → mauvais déploiement / mauvais service.

---

### 2) Si le 202 marche : est-ce que le background réussit ?

Chercher dans les logs Railway, **dans l’ordre** :
1. `report_daily accepted, running in background`
2. `report_daily: connecting SMTP smtp.gmail.com:587`
3. Puis soit :
   - ✅ `report_sent` → email parti
   - ❌ `report_failed` + erreur (535 auth, timeout, etc.)

Si tu vois "connecting SMTP…" mais rien après → blocage réseau/DNS/TLS (ou pas de timeout SMTP).

---

### 3) Test réseau qui tranche SMTP (Railway shell)

Dans le shell/console Railway du service :

**Test TCP (port 587 sortant) :**
```bash
nc -vz smtp.gmail.com 587
```
Attendu : `succeeded`.

**Test TLS STARTTLS :**
```bash
openssl s_client -starttls smtp -connect smtp.gmail.com:587 -crlf -quiet
```
Attendu : certificat + connexion établie.

**Interprétation :**  
- `nc` échoue → egress 587 bloqué.  
- `nc` OK mais `openssl` bloque → TLS/handshake/DNS.  
- Les deux OK → le blocage est dans le code SMTP (timeout, starttls, auth).

---

### 4) Gmail SMTP : pièges

- Compte expéditeur = SMTP_EMAIL.  
- SMTP_PASSWORD = **mot de passe d’application** (2FA obligatoire).  
- From cohérent avec le compte.  
- Vérifier Spam + Tous les messages côté réception.  
- Si credentials faux : `535 5.7.8 Username and Password not accepted` → doit apparaître en logs (ne devrait pas pendre).

---

### 5) Pourquoi HTTP 000 avant

La requête attendait : génération rapport + DB **puis** envoi SMTP (connexion + TLS + auth). Si une étape bloque (souvent SMTP), le serveur ne renvoie jamais → curl timeout → 000. Le 202 sépare "accuser réception" et "faire le boulot".

---

### 6) Rendre ça production-grade

Gmail SMTP en prod est fragile (quotas, blocages, latences).  
**Conseil :** passer à un provider email API (SendGrid / Mailgun / Postmark / Amazon SES) : pas de port 587, meilleurs logs, retries. Garder le **202 + background** dans tous les cas.

---

### 7) Réponse à fournir à l’expert (pour trancher en 1 message)

| Question | Ma réponse |
|----------|------------|
| **Quand tu fais le curl, est-ce que tu reçois 202 maintenant ?** | *(Oui / Non / Pas encore testé après dernier déploiement)* |
| **Dans les logs Railway, après "accepted", ça bloque à quel dernier log exact ?** | *(ex : "connecting SMTP…", "report_sent", "report_failed", rien après accepted, etc.)* |

Avec ça, l’expert peut dire si c’est infra (port/TLS), auth Gmail, ou DB/rapport — et donner la marche exacte pour corriger.

---

## Fichiers utiles

- Endpoint : `backend/routes/reports.py`  
- Envoi email : `backend/services/email_service.py` (send_daily_report_email)  
- Doc config : `docs/CONFIG_RAPPORT_QUOTIDIEN_COMPLETE.md`  
- Guide dépannage : `docs/RAPPORT_QUOTIDIEN_POURQUOI_PAS_EMAIL.md`

---

*Résumé + plan d’attaque pour expert (Railway / réseau / SMTP).*
