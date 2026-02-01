# Script de conversation — Agent vocal d'accueil & prise de RDV

Document unique décrivant le dialogue de l’agent (messages exacts, états, transitions).  
À utiliser pour revue par des experts et renforcement du comportement.

---

## 1. Message d’accueil (First Message — Vapi)

**À configurer dans le Dashboard Vapi (First Message) :**

```
Bonjour Cabinet Dupont, vous appelez pour un rendez-vous ?
```

- Remplacer « Cabinet Dupont » par le nom de l’entreprise (`config.BUSINESS_NAME`).
- Après ce message, l’utilisateur répond ; l’agent est en état `START` et route selon l’intent.

---

## 2. États de conversation

| État | Description |
|------|-------------|
| `START` | Après le First Message ; en attente de OUI / NON / CANCEL / MODIFY / FAQ / etc. |
| `QUALIF_NAME` | Demande du nom |
| `QUALIF_MOTIF` | Demande du motif (web ; en vocal ce champ peut être sauté selon config) |
| `QUALIF_PREF` | Demande créneau préféré (matin / après-midi) |
| `QUALIF_CONTACT` | Demande email ou téléphone |
| `CONTACT_CONFIRM` | Confirmation du numéro (vocal) ou dernière étape avant booking |
| `PROPOSE_SLOTS` | (interne) avant envoi des créneaux |
| `WAIT_CONFIRM` | Créneaux proposés ; en attente du choix (1, 2 ou 3) |
| `CANCEL_NAME` | Annulation : demande du nom |
| `CANCEL_CONFIRM` | Annulation : confirmation oui/non |
| `MODIFY_NAME` | Modification : demande du nom |
| `MODIFY_CONFIRM` | Modification : confirmation puis reroute vers QUALIF_PREF |
| `CLARIFY` | Après « non » au First Message ; clarification du besoin |
| `FAQ_ANSWERED` | Réponse FAQ donnée ; en attente de suite (autre question, RDV, au revoir) |
| `CONFIRMED` | Fin positive (RDV confirmé, annulation faite, etc.) |
| `TRANSFERRED` | Transfert à un humain |

---

## 3. Détection d’intention (au premier message ou en CLARIFY)

- **YES** : oui, ouais, ok, d’accord, c’est ça, etc. → booking ou confirmation.
- **NO** : non, nan, etc. → clarification (CLARIFY) sauf si mots FAQ (horaire, adresse…) → FAQ.
- **BOOKING** : rdv, rendez-vous, dispo, réserver, prendre un rdv, etc. → qualification RDV.
- **CANCEL** : annuler, annulation, annuler mon rdv, etc. → flow annulation.
- **MODIFY** : modifier, changer, déplacer, reporter, etc. → flow modification.
- **TRANSFER** : parler à quelqu’un, un humain, un conseiller, etc. → transfert.
- **ABANDON** : je rappellerai, plus tard, rien, etc. → au revoir.
- **FAQ** : défaut si pas d’autre intent ; recherche en base FAQ.

Référence code : `backend/engine.py` → `detect_intent()` ; patterns dans `backend/prompts.py` (YES_PATTERNS, NO_PATTERNS, CANCEL_PATTERNS, etc.).

---

## 4. Flow A — Prise de rendez-vous

### 4.1 Entrée

- **START** + intent **YES** ou **BOOKING** (ou depuis FAQ_ANSWERED avec YES/BOOKING).

### 4.2 Ordre des questions (qualification)

1. **Nom** — Vocal : `"Très bien ! C'est à quel nom ?"` (`QUALIF_QUESTIONS_VOCAL["name"]`)  
   Web : `"Quel est votre nom et prénom ?"`
2. **Motif** — Web : `"Pour quel sujet ? (ex : renouvellement, douleur, bilan…)"`  
   Vocal : peut être désactivé (chaîne vide dans `QUALIF_QUESTIONS_VOCAL["motif"]`).
3. **Préférence** — Vocal : `"Très bien {prénom}. Vous préférez plutôt le matin ou l'après-midi ?"`  
   Web : `"Quel créneau préférez-vous ? (ex : lundi matin, mardi après-midi)"`
4. **Contact** — Vocal : `"Parfait. Et votre numéro de téléphone pour vous rappeler ?"`  
   Web : `"Quel est votre moyen de contact ? (email ou téléphone)"`

Si l’appelant est identifié (caller ID), l’agent peut proposer directement :  
`"Votre numéro est bien le 06, 12, 34, 56, 78 ?"` (état `CONTACT_CONFIRM`).

