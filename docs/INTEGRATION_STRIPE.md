# Intégration Stripe

Guide de référence technique pour l'intégration Stripe (paiement et facturation). Synthétise tout ce qui est nécessaire pour comprendre, configurer, déboguer et étendre l'intégration.

> Pour les sujets pointus (E2E, install, audit pricing), voir les docs spécialisées en bas de page.

---

## Vue d'ensemble

UWI utilise Stripe pour :
- **Subscriptions** (abonnements mensuels) : 3 plans `starter`, `growth`, `pro`.
- **Hybrid pricing** : un prix **base** mensuel + un prix **metered** (facturation à la minute Vapi consommée).
- **Customer Portal** : gestion CB / factures par le client.
- **Embedded Checkout** : parcours d'inscription self-service depuis la landing.

```
                         ┌─► Hosted Checkout (admin) → Subscription créée
Client ──► UWI Admin ────┤
                         └─► send-payment-link → Email avec URL Checkout

         ┌─► Customer Portal (gérer CB / annuler)
Client ──┤
         └─► Embedded Checkout (landing self-service)

Stripe ──► POST /api/stripe/webhook ──► sync DB tenant_billing
                                       └─► suspend / unsuspend tenant

Cron quotidien ──► push_daily_usage ──► UsageRecord ou MeterEvent
                                       (depuis vapi_call_usage)
```

---

## Variables d'environnement

### Backend

#### Clés API

| Variable | Obligatoire | Rôle |
|---|---|---|
| `STRIPE_SECRET_KEY` | ✅ | Clé secrète API. Sans elle, les endpoints billing renvoient 503. |
| `STRIPE_WEBHOOK_SECRET` | ✅ | Vérification signature `/api/stripe/webhook` (sinon 503). |

#### Price IDs (par plan)

| Variable | Rôle |
|---|---|
| `STRIPE_PRICE_BASE_STARTER` / `_GROWTH` / `_PRO` | Price IDs **forfait mensuel** par plan |
| `STRIPE_PRICE_METERED_STARTER` / `_GROWTH` / `_PRO` | Price IDs **metered** (€/min) par plan |
| `STRIPE_PRICE_METERED_MINUTES` ou `STRIPE_METERED_PRICE_ID` | Fallback **un seul** price metered (legacy) |
| `STRIPE_PRICE_ID` | Fallback Embedded Checkout si pas de plan/price body |

#### URLs de redirection

| Variable | Rôle |
|---|---|
| `STRIPE_CHECKOUT_SUCCESS_URL` | Redirection après checkout admin (obligatoire pour `/stripe-checkout`) |
| `STRIPE_CHECKOUT_CANCEL_URL` | Redirection si annulation |
| `STRIPE_PORTAL_RETURN_URL` | Retour depuis Billing Portal (fallback : `STRIPE_CHECKOUT_SUCCESS_URL`) |
| `STRIPE_EMBEDDED_RETURN_URL` | Base URL pour Embedded Checkout (fallback : `FRONTEND_URL` puis `https://uwiapp.com`) |
| `CLIENT_APP_ORIGIN` (+ fallbacks `ADMIN_BASE_URL`, `FRONT_BASE_URL`, `APP_BASE_URL`) | Construit `success_url`/`cancel_url` pour `send-payment-link` |

#### Metering

| Variable | Défaut | Rôle |
|---|---|---|
| `STRIPE_USE_METER_EVENTS` | `false` | Si `true` → `billing.MeterEvent.create` (nouveau Stripe Meters). Sinon → `UsageRecord.create` (legacy). |
| `STRIPE_METER_EVENT_NAME` | `uwi.minutes` | Nom du meter event |

### Frontend (`landing/src/`)

| Variable | Rôle |
|---|---|
| `VITE_STRIPE_PUBLISHABLE_KEY` | `loadStripe()` côté Embedded Checkout |
| `VITE_STRIPE_API_URL` | URL du serveur Embedded Checkout (par défaut `http://localhost:4242` → voir `stripe-server/`) |

> Voir [`STRIPE_CHECKLIST_RAILWAY.md`](./STRIPE_CHECKLIST_RAILWAY.md) pour la liste complète à provisionner sur Railway.

---

## Plans & pricing

### Mapping plan → Stripe

100 % configurable par variables d'env. La fonction de référence est `_get_stripe_price_ids_for_plan()` dans `backend/routes/admin.py:3039`.

