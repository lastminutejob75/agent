# Fondation Stripe (agnostique prix)

Brique Stripe **sans figer les prix** : customer + subscription + usage framework. Les montants et plans se brancheront plus tard.

---

## Variables d'environnement (Checkout + usage)

| Variable | Rôle |
|----------|------|
| `STRIPE_SECRET_KEY` | Clé API Stripe |
| `STRIPE_WEBHOOK_SECRET` | Signature webhooks |
| `STRIPE_CHECKOUT_SUCCESS_URL` | Redirection après paiement réussi (ex. https://uwiapp.com/app?checkout=success) |
| `STRIPE_CHECKOUT_CANCEL_URL` | Redirection si annulation (ex. https://uwiapp.com/app?checkout=cancel) |
| `STRIPE_PRICE_BASE_STARTER` | Price ID abo base Starter |
| `STRIPE_PRICE_BASE_PRO` | Price ID abo base Pro |
| `STRIPE_PRICE_BASE_BUSINESS` | Price ID abo base Business |
| `STRIPE_PRICE_METERED_MINUTES` | Price ID usage metered (minutes) |
| `STRIPE_METERED_PRICE_ID` | Même valeur que `STRIPE_PRICE_METERED_MINUTES` (remplissage `stripe_metered_item_id` via webhook) |

Changer les montants plus tard = changer les Price dans le Dashboard Stripe et mettre à jour ces IDs.

---

## 1. DB Billing (migration 011)

Table **`tenant_billing`** (1 ligne par tenant) :

| Colonne | Type | Rôle |
|---------|------|------|
| `tenant_id` | BIGINT PK FK | Référence tenants |
| `stripe_customer_id` | TEXT | ID Stripe Customer (nullable) |
| `stripe_subscription_id` | TEXT | ID Subscription (nullable) |
| `billing_status` | TEXT | active / past_due / canceled / trialing / null |
| `plan_key` | TEXT | "starter" / "pro" / … (nullable) |
| `current_period_start` | TIMESTAMPTZ | Début période courante (nullable) |
| `current_period_end` | TIMESTAMPTZ | Fin période courante (nullable) |
| `trial_ends_at` | TIMESTAMPTZ | Fin essai (nullable) |
| `updated_at` | TIMESTAMPTZ | Dernière sync webhook / admin |

Pas de prix en DB : tout vient de Stripe (Products/Prices) quand tu les créeras.

---

## 2. Endpoints admin

| Méthode | Route | Rôle |
|---------|-------|------|
| GET | `/api/admin/tenants/{id}/billing` | Lecture billing (stripe_customer_id, billing_status, plan_key, period, trial_ends_at) |
| POST | `/api/admin/tenants/{id}/stripe-customer` | Créer un Stripe Customer pour le tenant, enregistrer `stripe_customer_id` (metadata.tenant_id = tenant_id) |
| POST | `/api/admin/tenants/{id}/stripe-checkout` | Créer une session Checkout (body: `plan_key`, optionnel `trial_days`) ; retourne `checkout_url` |
| GET | `/api/admin/tenants/{id}/usage?month=YYYY-MM` | Usage Vapi du mois : minutes_total, cost_usd, nb appels (depuis vapi_call_usage). **Convention : mois en UTC** (ended_at >= 1er 00:00:00 UTC, &lt; 1er jour mois suivant). Base pour CSV/PDF plus tard. |
| GET | `/api/admin/stats/billing-snapshot` | Coût Vapi ce mois (UTC), top tenants par coût ce mois, tenants past_due (count + ids). Sans prix. |

**Sécurité / audit** : à la création d’un Stripe Customer, log `STRIPE_CUSTOMER_CREATED tenant_id=… stripe_customer_id=…`.

Optionnel plus tard : POST `/api/admin/tenants/{id}/stripe-subscription` (lier une subscription existante ou créer avec un price_id).

---

## 3. Webhook Stripe (indispensable)

**Route** : `POST /api/stripe/webhook`  
**Secret** : `STRIPE_WEBHOOK_SECRET` (signature verification).

**Prod-grade :**
- **Raw body** : le handler utilise `await request.body()` (bytes) et pas de JSON parsé avant `stripe.Webhook.construct_event`, sinon la signature casse.
- **Idempotence + concurrence** : Idempotence & concurrency: INSERT event_id first; if conflict -> skip (already processed or handled by another worker).
- **billing_status** : source de vérité = `subscription.status` (customer.subscription.updated) ; on ne se base pas uniquement sur invoice.payment_failed.
- **Mapping tenant** : metadata `tenant_id` sur le Customer à la création ; fallback lookup par `stripe_customer_id` en DB.

**Events gérés** (sans prix, juste sync état) :

| Event | Action |
|-------|--------|
| `customer.subscription.created` | Récupérer customer_id → lookup tenant par stripe_customer_id → upsert subscription_id, status, plan_key, current_period_* |
| `customer.subscription.updated` | Idem : sync status, plan_key, current_period_start/end, trial_ends_at |
| `customer.subscription.deleted` | Mettre billing_status = canceled, subscription_id = null (ou garder pour historique) |
| `invoice.paid` | Optionnel : log ou mettre à jour last_paid_at si tu ajoutes la colonne |
| `invoice.payment_failed` | Optionnel : mettre billing_status = past_due ou notifier |
| `checkout.session.completed` | Si tu utilises Checkout : récupérer customer_id + subscription_id, lier au tenant (metadata ou lookup), upsert billing |

**Résultat** : l’admin affiche en temps réel « Stripe connecté / statut / période » sans toucher aux prix.

**STRIPE_METERED_PRICE_ID (optionnel mais recommandé)**  
Si défini, le webhook remplit `tenant_billing.stripe_metered_item_id` en sélectionnant l'item de subscription dont `price.id == STRIPE_METERED_PRICE_ID`.  
Sinon, fallback : premier item dont `price.recurring.usage_type == "metered"`.  
Recommandation : définir `STRIPE_METERED_PRICE_ID` en test et en live dès que le price « minutes » est créé, pour figer le mapping.

---

## 4. Admin UI (placeholder intelligent)

### Fiche tenant (AdminTenantDetail)

**Bloc « Stripe »**

- Affichage : stripe_customer_id (masqué partiel), billing_status, plan_key, current_period_end, trial_ends_at.
- Bouton **Créer customer** (appelle POST stripe-customer).
- Placeholder **Lier subscription** (désactivé ou « bientôt »).

**Bloc « Usage (Vapi) »**

- Déjà disponible via `tenantStats(id, 7)` et `tenantStats(id, 30)` : minutes 7j / 30j, cost_usd 7j / 30j.
- Afficher clairement : conso réelle + coût réel (sans plan pour l’instant).

**Usage mensuel**

- Lien ou section « Usage mois » : appel GET usage?month=YYYY-MM (affichage simple ; export CSV/PDF plus tard). Convention : **UTC** pour éviter les écarts fin/début de mois.

**Dashboard global (billing snapshot)**

- **Coût Vapi ce mois** (UTC), **top tenants par coût ce mois**, **tenants past_due** avec noms et liens : `tenants_past_due: [{ tenant_id, name, billing_status, current_period_end }]` pour une UI cliquable sans re-fetch. Appel `GET /api/admin/stats/billing-snapshot`. Ne dépend d’aucun prix.

---

## 5. Ce qu’on ajoutera quand les plans sont fixés

- Création des **Products/Prices** Stripe (starter, pro, business, overage €/min).
- **Billing model** : Billing model: choose metered billing (usage records) vs invoice items. Recommended: daily aggregation per tenant for reliability and fewer Stripe API calls.
- **Push d’usage** : job périodique qui lit `vapi_call_usage` par tenant et envoie à Stripe (report usage ou invoice items).
- Bouton **Créer abonnement** (Checkout ou Subscription API) avec choice du plan.

**Suspension past_due (V1, en place)** : colonnes `tenant_billing` (is_suspended, suspension_reason, suspended_at, force_active_override, force_active_until, suspension_mode). Job 03:00 UTC : suspend en **hard** si past_due/unpaid. **hard** = phrase fixe, zero LLM ; **soft** = message poli (MSG_VOCAL_SUSPENDED_SOFT), sans RDV. Soft propose uniquement pour suspension manuelle (recommandé : past_due reste hard). Admin : POST suspend (body: mode hard|soft), unsuspend, force-active (body: days).

---

## 6. Suggestion de plans (structure, sans chiffrer)

| Plan | Idée |
|------|------|
| **Starter** | X appels / minutes inclus |
| **Pro** | Plus + transferts avancés + horaires/FAQ |
| **Business** | Multi-numéros + reporting + SLA |
| **Overage** | €/min au-delà des inclus |

Les seuils et montants se décident plus tard ; le modèle (tenant_billing + usage Vapi + webhooks) reste le même.
