# Script de conversation complet — Agent vocal d'accueil & prise de RDV

Document unique pour analyse : tous les états, flows et répliques exactes (source `backend/prompts.py` + `backend/engine.py`).

---

## 1. Message d'accueil (First Message — Vapi)

**À configurer dans le Dashboard Vapi :**

```
Bonjour Cabinet Dupont, vous appelez pour un rendez-vous ?
```

- Remplacer « Cabinet Dupont » par `config.BUSINESS_NAME`.
- Après ce message, l'utilisateur répond ; l'agent est en état **START**.

---

## 2. États de conversation

| État | Description |
|------|-------------|
| **START** | Après le First Message ; en attente de OUI / NON / CANCEL / MODIFY / FAQ / etc. |
| **POST_FAQ** | Après une réponse FAQ + relance « Puis-je vous aider pour autre chose ? » ; en attente de non / oui-RDV / autre question. |
| **QUALIF_NAME** | Demande du nom |
| **QUALIF_MOTIF** | Demande du motif |
| **QUALIF_PREF** | Demande créneau préféré (matin / après-midi) |
| **QUALIF_CONTACT** | Demande email ou téléphone |
| **CONTACT_CONFIRM** | Confirmation du numéro (vocal) ou dernière étape avant booking |
| **WAIT_CONFIRM** | Créneaux proposés ; en attente du choix (1, 2 ou 3) |
| **CANCEL_NAME** | Annulation : demande du nom |
| **CANCEL_CONFIRM** | Annulation : confirmation oui/non |
| **MODIFY_NAME** | Modification : demande du nom |
| **MODIFY_CONFIRM** | Modification : confirmation puis reroute vers QUALIF_PREF |
| **CLARIFY** | Après « non » au First Message ; clarification du besoin |
| **INTENT_ROUTER** | Menu 1/2/3/4 (rdv, annuler, question, humain) |
| **CONFIRMED** | Fin positive (RDV confirmé, au revoir après FAQ, etc.) |
| **TRANSFERRED** | Transfert à un humain |

---

## 3. Détection d'intention

- **YES** : oui, ouais, ok, d'accord, c'est ça → booking ou confirmation.
- **NO** : non, nan → clarification (CLARIFY) ou, en POST_FAQ, au revoir.
- **BOOKING** : rdv, rendez-vous, dispo, réserver → qualification RDV.
- **CANCEL** : annuler, annulation → flow annulation.
- **MODIFY** : modifier, changer, déplacer → flow modification.
- **TRANSFER** : parler à quelqu'un, humain, conseiller → transfert.
- **ABANDON** : je rappellerai, plus tard, rien → au revoir.
- **FAQ** : défaut si pas d'autre intent ; recherche en base FAQ.

Référence : `backend/engine.py` → `detect_intent()` ; patterns dans `backend/prompts.py`.

---

## 4. Flow A — Prise de rendez-vous

### Entrée
- **START** + intent **YES** ou **BOOKING** (ou depuis **POST_FAQ** avec YES/BOOKING).

### Qualification (ordre des questions)

| Étape | Vocal | Web |
|-------|--------|-----|
| Nom | « Très bien. Quel est votre nom et prénom, s'il vous plaît ? » (VOCAL_NAME_ASK) | « Quel est votre nom et prénom ? » |
| Motif | « Désolé, j'ai pas bien compris. C'est plutôt pour un contrôle, une consultation, ou autre chose ? » (VOCAL_MOTIF_HELP) si besoin | Motif demandé |
| Préférence | « Très bien. Préférez-vous plutôt le matin, ou l'après-midi ? » (VOCAL_PREF_ASK) | Créneau préféré |
| Contact | « Pour confirmer tout ça, vous préférez qu'on vous rappelle ou qu'on vous envoie un email ? » (VOCAL_CONTACT_ASK) puis téléphone ou email | Email ou téléphone |

Si caller ID connu : « Le {phone_formatted}, c'est bien ça ? » (VOCAL_CONTACT_CONFIRM_SHORT).

### Proposition de créneaux (WAIT_CONFIRM)

**Message vocal (un seul bloc préface + liste) :**

```
Très bien. J'ai trois créneaux à vous proposer. Le {jour1} à {heure1}, dites un. Le {jour2} à {heure2}, dites deux. Le {jour3} à {heure3}, dites trois. Dites un, deux ou trois pour choisir.
```

Choix reconnus : « un », « 1 », « le premier », « oui 1 », « vendredi 14h » (si match unique), etc. (`detect_slot_choice_early`).

### Interruption pendant l'énumération (barge-in)