| Plan | Variable base | Variable metered |
|---|---|---|
| `starter` | `STRIPE_PRICE_BASE_STARTER` | `STRIPE_PRICE_METERED_STARTER` |
| `growth` | `STRIPE_PRICE_BASE_GROWTH` | `STRIPE_PRICE_METERED_GROWTH` |
| `pro` | `STRIPE_PRICE_BASE_PRO` | `STRIPE_PRICE_METERED_PRO` |

### Quotas & dépassement (côté app)

Définis dans la table `billing_plans` (PG) avec `DEFAULT_PLANS` dans `backend/billing_pg.py:491` :

| Plan | Minutes incluses | €/min dépassement |
|---|---:|---:|
| `starter` | 400 | défini par `PLAN_OVERAGE_EUR_PER_MIN` |
| `growth` | 800 | id. |
| `pro` | 1200 | id. |
| `business` / `custom` / `free` | variable | id. |

> Voir [`AUDIT_STRIPE_UWI_PRICING.md`](./AUDIT_STRIPE_UWI_PRICING.md) pour les choix de pricing.

---

## Endpoints backend

### Admin (`/api/admin/*`)

| Méthode | Path | Rôle | Auth |
|---|---|---|---|
| GET | `/api/admin/tenants/{id}/billing` | Lit l'état billing du tenant | admin |
| GET | `/api/admin/tenants/{id}/billing/invoices` | Liste les factures Stripe | admin |
| POST | `/api/admin/tenants/{id}/billing/change-plan` | `Subscription.modify` (nouveau base + metered) | admin |
| POST | `/api/admin/tenants/{id}/billing/cancel` | `cancel_at_period_end=True` | admin |
| POST | `/api/admin/tenants/{id}/billing/resume` | `cancel_at_period_end=False` | admin |
| POST | `/api/admin/tenants/{id}/billing/portal-link` | URL Billing Portal | admin |
| POST | `/api/admin/tenants/{id}/billing/set-metered-item` | Force `stripe_metered_item_id` (debug) | admin |
| POST | `/api/admin/tenants/{id}/billing/resync-metered-item` | Re-fetch sub Stripe + maj metered item | admin |
| POST | `/api/admin/tenants/{id}/stripe-customer` | `Customer.create` + DB | admin |
| POST | `/api/admin/tenants/{id}/stripe-checkout` | Hosted Checkout subscription | admin |
| POST | `/api/admin/tenants/{id}/send-payment-link` | Setup intent ou checkout 30j trial + email | admin |
| POST | `/api/admin/tenants/create` | **Provisioning complet** (customer + subscription) | admin |
| GET | `/api/admin/billing/overview` | Agrégat billing + usage (lecture DB seule) | admin |
| GET | `/api/admin/billing/plans` | Liste quotas (`get_billing_plans()`) | admin |
| GET | `/api/admin/stats/billing-snapshot` | Coûts + tenants `past_due` | admin |
| POST | `/api/admin/jobs/push-daily-usage` | Cron : push usage vers Stripe | admin |
| POST | `/api/admin/jobs/insert-test-usage` | Seed `vapi_call_usage` (E2E) | admin |
| GET | `/api/admin/tenants/{id}/stripe-usage-push-log` | Log idempotence push | admin |

### Public

| Méthode | Path | Rôle | Auth |
|---|---|---|---|
| POST | `/api/stripe/webhook` | **Webhook Stripe** | Signature uniquement |
| POST | `/create-checkout-session` | Embedded Checkout (FastAPI, `checkout_embedded.py`) | ⚠️ Public sans auth — à protéger |

### Serveur Node séparé

`stripe-server/server.js` expose `POST /create-checkout-session` et `GET /session-status` pour la landing publique. Configurable via `VITE_STRIPE_API_URL`.

---

## Webhooks Stripe

**Endpoint** : `POST /api/stripe/webhook` (`backend/routes/stripe_webhook.py:241`).

### Sécurité
- `STRIPE_WEBHOOK_SECRET` obligatoire (sinon **503**).
- Vérification : `stripe.Webhook.construct_event(payload, sig, secret)`.
- Body **raw bytes** requis (pas de JSON parsing avant signature).

### Idempotence
Table `stripe_webhook_events` (migration `012`) avec `try_acquire_stripe_event(event_id)`.

### Événements gérés

| Événement | Action |
|---|---|
| `customer.subscription.created` / `updated` | Re-fetch sub avec expand → `_sync_subscription` → si `active`/`trialing` → `set_tenant_unsuspended` |
| `customer.subscription.deleted` | `clear_subscription` |
| `invoice.payment_failed` | `update_billing_status(..., "past_due")` |
| `invoice.paid` | no-op (commentaire "optional") |
| `checkout.session.completed` | Résolution tenant (par customer ou metadata.tenant_id) → sync subscription + log metered item |

