# Dialogues de l’agent (voix / vocal) — extraction pour analyse

Document extrait de `backend/prompts.py` : **toutes les répliques que l’agent peut dire en canal vocal**, pour analyser le ton (sècheresse, chaleur, formules sobres).

---

## 1. Accueil / salutation

| Clé | Dialogue |
|-----|----------|
| VOCAL_SALUTATION | Bonjour et bienvenue chez {business_name} ! Vous appelez pour prendre un rendez-vous ? |
| VOCAL_SALUTATION_NEUTRAL | Bonjour ! Bienvenue chez {business_name}, je vous écoute. |
| VOCAL_SALUTATION_LONG | Bonjour ! Bienvenue chez {business_name}. Je suis là pour vous aider. Qu'est-ce que je peux faire pour vous ? |
| VOCAL_SALUTATION_SHORT | Oui, je vous écoute ? |

---

## 2. Silence / bruit / incompréhension

| Clé | Dialogue |
|-----|----------|
| MSG_SILENCE_1 | Je n'ai rien entendu. Pouvez-vous répéter ? |
| MSG_SILENCE_2 | Êtes-vous toujours là ? |
| MSG_NOISE_1 | Je n'ai pas bien entendu. Pouvez-vous répéter ? |
| MSG_NOISE_2 | Il y a du bruit. Pouvez-vous répéter plus distinctement ? |
| MSG_UNCLEAR_1 | Je vous entends mal. Pouvez-vous répéter ? |
| MSG_VOCAL_CROSSTALK_ACK | Je vous écoute. |
| MSG_OVERLAP_REPEAT | Je vous ai entendu en même temps. Pouvez-vous répéter maintenant ? |
| MSG_OVERLAP_REPEAT_SHORT | Pardon, pouvez-vous répéter ? |
| VOCAL_NOT_UNDERSTOOD | Pardon, j'ai pas bien compris. Vous pouvez répéter ? |

---

## 3. Transfert / clôture

| Clé | Dialogue |
|-----|----------|
| MSG_TRANSFER | Je vous mets en relation avec un humain pour vous aider. |
| VOCAL_TRANSFER_HUMAN | Bon, je vais vous passer quelqu'un qui pourra mieux vous aider. Un instant. |
| VOCAL_TRANSFER_COMPLEX | Je comprends. Je vais vous mettre en relation avec quelqu'un qui pourra mieux vous aider. Un instant. |
| VOCAL_STILL_UNCLEAR | Pas de problème, je vais vous passer quelqu'un qui pourra mieux vous aider. Un instant. |
| VOCAL_GOODBYE | Au revoir, bonne journée ! |
| VOCAL_GOODBYE_AFTER_BOOKING | Merci et à très bientôt ! |
| VOCAL_USER_ABANDON | Pas de problème ! N'hésitez pas à rappeler. Bonne journée ! |
| VOCAL_TAKE_TIME | Prenez votre temps, je vous écoute. |

---

## 4. FAQ

| Clé | Dialogue |
|-----|----------|
| VOCAL_FAQ_FOLLOWUP | Est-ce que je peux vous aider pour autre chose ? |
| VOCAL_FAQ_GOODBYE | Avec plaisir ! Bonne journée et à bientôt ! |
| VOCAL_FAQ_TO_BOOKING | Bien sûr ! C'est à quel nom ? |
| MSG_FAQ_REFORMULATE_VOCAL | J'ai pas bien saisi. Vous pouvez reformuler votre question ? |
| MSG_FAQ_RETRY_EXEMPLES_VOCAL | Je peux répondre sur les horaires, les tarifs, ou où on se trouve. Posez votre question simplement. |

---

## 5. Qualification — nom

| Clé | Dialogue |
|-----|----------|
| VOCAL_NAME_ASK | Très bien. C'est à quel nom ? |
| VOCAL_NAME_FAIL_1 | Je n'ai pas bien noté votre nom. Pouvez-vous répéter ? |
| VOCAL_NAME_FAIL_2 | Votre nom et prénom, par exemple : Martin Dupont. |
| MSG_QUALIF_NAME_RETRY_VOCAL | Juste avant, c'est à quel nom ? |
| MSG_QUALIF_NAME_INTENT_1 | D'accord, j'ai bien compris. C'est à quel nom ? |
| MSG_QUALIF_NAME_INTENT_2 | Votre nom et prénom, par exemple : Martin Dupont. |

---

## 6. Qualification — motif

