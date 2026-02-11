# RÈGLE ABSOLUE — Ne rien casser (Agent vocal UWi)

Tu travailles sur un agent conversationnel (web + vocal) en **production-grade**.  
Objectif prioritaire : **Fiabilité > Intelligence**.  
Tout changement doit **préserver** les comportements existants et **passer tous les tests**.

## 0) Interdits
- ❌ Ne pas modifier les textes "user-facing" hors `backend/prompts.py` (source de vérité).
- ❌ Ne pas introduire de nouvelles strings utilisateur hardcodées dans le code (sauf cas explicitement demandé).
- ❌ Ne pas changer un comportement existant sans ajouter/mettre à jour un test correspondant.
- ❌ Ne pas contourner les garde-fous anti-boucles (REPEAT, ABANDON, overlap, no_faq, yes_ambiguous, etc.).
- ❌ Ne pas ajouter un second routeur/LLM parallèle (START a **un seul routeur**).

## 1) Invariants à préserver (doivent rester vrais après tes changements)

### START
- START utilise **un seul router** (`route_start`) + override `detect_strong_intent`.
- Les formulations naturelles type "je demande à voir le docteur X" routent vers BOOKING.
- OUT_OF_SCOPE reste en START (non bloquant) et relance "Que souhaitez-vous ?".
- UNCLEAR no_faq : max 2 tours puis guidance/intent_router.

### Booking slots
- Propositions de créneaux **étalées** (jour/période + max 2/jour + fallback 2h).
- En vocal séquentiel : un "non" ne doit jamais proposer un voisin (±90 min) ni la même période refusée.
- Après 2 refus : question préférence ouverte (matin/après-midi/autre jour), avec reset des refus.
- Logs présents : `[SLOT_SEQUENTIAL] seq_skip=...` + `filtered_by_time_constraint=...`.

### Confirmations / Oui ambigu / C'est bien ça
- Normalisation STT unique via `intent_parser.normalize_stt_text()` (ç/accents).
- Pas de transfert immédiat au 1er échec de confirmation : **1 clarification minimum** avant transfert.
- "oui ambigu" géré via `session.awaiting_confirmation` + `yes_ambiguous_count` :
  - 1er oui ambigu → CLARIFY
  - 2e en booking → clarification serrée "oui/non"
  - 3e → intent_router
  - reset du compteur sur intent != YES

### REPEAT
- REPEAT rejoue **exactement** le dernier message envoyé :
  - via `last_say_key/kwargs` si dispo
  - sinon via `last_agent_message`
- REPEAT n'incrémente pas les compteurs d'échec et ne modifie pas `awaiting_confirmation`.
- `add_message(role="agent")` reset `last_say_key` ; seul `_say()` le rétablit.

### Vocal / barge-in
- Les tokens critiques ("non", "le 2", etc.) doivent arriver à l'engine même en overlap.
- Si `session.is_reading_slots=True` : "le 2 / deux / deuxième" doit sélectionner le slot immédiatement (fast-path avant REPEAT/UNCLEAR).

## 2) Checklist obligatoire avant de commit
1) 🔎 Cherche les impacts sur les states : `START`, `WAIT_CONFIRM`, `CONTACT_CONFIRM`, `QUALIF_*`.
2) 🧪 Ajoute ou mets à jour les tests :
   - au minimum 1 test "happy path"
   - au minimum 1 test "edge case" (overlap / oui ambigu / repeat / no_faq)
3) ✅ Lance la suite complète de tests :
   - booking / slots / prompt compliance / engine
4) 📌 Si tu modifies une règle UX : mets à jour `docs/*` concerné (monitoring/playbook/checklist).

## 3) Méthode de travail attendue
- Fais un patch **minimal**.
- Préfère des helpers réutilisables plutôt que du code dupliqué.
- Ajoute des logs utiles mais sans spam.
- Si tu hésites entre "smart" et "safe" : choisis "safe".

## 4) Ce que tu dois livrer
- Un diff clair (fichiers modifiés)
- Les tests ajoutés
- Une note courte "Pourquoi / Risques / Comment vérifier en prod"
