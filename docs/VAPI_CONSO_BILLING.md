# Conso & billing Vapi (source de vérité)

**Principe** : Vapi = source de vérité pour la **consommation** (minutes, coût, durée réelle). UWi = source de vérité pour le **fonctionnel** (RDV, transferts, events métier).

## Ce qu’on a en place

1. **Table `vapi_call_usage`** (migration `009_vapi_call_usage.sql`)
   - `tenant_id`, `vapi_call_id` (PK)
   - `started_at`, `ended_at`, `duration_sec`, `cost_usd`, `cost_currency`, `costs_json`
   - Remplie par le webhook **end-of-call-report**.

2. **Webhook** (`backend/routes/voice.py`)
   - Quand `message.type === "end-of-call-report"`, on appelle `ingest_end_of_call_report(payload)`.
   - On récupère `call` depuis `payload.call` ou `payload.message.call`.
   - On déduit le **tenant** via DID : `extract_to_number_from_vapi_payload` → `resolve_tenant_id_from_vocal_call` (même logique que pour persister le caller_id).
   - Champs utilisés : `call.id`, `call.startedAt`, `call.endedAt`, `call.duration`, `call.costs[]` (somme des `cost` en USD).

3. **Résolution tenant**
   - **DID** : numéro appelé (DID) → `tenant_routing` → `tenant_id`. C’est ce qu’on utilise aujourd’hui.
   - **Metadata** (futur) : si à l’init de l’appel tu envoies `tenant_id` en metadata côté Vapi, on pourra le lire dans le webhook et l’utiliser en priorité (fallback DID).

## Exemple JSON end-of-call-report

Pour adapter le parsing aux champs réels (noms, structure), il nous faut **un exemple** de payload reçu en webhook pour `message.type === "end-of-call-report"`.

À coller ici (ou dans un fichier `docs/sample_end_of_call_report.json`) :

- Un seul JSON d’event **end-of-call-report** (anonymiser numéros si besoin).
- Avec ça on pourra :
  - confirmer où sont `startedAt` / `endedAt` / `duration` / `costs`,
  - et brancher un fallback **metadata.tenant_id** si tu l’envoies.

D’après la doc Vapi :

- **Duration** : `call.endedAt - call.startedAt` (ou champ `duration` si présent).
- **Coûts** : `call.costs[]` avec pour chaque entrée `type`, `cost` (USD), et selon le type `minutes`, `provider`, `model`, etc.

## Suite prévue

- **Admin stats** (fait) : dans les endpoints `/api/admin/stats/*`, on utilise en priorité `vapi_call_usage` pour `minutes_total` et coût. Si la table est vide ou pas de données sur la fenêtre, fallback sur `call_sessions` (updated_at - started_at). Champs renvoyés : `minutes_total`, et si dispo `cost_usd_total` (global) / `cost_usd` (tenant).
- **Sync périodique** (cron 1–6 h) : appeler l’API Vapi (GET /call ou liste d’appels sur un intervalle), réconcilier les appels manquants (webhook down, etc.).
- **Page Billing** : afficher par tenant (30 j) minutes, coût estimé Vapi, top 10 tenants par coût.
- **Stripe** (à venir) : facturation par tenant (abonnement fixe et/ou surconsommation). La table `vapi_call_usage` servira de source pour l’usage reporté à Stripe (metered billing ou invoice items). Voir **`docs/STRIPE_BILLING.md`** pour le plan (schéma DB, webhooks, admin UI).

## Migration

En prod (Railway) :

```bash
# Exécuter la migration 009 (vapi_call_usage)
psql $DATABASE_URL -f migrations/009_vapi_call_usage.sql
```

Ou via ton script habituel (ex. `backend.run_migration`).