| Clé | Dialogue |
|-----|----------|
| MSG_AIDE_MOTIF | Pour continuer, indiquez le motif du rendez-vous (ex : consultation, contrôle, douleur, devis). Répondez en 1 courte phrase. |
| VOCAL_MOTIF_HELP | Désolé, j'ai pas bien compris. C'est plutôt pour un contrôle, une consultation, ou autre chose ? |
| MSG_QUALIF_MOTIF_RETRY_VOCAL | Attendez, c'est pour quoi exactement ? |

---

## 7. Qualification — préférence créneau (matin / après-midi)

| Clé | Dialogue |
|-----|----------|
| VOCAL_PREF_ASK | Vous préférez le matin ou l'après-midi ? |
| VOCAL_PREF_FAIL_1 | Préférez-vous avant midi ou plutôt après midi ? |
| VOCAL_PREF_FAIL_2 | Répondez simplement : matin ou après-midi. |
| VOCAL_PREF_ANY | Très bien. Je propose le matin. Ça vous va ? |
| VOCAL_PREF_ANY_NO | D'accord. Alors plutôt l'après-midi ? |
| VOCAL_PREF_CONFIRM_MATIN | D'accord, plutôt le matin. C'est bien ça ? |
| VOCAL_PREF_CONFIRM_APRES_MIDI | D'accord, plutôt l'après-midi. C'est bien ça ? |
| MSG_PREFERENCE_CONFIRM | D'accord, donc plutôt {pref}, c'est bien ça ? |
| MSG_QUALIF_PREF_RETRY_VOCAL | Vous préférez plutôt quel moment de la journée ? |
| MSG_QUALIF_PREF_INTENT_1 | D'accord, j'ai bien compris. Vous préférez le matin ou l'après-midi ? |
| MSG_QUALIF_PREF_INTENT_2 | Pour choisir le créneau : dites "matin" ou "après-midi". |

---

## 8. Choix de créneau (1, 2, 3)

| Clé | Dialogue |
|-----|----------|
| MSG_SLOTS_PREFACE_VOCAL | J'ai trois créneaux disponibles. |
| format_slot_proposal_vocal (3 slots) | J'ai trois créneaux. Un : {slot1}. Deux : {slot2}. Trois : {slot3}. Dites un, deux ou trois. |
| MSG_CONFIRM_INSTRUCTION_VOCAL | Pour confirmer, dites : un, deux ou trois. Vous pouvez aussi dire : oui un, oui deux, oui trois. |
| MSG_CONFIRM_RETRY_VOCAL | Je n'ai pas compris. Dites seulement : un, deux ou trois. |
| MSG_SLOT_EARLY_CONFIRM_VOCAL | Créneau {idx}, {label}, c'est bien ça ? |
| MSG_SLOT_BARGE_IN_HELP | D'accord. Dites juste 1, 2 ou 3. |
| MSG_WAIT_CONFIRM_NEED_NUMBER | D'accord. Pour confirmer, dites 1, 2 ou 3. |
| VOCAL_SLOT_FAIL_1 | Je n'ai pas compris. Dites seulement : un, deux ou trois. |
| VOCAL_SLOT_FAIL_2 | Par exemple : 'je prends le deux'. Alors ? |

---

## 9. Contact (téléphone / email)

| Clé | Dialogue |
|-----|----------|
| VOCAL_CONTACT_ASK | Pour confirmer tout ça, vous préférez qu'on vous rappelle ou qu'on vous envoie un email ? |
| VOCAL_CONTACT_EMAIL | D'accord. Dictez-moi votre email, tranquillement. Genre : jean point dupont arobase gmail point com. |
| VOCAL_CONTACT_PHONE | Parfait. C'est quoi votre numéro ? Allez-y doucement, je note. |
| VOCAL_CONTACT_RETRY | Excusez-moi, je n'ai pas bien noté. Pouvez-vous me donner votre numéro complet, chiffre par chiffre ? |
| VOCAL_PHONE_CONFIRM | Votre numéro est bien le {phone_spaced} ? |
| VOCAL_PHONE_CONFIRM_NO | D'accord. Quel est votre numéro ? |
| VOCAL_CONTACT_CONFIRM_SHORT | Le {phone_formatted}, c'est bien ça ? |
| VOCAL_CONTACT_CONFIRM_OK | Parfait, c'est noté. |
| VOCAL_CONTACT_CONFIRM_RETRY | D'accord, pouvez-vous me redonner votre numéro ? |
| VOCAL_PHONE_FAIL_1 | Je n'ai pas bien compris votre numéro. Pouvez-vous le redire ? |
| VOCAL_PHONE_FAIL_2 | Dites-le comme ceci : zéro six, douze, trente-quatre, cinquante-six, soixante-dix-huit. |
| VOCAL_PHONE_FAIL_3 | Je n'arrive pas à noter votre numéro. Pouvez-vous me donner un email ? |
| MSG_QUALIF_CONTACT_RETRY_VOCAL | Pour vous rappeler, c'est quoi le mieux ? Téléphone ou email ? |
| MSG_CONTACT_CONFIRM_INTENT_1 | D'accord. Juste pour confirmer : oui ou non ? |
| MSG_CONTACT_CONFIRM_INTENT_2 | Dites "oui" pour confirmer, ou "non" pour corriger. |
| MSG_QUALIF_CONTACT_INTENT | D'accord. Pour finaliser, j'ai besoin de votre email ou numéro de téléphone. |

