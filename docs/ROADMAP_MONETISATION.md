# Roadmap Monétisation (2 semaines)

Objectif : **lier l’usage Vapi à la facturation Stripe** et **bloquer automatiquement** en cas d’impayé ou de dépassement de quota, sans empiler de features hors scope.

---

## Décisions finales (business + architecture)

| Décision | Choix |
|----------|--------|
| **Stripe billing** | **Metered billing (Usage Records)** — pas d’Invoice Items en fin de mois. Stripe gère prorata, preview facture, facturation auto. |
| **Règle quota** | **80 %** = alerte uniquement (email + badge admin). **≥ 100 %** = **blocage automatique (hard suspension)**. Coût Vapi réel → pas de dépassement sans facturation. |
| **Où appliquer le blocage quota** | **À l’entrée d’appel** (check dans `_compute_voice_response_sync`), pas de job quotidien. Immédiat, pas de race condition, pas de dépassement pendant la journée. |

---

## Contexte actuel

- **Source de vérité usage** : `vapi_call_usage` (minutes, coût, par tenant, mois UTC).
- **Quotas** : `billing_plans` + `custom_included_minutes_month`, résolution plan par tenant, endpoint `GET .../quota?month=`.
- **Stripe** : `tenant_billing.stripe_customer_id` créé à la main (admin), webhooks subscription / invoice déjà branchés (sync `billing_status`, `plan_key`, etc.).
- **Blocage** : suspension manuelle ou via webhook `past_due` ; pas encore de blocage automatique sur quota dépassé.

---

## Structure Stripe recommandée

- **Product** : `UWi Voice`
- **Prices** :
  - Abo mensuel fixe (base) — récurrent.
  - **Usage metered (minutes)** :
    - `unit_amount` = prix par minute (cents)
    - `billing_scheme` = `per_unit`
    - `usage_type` = `metered`
    - `aggregate_usage` = `sum`
- **Usage Records** : `quantity` = minutes, `timestamp` = fin de journée UTC (ex. 23:59 UTC pour la journée concernée).

---

## Architecture technique

### 1. Push usage → Stripe

- **Module** : `backend/stripe_usage.py`
- **Fonction** : `push_daily_usage_to_stripe(date_utc: date)`
  - Agrège `vapi_call_usage` par `tenant_id` sur la **journée UTC** donnée.
  - Pour chaque tenant actif (avec `stripe_customer_id` et subscription avec item metered) : `Stripe.UsageRecord.create(subscription_item_id=..., quantity=minutes, timestamp=end_of_day_utc)`.
- **Fréquence** : **cron 01:00 UTC** (journée précédente).

### 2. Blocage quota (à l’entrée d’appel)

- **Point d’entrée** : `backend/routes/voice.py` → `_compute_voice_response_sync`.
- **Logique** : juste après le check suspension existant (`get_tenant_suspension`) :
  - Récupérer le **quota snapshot du mois** (used_minutes vs included_minutes — même logique que `GET .../quota`).
  - Si **usage ≥ included** (≥ 100 %) : appliquer **suspension hard** (ex. `set_tenant_suspended(tenant_id, reason="quota_exceeded")`) puis retourner la même phrase que pour un tenant suspendu (déjà gérée en tête de fonction).
- **Réutilisation** : `billing_pg.get_tenant_suspension`, `billing_pg.set_tenant_suspended` ; calcul quota = même logique que `admin_get_tenant_quota` / `_get_quota_used_minutes` + `get_plan_included_minutes` + override custom.

### 3. Alerte 80 %

- **80 %** : alerte uniquement (email + badge admin “Quota risk”), **pas de blocage**.
- **Badge admin** : déjà fourni par `GET /api/admin/stats/operations-snapshot` → `quota.over_80`.
- **Email** : job quotidien `run_quota_alerts_80()` ; cible : 80 ≤ usage_pct < 100 ; **anti-spam** : 1 email par tenant par mois (table `quota_alert_log`).
- **Event log** : `log_auth_event(tenant_id, "", "quota_alert_80_sent", month_utc)`.
- **Cron** : appeler `POST /api/admin/jobs/quota-alerts-80` (auth admin) 1×/jour, ou `run_quota_alerts_80()` en script.

---

## Ordre d’implémentation (recommandé)

1. **Choisir metered billing** ✅ (validé)
2. **Créer Product + Prices Stripe** (UWi Voice, prix mensuel fixe + price metered minutes).
3. **Implémenter push daily usage** : `backend/stripe_usage.py` + `push_daily_usage_to_stripe(date_utc)` — **sans** blocage quota au début.
4. **Tester facturation Stripe** en mode test (tenant test avec subscription + usage).
5. **Ajouter blocage quota ≥ 100 %** : check dans `_compute_voice_response_sync` + suspension si dépassement.
6. **Ajouter alerte 80 %** : email + badge admin.

