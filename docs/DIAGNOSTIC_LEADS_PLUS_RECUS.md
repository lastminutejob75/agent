# Diagnostic : plus de leads reçus / plus visibles en admin

Le flux lead : **Landing** (CreerAssistante) → `POST /api/pre-onboarding/commit` → **Backend** → `upsert_lead()` → table **pre_onboarding_leads** (PG) + email fondateur en async.

---

## Checklist rapide : « Lead introuvable » + « Pas d'email »

Si les deux échouent, vérifier dans cet ordre :

| # | Où | Quoi | Valeur attendue |
|---|-----|------|------------------|
| 1 | **Vercel** → Settings → Variables | `VITE_UWI_API_BASE_URL` | Même URL pour **Production ET Preview** (ex. `https://api.uwiapp.com`) |
| 2 | **Railway** → Variables | `DATABASE_URL` ou `PG_TENANTS_URL` | Postgres valide (leads y sont écrits) |
| 3 | **Railway** → Variables | `FOUNDER_EMAIL` ou `ADMIN_EMAIL` | Email qui reçoit les leads (ex. `contact@uwiapp.com`) |
| 4 | **Railway** → Variables | SMTP / Postmark | Configuré pour envoyer (voir `email_service.py`) |
| 5 | **Railway** → Logs | `commit_pre_onboarding_diagnostic` | Doit apparaître quand tu soumets un lead |
| 6 | **Railway** → Logs | `lead_founder_email on commit failed` | Si présent → problème email (destinataire, SMTP) |

**Test** : soumettre un lead depuis **www.uwiapp.com** (prod), pas une preview. Onglet **Réseau** : vérifier que `POST .../api/pre-onboarding/commit` part vers la bonne URL et retourne **200**.

**Diagnostic backend** : `GET /api/pre-onboarding/config` retourne `db_configured`, `email_recipient_configured`, `email_sender_configured`, `leads_ok`, `emails_ok`, `total_leads_in_db`, `backend_hint`. Si `total_leads_in_db: 0` → les commits ne vont pas sur ce backend (vérifier VITE_UWI_API_BASE_URL). Si `emails_ok: false` → définir FOUNDER_EMAIL (ou ADMIN_EMAIL, ADMIN_ALERT_EMAIL, REPORT_EMAIL) + Postmark ou SMTP sur Railway.

## Erreur « Lead introuvable » (écran finalisation)

Cette erreur apparaît quand un visiteur choisit un créneau de rappel (écran UWIFinalization) et que `POST /api/pre-onboarding/leads/{lead_id}/callback-booking` renvoie 404.

**Causes possibles :**
1. **lead_id perdu** — Le visiteur a rafraîchi la page ou fermé l’onglet après le commit. Le `lead_id` est stocké en sessionStorage ; s’il est vide, le callback n’est pas envoyé. Si le lien de retour pointe vers une URL sans `lead_id` en paramètre, il sera vide.
2. **Landing et backend sur des environnements différents** — La landing (ex. preview.vercel.app) pointe vers un backend de staging, le commit crée le lead en staging, mais le visiteur revient via une URL prod → le `lead_id` de staging n’existe pas en prod.
3. **DATABASE_URL / PG_TENANTS_URL** — Si le backend utilise une base différente entre le commit et le callback (réplicas, env distincts), le lead peut ne pas être trouvé.

**Vérification au chargement :** La landing appelle `GET /api/pre-onboarding/leads/{lead_id}/check` dès l'affichage de l'écran finalisation. Si 404 → message « Lien expiré » immédiat (pas de flow loading/reveal/congrats/handoff). Cela confirme que le lead n'existe pas dans le backend appelé.

**Diagnostic affiché :** En cas d'erreur, l'écran affiche « Backend : [URL] ». Vérifier que cette URL est bien celle du backend Railway prod (ex. `https://api.uwiapp.com` ou `https://agent-production-xxx.railway.app`). Si l'URL est différente ou vide → corriger `VITE_UWI_API_BASE_URL` sur Vercel (Preview ET Production) et redéployer.

**Vérifications :**
- Landing et admin : même `VITE_UWI_API_BASE_URL` (même backend).
- Railway : une seule base pour `DATABASE_URL` ou `PG_TENANTS_URL`.
- Logs Railway : chercher `callback_booking_diagnostic` et `commit_pre_onboarding_diagnostic` — le `db_hash` doit être identique.

---

## 1. Vérifier que la requête part bien vers le bon backend

