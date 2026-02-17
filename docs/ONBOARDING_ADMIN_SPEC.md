# Mini-PRD : Onboarding admin + accès client (v1)

Flow : **admin** crée le client → raccorde le DID → **client** se connecte par Magic Link → **/app** (appels / events / RDV) = preuve physique.

---

## 1) Tableau existant / à ajouter

### Déjà en place ✅

| Domaine | Élément |
|--------|--------|
| **Admin** | GET /admin/tenants |
| | GET /admin/tenants/:id |
| | POST /admin/routing (guard numéro test + 409 TEST_NUMBER_IMMUTABLE) |
| | POST /admin/tenants/:id/users |
| **Auth** | Magic link : request-link + verify |
| | /login fonctionnel |
| **App** | /app filtré par tenant (appels / events / RDV) |

### À ajouter (v1) ➕

| Élément |
|--------|
| POST /admin/tenants (create tenant) |
| Front : écran **Créer un client** |
| Front : bloc **Raccorder un numéro** sur détail tenant |
| Option B (bonus) : POST /admin/tenants/:id/invite (email + magic link direct) |

---

## 2) Parcours UX v1

### Étape 1 — Admin crée le client

- **Route front** : `/admin/clients/new` (ou modal depuis /admin)
- **Formulaire**
  - Nom entreprise (required)
  - Email contact (required)
  - Timezone (default Europe/Paris)
  - Business type (optional)
  - Notes (optional)
- **Action** : bouton **Créer le client** → POST /admin/tenants
- **Succès** : toast « Client créé » + redirect vers `/admin/tenants/:id`

### Étape 2 — Admin raccorde le DID client

Sur **/admin/tenants/:id** (détail tenant), bloc **« Raccorder un numéro »** :

- **Champs**
  - Numéro (DID) (required)
  - Channel = vocal (prérempli)
- **Action** : bouton **Activer** → POST /admin/routing
- **Succès** : « Numéro activé » + afficher la route active (did + channel)
- **Erreur 409** : si `error_code === "TEST_NUMBER_IMMUTABLE"` → afficher « Numéro test immuable » (message clair)

### Étape 3 — Accès dashboard client

- **Option A (zéro dev mail)**  
  Admin ajoute le user via POST /admin/tenants/:id/users.  
  Admin dit au client : « Allez sur /login, mettez votre email. »

- **Option B (plus fluide)**  
  Admin clique **« Envoyer accès dashboard »** → backend envoie un email avec magic link direct (POST /admin/tenants/:id/invite).

---

## 3) Spécifications API (payloads exacts)

### 3.1 POST /admin/tenants

**Body JSON**

```json
{
  "name": "Cabinet Dr Martin",
  "contact_email": "dr.martin@cabinet.fr",
  "timezone": "Europe/Paris",
  "business_type": "medical",
  "notes": "Client signé le 12/02. Numéro en commande."
}
```

**Response (201)**

```json
{
  "tenant_id": 123,
  "name": "Cabinet Dr Martin",
  "contact_email": "dr.martin@cabinet.fr",
  "timezone": "Europe/Paris",
  "business_type": "medical",
  "created_at": "2026-02-17T15:30:00Z"
}
```

**Règles**

- `name` obligatoire
- `contact_email` obligatoire (sert aussi par défaut pour inviter un user)
- `timezone` défaut Europe/Paris

---

### 3.2 POST /admin/routing (déjà)

**Body JSON** (backend attend `key`, pas `did_key`)

```json
{
  "channel": "vocal",
  "key": "+33988776655",
  "tenant_id": 123
}
```

**Response (200)** — implémentation actuelle : `{ "ok": true }`

**Erreur (409)** — corps plat

```json
{
  "detail": "Forbidden: test number +33939240575 must stay routed to TEST_TENANT_ID=1, got tenant_id=123",
  "error_code": "TEST_NUMBER_IMMUTABLE"
}
```

→ Front : si `error_code === "TEST_NUMBER_IMMUTABLE"` → afficher « Numéro test immuable ».

---

### 3.3 POST /admin/tenants/:id/users (déjà)

**Body JSON**

```json
{
  "email": "dr.martin@cabinet.fr",
  "role": "owner"
}
```

**Règle v1** : 1 email = 1 tenant. Si email déjà assigné à un autre tenant → 409 (ex. `EMAIL_ALREADY_ASSIGNED` ou message backend).

---

### 3.4 Option B — POST /admin/tenants/:id/invite

**Body JSON**

```json
{
  "email": "dr.martin@cabinet.fr"
}
```

**Response (200)**

```json
{
  "status": "sent"
}
```

**Comportement**

- Crée le user si absent (ou réutilise)
- Génère un magic link (TTL 15 min, one-time)
- Envoie l’email (Postmark/SMTP)
- Ne retourne jamais le lien en prod (seulement en dev si debug)

---

## 4) Texte email invitation (prêt)

**Objet** : Accès à votre dashboard UWi

**Corps**

```
Bonjour,

Votre dashboard UWi est prêt.

Cliquez ici pour vous connecter : {{MAGIC_LINK}}
(lien valable 15 minutes)

Vous pourrez y consulter vos appels traités, les événements et les rendez-vous.

— L’équipe UWi
```

---

## 5) Rappels de règles (en bas de spec)

- **v1** : 1 email = 1 tenant
- Aucun client ne doit pouvoir accéder au **TENANT_TEST**
- Magic link : one-time + expiration courte
- Routing : `tenant_routing` unique `(channel, did_key)` + guard numéro test immuable

---

## 6) Plan d’implémentation (ordre logique)

1. **POST /admin/tenants** + page **/admin/clients/new**
2. Bloc **« Raccorder un numéro »** sur détail tenant (UI + appel POST /admin/routing)
3. Option A : bouton « Ajouter user » (endpoint déjà là)
4. Option B (si souhaité) : endpoint **POST /admin/tenants/:id/invite** + envoi email

---

*Structure composants React (pages, hooks, states, gestion 409, toasts) : à détailler en plug-and-play dans le front actuel si besoin.*
