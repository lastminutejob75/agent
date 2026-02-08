# Analyse complète : Engine et script de l’agent

Document de référence pour **audit, refactoring et amélioration** du moteur conversationnel et du script (SYSTEM_PROMPT + prompts).

---

## 1. Vue d’ensemble

### 1.1 Fichiers principaux

| Fichier | Rôle |
|--------|------|
| **backend/engine.py** | Pipeline déterministe, détection d’intent, handlers par état (~2600 lignes) |
| **backend/prompts.py** | Source unique des messages utilisateur, format FAQ, qualification, SlotDisplay |
| **backend/fsm.py** | États et transitions autorisées (ConvState, VALID_TRANSITIONS) |
| **backend/guards.py** | Validation (langue, spam, longueur, filler, nom, contact, slot_choice_flexible) |
| **backend/session.py** | Modèle Session (état, qualif_data, pending_slots, compteurs recovery) |
| **backend/slot_choice.py** | Early commit (detect_slot_choice_early, detect_slot_choice_by_datetime) |
| **backend/config.py** | Seuils (FAQ, session, message, slots, recovery, STT, cabinet) |
| **backend/routes/voice.py** | Webhook Vapi, pré-traitement STT, overlap/crosstalk, reconstruction session |
| **SYSTEM_PROMPT.md** | Règles comportementales pour le LLM (identité, FAQ, qualification, transfert) |
| **docs/REGLES_AGENT_COMPLETES.md** | Synthèse PRD + audit vocal + Règle 11 STT |

### 1.2 Pipeline engine (ordre strict)

```
handle_message(conv_id, user_text)
├── Terminal gate (CONFIRMED/TRANSFERRED → MSG_CONVERSATION_CLOSED)
├── Anti-loop (turn_count > 25 → INTENT_ROUTER)
├── Intent override (CANCEL/MODIFY/TRANSFER/ABANDON/ORDONNANCE → flow dédié)
├── Correction / Répétition (attendez / répétez → rejouer question ou message)
├── Guards (vide → silence 1/2/3 → INTENT_ROUTER ; trop long ; langue ; spam)
├── Session gate (expiration → reset + MSG_SESSION_EXPIRED)
├── Détection intent (YES, NO, BOOKING, FAQ, CANCEL, MODIFY, TRANSFER, ABANDON, ORDONNANCE)
├── should_trigger_intent_router → INTENT_ROUTER si seuils dépassés
├── NO contextuel → handle_no_contextual (selon état)
└── Dispatch par état :
    ├── INTENT_ROUTER → _handle_intent_router
    ├── PREFERENCE_CONFIRM → _handle_preference_confirm
    ├── QUALIF_NAME / QUALIF_MOTIF / QUALIF_PREF / QUALIF_CONTACT → _handle_qualification
    ├── AIDE_CONTACT → _handle_aide_contact
    ├── WAIT_CONFIRM → _handle_booking_confirm
    ├── CANCEL_* → _handle_cancel
    ├── MODIFY_* → _handle_modify
    ├── ORDONNANCE_* → _handle_ordonnance_*
    ├── CLARIFY → _handle_clarify
    ├── CONTACT_CONFIRM → _handle_contact_confirm
    ├── START → first message (YES → booking, NO → CLARIFY, BOOKING → _start_booking_with_extraction…)
    ├── FAQ_ANSWERED → suite (YES/BOOKING, NO/ABANDON, ou FAQ)
    └── Fallback → TRANSFERRED
```

Toute réponse passe par **safe_reply()** (aucun silence, pas de liste d’events vide).

---

## 2. États et flux (FSM + états réels)

### 2.1 FSM formelle (fsm.py)

- **START** → FAQ_ANSWERED, QUALIF_NAME, TRANSFERRED  
- **QUALIF_NAME** → QUALIF_MOTIF, TRANSFERRED  
- **QUALIF_MOTIF** → QUALIF_PREF, AIDE_MOTIF, TRANSFERRED  
- **AIDE_MOTIF** → QUALIF_PREF, TRANSFERRED  
- **QUALIF_PREF** → QUALIF_CONTACT, TRANSFERRED  
- **QUALIF_CONTACT** → WAIT_CONFIRM, TRANSFERRED  
- **WAIT_CONFIRM** → CONFIRMED, TRANSFERRED  
- **CONFIRMED** / **TRANSFERRED** : terminaux  

États utilisés dans l’engine mais **hors FSM** (non validés par `validate_transition`) :  
INTENT_ROUTER, PREFERENCE_CONFIRM, AIDE_CONTACT, CLARIFY, CONTACT_CONFIRM, CANCEL_NAME, CANCEL_NO_RDV, CANCEL_CONFIRM, MODIFY_*, ORDONNANCE_*.

### 2.2 Flux booking (résumé)

