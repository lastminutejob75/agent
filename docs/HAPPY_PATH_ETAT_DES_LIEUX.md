# État des lieux — Parcours client (mode stabilisation)

**Objectif** : répondre à la question *« Si je suis un nouveau client, comment je fais ? »* et permettre un test manuel du début à la fin.

---

## 1. Comment un client est créé

### Deux façons possibles

| Voie | Où | Ce qui se passe |
|------|-----|------------------|
| **A. Inscription publique** | Landing → **Démarrer** → `/onboarding` | Formulaire : nom entreprise, **email**, agenda (provider + id). Clic **Créer** → `POST /api/public/onboarding` → crée **tenant** + (si **PG**) **tenant_user owner** avec cet email. |
| **B. Création par l’admin** | Admin → **Clients** → **Créer un client** (`/admin/tenants/new`) | Admin remplit nom, **email de contact**, etc. → crée tenant + **tenant_user owner** pour cet email. |

**Important** : pour que le client puisse se connecter plus tard, il faut un **tenant_user** lié à son email.  
- **PG** : l’onboarding public crée bien ce tenant_user.  
- **SQLite** : l’onboarding crée seulement le tenant + config, **pas de tenant_user** → le client ne peut pas se connecter par magic link après une inscription publique en mode SQLite.

En prod (Railway, PG) : **A** et **B** donnent bien un compte utilisable.

---

## 2. Comment le client se connecte

1. Aller sur **/login** (lien depuis la landing ou la page après onboarding).
2. Saisir **l’email** utilisé à la création (onboarding ou admin).
3. Clic **« Envoyer le lien »** → `POST /api/auth/request-link` (réponse toujours 200, anti-enumération).
4. Si l’email est connu (tenant_user existant) : un **magic link** est généré et envoyé par email (Postmark ou SMTP).  
   **Si `ENABLE_MAGICLINK_DEBUG=true`** : le lien s’affiche sur la page (pas d’email).
5. Cliquer le lien → `GET /api/auth/verify?token=...` → JWT créé → redirection vers **/app**.
6. Le JWT est stocké (localStorage, clé `uwi_tenant_token`). Le client est connecté.

**À vérifier en prod** :  
- `APP_BASE_URL` = URL de la landing (ex. https://uwiapp.com).  
- `JWT_SECRET` défini.  
- Envoi d’email configuré (Postmark ou SMTP) ; sinon utiliser `ENABLE_MAGICLINK_DEBUG=true` pour tester sans email.

---

## 3. Ce que le client voit après connexion

- **URL** : **/app** (dashboard).
- **Contenu** : tableau de bord (KPIs 7j, graphiques), statut technique, paramètres, RGPD.  
- **Isolation** : tout est scopé par `tenant_id` (dans le JWT). Pas d’erreur 401 si la session est valide.

**À vérifier** : ouvrir /app après connexion → la page charge, pas de 401, données cohérentes pour le tenant.

---

## 4. Appel vocal (réel)

- **Numéro de démo (public)** : documenté sur la landing (ex. 09 39 24 05 75). Routé vers un **tenant de démo** fixe. **Aucun lien** avec le compte créé à l’onboarding : tout le monde appelle le même numéro démo.
- **Client avec DID dédié** : si un DID a été affecté au tenant (config admin / Vapi), les appels sur ce DID arrivent sur ce tenant ; les events se loguent et le dashboard client peut se mettre à jour.

**À vérifier** : DID bien relié au tenant dans la config ; un appel reçu ; events visibles (admin ou client selon les écrans).

---

## 5. Réponses directes aux questions

- **Est-ce qu’il existe une page d’inscription publique ?**  
  **Oui** : `/onboarding` (accessible depuis la landing, bouton « Démarrer »).

- **Est-ce que l’admin peut créer le client manuellement ?**  
  **Oui** : `/admin/tenants/new` (Créer un client), avec email de contact → tenant + tenant_user owner.

- **Est-ce que l’email de connexion marche aujourd’hui en prod ?**  
  À **tester** : dépend de `APP_BASE_URL`, `JWT_SECRET`, et de l’envoi d’email (Postmark/SMTP ou `ENABLE_MAGICLINK_DEBUG=true`).

- **Si demain tu envoies à un vrai client : “Va sur uwiapp.com et crée ton compte” — peut-il le faire ?**  
  **Oui en théorie** (onboarding public + magic link), **à condition que** :  
  - le déploiement expose bien `/onboarding` et `/login` ;  
  - les variables d’auth et d’email sont correctes ;  
  - en prod on est bien en **PG** (pas SQLite), sinon l’onboarding public ne crée pas de tenant_user.

---

## 6. Scénario de test manuel proposé

**« Je suis un médecin, je découvre UWi, je veux l’essayer. »**

1. Ouvrir la landing (ex. https://uwiapp.com ou URL de staging).
2. Cliquer **Démarrer** → arriver sur `/onboarding`.
3. Remplir : nom du cabinet, **email réel** (pour recevoir le magic link), agenda (ex. none / vide si pas de cal).
4. Cliquer **Créer** → message de succès + proposition d’aller se connecter.
5. Aller sur **/login**, saisir le même email, **Envoyer le lien**.
6. (Si debug : copier le lien affiché ; sinon : ouvrir l’email et cliquer le lien.)
7. Vérifier la redirection vers **/app** et l’affichage du dashboard sans 401.
8. (Optionnel) Appeler le numéro de démo pour tester la voix (démo partagée, pas liée au compte).

**Noter** : tout ce qui casse ou prête à confusion (message, étape manquante, erreur réseau, 401, etc.).

---

## 7. Points de rupture possibles (à surveiller)

- **Onboarding en SQLite** : pas de tenant_user créé → impossible de se connecter après inscription publique.
- **CORS** : si la landing et l’API ne sont pas sur le même domaine, `CORS_ORIGINS` doit contenir l’origine de la landing.
- **Email non envoyé** : Postmark/SMTP non configurés ou erreur silencieuse → le client ne reçoit pas le magic link (utiliser `ENABLE_MAGICLINK_DEBUG=true` pour tester).
- **APP_BASE_URL incorrect** : le lien dans l’email pointe vers une mauvaise URL.
- **JWT_SECRET vide ou différent** : tokens invalides ou rejetés.

---

## 8. Suite recommandée (stabilisation)

- Geler les features (pas de Stripe, quotas, nouvelles routes) pendant la période de stabilisation.
- Valider le parcours **création → connexion → /app** en manuel (et en staging si possible).
- Corriger uniquement les bugs et les points de rupture identifiés.
- Une fois le happy path fiable : reprendre les évolutions (monétisation, etc.) sur une base solide.
