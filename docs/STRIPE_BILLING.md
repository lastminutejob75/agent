# Intégration Stripe (à venir)

**Contexte** : La brique conso est en place (`vapi_call_usage` = source de vérité minutes/coût). Stripe viendra s’appuyer dessus pour la facturation par tenant.

**Fondation (en place, sans prix)** : voir **`docs/STRIPE_FOUNDATION.md`** — DB `tenant_billing`, webhooks, admin « Créer customer », usage 7j/30j + usage mensuel.

---

## 1. Schéma DB (tenant_billing en place)

Table **tenant_billing** (migration 011) :

| Champ | Type | Rôle |
|-------|------|------|
| `stripe_customer_id` | TEXT | ID Stripe Customer |
| `stripe_subscription_id` | TEXT | ID Subscription (si abo) |
| `plan` | TEXT | starter / pro / … |
| `billing_status` | TEXT | active / past_due / canceled / trialing |
| `billing_anchor_day` | INT | optionnel, jour de facturation |
| `trial_ends_at` | TIMESTAMPTZ | optionnel |

---

## 2. Deux modèles possibles

### A) Abonnement fixe (simple)

- Subscription Stripe mensuelle fixe.
- Admin : statut, prochaine facture, montant.
- Conso Vapi = monitoring + base pour upsell.

### B) Abonnement + surconsommation (recommandé)

- Base mensuelle (ex. X minutes incluses).
- Surconsommation facturée (minutes / appels).
- **`vapi_call_usage`** alimente l’usage Stripe :
  - **Metered billing** (report usage sur un Price), ou
  - **Invoice items** (lignes d’usage sur la prochaine facture).

---

## 3. Pattern Stripe “pro”

1. **Stripe** : créer des **Prices** (abonnement récurrent + optionnel usage/metered).
2. **Par tenant** : créer **Customer** puis **Subscription** (liée aux Prices).
3. **Usage** : quotidien (ou horaire), agréger `vapi_call_usage` sur la période et **report usage** à Stripe (ou ajouter des invoice items).
4. Stripe gère factures, paiement, relances.

---

## 4. Webhooks Stripe indispensables

| Event | Action côté app |
|-------|------------------|
| `checkout.session.completed` | Lier customer/subscription au tenant, mettre à jour DB |
| `invoice.paid` | Mettre à jour statut / historique si besoin |
| `invoice.payment_failed` | Mettre à jour `billing_status` (ex. past_due), optionnel : notifier / auto-suspendre |
| `customer.subscription.updated` | Sync `billing_status`, `plan`, dates |
| `customer.subscription.deleted` | Marquer résilié, `billing_status = canceled` |

---

## 5. Admin UI à prévoir

- **Billing global** : top coûts, MRR, past_due, lien vers Stripe Dashboard.
- **Fiche tenant** : section “Stripe” (customer_id, subscription_id, statut, lien Stripe).
- Actions : “Créer abonnement” / “Résilier” / “Sync statut”.

---

## 6. Lien avec la conso

- **Source de vérité usage** : table **`vapi_call_usage`** (migration 009, webhook end-of-call-report).
- Agrégations déjà dispo : `minutes_total`, `cost_usd_total` (global ou par tenant, fenêtre configurable).
- Lors de l’implé Stripe : job périodique (cron) qui lit `vapi_call_usage` par tenant sur la période de facturation courante et envoie l’usage à Stripe (metered ou invoice items).

---

## 7. Prochaine étape (quand tu es prêt)

Décision à trancher :

- **A** – Abonnement fixe uniquement.
- **B** – Abonnement + surconsommation (minutes Vapi).

Une fois le choix fait + plans définis (prix, minutes incluses, règle de surcoût), on pourra :

1. Ajouter la migration DB (colonnes billing / table `tenant_billing`).
2. Implémenter les endpoints admin Stripe (create customer, create subscription, sync).
3. Implémenter la logique **usage → Stripe** basée sur `vapi_call_usage`.
4. Ajouter la page admin “Billing” et la section Stripe dans la fiche tenant.

---

*Doc créée pour ne pas oublier l’arrivée de Stripe ; à mettre à jour au moment de l’implé.*
