# Audit Stripe existant (UWI) + plan pricing SaaS (abonnement + minutes)

## 1) INVENTORY — Fichiers et rôles

| Fichier | Rôle | Endpoints / Variables / Dépendances |
|---------|------|-------------------------------------|
| **backend/routes/stripe_webhook.py** | Webhook Stripe (sync tenant_billing) | `POST /api/stripe/webhook`. Vérif signature `STRIPE_WEBHOOK_SECRET`, raw body. Events: subscription.created/updated/deleted, invoice.payment_failed, checkout.session.completed. Idempotence via `stripe_webhook_events`. |
| **backend/billing_pg.py** | Lecture/écriture tenant_billing, plans, quota | Pas d’endpoint. Utilise `DATABASE_URL` / `PG_TENANTS_URL`. `get_tenant_billing`, `set_stripe_customer_id`, `upsert_billing_from_subscription`, `set_stripe_metered_item_id`, `clear_subscription`, `update_billing_status`, `try_acquire_stripe_event`, `tenant_id_by_stripe_customer_id`, suspension, `billing_plans`, `get_quota_snapshot_month`. |
| **backend/stripe_usage.py** | Push usage Vapi → Stripe (metered) | Pas d’endpoint. `push_daily_usage_to_stripe(date_utc)`, `try_acquire_usage_push`, `mark_usage_push_sent/failed`. Idempotence via `stripe_usage_push_log`. Utilise `STRIPE_SECRET_KEY`, `get_tenant_billing` (stripe_metered_item_id). |
| **backend/routes/admin.py** | Checkout + customer admin | `POST /api/admin/tenants/{id}/stripe-customer`, `POST /api/admin/tenants/{id}/stripe-checkout` (body: plan_key, trial_days), `GET /api/admin/tenants/{id}/billing`, `GET /api/admin/tenants/{id}/usage?month=`. Dépend `STRIPE_SECRET_KEY`, `STRIPE_CHECKOUT_SUCCESS_URL`, `STRIPE_CHECKOUT_CANCEL_URL`, `STRIPE_PRICE_BASE_{STARTER\|PRO\|BUSINESS}`, `STRIPE_PRICE_METERED_MINUTES` / `STRIPE_METERED_PRICE_ID`. |
| **stripe-server/server.js** | Serveur Express Checkout (embedded) | `POST /create-checkout-session` (mode **payment** 1 price), `GET /session-status`. Env: `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID`, `FRONTEND_URL`, `CORS_ORIGIN`. **Indépendant du backend FastAPI** ; pas de subscription, pas de tenant_id. |
| **landing/src/pages/Checkout.jsx** | Page Checkout embedded (landing) | Appelle `stripeApiUrl/create-checkout-session` (stripe-server). Env: `VITE_STRIPE_PUBLISHABLE_KEY`, `VITE_STRIPE_API_URL`. Query: `price_id` / `price`. |
| **landing/src/admin/.../BillingUsageCard.jsx** | UI admin billing tenant | Affiche stripe_customer_id, bouton « Créer customer Stripe », appel `adminApi.createStripeCheckout(tenantId, { plan_key, trial_days })` → backend FastAPI. |
| **migrations/011_tenant_billing.sql** | Table tenant_billing | tenant_id PK, stripe_customer_id, stripe_subscription_id, billing_status, plan_key, current_period_*, trial_ends_at, updated_at. |
| **migrations/012_stripe_webhook_events.sql** | Idempotence webhook | event_id PK. |
| **migrations/013_tenant_billing_suspension.sql** | Colonnes suspension | is_suspended, suspension_reason, suspended_at. |
| **migrations/014_tenant_billing_suspension_mode.sql** | Mode suspension | suspension_mode, force_active_override, force_active_until. |
| **migrations/015_stripe_usage_push_log.sql** | Idempotence usage push | (tenant_id, date_utc) PK, quantity_minutes, stripe_usage_record_id, pushed_at ; + tenant_billing.stripe_metered_item_id. |
| **migrations/017_stripe_usage_push_log_status.sql** | Statut push | status (pending/sent/failed), error_short. |
| **docs/STRIPE_FOUNDATION.md** | Doc fondation | Variables, endpoints, events webhook, DB. |
| **docs/STRIPE_BILLING.md** | Doc billing (à venir) | Modèles abo + usage, webhooks. |
| **docs/ROADMAP_MONETISATION.md** | Roadmap | Metered billing, push daily usage, blocage quota, Stripe Checkout admin. |
| **tests/test_stripe_checkout.py** | Tests checkout admin | POST stripe-checkout, mock Stripe. |
| **tests/test_monetisation_quota_stripe.py** | Tests quota/suspension | Quota, suspension, Stripe. |

