# Pourquoi je ne reçois pas l’email du rapport des appels ?

L’email quotidien (stats : RDV pris, raccrochés, transferts, etc.) dépend de **3 blocs** : GitHub qui appelle ton API, Railway qui reçoit l’appel, et l’envoi SMTP. Si un seul manque, tu ne reçois rien.

---

## 1. Vérifier que l’API répond (test manuel)

Remplace par ton URL Railway et ton secret :

```bash
curl -s -X POST "https://TON-APP.railway.app/api/reports/daily" \
  -H "Content-Type: application/json" \
  -H "X-Report-Secret: TON_REPORT_SECRET"
```

**Ce que tu peux voir :**

| Réponse | Signification |
|--------|----------------|
| **503** | `REPORT_SECRET` non défini sur Railway → définir `REPORT_SECRET` sur Railway. |
| **403** | Le secret envoyé ne correspond pas à `REPORT_SECRET` sur Railway → même valeur partout. |
| **200** + `"email_skipped": "REPORT_EMAIL ou OWNER_EMAIL non défini"` | Aucune adresse de réception → définir `REPORT_EMAIL` (ou `OWNER_EMAIL`) sur Railway. |
| **200** + `"email_skipped": "SMTP non configuré"` | Pas d’envoi possible → définir `SMTP_EMAIL`, `SMTP_PASSWORD`, et éventuellement `SMTP_HOST` / `SMTP_PORT` sur Railway. |
| **200** + `"clients_notified": 1` (sans `email_skipped`) | Rapport généré et email envoyé (ou tenté). Vérifier la boîte mail et les spams. |

---

## 2. Variables à avoir sur Railway

Toutes en **Variables** du service (Railway) :

| Variable | Rôle |
|----------|------|
| **REPORT_SECRET** | Secret partagé avec GitHub (ex. mot de passe fort). |
| **REPORT_EMAIL** (ou **OWNER_EMAIL**) | Adresse qui **reçoit** le rapport (la tienne). |
| **SMTP_EMAIL** | Compte qui **envoie** l’email (ex. Gmail). |
| **SMTP_PASSWORD** | Mot de passe du compte ou **mot de passe d’application** (Gmail : Sécurité → Mots de passe d’application). |
| **SMTP_HOST** | Ex. `smtp.gmail.com` |
| **SMTP_PORT** | Ex. `587` |

Sans **REPORT_EMAIL** / **OWNER_EMAIL** → aucun envoi.  
Sans **SMTP_EMAIL** / **SMTP_PASSWORD** → l’API répond 200 mais l’email ne part pas (tu verras `email_skipped` dans la réponse après déploiement).

---

## 3. Vérifier que le job GitHub tourne à 19h Paris

- GitHub → ton repo → **Actions** → workflow **« Daily IVR Report »**.
- À 19h Paris (18h UTC), une exécution doit apparaître (trigger **schedule**).
- Tu peux aussi lancer **Run workflow** pour tester tout de suite.

**Secrets du dépôt (Settings → Secrets and variables → Actions) :**

| Secret | Valeur |
|--------|--------|
| **REPORT_URL** | URL de ton backend (ex. `https://ton-app.railway.app`) **sans** slash final. |
| **REPORT_SECRET** | **Même** valeur que `REPORT_SECRET` sur Railway. |

Si **REPORT_URL** ou **REPORT_SECRET** est manquant ou faux, le job échoue ou reçoit 403 et aucun rapport n’est déclenché.

---

## 4. Résumé des causes « je ne reçois pas l’email »

1. **REPORT_EMAIL** (ou OWNER_EMAIL) non défini sur Railway.  
2. **SMTP_EMAIL** ou **SMTP_PASSWORD** non définis sur Railway (ou mot de passe d’application Gmail non utilisé).  
3. **REPORT_URL** ou **REPORT_SECRET** manquant / incorrect dans les secrets GitHub → le job n’appelle pas ton API ou reçoit 403.  
4. Email parti mais **en spam** ou filtre du fournisseur.

Faire le `curl` ci-dessus après déploiement te dira exactement lequel de ces points bloque (503, 403, ou 200 + `email_skipped`).
