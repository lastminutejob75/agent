# Audit du canal vocal (Vapi)

Rapport d'audit complet des fonctions et flux du canal vocal UWi Agent.

---

## 1. Architecture des endpoints

| Endpoint | Méthode | Rôle |
|----------|---------|------|
| `/api/vapi/webhook` | POST | Webhook principal Vapi (transcriptions finales) |
| `/api/vapi/tool` | POST | Appels tool/functions depuis Vapi |
| `/api/vapi/chat/completions` | POST | Custom LLM (messages + streaming) |
| `/api/vapi/health` | GET | Santé du service vocal |
| `/api/vapi/test` | GET | Test rapide engine |
| `/api/vapi/test-calendar` | GET | Test connexion Google Calendar |

---

## 2. Flux webhook (`/api/vapi/webhook`)

### 2.1 Entrée

- **Payload** : `message` (role, type, transcript, transcriptType, confidence)
- **Routage tenant** : `extract_to_number_from_vapi_payload` → `resolve_tenant_id_from_vocal_call`
- **Session** : `session.channel = "vocal"`, `session.tenant_id = resolved_tenant_id`

### 2.2 Filtrage

- Messages non-`user` → HTTP 204
- `transcriptType == "partial"` → HTTP 204 (pas de tour)
- Classification STT : `_classify_stt_input(raw_text, confidence, transcript_type, message_type)`

### 2.3 Classification STT (`_classify_stt_input`)

| Résultat | Condition | Action |
|----------|-----------|--------|
| **TEXT** | Tokens critiques (oui, non, 1/2/3, confirme, etc.) | Toujours traité |
| **TEXT** | Transcript normalisé valide | `handle_message(call_id, text)` |
| **NOISE** | Vide + confidence < 0.35 | `handle_noise(session)` |
| **NOISE** | Court/filler + confidence < 0.50 | `handle_noise(session)` |
| **SILENCE** | Vide sans confidence | `handle_message(call_id, "")` |

### 2.4 Tokens critiques (jamais NOISE)

```python
CRITICAL_TOKENS = {"oui", "non", "ok", "1", "2", "3", "un", "deux", "trois",
    "premier", "deuxième", "troisième", "confirme", "je confirme", "oui je confirme", ...}
```

### 2.5 Réponse

- JSON `{"content": "<texte>"}` pour TTS Vapi

---

## 3. Flux chat/completions (`/api/vapi/chat/completions`)

Utilisé quand Vapi est configuré en Custom LLM (pas de Claude/GPT natif).

### 3.1 Extraction

- `call_id` : `payload.call.id` > `x-vapi-call-id` > `conversation_id` > fallback
- `user_message` : dernier message `role=user` (string ou liste OpenAI)
- `customer_phone` : `payload.call.customer.number`

### 3.2 Classification text-only

