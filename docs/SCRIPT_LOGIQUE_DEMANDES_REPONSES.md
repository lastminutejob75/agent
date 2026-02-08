# Script : logique des demandes et réponses

Document de référence pour analyser les **liens entre les demandes utilisateur** et les **réponses possibles** de l’agent (états, intents, messages).

---

## 1. États de la conversation (session.state)

| État | Description | Terminal |
|------|-------------|----------|
| **START** | Accueil, question ouverte "Comment puis-je vous aider ?" | Non |
| **CLARIFY** | Après "non" en START → clarification (question ou RDV ?) | Non |
| **POST_FAQ** | Après une réponse FAQ, relance "Souhaitez-vous autre chose ?" | Non |
| **POST_FAQ_CHOICE** | "Oui" ambigu après FAQ → disambiguation (RDV ou question ?) | Non |
| **QUALIF_NAME** | Demande du nom (prise de RDV) | Non |
| **QUALIF_MOTIF** | Demande du motif (désactivé en vocal) | Non |
| **AIDE_MOTIF** | Aide sur le motif (1 fois puis transfert) | Non |
| **QUALIF_PREF** | Demande préférence (matin / après-midi) | Non |
| **PREFERENCE_CONFIRM** | Confirmation préférence inférée ("Plutôt le matin, c’est bien ça ?") | Non |
| **QUALIF_CONTACT** | Demande contact (email / téléphone) — souvent après choix de créneau | Non |
| **CONTACT_CONFIRM** | Confirmation du numéro/email ("Le 06… c’est bien ça ?") | Non |
| **WAIT_CONFIRM** | Créneaux proposés, attente "oui 1", "oui 2" ou "oui 3" | Non |
| **INTENT_ROUTER** | Menu 1/2/3/4 (RDV, annuler/modifier, question, conseiller) | Non |
| **CANCEL_NAME** | Annulation : demande du nom | Non |
| **CANCEL_NO_RDV** | Annulation : RDV non trouvé (vérifier / humain) | Non |
| **CANCEL_CONFIRM** | Annulation : confirmation "Voulez-vous annuler ce RDV ?" | Non |
| **MODIFY_NAME** | Modification : demande du nom | Non |
| **MODIFY_NO_RDV** | Modification : RDV non trouvé | Non |
| **MODIFY_CONFIRM** | Modification : confirmation "Voulez-vous déplacer ce RDV ?" | Non |
| **ORDONNANCE_CHOICE** | Ordonnance : RDV ou message ? | Non |
| **ORDONNANCE_MESSAGE** | Ordonnance : saisie du message | Non |
| **ORDONNANCE_PHONE_CONFIRM** | Ordonnance : confirmation téléphone | Non |
| **AIDE_CONTACT** | Aide sur le contact (guidage email/téléphone) | Non |
| **CONFIRMED** | Fin normale (RDV confirmé, au revoir, abandon, etc.) | Oui |
| **TRANSFERRED** | Transfert vers un conseiller | Oui |
| **EMERGENCY** | Urgence médicale détectée | Oui |

---

## 2. Intents détectés (detect_intent / detect_strong_intent)

| Intent | Exemples de phrases utilisateur | Priorité |
|--------|----------------------------------|----------|
| **YES** | "oui", "ouais", "ok", "d'accord" | Haute (START) |
| **NO** | "non", "non merci" | Haute |
| **BOOKING** | "je veux un rdv", "prendre rendez-vous", "réserver" | Haute |
| **CANCEL** | "annuler", "annulation", "annuler mon rdv" | Forte (override) |
| **MODIFY** | "modifier", "changer", "déplacer mon rdv" | Forte (override) |
| **TRANSFER** | "parler à quelqu'un", "conseiller", "humain" (phrase ≥14 car.) | Forte (override) |
| **ABANDON** | "c'est tout", "rien", "au revoir" | Forte (override) |
| **ORDONNANCE** | "ordonnance", "renouvellement ordonnance" | Forte (override) |
| **FAQ** | Tout le reste (horaires, adresse, question…) → recherche FAQ | Par défaut |
| **UNCLEAR** | Message vide / non reconnu | Fallback |

