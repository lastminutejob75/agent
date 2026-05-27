# Intégrations externes — Index

Vue d'ensemble des trois intégrations principales du backend UWI : **Vapi** (vocal IA), **Stripe** (paiement), **Twilio** (téléphonie / SMS / WhatsApp).

Chaque intégration dispose d'une **doc de référence** (synthèse + diagnostic) et de docs **spécialisées** pour les sujets pointus (prompts, billing, STT, etc.).

---

## Vapi — Assistant vocal IA

> 📘 **Référence : [`INTEGRATION_VAPI.md`](./INTEGRATION_VAPI.md)**

| Sujet | Doc |
|---|---|
| Setup FR | [`VAPI_FRANCAIS_CHECKLIST.md`](./VAPI_FRANCAIS_CHECKLIST.md) |
| Schéma du `function_tool` | [`VAPI_TOOL_SCHEMA.md`](./VAPI_TOOL_SCHEMA.md) |
| Prompt système assistant | [`VAPI_PROMPT_ASSISTANT.md`](./VAPI_PROMPT_ASSISTANT.md) |
| Prompt booking | [`VAPI_PROMPT_BOOKING_STATUS.md`](./VAPI_PROMPT_BOOKING_STATUS.md) |
| STT Deepgram Nova-3 FR | [`VAPI_STT_NOVA3_FR.md`](./VAPI_STT_NOVA3_FR.md) |
| Fix STT | [`VAPI_STT_FIX.md`](./VAPI_STT_FIX.md) |
| Diagnostic silence | [`VAPI_SILENCE_DIAGNOSTIC.md`](./VAPI_SILENCE_DIAGNOSTIC.md) |
| Caller ID | [`VAPI_CALLER_ID.md`](./VAPI_CALLER_ID.md) |
| Consommation / billing | [`VAPI_CONSO_BILLING.md`](./VAPI_CONSO_BILLING.md) |
| Dashboard non connecté | [`DASHBOARD_VAPI_POURQUOI_PAS_CONNECTE.md`](./DASHBOARD_VAPI_POURQUOI_PAS_CONNECTE.md) |
| Vérif stats Vapi | [`DASHBOARD_STATS_VAPI_VERIFICATION.md`](./DASHBOARD_STATS_VAPI_VERIFICATION.md) |

---

## Stripe — Paiement & facturation

> 📘 **Référence : [`INTEGRATION_STRIPE.md`](./INTEGRATION_STRIPE.md)**

| Sujet | Doc |
|---|---|
| Fondations | [`STRIPE_FOUNDATION.md`](./STRIPE_FOUNDATION.md) |
| Billing détaillé | [`STRIPE_BILLING.md`](./STRIPE_BILLING.md) |
| Installation pas-à-pas | [`STRIPE_UWIAPP_INSTALL.md`](./STRIPE_UWIAPP_INSTALL.md) |
| Variables Railway | [`STRIPE_CHECKLIST_RAILWAY.md`](./STRIPE_CHECKLIST_RAILWAY.md) |
| Tests E2E | [`STRIPE_E2E_TESTS.md`](./STRIPE_E2E_TESTS.md) |
| Audit pricing | [`AUDIT_STRIPE_UWI_PRICING.md`](./AUDIT_STRIPE_UWI_PRICING.md) |
| Roadmap monétisation | [`ROADMAP_MONETISATION.md`](./ROADMAP_MONETISATION.md) |
| Trouver URL Stripe sur Railway | [`RAILWAY_TROUVER_URL_STRIPE.md`](./RAILWAY_TROUVER_URL_STRIPE.md) |

---

## Twilio — Téléphonie / SMS / WhatsApp

> 📘 **Référence : [`INTEGRATION_TWILIO.md`](./INTEGRATION_TWILIO.md)**

Twilio fournit les numéros DID et les canaux SMS/WhatsApp. Le traitement vocal est délégué à Vapi (BYO).

| Sujet | Doc |
|---|---|
| Routing tenant (DID → tenant_id) | [`TENANT_ROUTING.md`](./TENANT_ROUTING.md) |
| Rapports quotidiens (canaux SMS/WhatsApp) | [`RAPPORT_QUOTIDIEN_IVR.md`](./RAPPORT_QUOTIDIEN_IVR.md) |

> Pas de doc dédiée historiquement — la doc de référence ci-dessus consolide tout.

---

## Provisioning d'un tenant — vue d'ensemble

Le flow `POST /api/admin/tenants/create` (cf. [`API_ADMIN_ONBOARDING.md`](./API_ADMIN_ONBOARDING.md)) orchestre les 3 intégrations dans cet ordre :

```
1. PG          : tenant + tenant_config + user
2. Vapi        : create_vapi_assistant → vapi_assistant_id
3. Twilio/Vapi : assign_twilio_to_vapi (PATCH phone-number/{id})
                 + pg_add_routing("vocal", number, tenant_id)
4. Stripe      : Customer.create + Subscription.create (trial 30j)

Rollback en cas d'erreur (best-effort, certains items à nettoyer manuellement).
```

> Voir [`INTEGRATION_VAPI.md`](./INTEGRATION_VAPI.md), [`INTEGRATION_TWILIO.md`](./INTEGRATION_TWILIO.md) et [`INTEGRATION_STRIPE.md`](./INTEGRATION_STRIPE.md) pour les détails de chaque étape.

---

## Sécurité — résumé

| Intégration | Auth backend | Webhooks | Frontend |
|---|---|---|---|
| Vapi | `VAPI_API_KEY` (env) | `/api/vapi/webhook` — signature TODO ⚠️ | `VITE_VAPI_PUBLIC_KEY` (clé publique) |
| Stripe | `STRIPE_SECRET_KEY` (env) | `/api/stripe/webhook` — signature ✅ | `VITE_STRIPE_PUBLISHABLE_KEY` (clé publique) |
| Twilio | `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN` (env) | `/api/whatsapp/webhook` — signature HMAC ✅ (custom) | aucune variable frontend |

> Voir [`AUDIT_SECURITE_2026-05.md`](./AUDIT_SECURITE_2026-05.md) pour l'audit complet.

---

## Mode démo

Quand `ADMIN_DEMO_MODE=true` :
- Vapi : pas d'appels API réels (router `admin_demo` intercepte les endpoints admin).
- Stripe : pas de Customer/Subscription créés (middleware bloque les writes admin).
- Twilio : `GET /api/admin/twilio/numbers` retourne 5 numéros factices.

> Voir [`ADMIN_DEMO_MODE.md`](./ADMIN_DEMO_MODE.md).

---

## Voir aussi

- [`AUDIT_SECURITE_2026-05.md`](./AUDIT_SECURITE_2026-05.md) — audit sécurité complet (Vapi/Stripe/Twilio inclus)
- [`TESTS_BACKEND.md`](./TESTS_BACKEND.md) — tests unitaires backend
- [`API_ADMIN_ONBOARDING.md`](./API_ADMIN_ONBOARDING.md) — provisioning tenant complet
- [`ADMIN_DEMO_MODE.md`](./ADMIN_DEMO_MODE.md) — mode démo backend
- [`RAILWAY_VARIABLES.md`](./RAILWAY_VARIABLES.md) — toutes les variables d'env Railway
