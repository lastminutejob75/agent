# Script agent — tout-en-un : états, flux, demandes/réponses, répliques

Document unique regroupant : **états**, **intents**, **flux** (START, FAQ, POST_FAQ, booking, annulation, modification, ordonnance, INTENT_ROUTER), **liens demande → réponse** et **répertoire des répliques** (clés `prompts.py`).  
Source de vérité des messages : `backend/prompts.py`.

---

# Partie 1 — États de la conversation (session.state)

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
| **PREFERENCE_CONFIRM** | Confirmation préférence inférée ("Plutôt le matin, c'est bien ça ?") | Non |
| **QUALIF_CONTACT** | Demande contact (email / téléphone) | Non |
| **CONTACT_CONFIRM** | Confirmation du numéro/email ("Le 06… c'est bien ça ?") | Non |
| **WAIT_CONFIRM** | Créneaux proposés, attente "oui 1", "oui 2" ou "oui 3" | Non |
| **INTENT_ROUTER** | Menu 1/2/3/4 (RDV, annuler/modifier, question, conseiller) | Non |
| **CANCEL_NAME** / **CANCEL_NO_RDV** / **CANCEL_CONFIRM** | Annulation | Non |
| **MODIFY_NAME** / **MODIFY_NO_RDV** / **MODIFY_CONFIRM** | Modification | Non |
| **ORDONNANCE_CHOICE** / **ORDONNANCE_MESSAGE** / **ORDONNANCE_PHONE_CONFIRM** | Ordonnance | Non |
| **AIDE_CONTACT** | Aide contact (guidage email/téléphone) | Non |
| **CONFIRMED** | Fin normale | Oui |
| **TRANSFERRED** | Transfert conseiller | Oui |
| **EMERGENCY** | Urgence médicale | Oui |

**Transitions** : `backend/fsm.py` (ConvState, VALID_TRANSITIONS).

---

# Partie 2 — Intents détectés

| Intent | Exemples utilisateur | Priorité |
|--------|----------------------|----------|
| **YES** | "oui", "ouais", "ok", "d'accord" | Haute (START) |
| **NO** | "non", "non merci" | Haute |
| **BOOKING** | "je veux un rdv", "prendre rendez-vous", "réserver" | Haute |
| **CANCEL** | "annuler", "annulation", "annuler mon rdv" | Forte (override) |
| **MODIFY** | "modifier", "changer", "déplacer mon rdv" | Forte (override) |
| **TRANSFER** | "parler à quelqu'un", "conseiller", "humain" (phrase ≥14 car.) | Forte (override) |
| **ABANDON** | "c'est tout", "rien", "au revoir" | Forte (override) |
| **ORDONNANCE** | "ordonnance", "renouvellement ordonnance" | Forte (override) |
| **FAQ** | Horaires, adresse, question… → recherche FAQ | Par défaut |
| **UNCLEAR** | Message vide / non reconnu | Fallback |

Détection : `detect_intent()` / `detect_strong_intent()` dans `backend/engine.py`.

---

# Partie 3 — Flux START (accueil)

**Message agent (vocal)** : `"Bonjour, {business_name}. Comment puis-je vous aider ?"` (VOCAL_SALUTATION / get_vocal_greeting).

| Demande / comportement | Réponse agent | État suivant |
|------------------------|---------------|--------------|
| **YES** ("oui", "ok") | Demande du nom | QUALIF_NAME |
| **NO** | Clarification (question ou RDV ?) | CLARIFY |
| **BOOKING** | Démarrage booking (extraction entités) | QUALIF_NAME ou QUALIF_PREF |
| **CANCEL** | "À quel nom est le rendez-vous ?" | CANCEL_NAME |
| **MODIFY** | "À quel nom est le rendez-vous ?" | MODIFY_NAME |
| **TRANSFER** (phrase longue) | Message transfert | TRANSFERRED |
| **ABANDON** | Au revoir poli | CONFIRMED |
| **ORDONNANCE** | "Rendez-vous ou message ?" | ORDONNANCE_CHOICE |
| **FAQ** (match) | Réponse FAQ + "Souhaitez-vous autre chose ?" | POST_FAQ |
| **FAQ** (pas de match ×1) | "Je n'ai pas bien compris. Rendez-vous ou question ?" | START |
| **FAQ** (pas de match ×2) | "Je peux vous aider : RDV, horaires, adresse, services. Que souhaitez-vous ?" | START |
| **FAQ** (pas de match ×3) | Menu 1/2/3/4 | INTENT_ROUTER |