---

## 3. Flux principal : START → réponses possibles

### 3.1 Entrée : état START (accueil)

**Message agent (ex. vocal)** : `"Bonjour, {Cabinet}. Comment puis-je vous aider ?"`

| Demande / comportement utilisateur | Réponse agent | État suivant |
|------------------------------------|---------------|--------------|
| **YES** ("oui", "ok") | Demande du nom (qualif RDV) | QUALIF_NAME |
| **NO** | "Pas de souci ! Je peux vous renseigner…" (clarification) | CLARIFY |
| **BOOKING** ("je veux un rdv") | Démarrage booking (extraction entités) | QUALIF_NAME ou QUALIF_PREF |
| **CANCEL** | "Bien sûr. À quel nom est le rendez-vous ?" | CANCEL_NAME |
| **MODIFY** | "Bien sûr. À quel nom est le rendez-vous ?" | MODIFY_NAME |
| **TRANSFER** (phrase longue) | Message transfert | TRANSFERRED |
| **ABANDON** | "Pas de souci. N'hésitez pas à nous recontacter…" | CONFIRMED |
| **ORDONNANCE** | "Pour une ordonnance, rendez-vous ou message ?" | ORDONNANCE_CHOICE |
| **FAQ** (match FAQ) | Réponse FAQ + "Souhaitez-vous autre chose ?" | POST_FAQ |
| **FAQ** (pas de match, 1re fois) | "Je n'ai pas bien compris. Rendez-vous ou question ?" | START (start_unclear_count=1) |
| **FAQ** (pas de match, 2e fois) | "Je peux vous aider : RDV, horaires, adresse, services. Que souhaitez-vous ?" | START (start_unclear_count=2) |
| **FAQ** (pas de match, 3e fois) | Menu 1/2/3/4 (INTENT_ROUTER) | INTENT_ROUTER |

### 3.2 Messages associés (prompts)

- **Clarification 1 (START vague ×1)** : `VOCAL_START_CLARIFY_1` / `MSG_START_CLARIFY_1_WEB`  
  → *"Je n'ai pas bien compris. Souhaitez-vous prendre rendez-vous, ou avez-vous une question ?"*
- **Guidage (START vague ×2)** : `VOCAL_START_GUIDANCE` / `MSG_START_GUIDANCE_WEB`  
  → *"Je peux vous aider à prendre rendez-vous, répondre à vos questions sur nos horaires, notre adresse, ou nos services. Que souhaitez-vous ?"*
- **Menu (START vague ×3)** : `VOCAL_INTENT_ROUTER` / `MSG_INTENT_ROUTER`  
  → *"Dites un pour prendre rendez-vous… deux pour annuler… trois pour une question… quatre pour un conseiller."*

---

## 4. INTENT_ROUTER (menu 1/2/3/4)

**Message agent** : `VOCAL_INTENT_ROUTER` / `MSG_INTENT_ROUTER`  
*"Dites un pour prendre rendez-vous. Dites deux pour annuler ou modifier. Dites trois pour poser une question. Ou dites quatre pour parler à un conseiller."*

| Réponse utilisateur | Interprétation | Réponse / action | État suivant |
|---------------------|----------------|------------------|--------------|
| "un", "1", "premier", "rdv", "rendez-vous" | Choix 1 | Demande du nom | QUALIF_NAME |
| "deux", "2", "annuler", "modifier" | Choix 2 | Démarrage annulation | CANCEL_NAME |
| "trois", "3", "question" | Choix 3 | "Quelle est votre question ?" | START |
| "quatre", "4", "humain", "conseiller" | Choix 4 | Message transfert | TRANSFERRED |
| Incompréhension (×3) | Échec répété | Transfert (VOCAL_STILL_UNCLEAR / MSG_TRANSFER) | TRANSFERRED |
| Autre | Retry | "Dites un, deux, trois ou quatre, s'il vous plaît." | INTENT_ROUTER |

