# STRIPE – Checklist Railway (UWI)

Document de référence pour : refaire un environnement staging, onboard un dev, déboguer une facture, ou trancher « Stripe vs ton code ».

---

## 1. Variables d’environnement (Service API)

À définir sur le **service API Railway** (pas seulement au niveau Project) :

- `STRIPE_PRICE_BASE_STARTER`
- `STRIPE_PRICE_BASE_GROWTH`
- `STRIPE_PRICE_BASE_PRO`
- `STRIPE_PRICE_METERED_STARTER`
- `STRIPE_PRICE_METERED_GROWTH`
- `STRIPE_PRICE_METERED_PRO`
- `STRIPE_USE_METER_EVENTS=false` (par défaut)

⚠️ Les valeurs doivent être des `price_...`.  
Jamais `product_...`, `plan_...`, `mtr_...`.

Après modification → **redeploy** du service API.

---

## 2. Checkout Growth réel (prod/staging) — procédure complète

### 2.1 Pré-requis (30 s)

Sur le **service API** Railway (pas Project) :

- Les 6 `STRIPE_PRICE_*` sont définies
- `STRIPE_USE_METER_EVENTS=false`
- Service redéployé

### 2.2 Faire un checkout Growth

**Option A — Admin UI**  
Choisir un tenant test → « Souscrire Growth » → ouvrir l’URL Stripe Checkout.

**Option B — curl (recommandé)**  
Remplacer `TON_BACKEND`, `TENANT_ID`, `ADMIN_API_TOKEN` :

```bash
curl -X POST "https://TON_BACKEND/api/admin/tenants/TENANT_ID/stripe-checkout" \
  -H "Authorization: Bearer ADMIN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"plan_key":"growth"}'
```

✅ **Attendu :** JSON avec `checkout_url`.

### 2.3 Vérifier la page Stripe Checkout (avant paiement)

Tu dois voir **2 lignes** :

- **UWI Growth** → 149 €/mois  
- **Minutes (metered Growth)** → usage / compteur  

Une seule ligne → mapping `price_id` ou `line_items` incorrect (peu probable si les tests passent).

### 2.4 Paiement

- **Test mode Stripe :** carte test (ex. `4242...`)
- **Live :** paiement de test contrôlé (idéalement remboursable) sur un tenant sandbox

### 2.5 Vérifier que le webhook a rempli `stripe_metered_item_id`

**A) Logs Railway**  
Service API → Logs : chercher `checkout.session.completed` puis le sync subscription.

**B) Base Postgres**

```sql
SELECT tenant_id, plan_key, stripe_customer_id, stripe_subscription_id, stripe_metered_item_id, updated_at
FROM tenant_billing
WHERE tenant_id = 'TENANT_ID';
```

✅ **Attendu :**

- `plan_key = 'growth'`
- `stripe_subscription_id = sub_...`
- `stripe_metered_item_id = si_...` (non vide)

**Template à coller dans un ticket (après vérif) :**

```
Backend host :
Tenant_id :
plan_key demandé :
Checkout_url généré : OK / NOK
Résultat SQL (tenant_billing) :
Logs webhook : OK / NOK (event_id si dispo)
```

**Template à coller après le test (remplir les valeurs) :**

```
TENANT_ID: ...
plan_key: ...
stripe_customer_id: ...
stripe_subscription_id: ...
stripe_metered_item_id: ...
```

**Interprétation instantanée :**

| Cas | Valeurs | Action |
|-----|--------|--------|
| ✅ **OK** | `plan_key = growth`, `stripe_subscription_id = sub_...`, `stripe_metered_item_id = si_...` | Tout branché → passer à la vérif cron usage. |
| ❌ **Cas 1** | `stripe_subscription_id` vide | Webhook n’a pas traité `checkout.session.completed` (URL webhook, secret, ou event non reçu). |
| ❌ **Cas 2** | `stripe_subscription_id` rempli, `stripe_metered_item_id` vide | Webhook a sync la subscription mais n’a pas trouvé l’item metered : env `STRIPE_PRICE_METERED_*` manquantes / mauvais service Railway, ou mauvais `price_id` metered, ou line_items checkout sans metered (rare). |
| ❌ **Cas 3** | `plan_key` ≠ growth | Autre plan appelé ou mapping price→plan dans le webhook incomplet. |

Quand tu as tes valeurs (même masquées), les coller pour diagnostic précis.

### 2.6 Si `stripe_metered_item_id` est vide (plan de secours)

**Causes fréquentes :**

1. Env vars metered pas sur le bon service (API)
2. Un `STRIPE_PRICE_METERED_*` mal copié (price base au lieu de metered)
3. Webhook reçu mais impossible de récupérer la subscription (clé Stripe / permissions / version API)

**Où trouver les IDs dans Stripe :**

