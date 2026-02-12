# Configuration Magic Link (connexion sans mot de passe)

Ce guide permet de configurer l'envoi des emails de connexion Magic Link pour le dashboard UWi.

---

## Prérequis

- Postgres et migrations 007+008 OK (tables `tenant_users`, `magic_links`, `auth_events`)
- Ton email ajouté dans `tenant_users` (voir `make add-tenant-user EMAIL=...`)

---

## Option A : Postmark (recommandé)

Postmark est orienté emails transactionnels (délivrabilité, pas de spam).

### 1. Créer un compte Postmark

1. Va sur [postmarkapp.com](https://postmarkapp.com)
2. Crée un compte gratuit (1 000 emails/mois)
3. Ajoute un **Server** (environnement) → récupère le **Server API Token**

### 2. Valider un expéditeur (Sender)

1. Postmark → **Senders** → **Add Sender**
2. Saisis l’email qui enverra les Magic Links (ex. `noreply@ton-domaine.com` ou ton Gmail)
3. Valide via le lien envoyé par Postmark

### 3. Variables Railway (service agent)

| Variable | Valeur |
|----------|--------|
| `POSTMARK_SERVER_TOKEN` | Token API du Server Postmark |
| `POSTMARK_FROM_EMAIL` | Email validé (ex. `noreply@ton-domaine.com`) |
| `JWT_SECRET` | 32+ caractères aléatoires (`openssl rand -hex 32`) |
| `APP_BASE_URL` | URL de ta landing (ex. `https://uwiapp.com`, `http://localhost:5173` en dev) |

### 4. Redéployer

Redéploie le service agent sur Railway après modification des variables.

---

## Option B : SMTP (Gmail, etc.)

Utilise un compte email existant via SMTP.

### Variables Railway (service agent)

| Variable | Valeur |
|----------|--------|
| `SMTP_EMAIL` | Email expéditeur (ex. `ton@gmail.com`) |
| `SMTP_PASSWORD` | **Mot de passe d’application** (pas le mot de passe Gmail) |
| `SMTP_HOST` | `smtp.gmail.com` (Gmail) ou autre |
| `SMTP_PORT` | `587` |
| `JWT_SECRET` | 32+ caractères aléatoires |
| `APP_BASE_URL` | URL de ta landing |

### Gmail : mot de passe d’application

1. Google Account → Sécurité → Validation en 2 étapes activée
2. Mots de passe des applications → Génére un mot de passe pour « Mail »
3. Utilise ce mot de passe dans `SMTP_PASSWORD`

---

## Test

1. Ajoute ton email : `make add-tenant-user EMAIL=ton@email.com`
2. Va sur `/login` sur la landing
3. Entre ton email et clique sur « Envoyer le lien »
4. Vérifie ta boîte mail (et les spams)
5. Clique sur le lien → redirection vers `/app` (dashboard)

---

## Mode debug (sans email)

Pour tester sans configurer l’email :

| Variable | Valeur |
|----------|--------|
| `ENABLE_MAGICLINK_DEBUG` | `true` |

Le lien de connexion s’affiche directement sur la page après « Envoyer le lien ». Ne pas activer en production.

---

## Ordre des variables

Pour Postmark : `POSTMARK_*` prime sur `SMTP_*`.  
Si `POSTMARK_SERVER_TOKEN` est défini, SMTP n’est pas utilisé pour le Magic Link.
