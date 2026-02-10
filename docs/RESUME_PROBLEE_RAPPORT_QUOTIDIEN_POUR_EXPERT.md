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

## Fichiers utiles

- Endpoint : `backend/routes/reports.py`  
- Envoi email : `backend/services/email_service.py` (send_daily_report_email)  
- Doc config : `docs/CONFIG_RAPPORT_QUOTIDIEN_COMPLETE.md`  
- Guide dépannage : `docs/RAPPORT_QUOTIDIEN_POURQUOI_PAS_EMAIL.md`

---

*Résumé rédigé pour être transmis à un expert humain (Railway / réseau / SMTP).*