> **Pas géré** : `payment_intent.succeeded`. Le suivi se fait via `invoice.*` et `customer.subscription.*`.

---

## Provisioning : tenant ↔ Stripe

### Flow complet via `POST /api/admin/tenants/create` (`admin.py:3966`)

1. **PG** : `tenant`, `tenant_config`, `user` admin.
2. **Vapi** : `create_vapi_assistant` (cf. [`INTEGRATION_VAPI.md`](./INTEGRATION_VAPI.md)).
3. **Twilio** : `assign_twilio_to_vapi` si numéro fourni.
4. **Stripe** :
   - `stripe.Customer.create(email, name, metadata={tenant_id})`
   - `stripe.Subscription.create(customer, items=[base, metered?], trial_period_days=30, payment_behavior="default_incomplete")`
   - `upsert_billing_from_subscription(...)` → DB `tenant_billing`.
5. **Rollback** sur erreur (`_rollback_provisioning`, `admin.py:3943`) :
   - Supprime sub + customer Stripe
   - Supprime assistant Vapi
   - Delete tenant PG
   - ⚠️ Ne désassigne pas le numéro Vapi (TODO)

### Flow alternatif (sans full)

- `stripe-customer` seul → puis `stripe-checkout` ou `send-payment-link` plus tard.

---

## Metering : Vapi minutes → Stripe

### Source
Agrégation journalière UTC depuis `vapi_call_usage` via `_aggregate_usage_by_tenant_for_day()` (`stripe_usage.py:186`).

### Conditions
Tenant éligible si :
- `stripe_subscription_id` présent
- `stripe_metered_item_id` présent (extrait du sub par `_sync_subscription`)

### Modes (`STRIPE_USE_METER_EVENTS`)

| Mode | Stripe API |
|---|---|
| `false` (legacy) | `UsageRecord.create(action="set", timestamp=fin_jour_utc)` |
| `true` (Meters) | `billing.MeterEvent.create(event_name="uwi.minutes", payload={value, customer_id})` |

### Orchestration

`push_daily_usage_with_retry_48h()` (`stripe_usage.py:334`) :
- Push J-1 + J-2 (rattrapage)
- `run_upgrade_suggestions()` (logs uniquement, pas de changement de plan)

### Déclenchement prod
Cron qui appelle `POST /api/admin/jobs/push-daily-usage` (cf. [`ROADMAP_MONETISATION.md`](./ROADMAP_MONETISATION.md)).

### Idempotence
Table `stripe_usage_push_log` (migrations `015`, `017`) — empêche le double-push pour un même `(tenant_id, day, item_id)`.

---

## Base de données

| Table | Migration | Contenu |
|---|---|---|
| `tenant_billing` | `011_tenant_billing.sql` | `stripe_customer_id`, `stripe_subscription_id`, `billing_status`, `plan_key`, périodes, `trial_ends_at`, `updated_at` |
| extensions billing | `013_*`, `014_*` | Suspension automatique |
| `tenant_billing.stripe_metered_item_id` | `015_stripe_usage_push_log.sql` | Item ID metered de la sub |
| `stripe_webhook_events` | `012` | Idempotence webhooks (PK `event_id`) |
| `stripe_usage_push_log` | `015`, `017` | Idempotence push usage |
| `billing_plans` | `ensure_billing_plans()` (code) | Quotas et tarifs (PG) |

---

## Frontend admin

| Composant | Rôle |
|---|---|
| `landing/src/admin/pages/AdminBilling.jsx` | Vue d'ensemble billing (overview + plans) |
| `landing/src/admin/components/AdminBillingSection.jsx` | Actions par tenant : change-plan, cancel, resume, portal-link |
| `landing/src/admin/components/AdminTenantActionsTab.jsx` | Bouton Stripe checkout côté tenant |
| `landing/src/admin/components/TenantCreationWizard.jsx` | Provisioning (déclenche `tenants/create`) |
| `landing/src/lib/adminApi.js` | Wrapper REST : `getBillingOverview`, `changeTenantPlan`, etc. |

### Public (landing self-service)

| Composant | Rôle |
|---|---|
| `landing/src/pages/Checkout.jsx` | Embedded Checkout — `loadStripe(VITE_STRIPE_PUBLISHABLE_KEY)`, fetch `VITE_STRIPE_API_URL/create-checkout-session` |
| `landing/src/pages/CheckoutReturn.jsx` | Retour : fetch `VITE_STRIPE_API_URL/session-status` |

