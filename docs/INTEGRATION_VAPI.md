# Intégration Vapi

Guide de référence technique pour l'intégration Vapi (assistant vocal IA). Synthétise tout ce qui est nécessaire pour comprendre, configurer, déboguer et étendre l'intégration.

> Pour les sujets pointus, voir les docs spécialisées en bas de page (STT, prompts, billing, etc.).

---

## Vue d'ensemble

UWI utilise Vapi comme **assistant vocal téléphonique**. Chaque tenant dispose d'un assistant Vapi propre :
- Un numéro Twilio (BYO importé dans Vapi) reçoit les appels.
- Vapi orchestre la conversation (STT Deepgram Nova-3 FR + LLM OpenAI + TTS Azure).
- Le **custom LLM** est hébergé chez nous (`POST /api/vapi/chat/completions`) → permet une logique métier (FSM, FAQ, anti-loop).
- Un **function tool unique** (`function_tool`) expose 6+ actions : `get_slots`, `validate_contact`, `book`, `cancel`, `modify`, `transfer`, `faq`.
- Webhooks Vapi → `POST /api/vapi/webhook` (statut appel, transcripts, end-of-call-report, tool-calls).

```
Appelant ──► Twilio (DID) ──► Vapi (assistant tenant) ──┬─► Custom LLM /api/vapi/chat/completions
                                                        ├─► Function tool /api/vapi/tool
                                                        └─► Webhook /api/vapi/webhook (events)
```

---

## Variables d'environnement

### Backend (`backend/`)