### 4.3 Proposition de créneaux

Message vocal (3 créneaux) :

```
J'ai trois créneaux. Un : {slot1}. Deux : {slot2}. Trois : {slot3}. Dites un, deux ou trois.
```

Référence : `format_slot_proposal_vocal()` / `VOCAL_CONFIRM_SLOTS` selon implémentation.

Choix reconnus : « premier », « un », « 1 », « le premier » → créneau 1 ; idem pour 2 et 3 (`SLOT_CHOICE_FIRST`, `SLOT_CHOICE_SECOND`, `SLOT_CHOICE_THIRD`).

### 4.4 Après le choix du créneau

- Si **contact pas encore demandé** : demande du contact (ou confirmation du numéro si caller ID).
- Si **contact déjà confirmé** (ou après « oui » sur le numéro) : création du RDV puis message de confirmation.

### 4.5 Confirmation du RDV (après création)

Vocal (`format_booking_confirmed_vocal`) :

```
Parfait. Votre rendez-vous est confirmé pour {slot_label}. Vous recevrez un SMS de rappel. À bientôt {prénom} !
```

Web : message structuré avec date/heure, nom, motif, « À bientôt ! ».

Échec de réservation (créneau pris, erreur) → transfert avec `MSG_SLOT_ALREADY_BOOKED` ou équivalent.

---

## 5. Flow B — FAQ (question)

- **START** ou **CLARIFY** avec intent **FAQ** ou phrase reconnue comme question.
- Recherche FAQ (score ≥ seuil, ex. 80 %) → réponse + `Source : {FAQ_ID}` en web (optionnel en vocal).
- Suivi vocal : `"Est-ce que je peux vous aider pour autre chose ?"` (`VOCAL_FAQ_FOLLOWUP`).
- État après réponse : `FAQ_ANSWERED`. Suite possible : nouvelle question, OUI/BOOKING → booking, NON/ABANDON → au revoir.

Si pas de match FAQ :  
- 1er échec : message du type « Je n’ai pas cette information. Souhaitez-vous prendre un rendez-vous ? »  
- 2e échec : transfert (`MSG_TRANSFER` / `VOCAL_TRANSFER_HUMAN`).

---

## 6. Flow C — Annulation

- **START** + intent **CANCEL** (ou depuis CLARIFY).
- Message : `"Bien sûr, pas de problème ! C'est à quel nom ?"` (`VOCAL_CANCEL_ASK_NAME`).
- État `CANCEL_NAME` → recherche du RDV par nom (Google Calendar / BDD).
- Si **pas trouvé** : `"Je n'ai pas trouvé de rendez-vous à ce nom. Pouvez-vous me redonner votre nom complet ?"` (ou `VOCAL_CANCEL_NOT_FOUND`). Après 2 échecs → transfert.
- Si **trouvé** : `"Vous avez un rendez-vous {slot_label}. Vous voulez l'annuler ?"` (`VOCAL_CANCEL_CONFIRM`) → état `CANCEL_CONFIRM`.
- **OUI** → annulation effective → `"C'est fait, votre rendez-vous est annulé. Bonne journée !"` (`VOCAL_CANCEL_DONE`).
- **NON** → `"Pas de souci, votre rendez-vous reste pris. Bonne journée !"` (`VOCAL_CANCEL_KEPT`).
- Réponse non comprise → redemander oui/non.

---

## 7. Flow D — Modification

- **START** + intent **MODIFY** (ou depuis CLARIFY).
- Message : `"Pas de souci. C'est à quel nom ?"` (`VOCAL_MODIFY_ASK_NAME`).
- État `MODIFY_NAME` → recherche du RDV par nom.
- Si **pas trouvé** : même logique que annulation (redemander nom, puis transfert après 2 échecs).
- Si **trouvé** : `"Vous avez un rendez-vous {slot_label}. Vous voulez le déplacer ?"` (`VOCAL_MODIFY_CONFIRM`) → état `MODIFY_CONFIRM`.
- **OUI** → annulation de l’ancien RDV puis : `"J'ai annulé l'ancien. Plutôt le matin ou l'après-midi pour le nouveau ?"` (`VOCAL_MODIFY_CANCELLED`) → état `QUALIF_PREF` (reprise du flow booking).
- **NON** → même message que « garder le RDV » (`VOCAL_CANCEL_KEPT`).

---

## 8. Flow E — Clarification (après « non » au First Message)