---

## 2) CURRENT FLOW

```
[Admin] Créer customer Stripe
  → POST /api/admin/tenants/{id}/stripe-customer
  → Stripe Customer.create(metadata.tenant_id)
  → billing_pg.set_stripe_customer_id(tenant_id, cus_xxx)

[Admin] Créer abonnement (Checkout)
  → POST /api/admin/tenants/{id}/stripe-checkout { plan_key: "starter"|"pro"|"business", trial_days? }
  → Backend: ensure customer (create if missing) → Stripe Checkout.Session.create(mode=subscription, customer, line_items=[base_price, metered_price], subscription_data.metadata.tenant_id)
  → Retourne checkout_url → redirection user

[Stripe] Paiement réussi
  → Stripe envoie checkout.session.completed
  → POST /api/stripe/webhook (signature vérifiée, raw body)
  → tenant_id = metadata.tenant_id ou lookup stripe_customer_id → Subscription.retrieve → _sync_subscription → upsert_billing_from_subscription + set_stripe_metered_item_id

[Stripe] Sync abo
  → subscription.created/updated → _sync_subscription → tenant_billing (subscription_id, status, plan_key, period_*, stripe_metered_item_id)
  → subscription.deleted → clear_subscription
  → invoice.payment_failed → update_billing_status(past_due)

[Cron] Push usage
  → stripe_usage.push_daily_usage_to_stripe(yesterday_utc)
  → vapi_call_usage agrégé par tenant/jour → try_acquire_usage_push → UsageRecord.create(subscription_item=stripe_metered_item_id, quantity=minutes) → mark_usage_push_sent
```

**Flow parallèle (landing, non lié au multi-tenant)**  
Landing Checkout.jsx → stripe-server (Express) `/create-checkout-session` → mode **payment** (one-shot), 1 price_id. Pas de tenant_id, pas de subscription. À ne pas mélanger avec le flow admin/abo.

---

## 3) GAPS

- **Plans** : Code actuel = `starter | pro | business` et `STRIPE_PRICE_BASE_STARTER/PRO/BUSINESS`. Objectif = **Starter / Growth / Pro** (99 / 149 / 199 €, 400 / 800 / 1200 min, 0,19 / 0,17 / 0,15 €/min). Il manque **Growth** (plan_key + env `STRIPE_PRICE_BASE_GROWTH`) et **6 prices** Stripe (3 base + 3 metered) à créer.
- **Prix Stripe** : Aucun price_id documenté dans le repo. Les 6 prices (base Starter/Growth/Pro + minutes Starter/Growth/Pro) doivent être créés dans le Dashboard (ou script), puis les 6 env vars branchées.
- **Checkout** : Backend crée déjà **2 line_items** (base + metered). OK. Il faut s’assurer que chaque plan pointe vers le **bon** price base + le **bon** price metered (ou 1 seul price metered partagé avec 3 agrégations de coût selon plan — Stripe ne gère qu’un usage en quantité ; le €/min différent par plan se gère soit par 3 prices metered, soit par logique côté app).
- **Upgrade automatique** : **Absent**. Pas de `maybe_upgrade_plan(tenant_id, minutes_month_to_date)` ni simulation coût. À ajouter côté backend (job ou après push usage), sans changer Stripe (c’est nous qui décidons du plan et on crée une nouvelle subscription ou on change d’item si vous basculez en Stripe).
- **report_minutes(tenant_id, minutes, timestamp)** : Pas d’API explicite “report minutes”. L’usage est poussé par **push_daily_usage_to_stripe** (agrégation jour par jour depuis `vapi_call_usage`). Si vous voulez une API “report minutes” à la demande, à ajouter (sinon le cron suffit).
- **stripe-server (Express)** : Mode payment, 1 price, pas de tenant. Utile seulement pour un flux landing “one-shot”. Pour l’abo SaaS, tout passe par le **backend FastAPI** (stripe-checkout admin). À ne pas casser ; clarifier dans la doc quel flux utilise quoi.
- **BillingUsageCard** : Appelle bien `createStripeCheckout` (backend). OK.
- **Redirection success/cancel** : Backend retourne `checkout_url` ; redirection gérée par Stripe. `STRIPE_CHECKOUT_SUCCESS_URL` / `STRIPE_CHECKOUT_CANCEL_URL` à configurer (ex. dashboard ou page merci).