| Variable | Obligatoire | Défaut | Rôle |
|---|---|---|---|
| `VAPI_API_KEY` | ✅ | — | Clé secrète API Vapi (création/maj assistants, phone-number, tools) |
| `VAPI_ASSISTANT_ID` | optionnel | — | Assistant fallback si pas de mapping tenant |
| `VAPI_FUNCTION_TOOL_ID` | ✅ (provisioning) | — | ID du tool partagé `function_tool` (un seul pour toute la plateforme) |
| `VAPI_WEBHOOK_SECRET` | ✅ | — | Secret envoyé à Vapi (`server.secret`). **Utilisé pour vérifier la signature des webhooks entrants** (cf. section [Sécurité — Vérification des webhooks](#sécurité--vérification-des-webhooks-entrants)) |
| `VAPI_REQUIRE_SIGNATURE` | optionnel | `false` | Si `true` : rejette les webhooks Vapi non signés correctement (401). Si `false` : log un warning et accepte (mode migration douce). |
| `VAPI_SIGNATURE_DISABLED` | optionnel | `false` | Skip total de la vérification (uniquement dev/CI). Override `VAPI_REQUIRE_SIGNATURE`. |
| `VAPI_WEBHOOK_CREDENTIAL_ID` | optionnel | — | Alternative à `WEBHOOK_SECRET` (priorité sur ce dernier) |
| `VAPI_PUBLIC_BACKEND_URL` | ✅ | — | URL publique HTTPS du backend (utilisée pour `server.url` côté Vapi) |
| `PUBLIC_API_BASE_URL` / `API_BASE_URL` / `APP_BASE_URL` | fallback | — | Fallbacks si `VAPI_PUBLIC_BACKEND_URL` absent |
| `VAPI_INTERRUPTION_ENABLED` | optionnel | `true` | Permet à l'utilisateur d'interrompre l'assistant |
| `VAPI_ENDPOINTING_MS` | optionnel | `200` | Silence (ms) avant fin de tour utilisateur |
| `VAPI_FILLER_INJECTION` | optionnel | `false` | Injection automatique de "hum, bien sûr…" |
| `VAPI_DEBUG_TEST_AUDIO` | optionnel | `false` | Active routes de debug audio |

### Frontend (`landing/src/`)

| Variable | Rôle |
|---|---|
| `VITE_VAPI_PUBLIC_KEY` | Clé publique Vapi pour le widget vocal sur les pages publiques (`PagePubliquePraticienUWI.jsx`) |

---

## Architecture

### Fichiers principaux

| Fichier | Rôle |
|---|---|
| `backend/vapi_utils.py` | SDK helpers : `create_vapi_assistant`, `patch_vapi_assistant_*`, `assign_twilio_to_vapi`, schéma `function_tool` |
| `backend/routes/voice.py` | Routeur `/api/vapi/*` : webhook, tool, chat/completions, test |
| `backend/vapi_tool_handlers.py` | Implémentation des actions du tool (book, get_slots, etc.) |
| `backend/vapi_live_transfer.py` | Transfert humain en cours d'appel |
| `backend/vapi_usage_pg.py` | Persistence cycle de vie + usage (durée, coût) |
| `landing/src/lib/adminApi.js` | Wrapper REST côté admin (`updateTenantVapi`, etc.) |

### Endpoints `/api/vapi/*`

| Méthode | Path | Rôle | Auth |
|---|---|---|---|
| POST | `/api/vapi/webhook` | Webhook événements Vapi (status, transcript, tool-calls, end-of-call-report) | **Signature HMAC vérifiée** (`X-Vapi-Secret` ou `X-Vapi-Signature`) — cf. [Sécurité](#sécurité--vérification-des-webhooks-entrants) |
| POST | `/api/vapi/tool` | Handler HTTP du `function_tool` | **Signature HMAC vérifiée** (idem webhook) |
| POST | `/api/vapi/chat/completions` | Custom LLM (JSON ou SSE si `stream=true`) | Public |
| GET | `/api/vapi/_health` | Healthcheck | Public |
| GET | `/api/vapi/health` | Healthcheck (alias) | Public |
| GET | `/api/vapi/test-calendar` | Diagnostic Google Calendar | **Admin OU `ENABLE_DEBUG_ENDPOINTS=true`** |
| GET | `/api/vapi/test` | Test moteur (`handle_message`) | **Admin OU `ENABLE_DEBUG_ENDPOINTS=true`** |

> Les endpoints `/debug/vapi-*` (sync FAQ, clone tool, patch prompt, etc.) sont protégés par le middleware `debug_endpoints_guard` (cf. [`AUDIT_SECURITE_2026-05.md`](./AUDIT_SECURITE_2026-05.md)).

---

## Provisioning d'assistant

Lors de la création d'un tenant via `POST /api/admin/tenants/create` (voir [`API_ADMIN_ONBOARDING.md`](./API_ADMIN_ONBOARDING.md)) :

1. **Création tenant PG** (tenant + tenant_config + user admin).
2. **`create_vapi_assistant(...)`** (`backend/vapi_utils.py:425`) → `POST https://api.vapi.ai/assistant`
   - **Voice** : Azure Neural FR via `ASSISTANT_VOICES[assistant_id]`.
   - **Model** : `openai/gpt-4o-mini`, system prompt = secteur (`SECTOR_PROMPTS`) + FAQ tenant.
   - **Tools** : `model.toolIds = [VAPI_FUNCTION_TOOL_ID]` (le tool est partagé).
   - **Server** : `url = {VAPI_PUBLIC_BACKEND_URL}/api/vapi/webhook`, `secret` ou `credentialId`.
   - **Metadata** : `{tenant_id, assistant_id}`.
3. **PG update** : `pg_update_tenant_params(tid, {"vapi_assistant_id": vapi_id})`.
4. **Si numéro Twilio fourni** : `assign_twilio_to_vapi(vapi_assistant_id, twilio_number)` (cf. [`INTEGRATION_TWILIO.md`](./INTEGRATION_TWILIO.md)).

### Mises à jour d'assistant

| Fonction | Effet |
|---|---|
| `patch_vapi_assistant_system_prompt(assistant_id, new_prompt)` | PATCH `/assistant/{id}` |
| `update_vapi_assistant_faq(tenant_id)` | Reconstruit le system prompt à partir de la FAQ + secteur |
| `patch_vapi_assistant_add_tool(assistant_id)` | Ajoute le `VAPI_FUNCTION_TOOL_ID` aux toolIds |

---

## Function tool : `function_tool`

**Un seul tool partagé entre tous les assistants** (identifié par `VAPI_FUNCTION_TOOL_ID`). Le schéma OpenAI Function est défini dans `backend/vapi_utils.py:329`.

**URL serveur** : `{VAPI_PUBLIC_BACKEND_URL}/api/vapi/tool`.

### Actions exposées

| Action | Implémentation | Description |
|---|---|---|
| `get_slots` | `vapi_tool_handlers.handle_get_slots` | Liste créneaux disponibles |
| `validate_contact` | `vapi_tool_handlers.handle_validate_contact` | Valide nom/téléphone |
| `book` | `vapi_tool_handlers.handle_book` | Crée le RDV (Google Calendar / interne) |
| `cancel` | Engine `_get_engine(call_id).handle_message(...)` | Annulation guidée |
| `modify` | Engine | Modification |
| `transfer` | Engine + `vapi_live_transfer` | Transfert vers humain |
| `faq` | `tenant_faq_store(tid).search` + fallback engine | Réponse FAQ |

> Voir [`VAPI_TOOL_SCHEMA.md`](./VAPI_TOOL_SCHEMA.md) pour le schéma JSON complet.

---

## Webhooks Vapi

**Endpoint** : `POST /api/vapi/webhook` (`voice.py:1058`).

| `message.type` | Handler | Action |
|---|---|---|
| `assistant-request` | `_vapi_assistant_request_response` | Retourne l'assistant tenant (depuis routing) ou un assistant transient |
| `status-update` | `_persist_status_update_sync` (BG sauf ringing/in-progress) | MAJ `vapi_calls`, handoffs |
| `transcript` | `_schedule_transcript_persist` → `insert_call_transcript` | Persiste les transcripts par rôle |
| `tool-calls` | Boucle locale (dédup cache) → mêmes handlers que `/tool` | Action métier |
| `end-of-call-report` | `ingest_end_of_call_report` + `upsert_vapi_call(status="ended")` | Billing usage + clôture |

> Voir [`DASHBOARD_VAPI_POURQUOI_PAS_CONNECTE.md`](./DASHBOARD_VAPI_POURQUOI_PAS_CONNECTE.md) en cas de problème de réception webhook.

---

## Custom LLM (`/api/vapi/chat/completions`)

Vapi appelle ce endpoint comme s'il était un LLM compatible OpenAI. Permet :
- Mode **conversationnel P0** ([`CONVERSATIONAL_MODE_P0.md`](./CONVERSATIONAL_MODE_P0.md))
- FSM ([`FSM_STATES.md`](./FSM_STATES.md))
- Anti-loop, guardrails métier
- Streaming SSE si `stream=true`

> Le custom LLM peut être **désactivé** côté assistant Vapi (l'assistant tombe alors sur OpenAI direct). Vérifié via `_vapi_assistant_request_response`.

---

## Base de données

| Table | Migration | Contenu |
|---|---|---|
| `vapi_calls` | `028_vapi_calls_and_transcripts.sql` | Cycle de vie : `tenant_id`, `call_id`, `customer_number`, `assistant_id`, `phone_number_id`, `status`, timestamps, `ended_reason` |
| `call_transcripts` | `028` | Transcripts par rôle (assistant/user/tool) |
| `vapi_call_usage` | `009_vapi_call_usage.sql` | Durée + coût (`costs_json`) → reporté à Stripe pour billing |
| `tenant_config.params_json` → `vapi_assistant_id` | `005_postgres_tenants.sql` | Mapping tenant → assistant Vapi |

---

## Frontend admin

| Composant | Rôle |
|---|---|
| `landing/src/admin/components/TenantCreationWizard.jsx` | Sélection assistant + déclenchement provisioning |
| `landing/src/admin/components/AdminTenantActionsTab.jsx` | Vérifie éligibilité (`vapi_assistant_id` présent) |
| `landing/src/admin/pages/AdminTenantPage.jsx` | Affiche l'`vapi_assistant_id` du tenant |
| `landing/src/admin/pages/AdminBilling.jsx` | Coûts agrégés Vapi (depuis `vapi_call_usage`) |
| `landing/src/admin/components/dashboard/PlatformHealthPanel.jsx` | Status `services.vapi` |

### Page publique

`landing/src/pages/PagePubliquePraticienUWI.jsx` — widget Vapi web (`@vapi-ai/web`) avec `vapi.start(practitioner.vapiAssistantId)`. Utilise `VITE_VAPI_PUBLIC_KEY`.

---

## Mode démo

Quand `ADMIN_DEMO_MODE=true` :
- Le router `backend/admin_demo/router.py` intercepte les endpoints admin et retourne un dataset factice (assistants, appels, transcripts).
- Les **vrais appels Vapi** ne sont **jamais émis** depuis l'admin (création tenant désactivée côté UI).

> Voir [`ADMIN_DEMO_MODE.md`](./ADMIN_DEMO_MODE.md).

---

## Sécurité

| Item | Statut | Note |
|---|---|---|
| `VAPI_API_KEY` côté serveur uniquement | ✅ | Jamais exposé en frontend |
| `VITE_VAPI_PUBLIC_KEY` côté frontend | ✅ | Clé publique Vapi (limitée par CORS Vapi) |
| Validation signature webhook entrant | ✅ | Implémenté (`backend/vapi_security.py`) — mode souple par défaut, strict via `VAPI_REQUIRE_SIGNATURE=true`. Cf. [Vérification des webhooks](#sécurité--vérification-des-webhooks-entrants) |
| `/api/vapi/test*` protégés | ✅ | Middleware `_require_admin_or_debug_flag` (audit 2026-05) |
| `/debug/vapi-*` protégés | ✅ | Middleware `debug_endpoints_guard` |

### Sécurité — Vérification des webhooks entrants

Les endpoints `/api/vapi/webhook` et `/api/vapi/tool` vérifient l'authenticité de chaque requête avant de la traiter, à partir du secret partagé `VAPI_WEBHOOK_SECRET` (envoyé à Vapi via `server.secret` à la création de l'assistant).

**Deux modes d'authentification supportés** (Vapi peut envoyer l'un OU l'autre selon la config) :

1. **Shared secret (legacy)** — Vapi envoie le secret en clair dans le header `X-Vapi-Secret`. Comparaison `hmac.compare_digest` en temps constant avec notre secret local.
2. **HMAC-SHA256 (recommandé)** — Vapi calcule `HMAC-SHA256(body_brut, secret)` et l'envoie dans `X-Vapi-Signature` (avec ou sans préfixe `sha256=`). On recalcule et compare en temps constant.

**Modes de fonctionnement :**

| `VAPI_REQUIRE_SIGNATURE` | Comportement si signature invalide/absente |
|---|---|
| `false` (défaut, **mode souple**) | `logger.warning("[VAPI_WEBHOOK_SIGNATURE_INVALID] reason=...")` puis traite la requête normalement |
| `true` (**mode strict**) | `HTTPException 401 "Invalid Vapi signature"` |

Une troisième variable `VAPI_SIGNATURE_DISABLED=true` permet de skipper totalement la vérification (utilisé par `tests/conftest.py` pour ne pas casser les ~800 tests existants qui n'envoient pas de signature).

**Migration douce recommandée :**

1. **Phase 1 — Audit** (état actuel) : déployer en production avec `VAPI_REQUIRE_SIGNATURE=false`. Surveiller les logs `VAPI_WEBHOOK_SIGNATURE_INVALID` pendant 3-7 jours pour confirmer que tous les webhooks Vapi en production envoient effectivement une signature valide. Détecter d'éventuels mismatchs (header non envoyé, format inattendu, secret pas encore propagé).
2. **Phase 2 — Strict** : activer `VAPI_REQUIRE_SIGNATURE=true`. Les webhooks non signés ou mal signés sont rejetés en 401.

**Code source :** [`backend/vapi_security.py`](../backend/vapi_security.py) — fonction `verify_vapi_signature(body, headers) -> (ok, reason)`.

**Tests :** [`tests/test_vapi_security.py`](../tests/test_vapi_security.py) — 35 tests couvrant les modes shared secret, HMAC, signature absente/invalide, mode souple/strict, désactivation totale.

---

## Debug & opérationnel

### Vérifier qu'un tenant est correctement provisionné

```bash
# 1. Tenant a un vapi_assistant_id en PG
psql ... -c "select tenant_id, name, params_json->'vapi_assistant_id' from tenant_config where tenant_id=42;"

# 2. L'assistant existe chez Vapi
curl -H "Authorization: Bearer $VAPI_API_KEY" https://api.vapi.ai/assistant/{assistant_id}

# 3. Le numéro Twilio est routé vers cet assistant
curl -H "Authorization: Bearer $VAPI_API_KEY" https://api.vapi.ai/phone-number | jq '.[] | select(.number=="+33...")'

# 4. Le tenant_routing PG a le DID
psql ... -c "select * from tenant_routing where channel='vocal' and tenant_id=42;"
```

### Forcer la sync FAQ → assistant

`POST /debug/vapi-sync-faq` (auth admin requise).

### Tester un appel sans appeler le numéro

`POST /api/vapi/tool` avec un body simulant un tool-call permet de valider la chaîne (en dev) :

```bash
curl -X POST http://localhost:8000/api/vapi/tool \
  -H 'content-type: application/json' \
  -d '{"message":{"toolCalls":[{"id":"tc1","function":{"name":"function_tool","arguments":{"action":"get_slots","tenant_id":42}}}]}}'
```

---

## Voir aussi

### Configuration & opérations
- [`VAPI_FRANCAIS_CHECKLIST.md`](./VAPI_FRANCAIS_CHECKLIST.md) — checklist setup FR
- [`VAPI_CALLER_ID.md`](./VAPI_CALLER_ID.md) — gestion du numéro appelant
- [`DASHBOARD_VAPI_POURQUOI_PAS_CONNECTE.md`](./DASHBOARD_VAPI_POURQUOI_PAS_CONNECTE.md) — debug stats vapi non connectées

### Prompts & comportement
- [`VAPI_PROMPT_ASSISTANT.md`](./VAPI_PROMPT_ASSISTANT.md) — prompt système de référence
- [`VAPI_PROMPT_BOOKING_STATUS.md`](./VAPI_PROMPT_BOOKING_STATUS.md) — gestion des statuts de booking

### STT (transcription)
- [`VAPI_STT_NOVA3_FR.md`](./VAPI_STT_NOVA3_FR.md) — config Deepgram Nova-3 français
- [`VAPI_STT_FIX.md`](./VAPI_STT_FIX.md) — fix problèmes STT
- [`VAPI_SILENCE_DIAGNOSTIC.md`](./VAPI_SILENCE_DIAGNOSTIC.md) — diagnostic silences

### Tools
- [`VAPI_TOOL_SCHEMA.md`](./VAPI_TOOL_SCHEMA.md) — schéma complet du `function_tool`

### Billing
- [`VAPI_CONSO_BILLING.md`](./VAPI_CONSO_BILLING.md) — consommation et facturation
- [`INTEGRATION_STRIPE.md`](./INTEGRATION_STRIPE.md) — push usage Vapi → Stripe metering

### Téléphonie
- [`INTEGRATION_TWILIO.md`](./INTEGRATION_TWILIO.md) — couplage numéros Twilio ↔ Vapi
