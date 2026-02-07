# Changements voix / UX — Février 2026

Document de synthèse des correctifs P0/P1 (mission Cursor UWi Agent vocal).

## P0 — Correctifs critiques

### P0.1 — START : "oui" = ambigu (pas booking direct)
- **Problème** : En START, l’intent YES ("oui") partait en booking (QUALIF_NAME) → incohérent.
- **Changement** : En START, si intent == YES → clarification (état CLARIFY) avec message court : *"Pas de souci. C'est pour un rendez-vous, ou pour une question ?"*. Le booking explicite ("rdv", "prendre rendez-vous") reste inchangé.
- **Fichiers** : `backend/engine.py`, `backend/fsm.py` (état CLARIFY + transitions), `backend/prompts.py` (VOCAL_CLARIFY_YES_START, MSG_CLARIFY_YES_START).

### P0.2 — WAIT_CONFIRM : 1 créneau à la fois (vocal)
- **Problème** : 3 créneaux dictés d’un coup = surcharge cognitive + abandon.
- **Changement** : En vocal, proposition **séquentielle** : "Le prochain créneau est {label}. Ça vous convient ?" → OUI = confirmer ce créneau ; NON = proposer le suivant ; après 3 NON = VOCAL_NO_SLOTS + transfert. "Répéter" relit le créneau courant.
- **Fichiers** : `backend/engine.py` (_propose_slots, _handle_booking_confirm), `backend/prompts.py` (VOCAL_SLOT_ONE_PROPOSE, VOCAL_SLOT_SEQUENTIAL_NEED_YES_NO), `backend/session.py` (slot_offer_index, slot_proposal_sequential).

### P0.3 — Choix vocal (premier / deuxième / troisième)
- **Statut** : Déjà couvert par `slot_choice.py` et `guards.py` (premier, deuxième, troisième, le premier, 1/2/3, etc.). INTENT_ROUTER étendu (P1.5) avec "cat"/"catre" → option 4.

### P0.4 — MODIFY : ordre sécurisé (nouveau RDV avant annuler l’ancien)
- **Problème** : L’ancien RDV était annulé avant d’avoir confirmé le nouveau → risque de perte de RDV.
- **Changement** : 1) Trouver le RDV existant. 2) Demander préférence (matin/après-midi). 3) Proposer créneaux et obtenir confirmation du **nouveau** créneau. 4) **Seulement ensuite** : créer le nouveau RDV, annuler l’ancien, confirmer "J’ai déplacé votre rendez-vous vers {new_label}."
- **Fichiers** : `backend/engine.py` (_handle_modify MODIFY_CONFIRM : plus d’appel à cancel_booking ; _handle_contact_confirm : après book_slot_from_session success, si pending_cancel_slot → cancel_booking puis message VOCAL_MODIFY_MOVED), `backend/prompts.py` (VOCAL_MODIFY_NEW_PREF, VOCAL_MODIFY_MOVED, MSG_MODIFY_MOVED_WEB, MSG_MODIFY_NEW_PREF_WEB).

---

## P1 — Améliorations UX / ton / robustesse

### P1.1 — Registre professionnel-chaleureux
- "Qu’est-ce qui vous ferait plaisir ?" → *"Pas de souci. C'est pour un rendez-vous, ou pour une question ?"* (VOCAL_CLARIFY).
- "Je vais simplifier" → *"Pour aller plus vite, je vous propose quatre options."* (VOCAL_NAME_FAIL_3_INTENT_ROUTER, MSG_INTENT_ROUTER).
- "Ne quittez pas" → *"Un instant, s'il vous plaît."* (MSG_TRANSFER).

### P1.2 — Acquittements
- Doublons "Parfait" évités via messages dédiés ; ACK round-robin inchangé (Très bien / D’accord / Parfait).

### P1.3 — Fusion POST_FAQ (une seule phrase)
- Une seule phrase naturelle : *"Vous voulez prendre rendez-vous, ou poser une question ?"* (VOCAL_POST_FAQ_CHOICE, VOCAL_POST_FAQ_DISAMBIG, MSG_POST_FAQ_DISAMBIG_WEB). Suppression du "Dites : …" et des ":" inaudibles.

### P1.4 — CANCEL_NOT_FOUND
- Message : *"Je n'ai pas de rendez-vous enregistré à ce nom. Voulez-vous me redonner le nom exact, ou préférez-vous que je vous passe un conseiller ?"* (VOCAL_CANCEL_NOT_FOUND_VERIFIER_HUMAN). Intent : "redonner le nom" / "vérifier" → CANCEL_NAME ; "conseiller" / "quelqu'un" → TRANSFERRED (déjà géré dans _handle_cancel).

### P1.5 — INTENT_ROUTER
- Un seul "Dites" ; wording court. Parsing élargi : un/1/premier, deux/2/deuxième, trois/3/question, quatre/4/conseiller/humain, **cat/catre** (tolérance STT → option 4). Après 2 incompréhensions dans le router → transfert (intent_router_unclear_count).

