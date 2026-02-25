# Mot de passe oublié : ne reçoit pas l’email

L’API répond toujours **200** (pour ne pas révéler si l’email existe). Si l’email de réinitialisation ne part pas, vérifier la config **backend (Railway)**.

## 1. URL du lien (obligatoire)

Le backend doit connaître l’URL de la landing pour construire le lien dans l’email.

Sur **Railway** (service backend), définir **une** de ces variables :

- **APP_BASE_URL** = `https://www.uwiapp.com` (sans slash final)
- ou **FRONT_BASE_URL** = idem
- ou **FRONTEND_URL** = idem

Si aucune n’est définie → l’email **n’est pas envoyé** (log : `FRONT_BASE_URL/APP_BASE_URL not set`).

## 2. Envoi d’email (Postmark ou SMTP)

Il faut **soit** Postmark **soit** SMTP configuré.

### Option A : Postmark (recommandé en prod)

| Variable | Exemple | Description |
|----------|---------|-------------|
| **POSTMARK_SERVER_TOKEN** | `xxx-xxx-xxx` | Token API Postmark (Server → API Tokens) |
| **EMAIL_FROM** ou **POSTMARK_FROM_EMAIL** | `noreply@uwiapp.com` | Expéditeur **validé** dans Postmark (Sender Signature) |

### Option B : SMTP (ex. Gmail)

| Variable | Exemple | Description |
|----------|---------|-------------|
| **SMTP_EMAIL** | `ton-compte@gmail.com` | Compte qui envoie |
| **SMTP_PASSWORD** | Mot de passe d’application | Gmail : Sécurité → Mots de passe d’application |
| **SMTP_HOST** | `smtp.gmail.com` | (défaut si absent) |
| **SMTP_PORT** | `587` | (défaut si absent) |

Sans Postmark ni SMTP → l’email ne part pas (log : `email not sent — Email non configuré (Postmark ou SMTP)`).

## 3. Vérifier les logs Railway

Après une demande « Mot de passe oublié », regarder les **logs** du service backend sur Railway :

- `forgot-password: FRONT_BASE_URL/APP_BASE_URL not set` → définir **APP_BASE_URL** (ou FRONT_BASE_URL).
- `forgot-password: email not sent to xxx — Email non configuré` → configurer **Postmark** ou **SMTP** (voir ci‑dessus).
- `forgot-password: email not sent to xxx — Postmark 4xx...` ou erreur SMTP → problème de token, expéditeur non validé, ou mot de passe SMTP incorrect.

## 4. Résumé

| Problème | Action |
|----------|--------|
| Pas d’email reçu | 1) **APP_BASE_URL** = `https://www.uwiapp.com` (ou ton domaine). 2) **Postmark** (POSTMARK_SERVER_TOKEN + EMAIL_FROM) **ou** **SMTP** (SMTP_EMAIL + SMTP_PASSWORD). |
| Lien dans l’email en 404 | APP_BASE_URL doit être l’URL exacte de la landing (ex. https://www.uwiapp.com). |
| Email en spam | Vérifier l’expéditeur (Postmark : Sender Signature ; Gmail : mot de passe d’application). |

Voir aussi : `docs/RAILWAY_VARIABLES_EMAIL_AUTH.md`, `.env.example` (SMTP / Postmark).