- `classify_text_only(user_message)` → `("SILENCE" | "UNCLEAR" | "TEXT", normalized)`
- Pas de `confidence` (Custom LLM n'en fournit pas)

### 3.3 Overlap / semi-sourd

- `_is_agent_speaking(session)` : `now < session.speaking_until_ts`
- Si agent parle + UNCLEAR/SILENCE → `MSG_VOCAL_CROSSTALK_ACK` ("Je vous écoute.")
- Si agent parle + TEXT court (< 10 car) → `MSG_OVERLAP_REPEAT_SHORT`
- Si WAIT_CONFIRM + token critique → pas d'overlap (choix créneau valide)

### 3.4 UNCLEAR progressif

| Count | Action |
|-------|--------|
| 1 | `MSG_UNCLEAR_1` |
| 2 | `_trigger_intent_router(session, "unclear_text_2", ...)` |
| 3+ | `TRANSFERRED` + `VOCAL_TRANSFER_COMPLEX` |

### 3.5 Crosstalk window

- `CROSSTALK_WINDOW_SEC` (5s) : UNCLEAR court après réponse agent → ignoré
- `OVERLAP_WINDOW_SEC` (1.2s) : UNCLEAR récent → `MSG_OVERLAP_REPEAT`

### 3.6 Streaming

- `stream=true` → SSE mot par mot
- Cas spécial : `CANCEL_NAME` + nom détecté → message de tenue (`VOCAL_CANCEL_LOOKUP_HOLDING`) puis recherche RDV en thread

### 3.7 Stats et mémoire client

- `report_generator.record_interaction()` sur CONFIRMED/TRANSFERRED
- `client_memory.get_or_create()` + `record_booking()` si RDV confirmé

---

## 4. Flux tool (`/api/vapi/tool`)

- Paramètre : `parameters.user_message`
- Même routage tenant que webhook
- `handle_message(call_id, user_message)` → `{"result": "<texte>"}`

---

## 5. Modules STT

### 5.1 `stt_utils.py`

| Fonction | Rôle |
|----------|------|
| `normalize_transcript(text)` | Trim, suppression fillers début/fin, garde "ok"/"oui" |
| `is_filler_only(text)` | True si uniquement fillers (euh, hum, etc.) |

### 5.2 `stt_common.py`

| Fonction | Rôle |
|----------|------|
| `classify_text_only(text)` | SILENCE / UNCLEAR / TEXT (sans confidence) |
| `is_critical_token(text)` | Tokens jamais UNCLEAR |
| `is_critical_overlap(text)` | Mots à traiter même pendant TTS (barge-in) |
| `looks_like_garbage_or_wrong_language(text)` | Détection anglais/charabia |
| `estimate_tts_duration(text)` | ~13 car/s, min 0.8s, max 4.0s |

---

## 6. Engine vocal

### 6.1 `handle_noise(session)`

- Cooldown `NOISE_COOLDOWN_SEC` (2s)
- 1er bruit → `MSG_NOISE_1`
- 2e bruit → `MSG_NOISE_2`
- 3e bruit → `_trigger_intent_router(session, "noise_repeated", "")`

### 6.2 `handle_message(call_id, text)`

- Pipeline déterministe : edge-cases → session → FAQ → booking/qualif → transfer
- Messages vocal : préfixe `VOCAL_` dans `prompts.py` (ex. `VOCAL_INTENT_ROUTER`, `VOCAL_SLOT_ONE_PROPOSE`)
- Confirmation créneau : détection "oui 1/2/3", "confirme", "je confirme"

### 6.3 Reconstruction de session

- `_reconstruct_session_from_history(session, messages)` : fallback si session perdue (redémarrage)
- Extrait nom, préférence, contact depuis l'historique assistant/user
- Déduit l'état (QUALIF_NAME, WAIT_CONFIRM, etc.) depuis le dernier message assistant

---

## 7. Configuration (config.py)

| Variable | Défaut | Rôle |
|----------|--------|------|
| `NOISE_CONFIDENCE_THRESHOLD` | 0.35 | Transcript vide + conf < seuil → NOISE |
| `SHORT_TEXT_MIN_CONFIDENCE` | 0.50 | Texte court + conf < seuil → NOISE |
| `MIN_TEXT_LENGTH` | 5 | Texte < 5 car → court |
| `NOISE_COOLDOWN_SEC` | 2.0 | Anti-spam bruit |
| `MAX_NOISE_BEFORE_ESCALATE` | 3 | Bruits avant intent router |
| `CROSSTALK_WINDOW_SEC` | 5.0 | Fenêtre crosstalk |
| `OVERLAP_WINDOW_SEC` | 1.2 | Fenêtre overlap |
| `CROSSTALK_MAX_RAW_LEN` | 40 | Longueur max crosstalk |

---

## 8. Points d'attention

1. **Duplication CRITICAL_TOKENS** : `voice.py` et `stt_common.py` définissent des ensembles similaires. Centraliser dans `stt_common` si possible.
2. **Bug potentiel** : `voice.py` ligne 269 `return {}` pour `assistant-request` — devrait être `Response(status_code=204)` ou un objet valide selon le contrat Vapi.
3. **Conversational mode** : `_get_engine(call_id)` peut retourner `ConversationalEngine` si `CONVERSATIONAL_MODE_ENABLED` et canary. Sinon `ENGINE` (FSM).
4. **Consent** : `persist_consent_obtained` au premier message user (mode implicite) dans webhook uniquement.

---

## 9. Schéma de flux simplifié

```
Vapi (nova-2-phonecall)
    │
    ├─► Webhook (transcript final)
    │       │
    │       ├─ partial → 204
    │       ├─ _classify_stt_input
    │       │       ├─ NOISE → handle_noise
    │       │       ├─ SILENCE → handle_message("")
    │       │       └─ TEXT → handle_message(text)
    │       └─ {"content": "..."}
    │
    ├─► Chat/completions (Custom LLM)
    │       │
    │       ├─ classify_text_only
    │       ├─ Overlap guard (agent parle)
    │       ├─ SILENCE/UNCLEAR/TEXT → handle_message
    │       └─ stream ? SSE : JSON
    │
    └─► Tool
            └─ handle_message(user_message) → {"result": "..."}
```

---

*Document généré le 2026-02-03*