---

## 10. Confirmation de RDV / fin de prise de RDV

| Clé | Dialogue |
|-----|----------|
| format_booking_confirmed_vocal (avec prénom) | Parfait. Votre rendez-vous est confirmé pour {slot_label}. Vous recevrez un SMS de rappel. À bientôt {first_name} ! |
| format_booking_confirmed_vocal (sans prénom) | Parfait. Votre rendez-vous est confirmé pour {slot_label}. Vous recevrez un SMS de rappel. À bientôt ! |
| VOCAL_BOOKING_CONFIRMED | C'est noté pour {slot_label}. On vous attend, à bientôt ! |

---

## 11. Menu de routage (INTENT_ROUTER)

| Clé | Dialogue |
|-----|----------|
| VOCAL_INTENT_ROUTER | Dites : Un pour rendez-vous. Deux pour annuler. Trois pour une question. Quatre pour parler à quelqu'un. |
| VOCAL_NAME_FAIL_3_INTENT_ROUTER | Je vais simplifier. Dites : Un pour rendez-vous. Deux pour annuler. Trois pour une question. Quatre pour parler à quelqu'un. |
| MSG_INTENT_ROUTER | Je vais simplifier. Dites : un, pour prendre un rendez-vous ; deux, pour annuler ou modifier ; trois, pour poser une question ; quatre, pour parler à quelqu'un. Dites simplement : un, deux, trois ou quatre. |
| MSG_INTENT_ROUTER_RETRY | Dites juste le numéro. Par exemple : un pour rendez-vous. |

---

## 12. Clarification / flou

| Clé | Dialogue |
|-----|----------|
| VOCAL_CLARIFY | Pas de souci ! Je peux vous renseigner si vous avez une question, ou vous aider à prendre un rendez-vous. Qu'est-ce qui vous ferait plaisir ? |

---

## 13. Annulation (CANCEL)

| Clé | Dialogue |
|-----|----------|
| VOCAL_CANCEL_ASK_NAME | Bien sûr, pas de problème ! C'est à quel nom ? |
| VOCAL_CANCEL_LOOKUP_HOLDING | Un instant, je cherche votre rendez-vous. |
| VOCAL_CANCEL_NAME_RETRY_1 | Je n'ai pas noté votre nom. Vous pouvez répéter ? |
| VOCAL_CANCEL_NAME_RETRY_2 | Votre nom et prénom. Par exemple : Martin Dupont. |
| VOCAL_CANCEL_NOT_FOUND | Hmm, je ne trouve pas de rendez-vous à ce nom. Vous pouvez me redonner votre nom complet s'il vous plaît ? |
| VOCAL_CANCEL_NOT_FOUND_VERIFIER_HUMAN | Je ne trouve pas de rendez-vous au nom de {name}. Voulez-vous vérifier l'orthographe ou parler à quelqu'un ? Dites : vérifier, ou : humain. |
| VOCAL_CANCEL_CONFIRM | J'ai trouvé ! Vous avez un rendez-vous {slot_label}. Vous souhaitez l'annuler ? |
| VOCAL_CANCEL_DONE | C'est fait, votre rendez-vous est bien annulé. N'hésitez pas à nous rappeler si besoin. Bonne journée ! |
| VOCAL_CANCEL_KEPT | Pas de souci, votre rendez-vous est bien maintenu. On vous attend ! Bonne journée ! |
| CANCEL_FAILED_TRANSFER | Je n'arrive pas à annuler automatiquement. Je vous mets en relation avec quelqu'un. Un instant. |
| CANCEL_NOT_SUPPORTED_TRANSFER | Je peux vous aider, mais je ne peux pas annuler automatiquement dans ce système. Je vous mets en relation avec quelqu'un. Un instant. |
| ClarificationMessages CANCEL_CONFIRM | 1: Voulez-vous annuler ce rendez-vous ? Répondez oui ou non. / 2: Pour annuler, dites oui. Pour garder le rendez-vous, dites non. |

