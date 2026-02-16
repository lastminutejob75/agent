# Récupération du numéro client (Caller ID) — Stratégie définitive

## Problème

L’agent ne doit pas redemander le numéro lorsque Vapi le fournit déjà via les webhooks.

## Diagnostic Vapi (confirmé par analyse des webhooks)

### Webhooks qui **contiennent** `call.customer.number`

| Type | Moment | Usage |
|------|--------|--------|
| `status-update` (status: `in-progress`) | Début d’appel | **Source principale** — le plus fiable, arrive en premier |
| `assistant.started` | Début d’appel | Alternative selon config |
| `assistant-request` | Si configuré | Idem |
| `end-of-call-report` | Fin d’appel | Trop tard pour le flow ; utile pour logs |

### Webhooks qui **ne contiennent pas** `call.customer.number`

- `conversation-update` — seulement `message.conversation[]`
- `speech-update` — seulement `message.artifact`
- `tool-calls` — pas de call customer

### Extraction

**Chemin :** `payload["message"]["call"]["customer"]["number"]`  
**Fallback :** `payload["message"]["customer"]["number"]`

Implémentation : `backend/tenant_routing.py` → `extract_customer_phone_from_vapi_payload(payload)`.

---

## Implémentation backend

### 1. Persistance (webhook)

- **Fichier :** `backend/routes/voice.py` — `POST /api/vapi/webhook`
- **Types ciblés (uniquement ceux qui ont le numéro) :**
  - `status-update` avec `status == "in-progress"`
  - `assistant.started`, `assistant-request`, `status_update`
  - `end-of-call-report` (optionnel)
- **Règle :** idempotent — on ne remplit que si `session.customer_phone` est encore vide.
- **Log :** `CALLER_ID_PERSISTED` avec `call_id`, `msg_type`, `phone_masked` (ex. `+33XXXXXX14`).

### 2. State engine

- **Si `session.customer_phone`** → **CONTACT_CONFIRM** avec phrase courte (2 derniers chiffres).
- **Sinon** → **QUALIF_CONTACT** (CONTACT_COLLECT) avec message dédié.

### 3. Wording TTS (RGPD — ne jamais lire le numéro complet)

| Situation | Message (`backend/prompts.py`) |
|-----------|-------------------------------|
| Caller ID connu | `VOCAL_CONTACT_CONFIRM_CALLER_ID` : « J'ai un numéro qui se termine par {last_two}. C'est bien le vôtre ? Dites oui ou non. » |
| Caller ID absent / masqué | `VOCAL_CONTACT_NO_CALLER_ID` : « Je n'ai pas votre numéro qui s'affiche. Pouvez-vous me le donner ? » |
| Confirmation positive | « Parfait, c'est noté. » / `VOCAL_CONTACT_CONFIRM_OK` |
| Confirmation négative | `VOCAL_CONTACT_CONFIRM_NO` : « Pas de souci. Quel est le meilleur numéro pour vous joindre ? » |

### 4. Logs de diagnostic

| Log | Signification |
|-----|----------------|
| `CALLER_ID_PERSISTED` | Numéro extrait du webhook et persisté en session ; `phone_masked` = 2 derniers chiffres visibles. |
| `CALLER_ID_FOUND` | Engine utilise le caller ID → CONTACT_CONFIRM ; `last2`, `next`, `context` (optionnel). |
| `CALLER_ID_NOT_FOUND` | Pas de numéro en session → CONTACT_COLLECT (QUALIF_CONTACT). |

---

## Fallback UX (optionnel) — Prompt Vapi

Dans le **system prompt** de l’assistant Vapi (dashboard), on peut ajouter :

```text
Le numéro de l'appelant est : {{customer.number}}
Si ce numéro est disponible et non masqué, ne le redemande pas.
```

Ceci n’est **pas** la source de vérité (le backend webhook l’est) ; c’est un filet de sécurité UX.

---

## Checklist

- [x] Capturer le caller ID dès `status-update` (in-progress) dans le handler webhook
- [x] Persister en session (idempotent)
- [x] State engine : `session.customer_phone` → CONTACT_CONFIRM, sinon → QUALIF_CONTACT
- [x] Wording RGPD : 2 derniers chiffres uniquement en TTS
- [x] Logs : CALLER_ID_PERSISTED (masqué), CALLER_ID_FOUND, CALLER_ID_NOT_FOUND
- [ ] Tester avec un appel entrant et vérifier les logs Railway
- [ ] (Optionnel) Ajouter `{{customer.number}}` dans le prompt Vapi

---

## Référence

- Config / diagnostic : `VAPI_CONFIG.md` section « 3. Reconnaissance du numéro (caller ID) ».
