# Accès dashboard client

Ce document décrit comment un client (ou un commercial) accède au dashboard client et comment l’admin peut le configurer.

---

## 1. Comment le client accède à son dashboard

### Créer le client (avec l’email de connexion)

- **Admin** : **Clients** → **Créer un client**.
- Renseigner au minimum :
  - **Nom entreprise**
  - **Email de contact** (obligatoire) — **c’est l’email de connexion** : le client se connectera avec cet email.
- En enregistrant, le backend crée le tenant **et** un compte utilisateur (**rôle owner**) pour cet email. Ce compte permet ensuite la connexion par lien magique.

**Important** : l’email de contact n’est pas qu’un simple contact — il sert d’**identifiant de connexion**. Un tenant_user est créé automatiquement pour cet email avec le rôle **owner**.

### Connexion du client (magic link)

Le client n’a pas de mot de passe : il se connecte par **lien magique** envoyé par email.

- **Durée de validité** : 15 minutes (configurable via `MAGICLINK_TTL_MINUTES`).
- **Usage** : **one-time** (à usage unique). Une fois le lien utilisé, il est invalidé.

En pratique :

- **Option A** : indiquer au client d’aller sur **https://uwiapp.com/login** (ou votre domaine), d’entrer son email et de cliquer sur « Envoyer le lien ». Il reçoit un email avec le lien de connexion.
- **Option B** : depuis la fiche client, l’admin clique sur **« Ouvrir la page de connexion client »** : la page de connexion s’ouvre avec l’email déjà rempli. L’admin peut envoyer cette URL au client pour qu’il n’ait qu’à cliquer sur « Envoyer le lien » puis à ouvrir l’email.

Une fois le lien magique utilisé, le client arrive sur **/app** (son dashboard) et reste connecté.

- **Session** : la session est stockée **dans le navigateur (localStorage)** sous la clé `uwi_tenant_token` (JWT). Ce n’est pas un cookie HttpOnly en l’état.

### Ce que le client voit (dashboard)

- **Dashboard** : statut du service, dernière activité, indicateurs (appels, RDV, etc.).
- **Statut** : technique (DID, calendrier, agent).
- **RGPD** : consentements.
- **Paramètres** : email, timezone, calendrier, etc.

Tout est scopé par **tenant** : le JWT contient le `tenant_id`, donc le client ne voit que les données de son entreprise.

---

## 2. Wording des boutons admin

- **« Ouvrir la page de connexion client »** : ouvre la **page de connexion** (/login) avec l’email pré-rempli. Cela ne connecte pas le client ; il devra demander un lien magique puis cliquer sur le lien reçu par email.
- **« Dashboard client »** ou **« Voir comme le client »** : désigne l’accès au **dashboard** (/app) — soit en impersonation (voir comme le client), soit après connexion du client.

---

## 3. Cas « email = plusieurs tenants » (futur)

**V1** : un email est associé à **un seul tenant**. Si besoin multi-tenant (un même email sur plusieurs comptes), on activera une sélection ; le paramètre `tenant=…` (base64url) dans l’URL pourra servir à pré-sélectionner le tenant.

---

## 4. Si le client a été créé sans accès ou change d’email

Si le tenant a été créé sans email, ou si tu veux donner l’accès à un **autre** email que le contact initial :

- Ouvre la **fiche client** (détail du tenant).
- Utilise **« Ajouter un utilisateur »** (owner ou member) avec l’email concerné. Cela crée (ou associe) un **tenant_user** pour cet email, ce qui rend possible le magic link pour ce compte.

**Note** : ajouter un utilisateur **n’enlève pas** l’ancien (un autre email peut toujours être associé au même tenant tant qu’il a son propre tenant_user). Pour retirer un utilisateur, une action explicite sera nécessaire (feature existante ou à venir).

---

## 5. Vérifier ce que voit le client (impersonation)

- Dans la fiche client, cliquer sur **« Voir comme le client »** : une session temporaire (5 min) s’ouvre dans un nouvel onglet, avec un **bandeau rouge** « Mode admin – vous visualisez le compte de … ».
- Tu vois exactement le dashboard et les stats du client, sans avoir besoin de son email ou d’un magic link.

**V1** : l’impersonation donne un **accès complet** au dashboard (comme le client) : les mêmes appels API sont possibles. Une évolution « lecture seule » pourra être ajoutée plus tard.

---

## 6. Résumé

| Action admin | Effet pour le client |
|--------------|----------------------|
| **Créer un client** avec un **email de contact** | Un compte (tenant + tenant_user **owner**) est créé ; le client peut se connecter par magic link avec cet email. |
| **Ouvrir la page de connexion client** | Ouvre la page /login avec l’email pré-rempli (pour envoyer le lien au client ou tester). |
| **Voir comme le client** | Ouvre son dashboard en impersonation (support / QA). |
| **Ajouter un utilisateur** (fiche client) | Associe un autre email au même tenant ; ce compte pourra aussi se connecter par magic link. |

Le dashboard client (**/app**) est le même pour tous ; l’accès aux infos et aux stats est automatique dès qu’un **tenant_user** existe pour l’email et que le client s’est connecté au moins une fois par magic link.
