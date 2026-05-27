# Intégration Twilio

Guide de référence technique pour l'intégration Twilio (téléphonie + SMS + WhatsApp).

> Twilio est le **fournisseur de numéros** ; le **traitement vocal** est délégué à Vapi (BYO via Vapi Phone Numbers). Ce repo n'achète pas de numéros via API : il les **liste** parmi ceux déjà présents sur le compte et les **assigne** à un assistant Vapi.

---

## Vue d'ensemble

UWI utilise Twilio pour 3 usages distincts :

1. **Téléphonie entrante (vocal)** : numéros DID achetés à la main dans la console Twilio, importés en BYO chez Vapi, puis assignés à l'assistant du tenant.
2. **SMS** : envoi de SMS (pages publiques, rapports quotidiens, notifications).
3. **WhatsApp** : webhook entrant pour le canal conversationnel WhatsApp Business.

```
┌─ Téléphonie ────────────────────────────────────────────────┐
│ Console Twilio (achat) ──► Import BYO Vapi ──► assign_to_   │
│                                                 vapi_       │
│                                                 assistant   │
│                                                              │
│ Appelant ──► Twilio DID ──► Vapi (assistant tenant)          │
└──────────────────────────────────────────────────────────────┘

┌─ SMS / WhatsApp ────────────────────────────────────────────┐
│ Page publique → POST → Twilio Messages.create               │
│ Rapports quotidiens → SMSChannel / WhatsAppChannel          │
│ WhatsApp entrant → POST /api/whatsapp/webhook (TwiML)        │
└──────────────────────────────────────────────────────────────┘
```

---

## Variables d'environnement

| Variable | Obligatoire | Défaut | Rôle |
|---|---|---|---|
| `TWILIO_ACCOUNT_SID` | ✅ | — | Identifiant du compte Twilio |
| `TWILIO_AUTH_TOKEN` | ✅ | — | Secret API Twilio (aussi utilisé pour validation webhook WhatsApp) |
| `TWILIO_PHONE_NUMBER` | ✅ (SMS) | — | Numéro expéditeur SMS au format E.164 |
| `TWILIO_WHATSAPP_NUMBER` | optionnel | `+14155238886` (sandbox) | Numéro expéditeur WhatsApp (préfixé `whatsapp:` en code) |

> Le frontend (`landing/`) **n'utilise aucune variable** Twilio. Toute la config est côté backend.

> Variable liée : `OWNER_PHONE_NUMBER` — destinataire SMS/WhatsApp pour les rapports quotidiens.

---

## Architecture

### Fichiers principaux

| Fichier | Rôle |
|---|---|
| `backend/routes/admin.py` (l.4198+) | `GET /api/admin/twilio/numbers` |
| `backend/routes/public_pages.py` (l.296+) | `_send_sms` pour les pages publiques |
| `backend/reports.py` | `SMSChannel`, `WhatsAppChannel` pour rapports quotidiens |
| `backend/routes/whatsapp.py` | Webhook `POST /api/whatsapp/webhook` |
| `backend/channels/whatsapp.py` | `validate_webhook` (HMAC-SHA1 + base64) |
| `backend/vapi_utils.py` (l.814+) | `assign_twilio_to_vapi` — couplage numéro ↔ assistant Vapi |

> ⚠️ **Pas implémenté côté API** : search/purchase/release/configure-voice-url. L'achat se fait dans la console Twilio.

---

## Flow vocal complet

### Provisioning d'un numéro

**Étapes manuelles préalables** (one-shot par numéro) :
1. Acheter un numéro dans la **console Twilio**.
2. **Importer ce numéro chez Vapi** en BYO (dashboard Vapi → Phone Numbers → Add → Twilio).
   - Cela crée une entrée `phone-number` côté Vapi avec un `id` propre.
3. Côté **Vapi**, configurer la **voice URL** du numéro Twilio (TwiML) pour qu'elle pointe vers Vapi.
   - Vapi le fait automatiquement quand on importe en BYO.

> Tant que ces étapes ne sont pas faites, le numéro ne pourra pas être assigné à un tenant.

**Étapes automatisées** (à la création tenant) :

```
POST /api/admin/tenants/create
  body: { ..., twilio_number: "+33186..." }

  1. PG: tenant + tenant_config + user
  2. Vapi: create_vapi_assistant → vapi_assistant_id
  3. PG: tenant_config.params_json += { vapi_assistant_id }
  4. Twilio:
     - assign_twilio_to_vapi(vapi_assistant_id, twilio_number)
       → GET  https://api.vapi.ai/phone-number      (chercher l'entrée Vapi)
       → PATCH https://api.vapi.ai/phone-number/{id} { assistantId }
     - pg_add_routing("vocal", "+33186...", tenant_id)
  5. Stripe: customer + subscription
```

### `assign_twilio_to_vapi(assistant_id, twilio_number)` — étape clé

Dans `backend/vapi_utils.py:814` :