- La landing appelle **`VITE_UWI_API_BASE_URL`** + `/api/pre-onboarding/commit`.
- Si cette variable est vide ou pointe vers une autre URL (autre env, autre déploiement), les leads ne vont pas sur le bon service / la bonne base.

**À faire :**
- **Vercel** (ou hébergeur de la landing) → Variables d’environnement → vérifier **VITE_UWI_API_BASE_URL** = `https://agent-production-c246.up.railway.app` (sans slash final).
- Redéployer la landing après toute modification des variables (les variables Vite sont prises au build).

---

## 2. Vérifier que le backend reçoit bien le commit

- En cas de **CORS** ou **mauvaise URL**, le navigateur peut bloquer la requête (erreur réseau côté front, pas de log côté backend).
- Si la requête arrive au backend, un **succès** est loggé avec :  
  `commit_pre_onboarding_diagnostic` et `lead_id`, `deployment_id`, `db_hash`.

**À faire :**
- **Railway** → service API (agent-production-c246) → **Logs**.
- Soumettre un lead de test depuis la landing.
- Chercher dans les logs :
  - **`commit_pre_onboarding_diagnostic`** → la requête est bien arrivée et le lead a été enregistré.
  - **`rate_limit pre_onboarding_commit`** → blocage 429 (trop de requêtes).
  - **`upsert_lead ... failed`** ou **`insert_lead failed`** → erreur base de données.
  - **Aucune de ces lignes** → la requête n’atteint pas ce backend (mauvaise URL, CORS, ou autre service).

---

## 3. Vérifier la base de données (pre_onboarding_leads)

- Les leads sont enregistrés dans la table **pre_onboarding_leads** via **DATABASE_URL** ou **PG_TENANTS_URL**.

**À faire (Railway Postgres ou client SQL) :**
```sql
SELECT id, email, created_at, status
FROM pre_onboarding_leads
ORDER BY created_at DESC
LIMIT 20;
```
- Vérifier s’il existe des lignes avec **created_at** après le 27 février.
  - **Oui** → les leads sont bien en base ; le souci peut être côté admin (liste leads, filtre, ou autre).
  - **Non** → soit les commits n’arrivent pas au backend, soit ils échouent (validation, rate limit, erreur DB). Vérifier les logs (étape 2) et l’URL / CORS (étape 1).

---

## 4. Rate limit (peu probable pour “plus du tout de leads”)

- Limite : **10 req/min par IP**, **3 req/min par email**.
- En cas de dépassement → **429** et message "Trop de demandes...".
- Si tous les visiteurs passent par la même IP (proxy, NAT), 10 req/min pourraient bloquer après quelques soumissions. Vérifier les logs pour **`rate_limit pre_onboarding_commit`**.

---

## 5. Erreur 500 "Erreur enregistrement lead"

- Si **upsert_lead()** retourne `None` (exception en base), le backend renvoie 500 avec ce message.
- Causes possibles : table absente, colonne manquante (migration non exécutée), contrainte violée, **DATABASE_URL** / **PG_TENANTS_URL** pointant vers une autre base ou une base vide.

**À faire :**
- Consulter les **logs backend** au moment du commit pour une exception Python (traceback).
- Vérifier que la **migration** qui crée ou modifie **pre_onboarding_leads** a bien été exécutée sur la base utilisée en prod (celle de **PG_TENANTS_URL** ou **DATABASE_URL**).

---

## 6. Récap des causes les plus probables

| Symptôme | Cause probable | Vérification |
|----------|----------------|--------------|
| Aucun log `commit_pre_onboarding_diagnostic` | Requête n’arrive pas au bon backend (URL ou CORS) | VITE_UWI_API_BASE_URL sur la landing + onglet Réseau du navigateur (URL appelée, statut, CORS) |
| Log 429 / rate_limit | Rate limit dépassé | Logs backend ; en test, attendre 1 min ou tester depuis une autre IP/email |
| Log `insert_lead failed` / `upsert_lead ... failed` | Erreur base (table, colonne, contrainte, connexion) | Traceback dans les logs ; vérifier migrations et connexion PG |
| Requête 200 mais pas de ligne après le 27/02 en base | Mauvais schéma ou mauvaise base (ex. autre DATABASE_URL) | Vérifier quelle base est utilisée (env du service Railway) et exécuter le SELECT ci-dessus sur cette base |

En priorité : **1** (URL + déploiement landing), **2** (logs au moment d’un commit test), **3** (SELECT sur **pre_onboarding_leads**).

