# Diagnostic : passage nova-2 → nova-2-phonecall (STT)

## ÉTAPE 1 — Diagnostic (sans modification)

### 1) Webhook `/api/vapi/webhook` — où sont extraits transcript / confidence / transcriptType

| Élément | Fichier | Lignes | Constat |
|--------|---------|--------|--------|
| **Webhook** | `backend/routes/voice.py` | 183–237 | `vapi_webhook()` traite tous les messages avec du texte. |
| **Transcript** | `backend/routes/voice.py` | 206 | `user_text = message.get("content") or message.get("transcript") or ""`. Pas de `transcriptType` ni `confidence`. |
| **Confidence** | — | — | **Non utilisée** nulle part dans le webhook. |
| **transcriptType / partial / final** | — | — | **Non extrait**. Tout message avec `content`/`transcript` est traité comme final. |
| **Réponse Vapi** | `backend/routes/voice.py` | 221, 231 | `return {"content": response_text}` ou `return {}` si pas de texte. |

**Conclusion** : Les **partials** sont aujourd’hui traités comme des messages finaux → l’agent peut répondre sur des hypothèses de transcription (euh…, bruits), d’où le ressenti “il répond à côté” ou “il coupe”.

---

### 2) Usages de confidence / seuils / silence / fillers

| Thème | Fichier | Lignes | Constat |
|-------|---------|--------|--------|
| **Seuils confidence** | `backend/config.py` | 18 | Un seul seuil type “confidence” : `FAQ_THRESHOLD = 0.80` (match FAQ). Aucun seuil STT. |
| **Confidence** | `backend/entity_extraction.py` | 27, 306–329 | Champ `confidence` sur entités extraites (nom/motif), pas lié au STT. |
| **Transcript vide / silence** | `backend/engine.py` | 711–730 | Message vide → `empty_message_count` ; 1 → MSG_SILENCE_1, 2 → MSG_SILENCE_2, 3 → INTENT_ROUTER. **Aucune distinction bruit (confidence basse) vs vrai silence.** |
| **empty_message_count** | `backend/session.py` | 78, 135 | Compteur pour RÈGLE 3 (silence répété). |
| **RECOVERY_LIMITS silence** | `backend/config.py` | 48 | `"silence": 3` (2 messages vides + 3e → INTENT_ROUTER). |
| **Fillers / "euh"** | `backend/guards.py` | 29–50, 94–95, 124 | `clean_name_from_vocal`, `FILLERS_FR_NAME`, retrait en début de phrase pour noms. Pas de normalisation globale du transcript à l’entrée du webhook. |
| **Fillers** | `backend/engine.py` | 1157, 1294, 1409, 1671 | Rejet de fillers dans des contextes précis (QUALIF_NAME, QUALIF_PREF, etc.), pas à l’entrée. |

**Conclusion** : Aucun seuil de **confidence STT** (ex. 0.7) n’est utilisé. Avec nova-2-phonecall, transcripts vides ou très courts avec **confidence faible** devraient être traités comme **bruit** (noise), pas comme **silence** (sinon on incrémente `empty_message_count` et on enchaîne MSG_SILENCE_1/2 puis INTENT_ROUTER). Hypothèse la plus probable : **1) Partials traités comme final, 2) Pas de distinction bruit/silence, 3) Fillers non normalisés à l’entrée.**

---

### 3) Hypothèse la plus probable

1. **Partials** : Vapi envoie des `transcriptType: "partial"` (ou équivalent) que le backend ne filtre pas → réponses sur des transcriptions incomplètes / filler words.
2. **Confidence** : Pas de seuil → tout transcript est pris au sérieux ; en téléphonie la confidence baisse → transcripts courts/vides avec faible confidence devraient être ignorés ou traités en “bruit”.
3. **Fillers** : "euh", "heu", "..." non normalisés en entrée → intents instables ou rejets dans les flows (nom, préférence, etc.).

**Leviers à implémenter (ordre)** : 1) Ignorer les partial, 2) Seuils confidence + distinction NOISE vs SILENCE, 3) Normalisation fillers en entrée.

---

## Livrable final (patch appliqué)

### Fichiers modifiés / ajoutés

| Fichier | Action |
|---------|--------|
| `backend/config.py` | + STT_MODEL, NOISE_CONFIDENCE_THRESHOLD, SHORT_TEXT_MIN_CONFIDENCE, MIN_TEXT_LENGTH, NOISE_COOLDOWN_SEC, MAX_NOISE_BEFORE_ESCALATE |
| `backend/stt_utils.py` | **Nouveau** : normalize_transcript(), is_filler_only() |
| `backend/routes/voice.py` | Extraction transcriptType/confidence, partial→no-op, _classify_stt_input(), routing NOISE→handle_noise, SILENCE/TEXT→handle_message(normalized) |
| `backend/session.py` | + noise_detected_count, last_noise_ts ; reset() |
| `backend/prompts.py` | + MSG_NOISE_1, MSG_NOISE_2 |
| `backend/engine.py` | + handle_noise() ; _trigger_intent_router reset noise_detected_count/last_noise_ts |
| `tests/test_vapi_stt_phonecall.py` | **Nouveau** : 8 tests (normalize, partial no-op, NOISE, cooldown, handle_noise) |

### Seuils (avant → après)

| Seuil | Avant | Après (défaut, surchargeable env) |
|-------|--------|-------------------------------------|
| transcriptType partial | Traité comme final | Ignoré (no-op) |
| Confidence (transcript vide) | Non utilisé | < NOISE_CONFIDENCE_THRESHOLD (0.35) ⇒ NOISE |
| Confidence (texte court/filler) | Non utilisé | < SHORT_TEXT_MIN_CONFIDENCE (0.50) ⇒ NOISE |
| MIN_TEXT_LENGTH | — | 5 |
| NOISE_COOLDOWN_SEC | — | 2.0 |
| MAX_NOISE_BEFORE_ESCALATE | — | 3 (3e bruit ⇒ INTENT_ROUTER) |

### Tests

- `pytest tests/test_vapi_stt_phonecall.py` : 8 passent.
- `pytest tests/test_engine.py tests/test_report_daily.py` : 18 passent (non-régression).