**Messages (prompts)** : VOCAL_START_CLARIFY_1, VOCAL_START_GUIDANCE, VOCAL_INTENT_ROUTER.

---

# Partie 4 — INTENT_ROUTER (menu 1/2/3/4)

**Message** : VOCAL_INTENT_ROUTER / MSG_INTENT_ROUTER — *"Dites un pour prendre rendez-vous. Dites deux pour annuler ou modifier. Dites trois pour poser une question. Ou dites quatre pour parler à un conseiller."*

| Réponse utilisateur | Action | État suivant |
|---------------------|--------|--------------|
| "un", "1", "premier", "rdv", "rendez-vous" | Demande du nom | QUALIF_NAME |
| "deux", "2", "annuler", "modifier" | Démarrage annulation | CANCEL_NAME |
| "trois", "3", "question" | "Quelle est votre question ?" | START |
| "quatre", "4", "humain", "conseiller" | Transfert | TRANSFERRED |
| Incompréhension ×3 | Transfert (VOCAL_STILL_UNCLEAR) | TRANSFERRED |
| Autre | "Dites un, deux, trois ou quatre, s'il vous plaît." (MSG_INTENT_ROUTER_RETRY) | INTENT_ROUTER |

---

# Partie 5 — Flux prise de RDV (booking)

| État | Message agent | Réponse typique | État suivant |
|------|---------------|-----------------|--------------|
| QUALIF_NAME | "À quel nom, s'il vous plaît ?" (VOCAL_NAME_ASK) | "Martin Dupont" | QUALIF_PREF |
| QUALIF_PREF | "Vous préférez le matin ou l'après-midi ?" | "Le matin" / "L'après-midi" | Proposition créneaux |
| WAIT_CONFIRM | "Voici 3 créneaux… Répondez par oui 1, oui 2 ou oui 3" | "oui 2" / "le deux" | Demande contact |
| QUALIF_CONTACT / CONTACT_CONFIRM | "Quel numéro ?" / "Le 06… c'est bien ça ?" | Numéro / "oui" | Confirmation RDV |
| — | "Parfait, c'est noté. Bonne journée." (VOCAL_GOODBYE_AFTER_BOOKING) | — | CONFIRMED |

**Recovery** : après N échecs (nom, préférence, créneau, contact) → INTENT_ROUTER ou transfert (RECOVERY_LIMITS).

---

# Partie 6 — Flux FAQ et POST_FAQ

- **Match FAQ** : réponse FAQ + relance (VOCAL_FAQ_FOLLOWUP / MSG_FAQ_FOLLOWUP_WEB) → `session.state = "POST_FAQ"`.
- **Format réponse** : `format_faq_response(answer, faq_id)` ; en vocal pas de "Source : FAQ_XXX", relance uniquement.

**Routage en POST_FAQ** :

| Réponse utilisateur | Action | État suivant |
|---------------------|--------|--------------|
| Non / abandon (NO, ABANDON) | VOCAL_FAQ_GOODBYE / MSG_FAQ_GOODBYE_WEB | CONFIRMED |
| Oui / RDV (YES, BOOKING) | _start_booking_with_extraction | QUALIF_NAME |
| "Oui" seul (ambigu) | "Dites : rendez-vous, ou : question." (POST_FAQ_CHOICE) | POST_FAQ_CHOICE |
| Nouvelle question | state = START → _handle_faq (re-FAQ) | START |

