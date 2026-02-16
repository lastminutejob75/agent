# Récupération du numéro client (Caller ID) — Vapi

## Contexte

- L’assistant utilise **OpenAI GPT-4o** (plus de Custom LLM).
- Le **numéro client** n’est **pas** envoyé dans les requêtes Chat Completions : il est **uniquement** présent dans les **webhooks** Vapi (`/api/vapi/webhook`).

## Structure des webhooks Vapi

Tous les webhooks reçus ont la forme :

```json
{
  "message": {
    "type": "assistant.started" | "status-update" | "conversation-update" | ...,
    "call": {
      "id": "<call_id>",
      "customer": { "number": "+33652398414" },
      "phoneNumber": { "number": "+33939240575" }
    }
  }
}
```

**Chemin d’extraction du numéro client :** `payload["message"]["call"]["customer"]["number"]`.

## Implémentation côté backend

### 1. Extraction

- **Fichier :** `backend/tenant_routing.py`
- **Fonction :** `extract_customer_phone_from_vapi_payload(payload)`
- **Ordre des chemins testés :**
  1. `message.call.customer.number` / `message.call.customer.phone` (webhooks)
  2. `message.customer.number` (certains formats)
  3. `call.customer.number` (racine, ancien format)
  4. `call.from`, `customerNumber`, `callerNumber`, `messages[].customer`

### 2. Persistance au webhook

- **Fichier :** `backend/routes/voice.py`
- **Route :** `POST /api/vapi/webhook`
- **Comportement :** Dès qu’un webhook contient `message.call.customer.number` et un `call_id` :
  - Types concernés : `assistant.started`, `status-update` (status `in-progress`), `conversation-update`
  - On charge ou crée la session pour ce `call_id`, on met `session.customer_phone`, on sauvegarde.
  - On ne met à jour que si `session.customer_phone` est encore vide (évite d’écraser).

Log émis en cas de succès : `CALLER_ID_PERSISTED_FROM_WEBHOOK` avec `call_id` et `msg_type`.

### 3. Utilisation en conversation

- Les requêtes **Chat Completions** (ou **Tool**) n’ont pas le numéro dans le body.
- Elles utilisent le **même `call_id`** que les webhooks.
- Au chargement de la session (`_get_or_resume_voice_session`), `session.customer_phone` est donc déjà renseigné si le webhook a été traité avant.
- Dans **engine** : en `QUALIF_CONTACT`, si `session.customer_phone` est présent → passage direct en **CONTACT_CONFIRM** avec la phrase courte (2 derniers chiffres) : *« J’ai le numéro qui s’affiche, il se termine par XX. C’est bien le vôtre ? »*.

## Diagnostic

| Log | Signification |
|-----|----------------|
| `CALLER_ID_PERSISTED_FROM_WEBHOOK` | Le numéro a été extrait du webhook et sauvegardé en session pour ce `call_id`. |
| `CUSTOMER_PHONE_RECOGNITION` (has_number, payload_has_call, call_keys) | Vu dans les requêtes Chat Completions : indique si le payload contient un `call` (souvent non en Custom LLM / OpenAI). |
| `[QUALIF] using_caller_id contact_confirm_short` | L’engine a utilisé le caller ID pour proposer la confirmation courte. |
| `[QUALIF] no_caller_id → QUALIF_CONTACT` | Pas de numéro en session → l’agent demande le numéro. |

## Référence

- Rapport détaillé : voir le message utilisateur « RAPPORT CURSOR — Récupération customer_phone depuis les webhooks Vapi » (structure payload, chemins, solution recommandée).
- Config / diagnostic général : `VAPI_CONFIG.md` section « 3. Reconnaissance du numéro (caller ID) ».
