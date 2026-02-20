# Variables Railway — Email auth (magic link)

Toutes les variables ci‑dessous se configurent dans **Railway** → ton **service backend** → onglet **Variables**.  
Sans elles, l’inscription peut créer un tenant mais **la connexion client (magic link) ne fonctionne pas**.

---

## 1. Variables obligatoires pour l’email (Postmark)

| Variable | Valeur type | Où la trouver | À savoir |
|----------|-------------|---------------|----------|
| **POSTMARK_SERVER_TOKEN** | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` | Postmark → ton Server → **API Tokens** → "Server API token" | **Ne jamais** la mettre dans le code ou la doc publique. Sans elle, aucun email (magic link ni test) ne part. |
| **EMAIL_FROM** | `UWi <noreply@uwiapp.com>` ou `noreply@uwiapp.com` | Tu choisis l’email ; il doit être **validé** dans Postmark (Sender Signature). | Format possible : `"Nom <email@domaine.com>"` ou juste `email@domaine.com`. Doit être **exactement** un sender validé dans Postmark. |

**Alternative expéditeur** : tu peux utiliser **POSTMARK_FROM_EMAIL** au lieu de **EMAIL_FROM**. Le code prend dans l’ordre : POSTMARK_FROM_EMAIL → EMAIL_FROM → SMTP_EMAIL.

---

## 2. Variables obligatoires pour le lien de connexion

| Variable | Valeur type | Où la trouver | À savoir |
|----------|-------------|---------------|----------|
| **APP_BASE_URL** | `https://uwiapp.com` | L’URL de ta **landing / app client** (sans slash final). | Utilisée pour construire le lien du magic link. Si mauvaise URL → le lien dans l’email redirige ailleurs ou vers une 404. **Pas de slash à la fin.** |
| **JWT_SECRET** | Une chaîne aléatoire longue (ex. 32+ caractères) | Générer par ex. : `openssl rand -hex 32` | Déjà souvent présente. Elle signe le token du magic link. Si absente ou différente entre envs, le lien est rejeté après clic. |

---

## 3. Variable optionnelle (débogage)

| Variable | Valeur | Effet |
|----------|--------|--------|
| **ENABLE_MAGICLINK_DEBUG** | `true` | Sur **/login**, après "Envoyer le lien", le **lien s’affiche sur la page** au lieu d’envoyer l’email. Utile en dev pour tester sans configurer Postmark. En **prod**, laisser à `false` ou ne pas définir pour que l’email soit bien envoyé. |

---

## 4. Récap : à ajouter sur Railway pour que “email auth” marche

Dans l’ordre logique :

1. **APP_BASE_URL** = `https://uwiapp.com` (adapter si ton domaine est différent ; **sans** slash final).
2. **JWT_SECRET** = (secret fort, 32+ caractères).
3. **POSTMARK_SERVER_TOKEN** = (token API du Server Postmark).
4. **EMAIL_FROM** = `UWi <noreply@uwiapp.com>` (ou l’email que tu as validé dans Postmark).

Après déploiement :

- Tester l’envoi : **POST /api/admin/email/test** avec `{ "to": "ton@email.com" }` (auth admin).
- Si l’email “Test UWi” arrive → Postmark est bon.
- Puis tester **/login** → Envoyer le lien → recevoir l’email → clic → arrivée sur **/app**.

---

## 5. Si tu n’utilises pas Postmark (SMTP)

À la place de Postmark, le code peut utiliser SMTP. Dans ce cas, sur Railway il faut au minimum :

| Variable | Rôle |
|----------|------|
| **SMTP_EMAIL** | Adresse d’envoi (ex. Gmail). |
| **SMTP_PASSWORD** | Mot de passe ou “App Password” (Gmail). |
| **SMTP_HOST** | (optionnel) Défaut `smtp.gmail.com`. |
| **SMTP_PORT** | (optionnel) Défaut `587`. |

Pour le magic link, l’expéditeur utilisé est alors **SMTP_EMAIL**.  
Pour la prod, Postmark est en général plus simple (pas de 2FA Gmail, pas de blocage “app moins sécurisée”).