---

## 5. Flux prise de RDV (booking)

| État | Question / message agent | Réponse utilisateur typique | État suivant |
|------|---------------------------|------------------------------|--------------|
| QUALIF_NAME | "À quel nom, s'il vous plaît ?" | "Martin Dupont" | QUALIF_PREF (ou extraction → slot) |
| QUALIF_PREF | "Vous préférez le matin ou l'après-midi ?" | "Le matin" / "L'après-midi" | Proposition créneaux |
| WAIT_CONFIRM | "Voici 3 créneaux… Répondez par oui 1, oui 2 ou oui 3" | "oui 2" / "le deux" | Demande contact |
| QUALIF_CONTACT / CONTACT_CONFIRM | "Quel numéro pour vous rappeler ?" / "Le 06… c'est bien ça ?" | Numéro / "oui" | Confirmation RDV |
| Confirmation | "Parfait, c'est noté. Bonne journée." | — | CONFIRMED |

**Messages clés** :  
`VOCAL_NAME_ASK`, `get_qualif_question("pref")`, `format_slot_list_vocal`, `MSG_CONFIRM_INSTRUCTION_VOCAL`, `VOCAL_CONTACT_ASK`, `VOCAL_CONTACT_CONFIRM`, `VOCAL_BOOKING_CONFIRMED`, `VOCAL_GOODBYE_AFTER_BOOKING`.

**Recovery** : après N échecs (nom, préférence, créneau, contact) → INTENT_ROUTER ou transfert selon `RECOVERY_LIMITS` et compteurs.

---

## 6. Flux FAQ

| Contexte | Demande utilisateur | Réponse agent | État suivant |
|----------|---------------------|---------------|--------------|
| START / POST_FAQ | Question (ex. "Vos horaires ?") | Réponse FAQ + "Souhaitez-vous autre chose ?" | POST_FAQ |
| POST_FAQ | "Non" / "C'est tout" | "Merci de votre appel. Bonne journée." | CONFIRMED |
| POST_FAQ | "Oui" (ambigu) | "Dites : rendez-vous, ou : question." | POST_FAQ_CHOICE |
| POST_FAQ_CHOICE | "Rendez-vous" / "RDV" | Démarrage booking | QUALIF_NAME |
| POST_FAQ_CHOICE | "Question" / "?" | Reprise FAQ (state START) | START |

**Format réponse FAQ** : `format_faq_response(answer, faq_id)` → texte + "Source : FAQ_XXX". En vocal, pas de "Source" + relance `VOCAL_FAQ_FOLLOWUP`.

---

## 7. Flux Annulation (CANCEL)

| État | Message agent | Réponse utilisateur | État suivant |
|------|---------------|---------------------|--------------|
| CANCEL_NAME | "À quel nom est le rendez-vous ?" | "Dupont" | Recherche RDV |
| (RDV trouvé) | "Vous avez un RDV {slot}. Voulez-vous l'annuler ?" | "Oui" / "Non" | CANCEL_CONFIRM |
| CANCEL_CONFIRM | — | "Oui" → annulation, "Non" → maintien | CONFIRMED |
| (RDV non trouvé) | "Je ne trouve pas de RDV… Vérifier ou humain ?" | "vérifier" / "humain" | CANCEL_NAME ou TRANSFERRED |

**Messages** : `VOCAL_CANCEL_ASK_NAME`, `VOCAL_CANCEL_CONFIRM`, `VOCAL_CANCEL_DONE`, `VOCAL_CANCEL_KEPT`, `VOCAL_CANCEL_NOT_FOUND`, etc.

---

## 8. Flux Modification (MODIFY)

