# Config complète — Rapport quotidien (email à 19h Paris)

La config **locale** (.env) est déjà en place et validée par `make check-report-env`.  
Il reste à **Railway** et **GitHub** pour que le rapport part chaque jour.

---

## 1. Railway (Variables du service)

1. Ouvre [railway.app](https://railway.app) → ton projet → le service qui héberge le backend.
2. Onglet **Variables**.
3. Ajoute ou modifie **chaque ligne** ci‑dessous (nom = valeur).

| Variable | Valeur |
|----------|--------|
| `REPORT_EMAIL` | `henigoutal@gmail.com` |
| `REPORT_SECRET` | `MonRapportSecret2025` |
| `SMTP_EMAIL` | `henigoutal@gmail.com` |
| `SMTP_PASSWORD` | *(la même valeur que dans ton fichier `.env` à la racine)* |
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |

4. Enregistre. Railway redéploie si besoin.

---

## 2. GitHub (Secrets du dépôt)

1. Ouvre ton repo sur GitHub → **Settings** → **Secrets and variables** → **Actions**.
2. **New repository secret** pour chacun :

| Nom du secret | Valeur |
|---------------|--------|
| `REPORT_URL` | `https://agent-production-c246.up.railway.app` *(sans slash final)* |
| `REPORT_SECRET` | `MonRapportSecret2025` *(exactement la même que sur Railway)* |

---

## 3. Vérifier après configuration

**Test manuel (depuis ton Mac) :**
```bash
curl -s -X POST "https://agent-production-c246.up.railway.app/api/reports/daily" -H "X-Report-Secret: MonRapportSecret2025"
```

- `{"status":"ok","clients_notified":1}` → email envoyé (vérifier la boîte et les spams).
- `{"status":"ok","clients_notified":0,"email_error":"..."}` → lire le message `email_error` et corriger (souvent SMTP ou mot de passe).

**À 19h Paris** : le workflow GitHub **Daily IVR Report** appelle cette URL. Tu peux aussi lancer le workflow à la main : **Actions** → **Daily IVR Report** → **Run workflow**.

---

## Récap

| Où | Quoi |
|----|------|
| **Local** | ✅ Déjà fait (.env + `make check-report-env`) |
| **Railway** | Variables ci‑dessus (dont SMTP_PASSWORD = valeur de ton .env) |
| **GitHub** | Secrets REPORT_URL et REPORT_SECRET |