---

## 14. Modification (MODIFY)

| Clé | Dialogue |
|-----|----------|
| VOCAL_MODIFY_ASK_NAME | Pas de souci. C'est à quel nom ? |
| VOCAL_MODIFY_NAME_RETRY_1 | Je n'ai pas noté votre nom. Vous pouvez répéter ? |
| VOCAL_MODIFY_NAME_RETRY_2 | Votre nom et prénom. Par exemple : Martin Dupont. |
| VOCAL_MODIFY_NOT_FOUND | Hmm, j'ai pas trouvé de rendez-vous à ce nom. Vous pouvez me redonner votre nom complet ? |
| VOCAL_MODIFY_NOT_FOUND_VERIFIER_HUMAN | Je ne trouve pas de rendez-vous au nom de {name}. Voulez-vous vérifier l'orthographe ou parler à quelqu'un ? Dites : vérifier, ou : humain. |
| VOCAL_MODIFY_CONFIRM | Vous avez un rendez-vous {slot_label}. Vous voulez le déplacer ? |
| VOCAL_MODIFY_CANCELLED | OK, j'ai annulé l'ancien. Plutôt le matin ou l'après-midi pour le nouveau ? |
| ClarificationMessages MODIFY_CONFIRM | 1: Voulez-vous déplacer ce rendez-vous ? Répondez oui ou non. / 2: Pour déplacer, dites oui. Pour garder la date, dites non. |

---

## 15. Cas particuliers

| Clé | Dialogue |
|-----|----------|
| MSG_TIME_CONSTRAINT_IMPOSSIBLE | D'accord. Mais nous fermons à {closing}. Je peux vous proposer un créneau plus tôt, ou je vous mets en relation avec quelqu'un. Vous préférez : un créneau plus tôt, ou parler à quelqu'un ? |
| VOCAL_NO_SLOTS | Ah mince, on n'a plus de créneaux disponibles là. Je vous passe quelqu'un pour trouver une solution. |
| VOCAL_NO_SLOTS_MORNING | Désolé, rien de disponible le matin cette semaine. L'après-midi ça vous va ? |
| VOCAL_NO_SLOTS_AFTERNOON | Désolé, rien de disponible l'après-midi non plus. Je note votre demande. Votre numéro ? |
| VOCAL_WAITLIST_ADDED | C'est noté. On vous rappelle dès qu'un créneau se libère. Bonne journée ! |
| VOCAL_INSULT_RESPONSE | Je comprends que vous soyez frustré. Comment puis-je vous aider ? |
| msg_no_match_faq (vocal) | Hmm, là je suis pas sûr de pouvoir vous répondre. Je vous passe quelqu'un de chez {business_name}, d'accord ? |

---

## 16. Ordonnance

| Clé | Dialogue |
|-----|----------|
| VOCAL_ORDONNANCE_ASK_CHOICE | Pour une ordonnance, vous voulez un rendez-vous ou que l'on transmette un message ? |
| VOCAL_ORDONNANCE_CHOICE_RETRY_1 | Je n'ai pas compris. Vous préférez un rendez-vous ou un message ? |
| VOCAL_ORDONNANCE_CHOICE_RETRY_2 | Dites simplement : rendez-vous ou message. |
| VOCAL_ORDONNANCE_ASK_NAME | D'accord. C'est à quel nom ? |
| VOCAL_ORDONNANCE_NAME_RETRY_1 | Je n'ai pas noté votre nom. Répétez ? |
| VOCAL_ORDONNANCE_NAME_RETRY_2 | Votre nom et prénom, s'il vous plaît. |
| VOCAL_ORDONNANCE_PHONE_ASK | Quel est votre numéro de téléphone ? |
| VOCAL_ORDONNANCE_DONE | Parfait. Votre demande d'ordonnance est enregistrée. On vous rappelle rapidement. Au revoir ! |

---

## 17. Mots-signaux (TransitionSignals)

Utilisés en préfixe de certains messages : **Parfait.** / **Très bien.** / **D'accord.** / **Je regarde.** / **Voilà.**

---

## 18. Accusés de réception / fillers

- VOCAL_ACK_POSITIVE : D'accord. / Très bien. / Parfait. / OK. / Entendu.
- VOCAL_ACK_UNDERSTANDING : Je comprends. / Je vois. / Ah oui, d'accord.
- VOCAL_FILLERS : Alors, / Bon, / Donc, / Eh bien,

---

*Source : `backend/prompts.py`. Extraction pour analyse de ton (chaleur, sobriété, formules).*