Même logique que CANCEL pour la recherche (MODIFY_NAME, MODIFY_NO_RDV).  
Puis MODIFY_CONFIRM : "Voulez-vous le déplacer ?" → Oui → QUALIF_PREF (nouveau créneau) ; Non → CONFIRMED.  
Messages : `VOCAL_MODIFY_ASK_NAME`, `VOCAL_MODIFY_CONFIRM`, `VOCAL_MODIFY_CANCELLED`, etc.

---

## 9. Flux Ordonnance

| État | Message agent | Réponse utilisateur | État suivant |
|------|---------------|---------------------|--------------|
| ORDONNANCE_CHOICE | "Rendez-vous ou que l'on transmette un message ?" | "rdv" / "message" | QUALIF_NAME ou ORDONNANCE_MESSAGE |
| ORDONNANCE_MESSAGE | Saisie message + téléphone | Message + numéro | ORDONNANCE_PHONE_CONFIRM → CONFIRMED |

---

## 10. Triggers vers INTENT_ROUTER (résumé)

- **START** : 3 incompréhensions consécutives (start_unclear_count ≥ 3).
- **FAQ** (hors START) : 2 ou 3 no-match (no_match_turns) selon branche.
- **Silence** : 3 messages vides (empty_message_count ≥ 3).
- **Bruit STT** : 3 détections bruit (noise_detected_count ≥ 3).
- **Nom** : 3 échecs (name_fails ≥ 3) → `VOCAL_NAME_FAIL_3_INTENT_ROUTER` puis menu.
- **Préférence / créneau / contact** : après N échecs (RECOVERY_LIMITS) → INTENT_ROUTER.
- **CANCEL / MODIFY** : après échecs (vérifier / humain) → INTENT_ROUTER ou TRANSFERRED.
- **Anti-boucle** : turn_count > 25 → INTENT_ROUTER.
- **global_recovery_fails** ≥ 3 → INTENT_ROUTER.

---

## 11. Récap : liens Demande → Réponse (principaux)

| Demande (exemples) | Intent | Réponse type | État suivant |
|--------------------|--------|--------------|--------------|
| "oui" | YES | Demande nom | QUALIF_NAME |
| "je veux un rdv" | BOOKING | Demande nom / préférence | QUALIF_NAME / QUALIF_PREF |
| "annuler" | CANCEL | À quel nom ? | CANCEL_NAME |
| "modifier" | MODIFY | À quel nom ? | MODIFY_NAME |
| "horaires" / question FAQ | FAQ | Réponse FAQ + relance | POST_FAQ |
| "euh" / vague (×1) | FAQ (no match) | Rendez-vous ou question ? | START |
| "euh" / vague (×2) | FAQ (no match) | RDV, horaires, adresse, services. Que souhaitez-vous ? | START |
| "euh" / vague (×3) | FAQ (no match) | Menu 1/2/3/4 | INTENT_ROUTER |
| "un" / "1" (dans INTENT_ROUTER) | Choix 1 | Demande nom | QUALIF_NAME |
| "quatre" / "conseiller" (dans INTENT_ROUTER) | Choix 4 | Transfert | TRANSFERRED |
| "oui 2" (dans WAIT_CONFIRM) | Choix créneau 2 | Demande contact | QUALIF_CONTACT / CONTACT_CONFIRM |

---

## 12. Fichiers de référence

| Fichier | Rôle |
|---------|------|
| `backend/fsm.py` | États et transitions autorisées (ConvState, VALID_TRANSITIONS) |
| `backend/engine.py` | Détection intent, routing par état, handlers (_handle_faq, _handle_intent_router, etc.) |
| `backend/prompts.py` | Tous les messages (VOCAL_*, MSG_*, get_qualif_question, get_message) |
| `backend/guards.py` | Langue, spam, longueur (avant routing) |

Ce document peut servir de base pour des tests de scénarios ou pour analyser un parcours utilisateur de bout en bout.