```python
# 1. GET https://api.vapi.ai/phone-number
#    Cherche l'entrée dont .number ou .phoneNumber == twilio_number
#    (avec normalisation 00XX → +XX)

# 2. PATCH https://api.vapi.ai/phone-number/{id}
#    body: { "assistantId": assistant_id }
```

> Si le numéro n'existe pas chez Vapi (BYO pas fait), la fonction lève. Le rollback supprimera l'assistant Vapi et le tenant PG, mais **pas** la ligne `tenant_routing` ni la liaison Twilio→Vapi (à nettoyer manuellement).

### Routing à l'appel

À l'arrivée d'un appel sur le numéro Twilio :
1. Twilio route vers Vapi (URL Voice configurée à l'import BYO).
2. Vapi appelle `POST /api/vapi/webhook` avec `assistant-request`.
3. Le backend résout le tenant via `tenant_routing` (channel `vocal`, key = numéro normalisé).
4. Le custom LLM `/api/vapi/chat/completions` est appelé avec le contexte tenant.

---

## Endpoints

### Admin

| Méthode | Path | Rôle | Auth |
|---|---|---|---|
| GET | `/api/admin/twilio/numbers` | Liste les `IncomingPhoneNumber` du compte. Marque `available: num ∉ assigned` (où `assigned` vient de `tenant_routing`). Si SID/token absents ou erreur → `[]`. | admin |
| POST | `/api/admin/tenants/create` | Création tenant ; si `twilio_number` fourni, déclenche `assign_twilio_to_vapi` + `pg_add_routing` | admin |
| POST | `/api/admin/routing` | Route DID → tenant manuellement (`channel="vocal"`, `key="+33..."`) | admin |
| GET | `/api/admin/stats/platform-health` | Inclut `services.twilio` (présence env SID/token, pas de ping) | admin |

### Public

| Méthode | Path | Rôle | Auth |
|---|---|---|---|
| POST | `/api/whatsapp/webhook` | Webhook Twilio WhatsApp (form-urlencoded) → TwiML | Signature `X-Twilio-Signature` (HMAC-SHA1) |
| GET | `/api/whatsapp/health` | Healthcheck WhatsApp | Public |
| GET | `/api/whatsapp/test` | Infos config + endpoints | Public |

---

## SMS

### Pages publiques (`backend/routes/public_pages.py`)

`_send_sms(to, body)` — envoie un SMS via Twilio :
- Utilisé pour confirmation booking, annulation, etc.
- `from_=TWILIO_PHONE_NUMBER`, `to=` numéro patient.

### Rapports quotidiens (`backend/reports.py`)

Deux canaux Twilio :
- `SMSChannel` (l.146) : SMS au `OWNER_PHONE_NUMBER`.
- `WhatsAppChannel` (l.194) : message WhatsApp avec préfixe `whatsapp:`.

> Voir [`RAPPORT_QUOTIDIEN_IVR.md`](./RAPPORT_QUOTIDIEN_IVR.md).

---

## WhatsApp (canal conversationnel)

### Webhook entrant

`POST /api/whatsapp/webhook` reçoit un POST form-urlencoded de Twilio avec :
- `From`, `To`, `Body`, `MessageSid`, etc.
- Header `X-Twilio-Signature` pour validation HMAC.

### Validation signature

`backend/channels/whatsapp.py:115` — `validate_webhook(headers, url, params)` :
- Si `TWILIO_AUTH_TOKEN` absent → retourne `True` (validation **désactivée** + log warning).
- Sinon : HMAC-SHA1(URL + params triés concaténés, AUTH_TOKEN) en base64, comparé via `hmac.compare_digest`.

> ⚠️ Implémentation **maison**. À valider vs `RequestValidator` officiel Twilio si proxy/URL canonical compliquée.

### Réponse

TwiML XML retourné en `Content-Type: text/xml`.

> Voir aussi `backend/routes/whatsapp.py` et `tests/test_tenant_resolution_whatsapp.py`.

---

## Base de données

| Élément | Détail |
|---|---|
| `tenant_routing` | Migration `005_postgres_tenants.sql` (PG) ou `002_tenant_routing.sql` (SQLite legacy). Colonnes `(channel, key, tenant_id)`. Le numéro Twilio est stocké comme `key` avec `channel='vocal'`. |
| `tenant_config.params_json` | Peut contenir `phone_number` (numéro client à afficher) — pas le SID Twilio |

> ⚠️ **Aucune table dédiée Twilio** (pas de `twilio_phone_number_sid`). Le numéro Vapi `phone-number.id` n'est pas non plus persisté en PG. Si on veut désassigner proprement, il faut re-fetch côté Vapi.

---

## Frontend admin

| Composant | Rôle |
|---|---|
| `landing/src/admin/components/TenantCreationWizard.jsx` | Étape 2 du wizard : fetch `getTwilioNumbers()`, filtre `available`, envoie `twilio_number` à la création |
| `landing/src/admin/components/CreateTenantModal.jsx` | Idem (modal version pour conversion lead → tenant) |
| `landing/src/lib/adminApi.js` | `getTwilioNumbers()` → `GET /api/admin/twilio/numbers` |
| `landing/src/admin/components/dashboard/PlatformHealthPanel.jsx` | Affiche statut `services.twilio` |

---

## Mode démo

Quand `ADMIN_DEMO_MODE=true` :
- `GET /api/admin/twilio/numbers` retourne **5 numéros factices** (`+33186...`) via `backend/admin_demo/router.py:152`.
- `services.twilio` est forcé "ok" dans platform-health (`router.py:753`).
- Aucun appel API Twilio réel n'est émis.

> Voir [`ADMIN_DEMO_MODE.md`](./ADMIN_DEMO_MODE.md).

---

## Sécurité

| Item | Statut | Note |
|---|---|---|
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` côté serveur uniquement | ✅ | Frontend n'a pas accès |
| Validation signature webhook WhatsApp | ⚠️ Implémentation maison | OK pour usage standard, à valider en cas de proxy compliqué |
| `validate_webhook` retourne `True` si `AUTH_TOKEN` absent | ⚠️ "Dev mode" | Logger un warning. Configurer `AUTH_TOKEN` en prod. |
| Pas de validation pour le webhook Voice (Twilio Voice direct) | N/A | Voice passe par Vapi, pas par notre backend Twilio direct |

---

## Tests

| Fichier | Couvre |
|---|---|
| `tests/test_twilio_provisioning.py` | `GET /api/admin/twilio/numbers` : auth, sans creds, erreur SDK, filtre `available`, troncature `friendly`, demo mode (12 tests) |
| `tests/test_tenant_routing.py` | Normalisation DID, résolution `sip.twilio.com` |
| `tests/test_tenant_resolution_whatsapp.py` | Routing WhatsApp |
| `tests/test_normalize_e164.py` | Préfixe `whatsapp:`, format E.164 |

---

## Debug & opérationnel

### Vérifier qu'un numéro est correctement provisionné

```bash
# 1. Numéro présent sur le compte Twilio
twilio phone-numbers:list

# 2. Numéro importé chez Vapi
curl -H "Authorization: Bearer $VAPI_API_KEY" https://api.vapi.ai/phone-number | \
  jq '.[] | select(.number=="+33186...")'

# 3. Numéro routé dans tenant_routing
psql ... -c "select * from tenant_routing where channel='vocal' and key='+33186...';"

# 4. Tenant cible a un assistant Vapi
psql ... -c "select tenant_id, params_json->>'vapi_assistant_id' from tenant_config where tenant_id=42;"
```

### Désassigner un numéro

Pas d'endpoint dédié. Procédure manuelle :

```bash
# 1. Retirer la ligne PG
psql ... -c "delete from tenant_routing where channel='vocal' and key='+33186...';"

# 2. Désassigner côté Vapi (PATCH avec assistantId=null)
PHONE_ID=$(curl -H "Authorization: Bearer $VAPI_API_KEY" https://api.vapi.ai/phone-number | \
  jq -r '.[] | select(.number=="+33186...") | .id')
curl -X PATCH -H "Authorization: Bearer $VAPI_API_KEY" \
  -H 'content-type: application/json' \
  -d '{"assistantId": null}' \
  "https://api.vapi.ai/phone-number/$PHONE_ID"
```

### Tester l'envoi d'un SMS

```bash
python3 -c "
from twilio.rest import Client
import os
c = Client(os.environ['TWILIO_ACCOUNT_SID'], os.environ['TWILIO_AUTH_TOKEN'])
m = c.messages.create(to='+33...', from_=os.environ['TWILIO_PHONE_NUMBER'], body='Test UWI')
print(m.sid, m.status)
"
```

---

## Lacunes connues (TODO)

| TODO | Impact |
|---|---|
| Pas d'API search/purchase/release de numéro Twilio | Achat manuel uniquement |
| Pas de configuration auto de la voice URL Twilio (passe par BYO Vapi à l'import) | OK si import BYO Vapi est fait |
| Pas de désassignation Vapi dans le rollback de provisioning | Risque résiduel si erreur après step 4 |
| Pas de persistance `vapi_phone_number.id` en PG | Re-fetch nécessaire pour désassigner |
| `validate_webhook` retourne `True` sans token | Doc mentionne "dev mode" mais à durcir |

---

## Voir aussi

- [`INTEGRATION_VAPI.md`](./INTEGRATION_VAPI.md) — couplage assistant ↔ numéro
- [`API_ADMIN_ONBOARDING.md`](./API_ADMIN_ONBOARDING.md) — flow `tenants/create`
- [`TENANT_ROUTING.md`](./TENANT_ROUTING.md) — résolution DID → tenant
- [`RAPPORT_QUOTIDIEN_IVR.md`](./RAPPORT_QUOTIDIEN_IVR.md) — canaux SMS/WhatsApp pour rapports
- [`ADMIN_DEMO_MODE.md`](./ADMIN_DEMO_MODE.md) — mocks Twilio en demo