1. **START** : first message → YES → QUALIF_NAME (ou _start_booking_with_extraction si entités)  
2. **QUALIF_NAME** → nom valide → _next_qualif_step (motif ou pref selon config)  
3. **QUALIF_MOTIF** → motif valide / non générique → QUALIF_PREF (ou AIDE_MOTIF 1 fois)  
4. **QUALIF_PREF** → préférence (matin/après-midi) → PREFERENCE_CONFIRM → oui → _propose_slots  
5. **QUALIF_CONTACT** → contact valide → _propose_slots (ou CONTACT_CONFIRM si caller ID)  
6. **_propose_slots** → WAIT_CONFIRM + liste 3 créneaux  
7. **WAIT_CONFIRM** :  
   - early commit (oui 1, le premier, vendredi 14h si 1 match) → « C’est bien ça ? » (reste WAIT_CONFIRM, pending_slot_choice)  
   - « oui » après early commit → QUALIF_CONTACT ou CONTACT_CONFIRM  
   - choix 1/2/3 (ou flexible) → QUALIF_CONTACT ou CONTACT_CONFIRM  
   - échec → clarification puis INTENT_ROUTER ou TRANSFERRED (CONFIRM_RETRY_MAX)  
8. **CONTACT_CONFIRM** → oui → book_slot → CONFIRMED  

---

## 3. Script et messages (SYSTEM_PROMPT + prompts)

### 3.1 SYSTEM_PROMPT.md (résumé)

- Identité : agent d’accueil, fiabilité > intelligence.  
- Règles : FAQ ≥ 80 %, une question à la fois, pas d’action sans confirmation, français uniquement.  
- Jamais de silence : phrase de transfert ou une question de qualification.  
- FAQ : format « [Réponse] + Source : FAQ_ID ».  
- Qualification : nom → motif → créneau → contact (formats fermés).  
- Flow RDV : 3 créneaux, confirmation « oui 1/2/3 », gestion interruptions (validations rapides, ne pas redemander « un, deux, trois » après « Oui ! »).  
- Transfert : triggers (FAQ < 80 %, trop long, vide, spam, langue, non-conformité, doute).  
- Cas limites : messages vides/long/langue/spam/session.  

**Écart connu** : SYSTEM_PROMPT dit « Oui / Oui ! = premier créneau ». Le code P0.5 n’accepte plus « oui » seul comme choix (early commit uniquement avec marqueur ou jour+heure unique). Il faudrait aligner le prompt sur le comportement réel (confirmation « c’est bien ça ? » + « oui » pour valider le premier créneau).

### 3.2 prompts.py (extraits clés)

- **Silence / bruit / unclear** : MSG_SILENCE_1/2, MSG_NOISE_1/2, MSG_UNCLEAR_1, MSG_VOCAL_CROSSTALK_ACK, MSG_OVERLAP_*.  
- **Guards** : MSG_EMPTY_MESSAGE, MSG_TOO_LONG, MSG_FRENCH_ONLY, MSG_SESSION_EXPIRED, MSG_TRANSFER.  
- **Qualification** : get_qualif_question, get_clarification_message (name, preference, phone, slot_choice), MSG_QUALIF_*_INTENT_1/2.  
- **Booking** : MSG_CONFIRM_INSTRUCTION_*, format_slot_proposal, format_slot_early_confirm, MSG_SLOT_EARLY_CONFIRM.  
- **Intent router** : MSG_INTENT_ROUTER, VOCAL_INTENT_ROUTER.  
- **Cancel / Modify / Ordonnance** : VOCAL_CANCEL_*, MSG_CANCEL_*, etc.  

Tout message affiché à l’utilisateur devrait venir de `prompts.py` (aucun hardcode dans l’engine).

---

## 4. Points forts

- **Pipeline déterministe** : ordre fixe, pas de LLM pour le routage.  
- **Une source de vérité** pour les textes : prompts.py.  
- **Recovery progressif** : clarification puis INTENT_ROUTER (menu), pas de transfert direct au premier échec.  
- **Guards** : langue, longueur, spam, filler contextuel par état.  
- **Early commit** : choix non ambigu (oui 1, le premier, vendredi 14h si 1 slot) + confirmation « c’est bien ça ? ».  
- **Anti-faux positifs** : chiffre seul uniquement « 1 »/« 2 »/« 3 », sinon marqueur ou jour+heure unique.  
- **Vocal** : overlap/crosstalk, semi-sourd (speaking_until_ts), mots critiques toujours traités.  
- **Intent override** : CANCEL/MODIFY/TRANSFER/ABANDON/ORDONNANCE coupent le flow en cours.  
- **Safe_reply** : aucun message utilisateur ne produit une réponse vide.  

---

## 5. Pistes d’amélioration

### 5.1 Structure et lisibilité

| Piste | Détail |
|-------|--------|
| **Découper engine.py** | ~2600 lignes : extraire les handlers par flow dans des modules (e.g. `engine_booking.py`, `engine_cancel.py`, `engine_qualif.py`) et garder dans `engine.py` le pipeline + dispatch. |
| **FSM étendue** | Inclure INTENT_ROUTER, PREFERENCE_CONFIRM, CONTACT_CONFIRM, CANCEL_*, MODIFY_*, ORDONNANCE_* dans fsm.py et utiliser validate_transition() partout pour éviter des états « invisibles ». |
| **Constantes d’états** | Remplacer les strings en dur ("QUALIF_NAME", "WAIT_CONFIRM"…) par des constantes (ConvState ou autre enum) pour limiter les typos. |

