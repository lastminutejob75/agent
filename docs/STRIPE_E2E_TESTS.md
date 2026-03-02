# Série de tests E2E Stripe (UWI)

**Objectif** : Valider en prod/staging que le flux Stripe complet fonctionne (checkout, webhook, push usage, upgrade suggestions).

**Dernière exécution** : _à remplir (YYYY-MM-DD)_

---

## Pré-requis

- **Railway** (service API) :
  - `STRIPE_SECRET_KEY`
  - `STRIPE_WEBHOOK_SECRET`
  - `STRIPE_CHECKOUT_SUCCESS_URL` / `STRIPE_CHECKOUT_CANCEL_URL`
  - 6 `STRIPE_PRICE_*` (base + metered : starter, growth, pro)
  - `STRIPE_USE_METER_EVENTS=false` (par défaut)
- **Webhook Stripe** configuré sur : `https://agent-production-c246.up.railway.app/api/stripe/webhook`
- **Tenant test** : `TENANT_ID` (ex. `1`) — variable Railway ou ID connu
- **Admin** : `ADMIN_API_TOKEN` — variable Railway (Bearer) ou session cookie admin

> **Note** : `TENANT_ID` et `ADMIN_API_TOKEN` sont configurés sur Railway (variables d'environnement du service API ou du projet). Utiliser ces valeurs lors de l'exécution des tests.

**Script rapide** : `ADMIN_API_TOKEN=xxx TENANT_ID=1 ./scripts/run-stripe-e2e-tests.sh`

---

## TEST 1 — Checkout Growth (API + Stripe UI)

### 1.1 Commande exécutée

```bash
curl -i -X POST "https://agent-production-c246.up.railway.app/api/admin/tenants/TENANT_ID/stripe-checkout" \
  -H "Authorization: Bearer ADMIN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"plan_key":"growth"}'
```

Remplacer `TENANT_ID` et `ADMIN_API_TOKEN` par les valeurs configurées sur Railway.

### 1.2 Attendu

- **HTTP 200**
- Body JSON contient `checkout_url`

### 1.3 Vérification Stripe Checkout (avant paiement)

Ouvrir `checkout_url` dans le navigateur. Vérifier **2 lignes** :

- Base Growth 149€/mois
- Metered Growth (Minutes)

### 1.4 Paiement

- **Test mode** : carte `4242 4242 4242 4242`
- Compléter le paiement

### 1.5 Redirection

- Redirection vers `https://www.uwiapp.com/billing` (ou URL configurée dans `STRIPE_CHECKOUT_SUCCESS_URL`)
- Bandeau succès + URL nettoyée

### 1.6 Verdict

| Étape | Résultat | Notes |
|-------|----------|-------|
| API checkout_url | ⬜ OK / ❌ | |
| 2 lignes Stripe | ⬜ OK / ❌ | |
| Paiement | ⬜ OK / ❌ | |
| Redirection billing | ⬜ OK / ❌ | |

---

## TEST 2 — Webhook → tenant_billing

### 2.1 Requête SQL (Postgres)

```sql
SELECT tenant_id, plan_key, stripe_customer_id, stripe_subscription_id, stripe_metered_item_id, updated_at
FROM tenant_billing
WHERE tenant_id = 'TENANT_ID';
```

### 2.2 Attendu

- `plan_key = 'growth'`
- `stripe_subscription_id` LIKE `sub_%`
- `stripe_metered_item_id` LIKE `si_%` (non vide)

### 2.3 Logs Railway

Vérifier réception des events Stripe (200) : `checkout.session.completed`, `customer.subscription.updated`, etc.

### 2.4 Verdict

| Champ | Attendu | Observé |
|-------|--------|---------|
| plan_key | growth | |
| stripe_subscription_id | sub_... | |
| stripe_metered_item_id | si_... | |
| Logs webhook | 200 | |

**Verdict global TEST 2** : ⬜ ✅ / ❌

---

## TEST 3 — Push usage (legacy UsageRecord) + idempotence

### 3.1 Vérifier STRIPE_USE_METER_EVENTS

- `STRIPE_USE_METER_EVENTS=false` (ou non défini)

### 3.2 Règle : pousser le TOTAL des minutes (Option A)

Les prices metered Stripe sont configurés avec paliers (0€ jusqu'à 400/800/1200 min puis €/min). On pousse donc le **total** des minutes — Stripe applique les paliers.

**Checklist Stripe (metered price)** :
- Recurring → Usage type = **Metered**
- Billing scheme = **Progressive** (graduée)
- Tiers : 1→800 (Growth) = 0€/unité ; au-delà = 0,17€/unité

**Backend** : on pousse l'usage **journalier** (chaque jour). Stripe somme les records sur la période → total. Paliers appliqués au total. Ex. 500 min → 0€ ; 900 min → 100×0,17€.

### 3.3 Données usage (vapi_call_usage)

Pour déclencher un push, il faut des lignes dans `vapi_call_usage` pour **hier** (UTC) :

```sql
-- Vérifier les données existantes
SELECT tenant_id, ended_at, duration_sec, CEIL(SUM(duration_sec)::numeric / 60)::int AS minutes
FROM vapi_call_usage
WHERE ended_at >= (CURRENT_DATE - INTERVAL '1 day')::timestamp
  AND ended_at < CURRENT_DATE::timestamp
GROUP BY tenant_id, ended_at;
```

Si vide, insérer des données de test. **Schéma** : `tenant_id`, `vapi_call_id`, `started_at`, `ended_at`, `duration_sec`, `cost_usd`, `cost_currency`.

```sql
-- 55 min total pour hier (15+20+20). Exécuter sur Postgres Railway.
INSERT INTO vapi_call_usage (tenant_id, vapi_call_id, started_at, ended_at, duration_sec, cost_usd, cost_currency)
VALUES
  (1, 'test-usage-' || gen_random_uuid()::text,
   (date_trunc('day', now() AT TIME ZONE 'utc') - interval '1 day') + interval '10:00',
   (date_trunc('day', now() AT TIME ZONE 'utc') - interval '1 day') + interval '10:15',
   900, 0.05, 'USD'),
  (1, 'test-usage-' || gen_random_uuid()::text,
   (date_trunc('day', now() AT TIME ZONE 'utc') - interval '1 day') + interval '14:00',
   (date_trunc('day', now() AT TIME ZONE 'utc') - interval '1 day') + interval '14:20',
   1200, 0.07, 'USD'),
  (1, 'test-usage-' || gen_random_uuid()::text,
   (date_trunc('day', now() AT TIME ZONE 'utc') - interval '1 day') + interval '16:00',
   (date_trunc('day', now() AT TIME ZONE 'utc') - interval '1 day') + interval '16:20',
   1200, 0.07, 'USD')
ON CONFLICT (tenant_id, vapi_call_id) DO NOTHING;
```

Ou utiliser `scripts/insert_test_usage_tenant1.sql`.

### 3.4 Déclencher le job

```bash
curl -i -X POST "https://agent-production-c246.up.railway.app/api/admin/jobs/push-daily-usage" \
  -H "Authorization: Bearer ADMIN_API_TOKEN"
```

### 3.5 Attendu (logs Railway)

```
STRIPE_USAGE_PUSHED tenant_id=... date_utc=... minutes=...
```

### 3.6 Vérifier idempotence

- Relancer la même commande pour la même date
- Vérifier qu’aucun second push Stripe n’est effectué (skip car déjà `sent`)

```sql
SELECT tenant_id, date_utc, status, quantity_minutes, error_short
FROM stripe_usage_push_log
WHERE tenant_id = TENANT_ID
ORDER BY date_utc DESC
LIMIT 5;
```

**Attendu** : `status = 'sent'`, pas de doublon pour la même `(tenant_id, date_utc)`.

### 3.7 Verdict

| Étape | Résultat | Notes |
|-------|----------|-------|
| Données vapi_call_usage | ⬜ OK / ❌ | |
| Job push-daily-usage | ⬜ OK / ❌ | |
| Log STRIPE_USAGE_PUSHED | ⬜ OK / ❌ | |
| Idempotence (2e run skip) | ⬜ OK / ❌ | |
| stripe_usage_push_log status=sent | ⬜ OK / ❌ | |

**Verdict global TEST 3** : ⬜ ✅ / ❌

---

## TEST 4 — Upgrade suggestions (log-only)

### 4.1 Forcer un cas minutes élevé

Pour déclencher une suggestion upgrade (ex. Growth → Pro si minutes > seuil), insérer des données usage pour le mois en cours :

```sql
-- Vérifier minutes en période pour le tenant
-- (get_tenant_minutes_in_current_period lit vapi_call_usage sur current_period_start/end de tenant_billing)

-- Option : insérer des lignes avec ended_at dans la période courante
-- Ou modifier temporairement la logique pour tester
```

Alternative : appeler `run_upgrade_suggestions()` via un script Python (si endpoint dédié absent) :

```python
# Dans un shell Python (backend)
from backend.stripe_usage import run_upgrade_suggestions
run_upgrade_suggestions()
```

### 4.2 Déclencher via le job push-daily-usage

Le job `push_daily_usage_with_retry_48h` appelle automatiquement `run_upgrade_suggestions()` après le push. Donc un simple :

```bash
curl -X POST "https://agent-production-c246.up.railway.app/api/admin/jobs/push-daily-usage" \
  -H "Authorization: Bearer ADMIN_API_TOKEN"
```

exécute aussi les upgrade suggestions.

### 4.3 Attendu (logs)

Si un tenant a des minutes suffisantes pour justifier un upgrade :

```
UPGRADE_SUGGESTED tenant_id=... current_plan=growth suggested_plan=... minutes_used=... current_cost_eur=... suggested_cost_eur=... delta_eur=...
```

### 4.4 Verdict

| Étape | Résultat | Notes |
|-------|----------|-------|
| run_upgrade_suggestions exécuté | ⬜ OK / ❌ | |
| Log UPGRADE_SUGGESTED (si cas applicable) | ⬜ OK / ❌ / N/A | |

**Verdict global TEST 4** : ⬜ ✅ / ❌ / N/A

---

## TEST 5 (OPTIONNEL) — Meter Events (staging)

À exécuter **uniquement sur staging** avec :

- `STRIPE_USE_METER_EVENTS=true`
- `STRIPE_METER_EVENT_NAME=uwi.minutes`

### 5.1 Déclencher push

```bash
curl -X POST "https://STAGING_URL/api/admin/jobs/push-daily-usage" \
  -H "Authorization: Bearer ADMIN_API_TOKEN"
```

### 5.2 Attendu (logs)

```
STRIPE_METER_EVENT_PUSH_OK tenant_id=... minutes=... event_name=uwi.minutes
```

ou

```
STRIPE_USAGE_PUSHED tenant_id=... date_utc=... minutes=... (meter_events)
```

### 5.3 Vérification Stripe

Stripe Dashboard → **Billing** → **Facturation à l’usage** → **Compteurs** → « Minutes UWI » : vérifier réception des events.

### 5.4 Verdict

**Verdict global TEST 5** : ⬜ ✅ / ❌ / N/A (non exécuté)

---

## Checks transversaux

| Check | Statut |
|-------|--------|
| Aucun 4xx/5xx sur webhook lors des tests | ⬜ |
| Aucun "fallback first metered item" si env metered par plan configurée | ⬜ |
| Après paiement, tenant_billing cohérent | ⬜ |
| Erreurs documentées avec cause + fix | ⬜ |

---

## Troubleshooting

### Webhook 404 / non reçu

- Vérifier l’URL webhook dans Stripe Dashboard : `https://agent-production-c246.up.railway.app/api/stripe/webhook`
- Vérifier `STRIPE_WEBHOOK_SECRET` sur Railway
- Logs Railway : chercher `stripe webhook` ou `checkout.session.completed`

### stripe_metered_item_id vide

- Webhook a bien reçu `customer.subscription.updated` / `checkout.session.completed`
- Les `STRIPE_PRICE_METERED_*` sont définis et correspondent aux price_id des line_items Stripe
- Vérifier que le checkout inclut bien une ligne metered (Minutes)

### Push usage skip (STRIPE_USAGE_SKIP_NO_METERED_ITEM)

- `tenant_billing.stripe_metered_item_id` doit être rempli (voir TEST 2)
- Si vide : refaire un checkout ou vérifier le webhook

### Push usage failed (STRIPE_USAGE_PUSH_FAILED)

- Vérifier `stripe_subscription_id` et `stripe_metered_item_id` dans tenant_billing
- Vérifier que la subscription Stripe est `active`
- Logs : `error_short` dans `stripe_usage_push_log` pour le détail

### Idempotence : 2e run pousse quand même

- Vérifier que `try_acquire_usage_push` ne retourne pas True pour une ligne déjà `sent`
- Table `stripe_usage_push_log` : contrainte UNIQUE `(tenant_id, date_utc)` + `status='sent'` = pas de nouvel INSERT

---

## Résumé des verdicts

| Test | Verdict |
|------|---------|
| 1. Checkout Growth | ⬜ |
| 2. Webhook → tenant_billing | ⬜ |
| 3. Push usage + idempotence | ⬜ |
| 4. Upgrade suggestions | ⬜ |
| 5. Meter Events (staging) | ⬜ |

**Date** : _à remplir_  
**Exécuté par** : _à remplir_
