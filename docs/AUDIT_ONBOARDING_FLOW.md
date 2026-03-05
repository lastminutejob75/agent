# Audit complet du flow d'onboarding actuel

## 1. CreateTenantModal.jsx — Les 4 étapes

**Fichier :** `landing/src/admin/components/CreateTenantModal.jsx`

### Les 4 étapes (STEPS)

| Step | Label | Champs |
|------|-------|--------|
| 0 | Infos client | `name`, `email`, `phone` |
| 1 | Configuration | `sector`, `plan_key`, `twilio_number` |
| 2 | Assistant | `assistant_id` (Sophie, Laura, Emma, etc.) |
| 3 | Récapitulatif | Tous les champs + toggle `send_welcome` |

### Champs du formulaire (form state)

```javascript
{
  name: "",
  email: "",
  phone: "",
  sector: "medecin_generaliste",
  plan_key: "starter",
  assistant_id: "sophie",
  twilio_number: "",
  send_welcome: true,
  timezone: "Europe/Paris",
}
```

### Soumission finale

`handleSubmit` appelle **`adminApi.createTenantFull(payload)`** :

```javascript
// ligne 86
const res = await adminApi.createTenantFull(payload);
```

→ **POST `/api/admin/tenants/create`**

### Résultat affiché (step 4)

- `result.success` → grille Vapi, Stripe, Twilio, Email (✓ ou —)
- `result.results?.errors` → avertissements en orange
- Pas de lien vers le dashboard client ou paiement dans le modal

---

## 2. Backend POST /api/admin/tenants/create

**Fichier :** `backend/routes/admin.py` (lignes 2805–2970)

### Ce qu'il fait exactement

| Étape | Action | Automatique ? |
|-------|--------|---------------|
| 1 | Créer tenant en PG (`pg_create_tenant`) | ✅ |
| 1 | Créer `tenant_user` (owner) | ✅ |
| 1 | Mettre à jour flags (ENABLE_BOOKING, etc.) | ✅ |
| 1 | Mettre à jour params (assistant_name, phone_number, sector, plan_key) | ✅ |
| 2 | **Créer assistant Vapi** (`create_vapi_assistant`) | ✅ |
| 2 | **Assigner Twilio** à Vapi si numéro fourni | ✅ |
| 2 | **Ajouter routing** (`pg_add_routing`) | ✅ |
| 3 | **Créer Stripe Customer** | ✅ |
| 3 | **Créer Stripe Subscription** (base + metered) | ✅ |
| 3 | **Upsert billing** (tenant_billing) | ✅ |
| 4 | **Envoyer email de bienvenue** (`send_welcome_email`) | ✅ si `send_welcome` |

### Ce qui manque

- ❌ **Achat numéro Twilio** : le modal récupère les numéros déjà achetés (`getTwilioNumbers`) et en assigne un. Il n’achète pas un nouveau numéro.
- ❌ **Lien de paiement Stripe** : la subscription est créée directement. Pas de Checkout Session pour le client (pas de paiement différé).
- ❌ **Lien dashboard client** : l’email de bienvenue pointe vers `app_url` (ADMIN_BASE_URL / VITE_SITE_URL) → pas forcément vers `/login` avec email pré-rempli.

---

## 3. Dashboard client vs admin

### Dashboard client existant

**Oui.** Il existe un dashboard client séparé :

| Route | Composant | Description |
|-------|-----------|-----------|
| `/app` | `AppLayout` + `AppDashboard` | Vue d’ensemble client |
| `/app/appels` | `AppCalls` | Journal des appels |
| `/app/agenda` | `AppAgenda` | Mon agenda |
| `/app/actions` | `AppActions` | Actions en attente |
| `/app/facturation` | `AppFacturation` | Facturation |
| `/app/profil` | `AppProfil` | Mon profil |
| `/app/config` | `AppConfig` | Configuration IA |
| `/app/status` | `AppStatus` | Statut |
| `/app/settings` | `AppSettings` | Paramètres |
| `/app/rgpd` | `AppRgpd` | RGPD |

**Auth :** `/login` (email + mdp ou Google SSO) → cookie `uwi_session` → `api.tenantMe()` / `api.tenantDashboard()`.

**URL client :** `getClientLoginUrl(email, tenantId)` → `/login?email=...&from=admin&tenant=...`  
**Impersonation :** `POST /api/admin/tenants/{id}/impersonate` → token → `/app/impersonate?token=...`

### Dashboard admin

- `/admin` → dashboard admin
- `/admin/tenants/:id` → page tenant (Infos, Timeline, Appels, Factures, Quota, Actions)
- `/admin/tenants/:id/dashboard` → vue détaillée du tenant

---

## 4. Flow de paiement Stripe

### Existant

| Endpoint | Usage |
|----------|-------|
| `POST /api/admin/tenants/{id}/stripe-customer` | Créer un Stripe Customer (admin) |
| `POST /api/admin/tenants/{id}/stripe-checkout` | Créer une **Checkout Session** (plan_key, trial_days) → retourne `checkout_url` |
| `POST /create-checkout-session` (checkout_embedded) | Pour la landing `/checkout` (leads « Profiter du mois gratuit ») |
| Webhook Stripe | Sync `tenant_billing` (subscription.*, invoice.*, checkout.session.completed) |

### Dans createTenantFull

- Création directe de **Customer + Subscription** (pas de Checkout Session).
- Le client est facturé immédiatement (ou en trial si configuré côté Stripe).
- **Pas de lien de paiement** envoyé au client : l’admin crée le tenant, Stripe crée la subscription, le client reçoit l’email de bienvenue mais pas de lien pour payer.

### Flow Checkout séparé

- Admin peut appeler `POST /api/admin/tenants/{id}/stripe-checkout` (body: plan_key, trial_days) pour obtenir un `checkout_url` et le transmettre au client.
- Ce n’est pas intégré dans le flow CreateTenantModal.

---

## 5. Résumé — Ce qui manque pour un onboarding complet

| Composant | Existant | À faire |
|-----------|----------|---------|
| CreateTenantModal (4 étapes) | ✅ | — |
| Création tenant en DB | ✅ | — |
| Création tenant_user | ✅ | — |
| Assistant Vapi | ✅ | — |
| Numéro Twilio (assignation) | ✅ | Achat auto si pool vide ? |
| Stripe Customer | ✅ | — |
| Stripe Subscription | ✅ (directe) | Option : Checkout Session + lien |
| Email de bienvenue | ✅ | Lien vers `/login` + pré-rempli email |
| Dashboard client | ✅ | — |
| Lien de paiement au client | ❌ | Envoyer `checkout_url` ou email dédié |
| Connexion agenda (Google) | ❌ | Flow client pour connecter son calendrier |
| Flow lead → tenant | Partiel | `/creer-assistante` → `pre_onboarding` → lead → admin convertit manuellement |

---

## 6. Prochaines étapes recommandées

1. **Email de bienvenue** : utiliser `getClientLoginUrl(email, tenant_id)` pour le lien « Accéder à votre espace ».
2. **Lien de paiement** : soit garder la subscription directe + email de bienvenue, soit ajouter une option « Envoyer lien de paiement » (Checkout Session) dans le modal ou après création.
3. **Onboarding client** : flow pour connecter Google Calendar depuis le dashboard client (`/app/config` ou `/app/agenda`).
4. **Flow lead → tenant** : automatiser la conversion lead → tenant (ou wizard admin « Convertir ce lead » qui pré-remplit le CreateTenantModal).