---

## 4) ENV VARS (référence)

| Variable | Où utilisée |
|----------|-------------|
| `STRIPE_SECRET_KEY` | stripe_webhook (Subscription.retrieve), admin (Customer.create, Checkout.Session.create), stripe_usage (UsageRecord.create), stripe-server |
| `STRIPE_WEBHOOK_SECRET` | stripe_webhook (construct_event) |
| `STRIPE_CHECKOUT_SUCCESS_URL` | admin stripe-checkout |
| `STRIPE_CHECKOUT_CANCEL_URL` | admin stripe-checkout |
| `STRIPE_PRICE_BASE_STARTER` | admin (plan_key=starter) |
| `STRIPE_PRICE_BASE_PRO` | admin (plan_key=pro) |
| `STRIPE_PRICE_BASE_BUSINESS` | admin (plan_key=business) |
| `STRIPE_PRICE_BASE_GROWTH` | **Manquant** — à ajouter pour Growth |
| `STRIPE_PRICE_METERED_MINUTES` / `STRIPE_METERED_PRICE_ID` | admin (line_items metered), stripe_webhook (_get_metered_subscription_item_id), stripe_usage (indirect via metered_item_id) |

Landing / stripe-server : `VITE_STRIPE_PUBLISHABLE_KEY`, `VITE_STRIPE_API_URL`, `STRIPE_PRICE_ID`, `FRONTEND_URL`, `CORS_ORIGIN`.

---

## 5) DIAGNOSTIC RAPIDE

- **Webhook** : Signature vérifiée (raw body + `STRIPE_WEBHOOK_SECRET`). OK.
- **Events** : checkout.session.completed, customer.subscription.created/updated/deleted, invoice.payment_failed. invoice.paid traité (pass). OK.
- **Tracking usage** : Oui. `vapi_call_usage` → `push_daily_usage_to_stripe` → `UsageRecord.create` (idempotence `stripe_usage_push_log`). OK.
- **Checkout** : Backend = **Checkout Sessions** (subscription, 2 line items). Pas de Payment Links. OK.
- **Multi-tenant** : tenant_id dans metadata (customer + subscription + session). Fallback lookup par `stripe_customer_id` en DB. OK.

---

## 6) MINIMAL PLAN (PROD SAFE)

1. **Stripe Dashboard (ou API)**  
   Créer 1 Product “UWI Voice”, puis **6 Prices** :  
   - Starter base 99 €/mois récurrent ; Starter minutes 0,19 €/min metered.  
   - Growth base 149 €/mois ; Growth minutes 0,17 €/min metered.  
   - Pro base 199 €/mois ; Pro minutes 0,15 €/min metered.  
   Copier les price_id dans la config.

2. **Env**  
   Définir : `STRIPE_PRICE_BASE_STARTER`, `STRIPE_PRICE_BASE_GROWTH`, `STRIPE_PRICE_BASE_PRO`, `STRIPE_PRICE_METERED_MINUTES_STARTER`, `_GROWTH`, `_PRO` (ou 1 seul metered partagé si même unité et facturation côté vous). Backend actuel n’attend qu’**un** metered ; si 3 prices metered, adapter admin pour passer le bon metered selon plan_key.

3. **Backend — Checkout**  
   - Ajouter `plan_key: "growth"` dans `StripeCheckoutBody` et dans la résolution du base price (`STRIPE_PRICE_BASE_GROWTH`).  
   - Si 3 metered différents : selon plan_key, choisir `STRIPE_PRICE_METERED_MINUTES_STARTER/GROWTH/PRO` et l’envoyer comme 2e line_item. Fichier : `backend/routes/admin.py` (admin_create_stripe_checkout).

4. **Backend — Webhook**  
   - Déjà OK pour récupérer le metered item (STRIPE_METERED_PRICE_ID ou premier item metered). Si 3 metered, s’assurer que le bon price est associé au bon plan (ou garder un seul STRIPE_METERED_PRICE_ID et un seul price metered pour tous les plans si vous facturez pareil côté Stripe).

5. **billing_plans (DB)**  
   - Aligner les plans avec Starter/Growth/Pro : 400 / 800 / 1200 min. Fichier : `backend/billing_pg.py` (DEFAULT_PLANS) + migration optionnelle pour `billing_plans` (starter=400, growth=800, pro=1200).

