# Checklist : recevoir le rapport quotidien tous les soirs

Le **rapport des appels** est envoyé **par email** chaque soir (19h Paris). Il recense les appels de la journée pour vous donner du **feedback** et **améliorer le système** : appels menés à bien (RDV confirmé), raccrochés, transferts vers un humain, etc. Voici ce qu’il faut configurer pour le recevoir.

---

## 1. Quand le rapport part

- **Horaire** : tous les jours à **19h heure de Paris** (18h UTC).
- **Déclencheur** : un job GitHub Actions (`.github/workflows/daily-report.yml`) appelle ton backend à cette heure.

---

## 2. Ce qu’il faut configurer

### A. Sur **GitHub** (secrets du dépôt)

| Secret | Valeur | Rôle |
|--------|--------|------|
| `REPORT_URL` | URL de base du backend, ex. `https://ton-app.railway.app` | Sans `https://` final. Le workflow fait `POST ${REPORT_URL}/api/reports/daily`. |
| `REPORT_SECRET` | Même valeur que sur Railway (ex. un mot de passe fort) | En-tête `X-Report-Secret` pour autoriser l’appel. |

**Où les mettre :** GitHub → ton repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.

### B. Sur **Railway** (variables d’environnement du service)

| Variable | Obligatoire | Rôle |
|----------|-------------|------|
| `REPORT_SECRET` | Oui | Doit être **identique** à `REPORT_SECRET` sur GitHub. Sinon → 403. |
| `REPORT_EMAIL` ou `OWNER_EMAIL` | Oui | **Adresse qui reçoit le rapport** (la tienne). Ex. `REPORT_EMAIL=ton@email.com`. |
| `SMTP_HOST` | Oui pour envoyer | Ex. `smtp.gmail.com`. |
| `SMTP_PORT` | Oui | Ex. `587`. |
| `SMTP_EMAIL` | Oui | Compte qui **envoie** l’email (souvent = compte Gmail ou SMTP). |
| `SMTP_PASSWORD` | Oui | Mot de passe du compte ou **mot de passe d’application** (Gmail : compte Google → Sécurité → Mots de passe d’application). |

Sans `REPORT_SECRET` → l’endpoint renvoie 503.  
Sans `REPORT_EMAIL` / `OWNER_EMAIL` → le backend ne peut pas envoyer (réponse 200 mais 0 email).  
Sans SMTP configuré → l’envoi d’email échoue et tu ne reçois rien.

---

## 3. Tester à la main

Pour vérifier sans attendre 19h :

```bash
curl -X POST "https://TON-APP.railway.app/api/reports/daily" \
  -H "Content-Type: application/json" \
  -H "X-Report-Secret: TON_REPORT_SECRET"
```

- **200** + JSON `{"status":"ok","clients_notified":1}` → le rapport a été généré et l’email envoyé (ou tenté).
- **403** → le `X-Report-Secret` ne correspond pas à `REPORT_SECRET` sur Railway.
- **503** → `REPORT_SECRET` n’est pas défini sur Railway.

Ensuite, vérifie ta boîte mail (et les spams) à l’adresse `REPORT_EMAIL` / `OWNER_EMAIL`.

---

## 4. Vérifier que le job GitHub tourne

- GitHub → **Actions** → onglet **Daily IVR Report**.
- Après 19h Paris, une exécution doit apparaître (trigger `schedule`).
- Tu peux aussi lancer le workflow à la main : **Run workflow** (bouton dans la page Actions).

Si le job échoue : vérifier que `REPORT_URL` et `REPORT_SECRET` sont bien renseignés dans les secrets du repo.

---

## 5. Contenu du rapport (feedback pour améliorer le système)

Le rapport contient pour la journée écoulée :

- **Appels reçus** (total)
- **Menés à bien** : RDV confirmé
- **Transferts** vers un humain
- **Raccrochés / abandons**
- **Santé de l’agent** : intent router, recovery, anti-loop
- **Principales incompréhensions** (TOP 3) et **recommandation du jour**
- **Alertes** (silences répétés, etc.)

Objectif : utiliser ces chiffres pour ajuster les prompts, les réglages ou la formation, et améliorer le système au fil du temps.

Les données viennent des tables `ivr_events` et `calls` en base. Les appels doivent être associés à un `client_id` (fait par le webhook Vapi quand la session est liée à un client) pour que les stats soient correctes.

---

## Résumé

| Où | Quoi |
|----|------|
| **GitHub** | Secrets `REPORT_URL` + `REPORT_SECRET` |
| **Railway** | `REPORT_SECRET`, `REPORT_EMAIL` (ou `OWNER_EMAIL`), SMTP (`SMTP_HOST`, `SMTP_PORT`, `SMTP_EMAIL`, `SMTP_PASSWORD`) |
| **Test** | `curl -X POST "https://.../api/reports/daily" -H "X-Report-Secret: ..."` |

Quand tout est coché, tu es censé recevoir **tous les soirs** un email avec le rapport des appels et des stats.

---

## 6. En cas d’échec GitHub Actions

- **« Internal server error » / HTTP 500**  
  Le backend a planté. Vérifier les **logs Railway** au moment du cron (19h Paris) : l’endpoint renvoie maintenant du 200 avec `{"status": "error", "error": "..."}` en cas d’exception, donc en principe plus de 500. Si tu as encore du 500, c’est avant notre fix (redéploie) ou une autre route. Vérifier aussi que `REPORT_SECRET`, `REPORT_EMAIL`, `SMTP_*` sont bien définis sur Railway.

- **« The job was not acquired by Runner »**  
  Problème côté GitHub (runner hébergé indisponible). Relancer le workflow à la main (Actions → Daily IVR Report → Run workflow). Si ça se répète, décaler l’heure du cron (ex. `5 18 * * *` = 18h05 UTC).

- **Vérifier les secrets GitHub**  
  Settings → Secrets and variables → Actions : `REPORT_URL` (ex. `https://ton-app.railway.app`) et `REPORT_SECRET` (même valeur que sur Railway). Sans eux, le step échoue avec un message explicite.