- **Stripe Dashboard** → **Customers** → client du tenant → **Subscriptions** → ouvrir la subscription → **Items** : repérer l’item metered → noter `si_...` (Subscription Item ID) et son **Price** (`price.id`).
- Comparer ce `price.id` à la valeur de `STRIPE_PRICE_METERED_GROWTH` en env : ils doivent être identiques. Sinon, corriger l’env ou le mapping côté webhook.

Pour diagnostic : indiquer l’environnement (staging/test mode vs live) et le résultat de la requête SQL (tenant_id masqué si besoin).

### 2.7 Diagnostic : erreur « metered_price_id / STRIPE_PRICE_METERED_* required » (curl checkout)

Si toutes les variables sont présentes dans l’UI Railway mais le curl renvoie encore cette erreur, 3 causes probables :

**1) Pas de Redeploy**  
Le process tourne avec l’ancien env.  
→ Railway → Service API → **Redeploy** → relancer le curl.

**2) Mauvais service**  
Les vars sont sur un autre service (worker, cron).  
→ Railway → Service qui sert `https://agent-production-c246.up.railway.app` → Settings → vérifier que c’est bien celui où les vars sont définies.

**3) Parsing / code pas à jour**  
Espace, guillemets, casse, ou code déployé pas à jour.

- **A) Contournement immédiat**  
  Ajouter aussi la variable legacy (même valeur que le metered Growth) :  
  `STRIPE_PRICE_METERED_MINUTES=price_1T5mYBBRn0iGDwpub4RxKG4l`  
  Puis **Redeploy** → relancer le curl.  
  Si ça marche : le code en prod ne lit pas `STRIPE_PRICE_METERED_GROWTH` (déploiement / commit / container pas à jour).

- **B) Vérifier les logs**  
  Dans les logs Railway, chercher le warning :  
  `STRIPE_CHECKOUT_LEGACY_METERED ...`  
  S’il n’apparaît pas alors que la legacy est définie → code prod pas à jour.

**Pour diagnostic précis :** coller ici le **JSON complet** renvoyé par le curl + **une ligne de log Railway** autour de l’appel. On en déduit : mauvais service / pas redeploy / code pas à jour / variable mal lue.

---

## 3. Vérification Webhook (rappel)

Après paiement réussi, la requête ci-dessus (section 2.5 B) doit montrer `stripe_metered_item_id` non vide. Sinon → section 2.6.

---

## 4. Cron Usage

**Logs attendus :**

```
STRIPE_USAGE_PUSHED tenant_id=... date_utc=... minutes=...
```

**Idempotence (pas de double push) :**

```sql
SELECT tenant_id, date_utc, status
FROM stripe_usage_push_log
WHERE tenant_id = 'X'
ORDER BY date_utc DESC;
```

**Attendu :**

- `status = 'sent'` pour les dates poussées
- Pas de doublon pour la même `(tenant_id, date_utc)`

---

## 5. Upgrade Suggestions (V1)

Logs possibles après le cron :

```
UPGRADE_SUGGESTED tenant_id=... current_plan=... suggested_plan=... delta_eur=...
```

Aucune action Stripe automatique en V1 (log uniquement).

---

## 6. (Plus tard) Test Meter Events

Pour tester le push via Billing Meter Events :

1. Sur staging ou un tenant test : `STRIPE_USE_METER_EVENTS=true`
2. (Optionnel) `STRIPE_METER_EVENT_NAME=uwi.minutes`
3. Déclencher un push usage (cron ou endpoint admin).
4. Dans Stripe : **Billing → Facturation à l’usage → Compteurs** → « Minutes UWI » : vérifier que les événements arrivent.

---

## Tests Stripe (local)

En local, après `pip install -r requirements.txt` (ou venv activé) :

| Objectif | Commande |
|----------|----------|
| Tests usage uniquement | `pytest tests/test_stripe_usage.py -v` |
| Tests checkout uniquement | `pytest tests/test_stripe_checkout.py -v` |
| Les deux fichiers | `pytest tests/test_stripe_usage.py tests/test_stripe_checkout.py -v` |
| Tous les tests dont le nom contient "stripe" | `pytest -k stripe -v` |
| Un seul test | `pytest tests/test_stripe_checkout.py::test_stripe_checkout_growth_uses_plan_specific_prices -v` |

Avec `python3` explicite : `python3 -m pytest tests/test_stripe_usage.py -v`.

Si les tests re-cassent en local (import bcrypt / email_validator) : `pip3 install -r requirements.txt`.

---

## Bonne pratique supplémentaire

En bas de ce fichier (ou dans un runbook), maintenir :

- **Dernière validation prod :** `YYYY-MM-DD`
- **Stripe API version utilisée :** `xxxx-xx-xx`

Ça évite les surprises quand Stripe change un comportement.

---

*Dernière validation prod : _à remplir_*  
*Stripe API version utilisée : _à remplir_*