- Si l'utilisateur dit « un » / « 1 » pendant la liste → **arrêt immédiat**, pas de ré-énumération.
- Réponse : « Très bien. Donc le créneau {idx}, {label}. C'est bien ça ? » (MSG_SLOT_EARLY_CONFIRM_VOCAL).
- Si « oui » / « d'accord » sans numéro : « D'accord. Pour confirmer, dites simplement un, deux ou trois, s'il vous plaît. » (MSG_WAIT_CONFIRM_NEED_NUMBER).

### Après choix de créneau

- Demande contact si pas encore fait (ou confirmation numéro).
- Après « oui » sur le numéro → création du RDV.

### Confirmation du RDV (après création)

**Vocal (format_booking_confirmed_vocal) :**

- Avec prénom : « Parfait. Votre rendez-vous est confirmé pour {slot_label}. Vous recevrez un SMS de rappel. À bientôt {first_name} ! »
- Sans prénom : « Parfait. Votre rendez-vous est confirmé pour {slot_label}. Vous recevrez un SMS de rappel. À bientôt ! »

**Créneau pris entre-temps (retry) :**

- 1er ou 2e échec : « Ce créneau vient d'être pris. Je vous propose d'autres disponibilités. Le matin ou l'après-midi ? » (MSG_SLOT_TAKEN_REPROPOSE) → retour QUALIF_PREF.
- 3e échec : « Je suis désolée, les créneaux changent vite. Je vous mets en relation avec un conseiller. » (MSG_SLOT_TAKEN_TRANSFER).

---

## 5. Flow B — FAQ (question)

- **START** ou **CLARIFY** avec intent **FAQ** ou phrase reconnue comme question.
- Recherche FAQ (score ≥ 80 %) → réponse factuelle + en web « Source : {FAQ_ID} ».
- **Relance systématique** (vocal et web) :
  - **Vocal** : « Avec plaisir. Puis-je vous aider pour autre chose ? » (VOCAL_FAQ_FOLLOWUP)
  - **Web** : « Souhaitez-vous autre chose ? » (MSG_FAQ_FOLLOWUP_WEB)
- **État après réponse** : **POST_FAQ**.

### Routage en POST_FAQ

| Réponse utilisateur | Action |
|---------------------|--------|
| **Non / c'est tout** (NO, ABANDON) | « Très bien. Merci de votre appel, et bonne journée ! » (VOCAL_FAQ_GOODBYE) → **CONFIRMED** |
| **Oui / rendez-vous** (YES, BOOKING) | Démarrage booking → QUALIF_NAME avec « Avec plaisir. Pour le rendez-vous, à quel nom, s'il vous plaît ? » (VOCAL_FAQ_TO_BOOKING) |
| **Autre question** | Re-FAQ (state = START → _handle_faq). 1er no-match : reformulation ; 2e : INTENT_ROUTER. |

### FAQ sans match

- 1er échec : « Je n'ai pas bien saisi. Pouvez-vous reformuler, s'il vous plaît ? » (MSG_FAQ_REFORMULATE_VOCAL).
- 2e échec : menu INTENT_ROUTER.

---

## 6. Flow C — Annulation

- **START** + intent **CANCEL** (ou depuis CLARIFY).
- « Bien sûr, pas de problème ! C'est à quel nom ? » (VOCAL_CANCEL_ASK_NAME) → **CANCEL_NAME**.
- Recherche du RDV par nom.
- **Pas trouvé** : « Hmm, je ne trouve pas de rendez-vous à ce nom. Vous pouvez me redonner votre nom complet s'il vous plaît ? » (VOCAL_CANCEL_NOT_FOUND). Après 2 échecs → transfert.
- **Trouvé** : « J'ai trouvé ! Vous avez un rendez-vous {slot_label}. Vous souhaitez l'annuler ? » (VOCAL_CANCEL_CONFIRM) → **CANCEL_CONFIRM**.
- **OUI** → « C'est fait, votre rendez-vous est bien annulé. N'hésitez pas à nous rappeler si besoin. Bonne journée ! » (VOCAL_CANCEL_DONE).
- **NON** → « Pas de souci, votre rendez-vous est bien maintenu. On vous attend ! Bonne journée ! » (VOCAL_CANCEL_KEPT).

---

## 7. Flow D — Modification

- **START** + intent **MODIFY** (ou depuis CLARIFY).
- « Pas de souci. C'est à quel nom ? » (VOCAL_MODIFY_ASK_NAME) → **MODIFY_NAME**.
- Si trouvé : « Vous avez un rendez-vous {slot_label}. Vous voulez le déplacer ? » (VOCAL_MODIFY_CONFIRM) → **MODIFY_CONFIRM**.
- **OUI** → « OK, j'ai annulé l'ancien. Plutôt le matin ou l'après-midi pour le nouveau ? » (VOCAL_MODIFY_CANCELLED) → **QUALIF_PREF** (reprise booking).
- **NON** → même message que garder le RDV (VOCAL_CANCEL_KEPT).

