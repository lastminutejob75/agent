# Checklist prod / test — UWi prêt pour les clients

À vérifier avant de proposer UWi en test (vocal ou web).

---

## 1. Déploiement Railway

| Élément | Statut | Comment vérifier |
|--------|--------|-------------------|
| **Build** | ☐ | Build Docker OK sur Railway (railway.toml + Dockerfile) |
| **PORT** | ☐ | Variable `PORT` fournie par Railway (automatique) |
| **RAILWAY_PUBLIC_DOMAIN** | ☐ | Présent en prod (pour keep-alive et webhook Vapi) |
| **Health check** | ☐ | `GET https://<ton-app>.railway.app/health` → `status: "ok"` |

---

## 2. Variables d'environnement (Railway)

### Obligatoires pour le cœur (RDV + vocal)

| Variable | Rôle | Exemple |
|----------|------|---------|
| **GOOGLE_SERVICE_ACCOUNT_BASE64** | Compte de service Google (JSON encodé base64) | `eyJ0eXBlIjoi...` |
| **GOOGLE_CALENDAR_ID** | ID du calendrier cible | `xxx@group.calendar.google.com` |

→ Sans ces deux : l’app démarre mais slots/booking en fallback SQLite (ou erreur selon config).

### Optionnelles mais recommandées pour test client

| Variable | Rôle | Exemple |
|----------|------|---------|
| **REPORT_EMAIL** ou **OWNER_EMAIL** | Destinataire rapports quotidiens | `cabinet@exemple.fr` |
| **NOTIFICATION_EMAIL** | Demandes ordonnance (sinon REPORT_EMAIL) | idem |
| **SMTP_EMAIL** | Envoi emails (rapports + ordonnance) | `noreply@domaine.fr` |
| **SMTP_PASSWORD** | Mot de passe SMTP | (app password Gmail ou autre) |
| **SMTP_HOST** / **SMTP_PORT** | Serveur SMTP | `smtp.gmail.com`, `587` |

### Optionnelles (rapport Telegram, Twilio, etc.)

| Variable | Rôle |
|----------|------|
| **TELEGRAM_BOT_TOKEN** / **TELEGRAM_OWNER_ID** | Rapport quotidien Telegram |
| **REPORT_SECRET** | Sécurisation endpoint rapport |
| **TWILIO_*** | WhatsApp / SMS (si utilisé) |

---

## 3. Endpoints à tester

Une fois l’URL Railway connue (`https://<app>.railway.app`) :

| URL | Méthode | Attendu |
|-----|---------|--------|
| `/health` | GET | `status: "ok"`, `credentials_loaded: true`, `calendar_id_set: true` si Google configuré |
| `/api/vapi/health` | GET | `status: "ok", "service": "voice"` |
| `/api/vapi/test` | GET | `status: "ok"`, `response` avec un texte (ex. message d’accueil) |

Commande rapide (remplacer `BASE_URL`) :
```bash
curl -s https://<BASE_URL>/health | jq .
curl -s https://<BASE_URL>/api/vapi/health | jq .
curl -s https://<BASE_URL>/api/vapi/test | jq .
```

Ou utiliser le script : `python scripts/check_prod.py` (voir ci‑dessous).

---

## 4. Vapi (canal vocal)

| Élément | Statut | Comment vérifier |
|--------|--------|-------------------|
| **Server URL (webhook)** | ☐ | Dans le dashboard Vapi : `https://<ton-app>.railway.app/api/vapi/webhook` (pas localhost, pas ngrok en prod) |
| **First Message** | ☐ | Configuré (ex. « Bonjour [Cabinet], vous appelez pour un rendez-vous ? ») — voir VAPI_CONFIG.md |
| **Test d’appel** | ☐ | Un appel test : premier message entendu, puis une réponse après « Oui » ou « Non » |

Important : le webhook Vapi doit pointer vers l’URL **publique** Railway (HTTPS).

---

## 5. Google Calendar

| Élément | Statut | Comment vérifier |
|--------|--------|-------------------|
| **Calendrier partagé** | ☐ | Le calendrier `GOOGLE_CALENDAR_ID` est partagé avec le `client_email` du Service Account (droit « Modifier les événements ») |
| **Slots visibles** | ☐ | `GET /health` → `free_slots` ≥ 0 (ou appeler `/debug/slots` en dev) |

Voir GOOGLE_CALENDAR_SETUP.md et PROBLEME_RAILWAY_GOOGLE_CALENDAR.md en cas de souci.

---

## 6. Résumé « tout est vert »

- [ ] Railway : app déployée, health check vert.
- [ ] Env : au minimum `GOOGLE_SERVICE_ACCOUNT_BASE64` + `GOOGLE_CALENDAR_ID` ; idéalement SMTP + REPORT_EMAIL / NOTIFICATION_EMAIL.
- [ ] `/health` et `/api/vapi/health` retournent OK.
- [ ] Vapi : webhook = `https://<app>.railway.app/api/vapi/webhook`, test d’appel OK.
- [ ] Calendrier partagé avec le Service Account.

Quand tout est coché, tu peux proposer UWi en test (vocal et/ou web) en donnant le numéro Vapi ou l’URL du widget.

---

## Script de vérification automatique

Depuis la racine du projet :

```bash
# Vérifier une instance déployée (remplacer par ton URL Railway)
export BASE_URL=https://ton-app.railway.app
python scripts/check_prod.py
```

Le script appelle `/health` et `/api/vapi/health` et affiche OK / KO pour chaque critère.