### P1.6 — Strong intents en plein booking
- Dans QUALIF_NAME, QUALIF_MOTIF, QUALIF_PREF, QUALIF_CONTACT, WAIT_CONFIRM : si `detect_strong_intent()` renvoie CANCEL / MODIFY / TRANSFER / ABANDON / FAQ → routage immédiat vers le handler adéquat (annulation, modification, transfert, au revoir, FAQ).

### P1.7 — Anti-boucle START ↔ INTENT_ROUTER
- Compteur `session.intent_router_visits`. Si ≥ 2 visites au router → transfert direct avec *"Je vois que c'est compliqué. Je vous passe un conseiller. Un instant."* (VOCAL_INTENT_ROUTER_LOOP).

### P1.8 — PHONE_FAIL ladder + fallback email
- FAIL_1 : *"Je n'ai pas bien compris le numéro. Pouvez-vous le répéter lentement ?"*
- FAIL_2 : *"Dites les chiffres deux par deux. Par exemple : zéro six, douze, trente-quatre…"*
- FAIL_3 : *"Pas de souci. On peut aussi prendre votre email. Quelle est votre adresse email ?"*
- Normalisation téléphone : gérée dans guards / engine (formats mots, chiffres, +33, sans zéro).

---

## Tests et qualité

- **T1** : `tests/test_prompt_compliance.py` — MSG_TRANSFER mis à jour (Un instant). Toute clé modifiée doit être reflétée dans les tests.
- **T2** : Scénarios de parcours (à compléter si besoin) : START + "oui" → CLARIFY ; WAIT_CONFIRM séquentiel ; MODIFY ordre ; CANCEL_NOT_FOUND ; INTENT_ROUTER "cat" → 4 ; contact FAIL_3 → email.
- **T3** : Non-régression : flux FAQ, overrides CANCEL/MODIFY/TRANSFER restent prioritaires.

---

## Impacts attendus

- **STT** : Moins d’échecs sur "oui deux" / "cat" grâce au séquentiel et aux synonymes.
- **Charge cognitive** : Un créneau à la fois en vocal ; phrases courtes ; un seul "Dites" au router.
- **Cohérence** : "Oui" en START ne lance plus un booking par erreur ; MODIFY ne supprime plus le RDV avant d’en avoir un nouveau.
- **Abandons** : Réduction attendue grâce à la clarification, au séquentiel et à l’anti-boucle router.

---

## Mapping STT → intent (février 2026)

Tableau implémenté pour tolérance large et zéro ambiguïté silencieuse :

- **Global** : TRANSFER (conseiller, humain, standard…), ABANDON (au revoir, c'est tout, rien en POST_FAQ…), CANCEL/MODIFY (strong override), BOOKING (explicite, jamais "oui"), YES/NO (nom merci = NO), **REPEAT** (répète, encore, pardon… → relire dernier message), **rien** hors POST_FAQ → UNCLEAR.
- **INTENT_ROUTER** : ROUTER_1..4 avec listes `ROUTER_*_PATTERNS` ; **hein** seul / **de** seul → retry (pas 1 ni 2) ; **ROUTER_4_STT_TOLERANCE** : cat, catre, quattre, katr, quatres → 4 ; 2 incompréhensions → transfert.
- **Slots** : mode séquentiel vocal = YES/NO/REPEAT uniquement (pas "oui un/deux/trois").
- **Contact** : CONTACT_PHONE_PATTERNS / CONTACT_EMAIL_PATTERNS ; **mel, mèl, mél** → email ; `normalize_phone_fr` : 9 chiffres 6/7 → 0 prefix, +33 géré.

Détail : `backend/prompts.py` (patterns), `backend/engine.py` (detect_intent, REPEAT, _handle_intent_router), `backend/guards.py` (normalize_phone_fr, is_contact_selector_word, detect_contact_type_preference).

---

## Fichiers modifiés (résumé)

| Fichier | Changements principaux |
|---------|------------------------|
| `backend/engine.py` | P0.1 YES→CLARIFY ; P0.2 séquentiel slots ; P0.4 MODIFY ordre ; P1.5 router parsing ; P1.6 strong intents ; P1.7 intent_router_visits |
| `backend/fsm.py` | État CLARIFY, transitions START→CLARIFY, CLARIFY→… |
| `backend/prompts.py` | VOCAL_CLARIFY, VOCAL_CLARIFY_YES_START, VOCAL_SLOT_ONE_PROPOSE, VOCAL_MODIFY_*, VOCAL_INTENT_ROUTER, VOCAL_PHONE_FAIL_*, etc. |
| `backend/session.py` | slot_offer_index, slot_proposal_sequential, intent_router_visits, intent_router_unclear_count |
| `tests/test_prompt_compliance.py` | MSG_TRANSFER wording |