---

## 8. Flow E — Clarification (après « non » au First Message)

- **START** + intent **NO** → **CLARIFY**.
- « Pas de souci ! Je peux vous renseigner si vous avez une question, ou vous aider à prendre un rendez-vous. Qu'est-ce qui vous ferait plaisir ? » (VOCAL_CLARIFY).
- Suite : YES/BOOKING → booking ; FAQ/question → FAQ ; CANCEL/MODIFY/TRANSFER → flow correspondant.
- Après 3 relances flou : « Pas de problème, je vais vous passer quelqu'un qui pourra mieux vous aider. Un instant. » (VOCAL_STILL_UNCLEAR) → transfert.

---

## 9. Flow F — Transfert humain

- Intent **TRANSFER** ou 2 échecs no-match FAQ ou spam/abus, etc.
- **Vocal** : « Je comprends. Je vais vous mettre en relation avec quelqu'un qui pourra mieux vous aider. Un instant. » (VOCAL_TRANSFER_COMPLEX).
- **Web** : « Je vous mets en relation avec un conseiller. Ne quittez pas, s'il vous plaît. » (MSG_TRANSFER).
- État : **TRANSFERRED**.

---

## 10. Menu INTENT_ROUTER (1/2/3/4)

- **Vocal** : « Je vais simplifier. Dites : un pour rendez-vous, deux pour annuler, trois pour une question, quatre pour parler à quelqu'un. » (VOCAL_INTENT_ROUTER).
- **Web** : « Je vais simplifier. Dites : un, pour prendre un rendez-vous ; deux, pour annuler ou modifier ; trois, pour poser une question ; quatre, pour parler à quelqu'un. Dites simplement : un, deux, trois ou quatre. » (MSG_INTENT_ROUTER).

---

## 11. Répliques vocales — récapitulatif par thème

### Accueil / salutation
- VOCAL_SALUTATION : « Bonjour et bienvenue chez {business_name} ! Vous appelez pour prendre un rendez-vous ? »
- VOCAL_SALUTATION_NEUTRAL : « Bonjour ! Bienvenue chez {business_name}, je vous écoute. »
- VOCAL_SALUTATION_SHORT : « Bonjour, je vous écoute. »

### Silence / bruit / incompréhension
- MSG_SILENCE_1 : « Je n'ai pas bien entendu. Pourriez-vous répéter, s'il vous plaît ? »
- MSG_SILENCE_2 : « Je vous écoute, prenez votre temps. »
- MSG_NOISE_1 : « Je vous entends un peu mal. Pourriez-vous répéter, s'il vous plaît ? »
- MSG_UNCLEAR_1 : « La ligne n'est pas très claire. Pourriez-vous répéter, s'il vous plaît ? »
- MSG_VOCAL_CROSSTALK_ACK : « Je vous écoute. »
- MSG_OVERLAP_REPEAT_SHORT : « Pardon. Répétez, s'il vous plaît. »

### FAQ
- VOCAL_FAQ_FOLLOWUP : « Avec plaisir. Puis-je vous aider pour autre chose ? »
- VOCAL_FAQ_GOODBYE : « Très bien. Merci de votre appel, et bonne journée ! »
- VOCAL_FAQ_TO_BOOKING : « Avec plaisir. Pour le rendez-vous, à quel nom, s'il vous plaît ? »
- MSG_FAQ_REFORMULATE_VOCAL : « Je n'ai pas bien saisi. Pouvez-vous reformuler, s'il vous plaît ? »
- MSG_FAQ_RETRY_EXEMPLES_VOCAL : « Je peux vous répondre sur les horaires, les tarifs, ou l'adresse. Quelle est votre question ? »

### Qualification — nom
- VOCAL_NAME_ASK : « Très bien. Quel est votre nom et prénom, s'il vous plaît ? »
- VOCAL_NAME_FAIL_1 : « Je n'ai pas bien saisi votre nom. Pouvez-vous répéter, s'il vous plaît ? »
- VOCAL_NAME_FAIL_2 : « Votre nom et prénom. Par exemple : Martin Dupont. »

### Qualification — motif
- VOCAL_MOTIF_HELP : « Désolé, j'ai pas bien compris. C'est plutôt pour un contrôle, une consultation, ou autre chose ? »
- MSG_QUALIF_MOTIF_RETRY_VOCAL : « Attendez, c'est pour quoi exactement ? »