- **START** + intent **NO** → état `CLARIFY`.
- Message : `"Pas de souci. Vous avez une question ou vous souhaitez prendre rendez-vous ?"` (`VOCAL_CLARIFY`).
- Suite selon intent :
  - **YES / BOOKING** ou mots « rendez-vous », « rdv » → `QUALIF_NAME` avec `"Bien sûr ! C'est à quel nom ?"` (`VOCAL_FAQ_TO_BOOKING`).
  - Question ou **FAQ** → recherche FAQ (seuil plus bas possible en CLARIFY).
  - **CANCEL** → flow annulation.
  - **MODIFY** → flow modification.
  - **TRANSFER** → transfert.
  - Toujours pas clair : après 2 relances → `"Je vais vous mettre en relation avec quelqu'un qui pourra mieux vous aider."` (`VOCAL_STILL_UNCLEAR`) puis transfert.

---

## 9. Flow F — Transfert humain

- Intent **TRANSFER** ou 2 échecs no-match FAQ ou conditions de sécurité (spam, abus, etc.).
- Message vocal : `"Je comprends. Je vais vous mettre en relation avec quelqu'un qui pourra mieux vous aider. Un instant."` (`VOCAL_TRANSFER_COMPLEX`).
- Message web : `"Je vous mets en relation avec un humain pour vous aider."` (`MSG_TRANSFER`).
- État : `TRANSFERRED`. Les messages suivants reçoivent `MSG_CONVERSATION_CLOSED` (ou équivalent) sans relancer de flow.

---

## 10. Cas limites (edge cases)

| Cas | Message agent (référence) |
|-----|---------------------------|
| Message vide | `MSG_EMPTY_MESSAGE` : "Je n'ai pas reçu votre message. Pouvez-vous réessayer ?" |
| Message trop long (>500 car.) | `MSG_TOO_LONG` : "Votre message est trop long. Pouvez-vous résumer ?" |
| Langue non française | `MSG_FRENCH_ONLY` : "Je ne parle actuellement que français." |
| Spam / insultes | Transfert silencieux (sans message spécifique ou message poli court). |
| Session expirée (timeout) | `MSG_SESSION_EXPIRED` : "Votre session a expiré. Puis-je vous aider ?" |
| Déjà en CONFIRMED ou TRANSFERRED | `MSG_CONVERSATION_CLOSED` : "C'est terminé pour cette demande…" |
| Choix de créneau invalide (retry) | Vocal : `MSG_CONFIRM_RETRY_VOCAL` "Je n'ai pas compris. Dites seulement : un, deux ou trois." |
| Contact invalide (1 retry) | `MSG_CONTACT_RETRY` ou vocal `VOCAL_CONTACT_RETRY`. Après 2–3 échecs → transfert. |
| Aucun créneau dispo | `VOCAL_NO_SLOTS` / `MSG_NO_SLOTS_AVAILABLE` puis transfert. |

---

## 11. Fichiers de référence

| Fichier | Rôle |
|---------|------|
| `backend/prompts.py` | Tous les messages (constantes et fonctions `format_*`, `get_qualif_question`, etc.) |
| `backend/engine.py` | États, transitions, handlers (`_handle_*`, `_start_*`, `detect_intent`, `detect_slot_choice`) |
| `backend/guards.py` | Validation (nom, motif, contact, langue, spam), parsing vocal (téléphone, email) |
| `backend/entity_extraction.py` | Extraction nom / motif / préférence depuis le premier message |
| `VAPI_CONFIG.md` | First Message et résumé des flows pour la config Vapi |
| `SYSTEM_PROMPT.md` | Règles métier et contraintes de l’agent |

---

## 12. Points à renforcer (pour experts)

- **Robustesse reconnaissance vocale** : variantes « oui », « un/deux/trois », noms et numéros dictés (déjà partiellement gérés dans `guards` et `detect_slot_choice`).
- **Cohérence des messages** : une seule source de vérité dans `prompts.py` ; éviter les chaînes en dur dans `engine.py`.
- **Gestion des erreurs** : timeout API, calendrier indisponible, double réservation → messages clairs et transfert si besoin.
- **Accessibilité** : formulations courtes et claires pour le TTS ; éviter les listes longues à l’oral.
- **Tests** : scénarios de bout en bout (booking, FAQ, cancel, modify, clarify, transfer) alignés sur ce script.

---

*Dernière mise à jour : aligné sur `backend/prompts.py` et `backend/engine.py` actuels.*