> ⚠️ La landing publique pointe vers **`stripe-server/`** (Express) pour Embedded Checkout, **pas** le backend FastAPI.

---

## Mode démo

Quand `ADMIN_DEMO_MODE=true` :
- Tous les endpoints `/api/admin/billing/*` retournent du dataset factice (router `backend/admin_demo/`).
- Le middleware `admin_demo_write_block` bloque les POST (403) → impossible de créer un customer/sub réel par accident.
- Les boutons "Portail Stripe", "Réactiver", "Annuler abonnement", "Changer de plan" sont désactivés côté UI avec tooltip explicatif.

> Voir [`ADMIN_DEMO_MODE.md`](./ADMIN_DEMO_MODE.md).

---

## Sécurité

| Item | Statut |
|---|---|
| `STRIPE_SECRET_KEY` côté serveur uniquement | ✅ |
| `STRIPE_WEBHOOK_SECRET` obligatoire (sinon 503) | ✅ |
| Vérification signature webhook | ✅ `stripe.Webhook.construct_event` |
| Endpoints `/api/admin/billing/*` protégés | ✅ `Depends(_verify_admin)` |
| `POST /create-checkout-session` (FastAPI) sans auth | ⚠️ À protéger (clé API ou reverse-proxy) si exposé Internet |
| `VITE_STRIPE_PUBLISHABLE_KEY` côté frontend | ✅ Clé publique, OK |

---

## Tests

| Fichier | Couvre |
|---|---|
| `tests/test_stripe_checkout.py` | Hosted Checkout admin (URL, metadata, customer, erreurs env) |
| `tests/test_stripe_usage.py` | `UsageRecord` vs `MeterEvent`, `push_usage_via_meter_events` |
| `tests/test_monetisation_quota_stripe.py` | Idempotence double-run `push_daily_usage_to_stripe` |

> Voir [`STRIPE_E2E_TESTS.md`](./STRIPE_E2E_TESTS.md) pour les scénarios E2E manuels.

---

## Debug & opérationnel

### Vérifier l'état Stripe d'un tenant

```bash
# 1. Etat en DB
curl -H "Authorization: Bearer $ADMIN_API_TOKEN" \
  http://localhost:8000/api/admin/tenants/42/billing

# 2. Subscription Stripe
stripe subscriptions retrieve $SUB_ID --expand items.data

# 3. Re-sync depuis Stripe
curl -X POST -H "Authorization: Bearer $ADMIN_API_TOKEN" \
  http://localhost:8000/api/admin/tenants/42/billing/resync-metered-item
```

### Forcer le push usage du jour

```bash
curl -X POST -H "Authorization: Bearer $ADMIN_API_TOKEN" \
  http://localhost:8000/api/admin/jobs/push-daily-usage
```

### Logs idempotence

```sql
select * from stripe_usage_push_log where tenant_id = 42 order by day desc limit 10;
select * from stripe_webhook_events order by created_at desc limit 20;
```

### Tester un webhook localement

```bash
stripe listen --forward-to localhost:8000/api/stripe/webhook
stripe trigger customer.subscription.updated
```

---

## Voir aussi

### Setup & ops
- [`STRIPE_FOUNDATION.md`](./STRIPE_FOUNDATION.md) — fondations et choix d'architecture
- [`STRIPE_BILLING.md`](./STRIPE_BILLING.md) — détails facturation
- [`STRIPE_UWIAPP_INSTALL.md`](./STRIPE_UWIAPP_INSTALL.md) — installation pas-à-pas
- [`STRIPE_CHECKLIST_RAILWAY.md`](./STRIPE_CHECKLIST_RAILWAY.md) — variables Railway

### Tests
- [`STRIPE_E2E_TESTS.md`](./STRIPE_E2E_TESTS.md) — scénarios E2E
- [`TESTS_BACKEND.md`](./TESTS_BACKEND.md) — vue d'ensemble tests backend

### Pricing & monétisation
- [`AUDIT_STRIPE_UWI_PRICING.md`](./AUDIT_STRIPE_UWI_PRICING.md) — audit pricing
- [`ROADMAP_MONETISATION.md`](./ROADMAP_MONETISATION.md) — roadmap

### Liés
- [`INTEGRATION_VAPI.md`](./INTEGRATION_VAPI.md) — source des minutes facturées
- [`API_ADMIN_ONBOARDING.md`](./API_ADMIN_ONBOARDING.md) — provisioning tenant complet