### Qualification — préférence (matin / après-midi)
- VOCAL_PREF_ASK : « Très bien. Préférez-vous plutôt le matin, ou l'après-midi ? »
- VOCAL_PREF_FAIL_1 : « Je vous écoute. Plutôt le matin, ou l'après-midi ? »
- VOCAL_PREF_FAIL_2 : « Vous pouvez simplement dire : matin, ou après-midi, s'il vous plaît. »
- VOCAL_PREF_CONFIRM_MATIN : « D'accord, plutôt le matin. C'est bien ça ? »
- VOCAL_PREF_CONFIRM_APRES_MIDI : « D'accord, plutôt l'après-midi. C'est bien ça ? »

### Choix de créneau (1, 2, 3)
- MSG_SLOT_EARLY_CONFIRM_VOCAL : « Très bien. Donc le créneau {idx}, {label}. C'est bien ça ? »
- MSG_SLOT_BARGE_IN_HELP : « Pas de souci. Vous pouvez dire : un, deux ou trois, s'il vous plaît. »
- MSG_WAIT_CONFIRM_NEED_NUMBER : « D'accord. Pour confirmer, dites simplement un, deux ou trois, s'il vous plaît. »
- VOCAL_SLOT_FAIL_1 : « Je n'ai pas bien saisi. Vous pouvez dire : un, deux ou trois, s'il vous plaît. »
- VOCAL_SLOT_FAIL_2 : « Par exemple : je prends le deux. Lequel vous convient ? »

### Contact (téléphone / email)
- VOCAL_CONTACT_ASK : « Pour confirmer tout ça, vous préférez qu'on vous rappelle ou qu'on vous envoie un email ? »
- VOCAL_CONTACT_PHONE : « Parfait. C'est quoi votre numéro ? Allez-y doucement, je note. »
- VOCAL_CONTACT_CONFIRM_SHORT : « Le {phone_formatted}, c'est bien ça ? »
- VOCAL_PHONE_FAIL_1 : « Je n'ai pas bien compris votre numéro. Pouvez-vous le redire ? »
- VOCAL_PHONE_FAIL_2 : « Dites-le comme ceci : zéro six, douze, trente-quatre, cinquante-six, soixante-dix-huit. »
- VOCAL_PHONE_FAIL_3 : « Je n'arrive pas à noter votre numéro. Pouvez-vous me donner un email ? »

### Transfert / clôture
- MSG_TRANSFER : « Je vous mets en relation avec un conseiller. Ne quittez pas, s'il vous plaît. »
- VOCAL_TRANSFER_COMPLEX : « Je comprends. Je vais vous mettre en relation avec quelqu'un qui pourra mieux vous aider. Un instant. »
- VOCAL_GOODBYE : « Merci de votre appel. Je vous souhaite une excellente journée, au revoir. »

### Cas limites
- MSG_EMPTY_MESSAGE : « Je n'ai pas reçu votre message. Pouvez-vous réessayer ? »
- MSG_TOO_LONG : « Votre message est trop long. Pouvez-vous résumer ? »
- MSG_FRENCH_ONLY : « Je ne parle actuellement que français. »
- MSG_SESSION_EXPIRED : « Votre session a expiré. Puis-je vous aider ? »
- VOCAL_NO_SLOTS : « Ah mince, on n'a plus de créneaux disponibles là. Je vous passe quelqu'un pour trouver une solution. »
- VOCAL_MEDICAL_EMERGENCY : (urgence médicale — appeler 15 / 112)

---

## 12. Fichiers de référence

| Fichier | Rôle |
|---------|------|
| `backend/prompts.py` | Toutes les répliques (constantes + `format_*`, `get_qualif_question`) |
| `backend/engine.py` | États, transitions, handlers, `detect_intent`, `_handle_faq`, POST_FAQ |
| `backend/fsm.py` | États et transitions (POST_FAQ, CONFIRMED, etc.) |
| `backend/guards.py` | Validation nom, motif, contact, langue, spam ; parsing vocal |
| `docs/DIALOGUES_AGENT_VOCAL.md` | Extraction détaillée des dialogues pour analyse de ton |
| `SCRIPT_CONVERSATION_AGENT.md` | Version synthétique du script (racine projet) |
| `SYSTEM_PROMPT.md` | Règles métier et contraintes |

---

*Dernière mise à jour : POST_FAQ, VOCAL_FAQ_FOLLOWUP / VOCAL_FAQ_GOODBYE, retry créneau pris, relance FAQ web. Source : `backend/prompts.py` et `backend/engine.py`.*
