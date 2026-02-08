# Fix STT nova-2 → nova-2-phonecall

**Date** : 2025-02-04  
**Version** : V3.1  
**Impact** : Compatibilité Deepgram nova-2-phonecall

## Changements

### Schéma Vapi stable
- Format : `{"content": text}` partout
- No-op (partial) : `{"content": ""}`
- Pas de variation de format

### Partials ignorés (no-op)
- Transcripts "partial" ne déclenchent aucune réponse
- Évite barge-in involontaire
- Évite spam pendant que user parle

### RÈGLE 11 : NOISE ≠ SILENCE
- Bruit ambiant détecté séparément du silence
- Compteur `noise_detected_count` distinct de `empty_message_count`
- Messages progressifs : MSG_NOISE_1 → MSG_NOISE_2 → INTENT_ROUTER
- Cooldown anti-spam : 2 secondes entre messages NOISE

### Seuils calibrés pour nova-2-phonecall
- `NOISE_CONFIDENCE_THRESHOLD = 0.35` (vs 0.7 pour nova-2)
- `SHORT_TEXT_MIN_CONFIDENCE = 0.50` (vs 0.8)
- `MIN_TEXT_LENGTH = 5` caractères
- Configurables via env vars

### Extraction robuste (fallbacks)
- `transcriptType` : 4 fallbacks (transcriptType → type → isFinal → final → "final")
- `transcript` : transcript → content → text
- `confidence` : Peut être None (pas de crash)

### Normalisation fillers prudente
- Suppression : euh/heu/hum/hmm/ben/bah/donc/alors/ponctuation
- Préservation : ok/oui/non (intents critiques)
- Nettoyage : début/fin uniquement (contenu central intact)

### Reset noise (P0-B)
- Reset `noise_detected_count` / `last_noise_ts` **uniquement** quand la réponse a `conv_state` in (`CONFIRMED`, `TRANSFERRED`)
- Pas de reset après chaque message : la condition est dans `_maybe_reset_noise_on_terminal(session, events)` (vérification de `events[0].conv_state`)

### P1 : NOISE sans confidence (message_type)
- Si transcript vide et Vapi n’envoie pas `confidence` : utilisation de `message.type`
- Si `message.type` contient "user-message", "audio", "speech" ou "detected" → classé NOISE (parole détectée, pas transcrite)
- Sinon → SILENCE (vrai silence)

### Logs calibration (sans PII)
- Event : `stt_noise_detected`
- Metrics : call_id, state, confidence, text_len, normalized_len, noise_count
- Pas de transcript complet (privacy)

### Tests
- 12 tests STT phonecall (dont no-op format, confidence None, filler ok, noise reset)
- 18 tests régression (engine + reporting)
- 30/30 tests passent

## Validation terrain

### Tests requis avant prod
1. Parole lente (partials) → pas de spam
2. Bruit à côté → MSG_NOISE_1 (pas silence)
3. Silence réel → MSG_SILENCE_1
4. "ok"/"oui" → préservés

### P0-A : Tester `{"content": ""}` sur staging
- Appeler staging, parler lentement avec pauses ("Bon... (pause) ...jour")
- Vérifier : pas de beep/coupure, pas d’interruption, latence normale  
- Si problème → utiliser `{"content": " "}` (espace) pour no-op

### P0-B : Reset noise uniquement sur terminaux
- Vérifié : `_maybe_reset_noise_on_terminal` ne reset que si `events[0].conv_state in ("CONFIRMED", "TRANSFERRED")`
- Appelée après SILENCE/TEXT mais condition à l’intérieur = pas de reset intempestif

## Calibration post-déploiement

Après 50–100 appels :
- Analyser logs `stt_noise_detected`
- Vérifier distribution confidence NOISE
- Ajuster seuils si besoin :
  - Trop de NOISE (conf > 0.50) → Baisser 0.35 → 0.30
  - Pas assez NOISE → Monter 0.35 → 0.40

## Rollback si besoin

```bash
# Revenir à nova-2 général
# Dans Vapi Dashboard :
# STT Model: nova-2 (non-phonecall)
# Env vars :
# NOISE_CONFIDENCE_THRESHOLD=0.70
# SHORT_TEXT_MIN_CONFIDENCE=0.80
```