### 5.2 Comportement et cohérence

| Piste | Détail |
|-------|--------|
| **SYSTEM_PROMPT vs code** | Aligner le prompt avec le fait que « oui » seul ne choisit plus le créneau 1 ; décrire la séquence : early commit → « c’est bien ça ? » → « oui » = validation. |
| **Ordre qualification** | get_next_missing_field(skip_contact=True) peut faire NAME → PREF sans MOTIF (si motif non requis). Documenter clairement le flow « avec/sans motif » et les cas où on saute le motif. |
| **CONFIRM_RETRY_MAX = 1** | Une seule redemande en WAIT_CONFIRM puis transfert ; selon produit, envisager 2 redemandes (RECOVERY_LIMITS slot_choice=3 déjà utilisé pour INTENT_ROUTER). |

### 5.3 Robustesse

| Piste | Détail |
|-------|--------|
| **Reconstruction session (voice)** | _reconstruct_session_from_history : utile après redémarrage ; ne peut pas retrouver pending_slots. Option : persister les 3 derniers slots proposés (ex. dans session_store) pour pouvoir les reproposer en WAIT_CONFIRM. |
| **Erreurs tools_booking** | get_slots_for_display / book_slot : en cas d’exception, le fallback est souvent « transfert ». Ajouter des messages dédiés (ex. « Problème d’agenda, je vous transfère ») et du logging structuré. |
| **Double validation** | En WAIT_CONFIRM, après early commit, « oui » est accepté comme confirmation ; s’assurer qu’aucun autre intent (ex. BOOKING) ne réutilise ce « oui » dans un autre sens. |

### 5.4 Vocal (Vapi)

| Piste | Détail |
|-------|--------|
| **Estimation TTS** | estimate_tts_duration : actuellement ~13 car/s ; vérifier avec les voix réelles (langue, débit) et ajuster ou rendre configurable. |
| **Logs overlap** | Ajouter un log explicite (ex. overlap_detected, overlap_ignored, critical_overlap_allowed) pour le debug et le tuning des fenêtres. |
| **Reconstruction + WAIT_CONFIRM** | En WAIT_CONFIRM reconstruit, les slots sont re-fetched au prochain message ; le message utilisateur peut ne plus correspondre aux nouveaux slots. Documenter ou limiter les changements de créneaux entre deux tours. |

### 5.5 Tests et maintenabilité

| Piste | Détail |
|-------|--------|
| **Tests par flow** | Regrouper les tests par flux (booking, cancel, modify, intent_router, qualif_name, etc.) pour faciliter les régressions. |
| **Scénarios E2E** | Quelques scénarios complets (START → CONFIRMED ou TRANSFERRED) avec messages réels (y compris « vendredi 14h », « oui 1 » → « oui »). |
| **Compliance prompts** | test_prompt_compliance.py : s’assurer que chaque constante utilisée dans l’engine est couverte et que les changements de wording passent par ce fichier. |

### 5.6 Performance et coût

| Piste | Détail |
|-------|--------|
| **Chargement session** | Déjà optimisé (cache mémoire, SQLite). Si volumétrie forte, envisager cache distribué ou TTL court pour les sessions inactives. |
| **FAQ** | rapidfuzz : seuil 80 % ; pas d’appel LLM pour le routage. Possible d’ajouter un cache des dernières questions FAQ (question normalisée → faq_id) pour éviter des recherches répétées. |

---

## 6. Résumé des règles anti-faux-positifs (slot_choice)

- **Chiffre seul** : accepté uniquement si le message normalisé est exactement « 1 », « 2 » ou « 3 ».  
- **En phrase** : un chiffre n’est accepté qu’avec un marqueur (oui 1, choix 2, option 3, créneau 1, numéro 2, n° 3, le 1/2/3, premier/deuxième/troisième).  
- **« Oui » seul** : jamais interprété comme choix de créneau.  
- **Jour seul / heure seule** : refusé (vendredi → None, 14h → None).  
- **Jour+heure** : accepté uniquement si exactement un slot correspond ; 0 ou >1 → None.  

Ces règles sont implémentées dans `backend/slot_choice.py` et utilisées dans `_handle_booking_confirm`.

---

## 7. Prochaines étapes suggérées

1. **Court terme** : Aligner SYSTEM_PROMPT.md avec le comportement early commit + « c’est bien ça ? » (pas « oui » seul = créneau 1).  
2. **Moyen terme** : Étendre la FSM aux états réels et utiliser validate_transition dans l’engine ; extraire les gros handlers (booking, cancel, modify, qualif) dans des modules dédiés.  
3. **Optionnel** : Messages d’erreur explicites pour tools_booking ; logs structurés overlap/crosstalk ; 1–2 scénarios E2E complets (vocal + web).

Ce document peut servir de base pour un audit ciblé (ex. « tout ce qui touche au silence » ou « tout ce qui touche à la confirmation de créneau ») et pour prioriser les évolutions.