**POST_FAQ_CHOICE** : "Rendez-vous" / "RDV" → booking (QUALIF_NAME) ; "Question" / "?" → re-FAQ (START).

**Comportement cible** :  
User : « Quels sont vos horaires ? » → Agent : « Nous sommes ouverts de 9h à 18h. Puis-je vous aider pour autre chose ? » → POST_FAQ.  
User : « Non merci » → VOCAL_FAQ_GOODBYE → CONFIRMED.  
User : « Oui » → POST_FAQ_CHOICE ; « Je voudrais un rdv » → booking.

---

# Partie 7 — Flux Annulation (CANCEL)

| État | Message agent | Réponse utilisateur | État suivant |
|------|---------------|---------------------|--------------|
| CANCEL_NAME | "À quel nom est le rendez-vous ?" (VOCAL_CANCEL_ASK_NAME) | "Dupont" | Recherche RDV |
| (RDV trouvé) | "Vous avez un RDV {slot}. Vous souhaitez l'annuler ?" (VOCAL_CANCEL_CONFIRM) | "Oui" / "Non" | CANCEL_CONFIRM |
| CANCEL_CONFIRM | — | "Oui" → annulation, "Non" → maintien | CONFIRMED |
| (RDV non trouvé) | "Je ne trouve pas… Vérifier ou humain ?" (VOCAL_CANCEL_NOT_FOUND_VERIFIER_HUMAN) | "vérifier" / "humain" | CANCEL_NAME ou TRANSFERRED |

Messages : VOCAL_CANCEL_ASK_NAME, VOCAL_CANCEL_CONFIRM, VOCAL_CANCEL_DONE, VOCAL_CANCEL_KEPT, VOCAL_CANCEL_NOT_FOUND, etc.

---

# Partie 8 — Flux Modification (MODIFY)

Même logique que CANCEL pour la recherche (MODIFY_NAME, MODIFY_NO_RDV).  
MODIFY_CONFIRM : "Voulez-vous le déplacer ?" → Oui → QUALIF_PREF (nouveau créneau) ; Non → CONFIRMED.  
Messages : VOCAL_MODIFY_ASK_NAME, VOCAL_MODIFY_CONFIRM, VOCAL_MODIFY_CANCELLED, etc.

---

# Partie 9 — Flux Ordonnance

| État | Message agent | Réponse utilisateur | État suivant |
|------|---------------|---------------------|--------------|
| ORDONNANCE_CHOICE | "Rendez-vous ou que l'on transmette un message ?" (VOCAL_ORDONNANCE_ASK_CHOICE) | "rdv" / "message" | QUALIF_NAME ou ORDONNANCE_MESSAGE |
| ORDONNANCE_MESSAGE | Saisie message + téléphone | Message + numéro | ORDONNANCE_PHONE_CONFIRM → CONFIRMED |

---

# Partie 10 — Triggers vers INTENT_ROUTER

- **START** : start_unclear_count ≥ 3.
- **FAQ** (hors START) : no_match_turns 2 ou 3 selon branche.
- **Silence** : empty_message_count ≥ 3.
- **Bruit STT** : noise_detected_count ≥ 3.
- **Nom** : name_fails ≥ 3 → VOCAL_NAME_FAIL_3_INTENT_ROUTER puis menu.
- **Préférence / créneau / contact** : RECOVERY_LIMITS → INTENT_ROUTER.
- **CANCEL / MODIFY** : échecs → INTENT_ROUTER ou TRANSFERRED.
- **Anti-boucle** : turn_count > 25.
- **global_recovery_fails** ≥ 3.

---

# Partie 11 — Récap : liens Demande → Réponse