---

## Priorités (livrables)

| Priorité | Objectif | Livrable |
|----------|----------|----------|
| **1** | Lier usage Vapi → Stripe | Module `stripe_usage.py`, `push_daily_usage_to_stripe`, cron 01:00 UTC. Product/Price metered créés dans Stripe. |
| **2** | Blocage automatique | Check quota à l’entrée d’appel (`_compute_voice_response_sync`) ; si usage ≥ included → hard suspension « quota ». Impayé déjà géré par webhooks. |
| **3** | Seuil 80 % | Alerte seule (email + badge admin), pas de blocage. |

---

## Ce qu’on ne fait pas dans ces 2 semaines

- Refonte UX dashboard client.
- Migration JWT client vers cookie HttpOnly.
- Audit log détaillé (impersonation).
- Page « Ma facturation » côté client.
- Rate limiting avancé.

→ Backlog **Solidifier** / **Expérience client**.

---

**Stripe Checkout (création abonnement)**  
- `POST /api/admin/tenants/{id}/stripe-checkout` (body : `plan_key`, optionnel `trial_days`) → `checkout_url`.  
- Env : `STRIPE_CHECKOUT_SUCCESS_URL`, `STRIPE_CHECKOUT_CANCEL_URL`, `STRIPE_PRICE_BASE_STARTER/PRO/BUSINESS`, `STRIPE_PRICE_METERED_MINUTES`.  
- UI admin : bloc « Démarrer abonnement » (plan + Générer lien Checkout, Copier, Ouvrir) ; désactivé si `billing_status` = active/trialing.  
- Voir `docs/STRIPE_FOUNDATION.md` pour la liste des variables.

---

## Backlog (hors 2 semaines)

- **Solidifier** : cookie HttpOnly pour JWT client, rate limiting, audit log centralisé.
- **Expérience client** : alertes quota (email 80 % / 100 %), page « Ma facturation » client.

---

## 3 micro-améliorations prod-grade (optionnel, très rentables)

1. **stripe_usage_push_log : statut**  
   Ajouter colonnes `status` (`pending` \| `sent` \| `failed`) + `error_short` (texte court). Avantage : diagnostic « pourquoi ça ne push pas » sans fouiller les logs. Aujourd’hui : INSERT puis DELETE si échec (retry OK).

2. **stripe_metered_item_id : remplir automatiquement**  
   S’assurer que les webhooks `customer.subscription.updated` (et `subscription.created`) récupèrent le subscription_item metered et le stockent dans `tenant_billing.stripe_metered_item_id`. Sinon le push usage ne peut pas appeler Stripe. **Config** : définir `STRIPE_METERED_PRICE_ID` en env (test + live) dès que le price minutes est créé → voir `docs/STRIPE_FOUNDATION.md`.

3. **Cron push daily : retry 48h**  
   Si le cron échoue (Stripe down), au prochain run : pousser « hier » et « avant-hier » si pas déjà dans `stripe_usage_push_log`. Rattrapage simple sans queue.

---

## 4 points à verrouiller absolument

### 1) Idempotence du push Stripe (éviter double facturation)

Ne jamais envoyer 2 fois l’usage d’un même jour pour un même tenant.

**Table PG à ajouter : `stripe_usage_push_log`**

| Colonne | Type | Description |
|--------|------|--------------|
| `tenant_id` | int | FK tenant |
| `date_utc` | date | YYYY-MM-DD (jour poussé) |
| `quantity_minutes` | int | Minutes envoyées |
| `stripe_usage_record_id` | text (optionnel) | Id Stripe si besoin |
| `pushed_at` | timestamptz | Heure du push |

**Contrainte** : `UNIQUE (tenant_id, date_utc)`.

**Logique** : avant d’envoyer un UsageRecord, faire un `INSERT` (ou upsert “acquire”) sur cette table ; si conflit (déjà une ligne pour ce tenant + date) → **skip** (ne pas appeler Stripe).

### 2) Mapping tenant → subscription item metered

Stripe exige le **subscription_item** (item metered) pour `UsageRecord.create`, pas seulement `subscription_id`.

**Colonne à ajouter dans `tenant_billing`** : `stripe_metered_item_id` (ou `stripe_usage_item_id`).

- Récupérée et stockée lors du sync subscription (webhook `subscription.updated` ou `subscription.created`).
- Sans ça, impossible de savoir quel item utiliser pour le push.