---

## 7. Leads reçus par email mais absents de la liste admin

Si les **emails avec RDV confirmé** arrivent bien mais que la **liste /admin/leads** est vide, les leads sont bien en base (même backend, même table). **CORS correct (uwiapp.com)** : les vraies causes possibles sont ci‑dessous. La page admin affiche maintenant un message d’erreur explicite en cas d’échec (401, 403, 503, etc.).

### 7.1 CORS admin (403) — cause la plus fréquente

- Les routes **`/api/admin/*`** sont protégées par **ADMIN_CORS_ORIGINS** (ou, si vide, par **CORS_ORIGINS**).
- Si la page admin est ouverte depuis une **origine** (ex. `https://ton-app.vercel.app`) qui n’est pas dans cette liste, le backend renvoie **403** sur `GET /api/admin/leads`.
- Le frontend attrape l’erreur et affiche une liste vide (sans message "403").

**Historique :** Un changement CORS (commit du 24 février) avait restreint le défaut à `uwiapp.com` uniquement (plus de localhost). Selon la date de déploiement sur Railway, la liste admin a pu cesser d’afficher les leads à partir du 28 février. Le défaut a été rétabli pour inclure à nouveau localhost ; si ton admin est sur **Vercel**, ajoute son URL dans **CORS_ORIGINS** sur Railway.

**À faire :**
- **Railway** → service API → Variables : vérifier **ADMIN_CORS_ORIGINS** (ou **CORS_ORIGINS**).
- Y inclure **exactement** l’origine de la page admin (ex. `https://ton-app.vercel.app`), sans slash final, séparée par des virgules si plusieurs.
- Redéployer le service après modification.
- Dans l’onglet **Réseau** du navigateur (page /admin/leads), vérifier la requête vers `.../api/admin/leads` : si **403** → confirmer que l’origine est bien autorisée.

### 7.2 Backend retourne 0 lead (list_leads en erreur)

- Si **list_leads** lève une exception (connexion DB, schéma), elle retourne `[]` et le log contient **`list_leads failed`**.
- Les logs backend enregistrent aussi **`admin_leads_list ... count=0`** (ou le nombre retourné) à chaque appel réussi.

**À faire :**
- **Railway** → Logs : ouvrir la page /admin/leads puis chercher **`admin_leads_list`**.
  - **count=0** et pas de `list_leads failed` → la base ne contient pas de lignes (ou filtre status/enterprise qui exclut tout) ; vérifier le SELECT en §3.
  - **`list_leads failed`** → consulter la traceback pour erreur DB / colonne manquante.

### 7.3 401 Unauthorized — token manquant ou invalide (cause fréquente)

- L’admin exige un **cookie JWT** (après login email/mdp) ou un **Bearer token** (ADMIN_API_TOKEN).
- Si le token a expiré ou est invalide, le backend renvoie **401**. Le front affichait auparavant une liste vide sans message ; il affiche maintenant **« Session expirée ou token invalide. Reconnectez-vous depuis la page Admin. »**
- **À faire :** se reconnecter depuis la page Admin (ou ressaisir le token). Vérifier que le cookie/token est bien envoyé (onglet Réseau → requête `/api/admin/leads` → en-têtes).

### 7.4 Erreur DB dans list_leads (200 mais leads vides)

- Si **list_leads()** lève une exception (connexion PG, colonne manquante, etc.), elle retourne `[]` et le backend renvoie **200** avec `"leads": []`.
- **À faire :** dans les logs Railway, chercher **`list_leads failed`** + la traceback. Vérifier migrations appliquées et que **DATABASE_URL** / **PG_TENANTS_URL** pointent bien vers la même base que celle qui reçoit les commits (pre_onboarding).

### 7.5 Vérification rapide (curl)

- Appeler en direct (avec le token admin) :  
  `curl -s -H "Authorization: Bearer VOTRE_ADMIN_TOKEN" "https://agent-production-c246.up.railway.app/api/admin/leads"`  
- **200** avec tableau `leads` non vide → le backend renvoie les leads ; si le front affiche vide, vérifier l’URL appelée (VITE_UWI_API_BASE_URL) et le token envoyé.
- **401** → token manquant ou invalide (§ 7.3).
- **403** → CORS / origine non autorisée (§ 7.1).
- **200** avec `"leads": []` → soit la base est vide pour les filtres, soit **list_leads** a échoué (logs § 7.2 / 7.4).