| Demande (exemples) | Intent | Réponse type | État suivant |
|--------------------|--------|--------------|--------------|
| "oui" | YES | Demande nom | QUALIF_NAME |
| "je veux un rdv" | BOOKING | Demande nom / préférence | QUALIF_NAME / QUALIF_PREF |
| "annuler" | CANCEL | À quel nom ? | CANCEL_NAME |
| "modifier" | MODIFY | À quel nom ? | MODIFY_NAME |
| "horaires" / question FAQ | FAQ | Réponse FAQ + relance | POST_FAQ |
| "euh" / vague ×1 | FAQ (no match) | Rendez-vous ou question ? | START |
| "euh" / vague ×2 | FAQ (no match) | RDV, horaires, adresse, services. Que souhaitez-vous ? | START |
| "euh" / vague ×3 | FAQ (no match) | Menu 1/2/3/4 | INTENT_ROUTER |
| "un" / "1" (dans INTENT_ROUTER) | Choix 1 | Demande nom | QUALIF_NAME |
| "quatre" / "conseiller" (dans INTENT_ROUTER) | Choix 4 | Transfert | TRANSFERRED |
| "oui 2" (dans WAIT_CONFIRM) | Choix créneau 2 | Demande contact | QUALIF_CONTACT / CONTACT_CONFIRM |

---

# Partie 12 — Répertoire des répliques (clés prompts.py)

## Accueil / salutation

| Clé | Dialogue (vocal) |
|-----|------------------|
| VOCAL_SALUTATION | Bonjour, {business_name}. Comment puis-je vous aider ? |
| VOCAL_SALUTATION_NEUTRAL | Bonjour, bienvenue chez {business_name}. Je vous écoute. |
| VOCAL_SALUTATION_SHORT | Bonjour, je vous écoute. |

## Guidage START (question ouverte)

| Clé | Dialogue |
|-----|----------|
| VOCAL_START_CLARIFY_1 | Je n'ai pas bien compris. Souhaitez-vous prendre rendez-vous, ou avez-vous une question ? |
| VOCAL_START_GUIDANCE | Je peux vous aider à prendre rendez-vous, répondre à vos questions sur nos horaires, notre adresse, ou nos services. Que souhaitez-vous ? |
| VOCAL_START_GUIDANCE_SHORT | Je peux vous aider pour : un rendez-vous, nos horaires, notre adresse, ou autre chose. Que voulez-vous ? |

## Silence / bruit / incompréhension

| Clé | Dialogue |
|-----|----------|
| MSG_SILENCE_1 | Je n'ai rien entendu. Pouvez-vous répéter ? |
| MSG_SILENCE_2 | Êtes-vous toujours là ? |
| MSG_NOISE_1 | Excusez-moi. Je vous entends mal. Pouvez-vous répéter, s'il vous plaît ? |
| VOCAL_NOT_UNDERSTOOD | Excusez-moi, je n'ai pas bien compris. Pouvez-vous reformuler ? |
| MSG_FAQ_REFORMULATE_VOCAL | Excusez-moi. Je n'ai pas bien saisi. Pouvez-vous reformuler, s'il vous plaît ? |

## Transfert / clôture

| Clé | Dialogue |
|-----|----------|
| MSG_TRANSFER | Je vous transfère vers un conseiller. Ne quittez pas, s'il vous plaît. |
| VOCAL_TRANSFER_HUMAN | Je vous transfère vers un conseiller qui pourra vous aider. Un instant, s'il vous plaît. |
| VOCAL_TRANSFER_COMPLEX | Je comprends. Je vais vous mettre en relation avec quelqu'un qui pourra mieux vous aider. Un instant. |
| VOCAL_STILL_UNCLEAR | Pas de problème, je vais vous passer quelqu'un qui pourra mieux vous aider. Un instant. |
| VOCAL_GOODBYE | Merci de votre appel. Bonne journée. |
| VOCAL_GOODBYE_AFTER_BOOKING | Merci, à très bientôt. Bonne journée. |
| VOCAL_FAQ_GOODBYE | Merci de votre appel. Bonne journée. |
| VOCAL_USER_ABANDON | Pas de souci. N'hésitez pas à nous recontacter si besoin. Bonne journée. |

