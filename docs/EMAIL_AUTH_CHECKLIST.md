# Email auth — Checklist “ça marche”

Le magic link est **le** système de connexion client (pas de mot de passe). Si l’email n’est pas configuré, l’inscription peut créer un tenant… mais **la connexion est impossible**. Le socle, c’est : **email auth fonctionne en prod**.

---

## 1. Définition de “ça marche”

- Tu vas sur **/login**, tu mets un email (déjà connu : tenant_user existant), tu cliques **« Envoyer le lien »**, et :
  - **soit** tu reçois un email Postmark en **&lt; 30 s** ;
  - **soit** (en dev) tu vois le lien sur la page si **ENABLE_MAGICLINK_DEBUG=true**.
- Tu cliques sur le lien → tu arrives sur **/app**.

---

## 2. Minimal setup Postmark

### A) Sender validé

Dans Postmark :

- soit tu valides un **email expéditeur** (ex. noreply@uwiapp.com) ;
- soit tu valides ton **domaine** (mieux à terme).

Pour démarrer vite : valide un **sender email**.

### B) Clé API serveur

Dans Postmark → **Server** → **API Token** (ex. `POSTMARK_SERVER_TOKEN`).

### C) Variables d’env (Railway – backend)

À mettre dans Railway (Variables) :

| Variable | Exemple | Rôle |
|----------|--------|------|
| **POSTMARK_SERVER_TOKEN** | (token Postmark) | Envoi via Postmark |
| **EMAIL_FROM** | `UWi <noreply@uwiapp.com>` | Expéditeur (ou **POSTMARK_FROM_EMAIL** si tu préfères) |
| **APP_BASE_URL** | `https://uwiapp.com` | Base des liens (magic link) — **sans slash final** |
| **JWT_SECRET** | (secret 32+ car) | Déjà requis pour signer le token du lien |

Le code utilise, dans l’ordre : **POSTMARK_FROM_EMAIL**, puis **EMAIL_FROM**, puis **SMTP_EMAIL** pour l’expéditeur. Donc **EMAIL_FROM** suffit (ex. `UWi <noreply@uwiapp.com>`).

### D) Template

Tu peux commencer sans template Postmark : le backend envoie un HTML simple avec le lien.

---

## 3. Tester l’envoi sans UI (recommandé)

Avant de valider tout le flux /login → email → /app, tu peux prouver que Postmark est OK avec l’endpoint admin :

**POST /api/admin/email/test**  
- Body : `{ "to": "tonemail@..." }`  
- Auth : cookie admin ou `Authorization: Bearer <ADMIN_API_TOKEN>`  

Réponse : `{ "ok": true, "message": "Email envoyé" }` ou 502 + détail si échec.

Si cet envoi fonctionne, la config Postmark (ou SMTP) est bonne ; le reste du flux magic link dépend en plus de **APP_BASE_URL** et **JWT_SECRET**.

---

## 4. Checklist “email auth” (ordre conseillé)

1. **Railway** : **APP_BASE_URL** = `https://uwiapp.com` (sans slash final).
2. **Railway** : **JWT_SECRET** défini (32+ caractères).
3. **Postmark** : sender validé (email ou domaine).
4. **Railway** : **POSTMARK_SERVER_TOKEN** = token API Postmark.
5. **Railway** : **EMAIL_FROM** = ex. `UWi <noreply@uwiapp.com>`.
6. **Test** : **POST /api/admin/email/test** avec `{ "to": "ton@email.com" }` → tu reçois l’email “Test UWi”.
7. **Test** : **/login** → “Envoyer le lien” (avec un email qui a un tenant_user) → tu reçois l’email → tu cliques → **/app**.

---

## 5. Si l’email n’arrive pas

- Dans **Postmark** : vérifier si le message apparaît comme **Sent** ou **Bounced** (et la raison du bounce).
- Vérifier la valeur exacte de **EMAIL_FROM** (ou **POSTMARK_FROM_EMAIL**) : doit correspondre à un sender validé (ex. `noreply@uwiapp.com` ou `UWi <noreply@uwiapp.com>`).
- En prod, ne pas laisser **ENABLE_MAGICLINK_DEBUG=true** si tu veux tester l’email réel (en dev, tu peux le mettre pour voir le lien sans email).

Tant que l’email auth ne marche pas, on ne touche à rien d’autre.
