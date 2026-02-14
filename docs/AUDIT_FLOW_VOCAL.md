# Audit du flow vocal (Vapi / nova-2-phonecall)

Synthèse de l'audit du flux vocal pour l'agent UWi.

---

## 1. Architecture

| Composant | Rôle |
|-----------|------|
| `backend/routes/voice.py` | Webhook Vapi, decision, tool, chat/completions, classification STT |
| `backend/engine.py` | FSM, états, confirmation créneaux, `handle_message` / `handle_noise` |
| `backend/tools_booking.py` | Slots Google Calendar / SQLite, `source="google"` |
| `backend/guards.py` | Validation vocale, `validate_booking_confirm`, `detect_slot_choice_flexible` |
| `backend/intent_parser.py` | Détection intent, `_is_yes`, `_is_no`, `extract_slot_choice`, `normalize_stt_text` |
| `backend/slot_choice.py` | `detect_slot_choice_early` (choix explicite 1/2/3, jour+heure) |
| `backend/stt_common.py` | Classification text-only (SILENCE/UNCLEAR/TEXT), tokens critiques |
| `backend/stt_utils.py` | `normalize_transcript`, `is_filler_only` |

---

## 2. Flux webhook Vapi

1. **Payload** : `message.role == "user"` uniquement
2. **Transcript** : `transcriptType == "final"` (partial ignoré pour nova-2-phonecall)
3. **Classification** : `_classify_stt_input(raw_text, confidence, transcript_type)` → `NOISE` | `SILENCE` | `TEXT`
4. **NOISE** → `handle_noise(session)` (pas de réponse ou micro-réponse)
5. **TEXT** → `handle_message(conv_id, text)` → events
6. **Réponse** : `events[0].text` envoyé au TTS

---

## 3. Classification STT (`voice.py`)

- **Tokens critiques** : oui, non, ok, 1/2/3, premier/deuxième/troisième → toujours **TEXT** (jamais NOISE)
- **Transcript vide** + confidence basse → **NOISE**
- **Court/filler** + confidence basse → **NOISE**
- **Sinon** → **TEXT**

---

## 4. Confirmation créneau ("oui je confirme")

**Contexte** : Après proposition de créneaux, l'agent demande « Vous confirmez ? ». L'utilisateur peut dire « oui je confirme », « je confirme », « confirme ».

**Implémentation** (`engine.py` ~l.2722–2747) :

```python
# Détection explicite de "confirme" dans le texte normalisé
elif "confirme" in (_t_ascii or "") and len(_t_ascii or "") <= 30:
    slot_idx = session.pending_slot_choice
    session.awaiting_confirmation = None
    # → passage au contact (CONTACT_CONFIRM)
```

**Variantes acceptées** :
- « oui » seul (si `pending_slot_choice` déjà défini)
- « c'est bien ça » / « c'est correct »
- « oui c'est bien ça » (≤25 car)
- « oui je confirme » / « je confirme » / « confirme » (≤30 car)

---

## 5. Choix de créneau (`slot_choice.py`)

- **Chiffre seul** : uniquement « 1 », « 2 », « 3 » (pas « j'ai 2 questions »)
- **Phrase** : « oui 1 », « choix 2 », « le premier », « vendredi 14h » (si match exact d'un slot)
- **Jour seul ou heure seule** : refusé (ambiguïté)

---

## 6. Tests

- `test_vocal_confirmations.py` : confirmations oui/non
- `test_vocal_mapping.py` : mapping STT
- `test_vocal_email_min.py` : email minimal vocal
- `test_engine.py` : flow engine
- `test_prompt_compliance.py` : conformité messages

**Statut** : 85 tests passent (dont vocal/engine).

---

## 7. Points de vigilance

| Point | Vérification |
|-------|--------------|
| RDV Google | `source="google"` dans `_get_slots_from_google_calendar` et `_propose_slots` |
| "oui je confirme" | Détection via `"confirme" in _t_ascii` |
| Tokens critiques | `CRITICAL_TOKENS` dans `voice.py` et `stt_common.py` |
| Recovery slot_choice | 3 échecs → transfert (`should_escalate_recovery`) |
| Session TTL | 15 min (config) |

---

## 8. Fichiers modifiés récemment (corrections)

- `backend/engine.py` : détection « confirme » pour confirmation créneau
- `backend/tools_booking.py` : `source="google"` pour slots Google Calendar

---

*Document généré le 2025-02-03.*