## FAQ

| Clé | Dialogue |
|-----|----------|
| VOCAL_FAQ_FOLLOWUP | Souhaitez-vous autre chose ? |
| VOCAL_FAQ_TO_BOOKING | Très bien. Pour le rendez-vous, à quel nom, s'il vous plaît ? |
| VOCAL_POST_FAQ_CHOICE | Dites : rendez-vous, ou : question. |
| VOCAL_POST_FAQ_DISAMBIG | Vous voulez prendre rendez-vous, ou poser une question ? |

## Qualification — nom

| Clé | Dialogue |
|-----|----------|
| VOCAL_NAME_ASK | Pour le rendez-vous, à quel nom, s'il vous plaît ? |
| VOCAL_NAME_FAIL_1 | Excusez-moi. Je n'ai pas bien saisi votre nom. Pouvez-vous répéter, s'il vous plaît ? |
| VOCAL_NAME_FAIL_2 | Votre nom et prénom. Par exemple : Martin Dupont. |

## Qualification — préférence (matin / après-midi)

| Clé | Dialogue |
|-----|----------|
| VOCAL_PREF_ASK | Vous préférez plutôt le matin ou l'après-midi ? |
| VOCAL_PREF_FAIL_1 | Je vous écoute. Plutôt le matin, ou l'après-midi ? |
| VOCAL_PREF_CONFIRM_MATIN | D'accord, plutôt le matin. C'est bien ça ? |
| VOCAL_PREF_CONFIRM_APRES_MIDI | D'accord, plutôt l'après-midi. C'est bien ça ? |
| MSG_PREFERENCE_CONFIRM | D'accord, donc plutôt {pref}, c'est bien ça ? |

## Choix de créneau (1, 2, 3)

| Clé | Dialogue |
|-----|----------|
| VOCAL_CONFIRM_SLOTS (format_slot_list_vocal) | Trois créneaux : un — {slot1}, deux — {slot2}, trois — {slot3}. Dites un, deux ou trois. |
| MSG_CONFIRM_INSTRUCTION_VOCAL | Pour confirmer, dites : oui un, oui deux ou oui trois. |
| VOCAL_SLOT_FAIL_1 | Je n'ai pas bien saisi. Vous pouvez dire : un, deux ou trois, s'il vous plaît. |
| VOCAL_SLOT_FAIL_2 | Par exemple : je prends le deux. Lequel vous convient ? |

## Contact (téléphone / email)

| Clé | Dialogue |
|-----|----------|
| VOCAL_CONTACT_ASK | Pour vous recontacter, j'ai besoin d'un téléphone ou d'un email. Vous préférez lequel ? |
| VOCAL_CONTACT_EMAIL | Très bien. Quelle adresse email ? |
| VOCAL_CONTACT_PHONE | Parfait. Et votre numéro de téléphone pour vous rappeler ? |
| VOCAL_CONTACT_CONFIRM / VOCAL_CONTACT_CONFIRM_SHORT | Le {phone_formatted}, c'est bien ça ? |
| VOCAL_CONTACT_CONFIRM_OK | Parfait, c'est noté. |
| VOCAL_PHONE_FAIL_1 / FAIL_2 / FAIL_3 | Redemande ou proposition email. |

## Confirmation RDV

| Clé | Dialogue |
|-----|----------|
| VOCAL_BOOKING_CONFIRMED | C'est noté pour {slot_label}. Vous recevrez un rappel. À bientôt ! |
| format_booking_confirmed_vocal | Parfait. Votre rendez-vous est confirmé pour {slot_label}. Vous recevrez un SMS de rappel. À bientôt ! |

## Menu INTENT_ROUTER