6. **report_minutes (optionnel)**  
   - Si besoin d’une API “report minutes” : ajouter `POST /api/internal/report-usage` (ou admin) qui enregistre en base puis appelle un push vers Stripe (ou seulement en base et laisser le cron quotidien pousser). Sinon garder uniquement `push_daily_usage_to_stripe` (cron).

7. **maybe_upgrade_plan (backend)**  
   - Nouvelle fonction : `maybe_upgrade_plan(tenant_id, minutes_month_to_date)`. Règles : si Starter et >800 min et coût simulé Growth < coût actuel → upgrade ; si Growth et >1200 min et Pro plus avantageux → upgrade. Implémentation : soit création nouvelle subscription Stripe (cancel current + create new avec nouveau price), soit changement d’item (Stripe API). Appel : depuis un job après push usage ou depuis un endpoint admin “suggest upgrade”.

8. **Cron push usage**  
   - Déjà en place. Vérifier que le cron (01:00 UTC) appelle `push_daily_usage_with_retry_48h` (ou équivalent). Pas de changement si déjà déployé.

9. **Tests**  
   - Ajouter tests pour plan_key=growth et pour les 3 plans (base + metered). Adapter mocks price_id si besoin.

10. **Doc**  
    - Mettre à jour STRIPE_FOUNDATION.md : ajouter STRIPE_PRICE_BASE_GROWTH, les 6 prices, et la logique upgrade (où elle est appelée, pas de changement Stripe automatique).

---

## 7) Checklist pré-prod (vérifs indispensables)

**A. Env vars (Railway → service API → Variables)**  
Les 6 variables doivent être définies sur le service qui exécute l’API (pas seulement en project) :
- `STRIPE_PRICE_BASE_STARTER`, `STRIPE_PRICE_BASE_GROWTH`, `STRIPE_PRICE_BASE_PRO`
- `STRIPE_PRICE_METERED_STARTER`, `STRIPE_PRICE_METERED_GROWTH`, `STRIPE_PRICE_METERED_PRO`  
En prod : laisser les legacy (`STRIPE_PRICE_METERED_MINUTES`, `STRIPE_METERED_PRICE_ID`) vides pour éviter de masquer une mauvaise config. Si legacy est utilisé, un log `STRIPE_CHECKOUT_LEGACY_METERED` apparaît au checkout.

**B. Webhook : metered item après checkout**  
Après un checkout Growth (test) : dans `tenant_billing`, `stripe_metered_item_id` doit être rempli. Les logs webhook ne doivent pas reposer sur le fallback “premier item metered” si les 3 env metered sont définis.

**C. Cron : pas de spam**  
`run_upgrade_suggestions()` logue **une seule ligne par tenant** ayant une suggestion, avec : `tenant_id`, `current_plan`, `suggested_plan`, `minutes_used`, `current_cost_eur`, `suggested_cost_eur`, `delta_eur`.

**D. Migration**  
Exécuter `migrations/030_billing_plans_starter_growth_pro.sql` sur la DB prod (Railway → Postgres → Query) pour créer/aligner `billing_plans` (starter 400, growth 800, pro 1200).

**E. Tests / bcrypt**  
Les tests (dont Stripe checkout) nécessitent les deps du projet. En CI/local : `pip install -r requirements.txt`. Ne pas contourner l’absence de bcrypt (auth en dépend).

---

## 8) RISKS / GOTCHAS

- **Prorations** : Changement de plan en cours de période → prorata Stripe. Bien tester upgrade (cancel + create vs update subscription items).
- **Cycle de facturation** : Anchor sur subscription. Si upgrade, définir si nouvelle période ou prorata.
- **Arrondis** : `push_daily_usage_to_stripe` utilise `CEIL(SUM(duration_sec)/60)`. Cohérent avec un quantity entier pour UsageRecord.
- **Retries webhook** : Stripe renvoie les events. Idempotence via `stripe_webhook_events` (INSERT event_id) évite double traitement. OK.
- **Double push usage** : Idempotence via `stripe_usage_push_log` (tenant_id, date_utc). OK.
- **Metered : 1 vs 3 prices** : Un seul price metered = un seul “bucket” de facturation ; les différences €/min par plan peuvent être gérées en ayant 3 prices metered (recommandé pour 0,19 / 0,17 / 0,15) et 2 line_items par plan (base + metered correspondant).