### 3) Conversion minutes : règle d’arrondi

- **Recommandation** : **somme des `duration_sec` sur la journée**, puis **`ceil(somme_sec / 60)`** pour le jour.
- Évite les arrondis par appel qui faussent le total.
- Stripe `quantity` : souvent **entier** (selon le Price) → utiliser un `int(minutes)`.

### 4) Quota check : cas `included_minutes_month = 0`

Si `included == 0` (plan non configuré / gratuit sans quota), un check `used >= included` bloquerait tout.

**Décision** : **ne pas bloquer si `included == 0`** ; logger `quota not configured` et laisser passer.

---

## Pseudo-code prod-grade : `push_daily_usage_to_stripe(date_utc)`

```python
def push_daily_usage_to_stripe(date_utc: date):
    # date_utc = jour à pousser (ex: yesterday UTC)
    # window: [date_utc 00:00:00, date_utc+1 00:00:00)

    # 1) Agréger usage par tenant pour ce jour
    rows = pg.query("""
      SELECT tenant_id,
             CEIL(SUM(duration_sec)::numeric / 60.0) AS minutes
      FROM vapi_call_usage
      WHERE ended_at >= %(start)s AND ended_at < %(end)s
      GROUP BY tenant_id
      HAVING SUM(duration_sec) > 0
    """, start=..., end=...)

    for r in rows:
      tenant_id = r.tenant_id
      minutes = int(r.minutes)

      # 2) Vérifier mapping billing
      billing = get_tenant_billing(tenant_id)
      if not billing or not billing.get("stripe_subscription_id") or not billing.get("stripe_metered_item_id"):
          log("STRIPE_USAGE_SKIP_NO_SUB", tenant_id=tenant_id)
          continue

      # 3) Idempotence : acquérir le droit de push (INSERT unique tenant_id, date_utc)
      acquired = try_acquire_usage_push(tenant_id, date_utc)
      if not acquired:
          continue

      # 4) Push UsageRecord (action="set" + 1 push/jour = safe)
      stripe.UsageRecord.create(
          subscription_item=billing["stripe_metered_item_id"],
          quantity=minutes,
          timestamp=end_of_day_utc_timestamp(date_utc),  # ex. 23:59:59 UTC
          action="set"
      )

      mark_usage_push_success(tenant_id, date_utc, quantity_minutes=minutes)
```

- **action** : `"set"` (valeur fixée à ce timestamp) + idempotence = 1 push/jour, pas de double facturation. Ne pas utiliser `increment` sans garde-fou.

---

## Diff précis : quota check dans `_compute_voice_response_sync`

**Emplacement** : juste après `get_tenant_suspension()`, avant toute logique session/engine.

```python
# Déjà en place :
susp = get_tenant_suspension(tenant_id)
if susp.is_suspended:
    return suspended_message(...)

# À ajouter :
quota = get_quota_snapshot_month(tenant_id, month_utc=now_utc_month())
if quota.included_minutes_month > 0 and quota.used_minutes_month >= quota.included_minutes_month:
    set_tenant_suspended(tenant_id, reason="quota_exceeded", mode="hard")
    log_event("TENANT_SUSPENDED_QUOTA_EXCEEDED", tenant_id=tenant_id)
    return suspended_message(...)
# Si included == 0 : ne pas bloquer (log "quota not configured" si besoin)
```

---

## Tests minimaux (en place)

| Test | Objectif |
|------|----------|
| **Push usage idempotent** | `test_push_daily_usage_idempotent_second_run_skips_stripe_call` : 1er run try_acquire True → UsageRecord.create appelé ; 2e run try_acquire False → create pas rappelé. |
| **Quota block** | `included=100`, `used=100` → suspension hard + message suspendu, engine non appelé. |
| **included=0** | `included=0` → pas de blocage, pas de suspension, engine appelé. |
| **Déjà suspendu** | Si `get_tenant_suspension` renvoie déjà suspendu → quota check jamais appelé, `set_tenant_suspended` pas rappelé. |

---

## Références code

- **Suspension** : `backend/billing_pg.get_tenant_suspension`, `set_tenant_suspended` ; `backend/routes/voice._compute_voice_response_sync` (début : check suspension puis engine).
- **Quota** : `backend/routes/admin.py` (quota, `_get_quota_used_minutes`), `backend/billing_pg.get_plan_included_minutes`, `custom_included_minutes_month`.
- **Usage** : table `vapi_call_usage` ; agrégation par jour UTC pour Stripe, par mois UTC pour quota.