| Clé | Dialogue |
|-----|----------|
| VOCAL_INTENT_ROUTER | Je vous écoute. Dites un pour prendre rendez-vous. Dites deux pour annuler ou modifier. Dites trois pour poser une question. Ou dites quatre pour parler à un conseiller. |
| VOCAL_NAME_FAIL_3_INTENT_ROUTER | Je vais simplifier. Dites un pour rendez-vous… (idem menu) |
| MSG_INTENT_ROUTER | Je vais simplifier. Dites : un, pour prendre un rendez-vous ; deux, pour annuler ou modifier ; trois, pour poser une question ; quatre, pour parler à quelqu'un. |
| MSG_INTENT_ROUTER_RETRY | Vous pouvez simplement dire : un, deux, trois ou quatre, s'il vous plaît. |
| MSG_INTENT_ROUTER_FAQ | Quelle est votre question ? |

## Clarification

| Clé | Dialogue |
|-----|----------|
| VOCAL_CLARIFY | Pas de souci ! Je peux vous renseigner si vous avez une question, ou vous aider à prendre un rendez-vous. Qu'est-ce qui vous ferait plaisir ? |
| MSG_CLARIFY_WEB_START | D'accord. Vous avez une question ou un autre besoin ? |

## Annulation (CANCEL)

| Clé | Dialogue |
|-----|----------|
| VOCAL_CANCEL_ASK_NAME | Bien sûr. À quel nom est le rendez-vous, s'il vous plaît ? |
| VOCAL_CANCEL_CONFIRM | J'ai trouvé votre rendez-vous {slot_label}. Souhaitez-vous l'annuler ? |
| VOCAL_CANCEL_DONE | C'est fait, votre rendez-vous est annulé. Bonne journée ! |
| VOCAL_CANCEL_KEPT | Pas de souci, votre rendez-vous est maintenu. Bonne journée ! |
| VOCAL_CANCEL_NOT_FOUND / VERIFIER_HUMAN | Je ne trouve pas… Vérifier ou humain ? |

## Modification (MODIFY)

| Clé | Dialogue |
|-----|----------|
| VOCAL_MODIFY_ASK_NAME | Très bien. À quel nom est le rendez-vous, s'il vous plaît ? |
| VOCAL_MODIFY_CONFIRM | Vous avez un rendez-vous {slot_label}. Vous voulez le déplacer ? |
| VOCAL_MODIFY_CANCELLED | J'ai annulé l'ancien. Plutôt le matin ou l'après-midi pour le nouveau ? |

## Ordonnance

| Clé | Dialogue |
|-----|----------|
| VOCAL_ORDONNANCE_ASK_CHOICE | Pour une ordonnance, vous voulez un rendez-vous ou que l'on transmette un message ? |
| VOCAL_ORDONNANCE_DONE | Parfait. Votre demande d'ordonnance est enregistrée. On vous rappelle rapidement. Au revoir ! |

## Cas particuliers

| Clé | Dialogue |
|-----|----------|
| VOCAL_NO_SLOTS | Je suis désolée. Nous n'avons plus de créneaux disponibles. Je vous mets en relation avec un conseiller. |
| VOCAL_INSULT_RESPONSE | Je comprends que vous soyez frustré. Comment puis-je vous aider ? |

**Acquittements (round-robin)** : ACK_VARIANTS_LIST → "Très bien." / "D'accord." / "Parfait." (pick_ack).

---

# Partie 13 — Fichiers de référence

| Fichier | Rôle |
|---------|------|
| `backend/fsm.py` | États et transitions (ConvState, VALID_TRANSITIONS) |
| `backend/engine.py` | Détection intent, routing, handlers (_handle_faq, _handle_intent_router, etc.) |
| `backend/prompts.py` | **Source de vérité** : tous les messages (VOCAL_*, MSG_*, get_qualif_question, get_message) |
| `backend/guards.py` | Langue, spam, longueur (avant routing) |

---

*Document généré à partir de SCRIPT_LOGIQUE_DEMANDES_REPONSES.md, SCRIPT_CONVERSATION_COMPLET.md et DIALOGUES_AGENT_VOCAL.md. Pour le wording exact à l’instant T, se référer à `backend/prompts.py`.*
