# Rapport d'audit — 10 règles globales (Agent Vocal UWI)

**Référence :** PROMPT_AUDIT_10_REGLES.md (Downloads)  
**Date :** 2025-02-03  
**Périmètre :** backend (engine, prompts, session, guards, config, tools_booking).

---

## RÈGLE 1 — INTENT OVERRIDE ABSOLU

**Statut global :** ✅ CONFORME

**Détails :**

#### A. Fonction detect_strong_intent()
- ✅ Implémentée  
- Fichier : `backend/engine.py` (lignes 394-410)  
- Couvre CANCEL, MODIFY, TRANSFER, ABANDON, ORDONNANCE (patterns dans `prompts.CANCEL_PATTERNS`, etc.)

```394:411:backend/engine.py
def detect_strong_intent(text: str) -> Optional[str]:
    """
    Détecte les intents qui préemptent le flow en cours (CANCEL, MODIFY, TRANSFER, ABANDON).
    """
    t = text.strip().lower()
    if not t:
        return None
    if any(p in t for p in prompts.CANCEL_PATTERNS):
        return "CANCEL"
    if any(p in t for p in prompts.MODIFY_PATTERNS):
        return "MODIFY"
    if any(p in t for p in prompts.TRANSFER_PATTERNS):
        return "TRANSFER"
    if any(p in t for p in prompts.ABANDON_PATTERNS):
        return "ABANDON"
    if any(p in t for p in prompts.ORDONNANCE_PATTERNS):
        return "ORDONNANCE"
    return None
```

#### B. Intent override dans le pipeline
- ✅ Implémenté  
- Fichier : `backend/engine.py` — bloc après anti-loop, **avant** guards basiques (l.658-681)  
- Switch immédiat : CANCEL → _start_cancel, MODIFY → _start_modify, TRANSFER → TRANSFERRED, ABANDON → CONFIRMED + message, ORDONNANCE → _handle_ordonnance_flow  
- Condition d’override : `should_override_current_flow_v3(session, user_text)` (évite re-trigger si déjà dans le bon flow)

```661:681:backend/engine.py
        if should_override_current_flow_v3(session, user_text):
            strong = detect_strong_intent(user_text)
            session.last_intent = strong
            log_ivr_event(logger, session, "intent_override")
            if strong == "CANCEL":
                return safe_reply(self._start_cancel(session), session)
            if strong == "MODIFY":
                return safe_reply(self._start_modify(session), session)
            if strong == "TRANSFER":
                session.state = "TRANSFERRED"
                ...
            if strong == "ABANDON":
                ...
            if strong == "ORDONNANCE":
                return safe_reply(self._handle_ordonnance_flow(session, user_text), session)
```

#### C. Test de vérification
- ✅ Existant  
- Fichier : `tests/test_niveau1.py` — `test_annuler_pendant_booking()` (l.43-53) : booking puis "je veux annuler" → vérification du comportement CANCEL  
- `test_intent_override_transfer()` (l.115-124) : "je veux parler à un humain" → TRANSFERRED

**Recommandation :** Aucune.

---

## RÈGLE 2 — MAX RECOVERY = 2

**Statut global :** ✅ CONFORME

**Détails :**

#### A. Compteurs recovery par contexte
- ✅ Présents dans `backend/session.py` : `slot_choice_fails`, `name_fails`, `phone_fails`, `preference_fails`, `global_recovery_fails`, etc.  
- ✅ `MAX_CONTEXT_FAILS = 3` (2 retries + 3e → menu)

```80:96:backend/session.py
    slot_choice_fails: int = 0
    name_fails: int = 0
    phone_fails: int = 0
    preference_fails: int = 0
    ...
    MAX_CONTEXT_FAILS = 3  # Échecs sur un même contexte → escalade INTENT_ROUTER
```

#### B. Recovery progressive
- ✅ Messages différenciés retry 1 / 2 dans `prompts.ClarificationMessages` (NAME_UNCLEAR, SLOT_CHOICE_UNCLEAR, etc.) et `get_clarification_message()`.  
- ✅ 3e échec → `_trigger_intent_router(session, "name_fails_3" | "slot_choice_fails_3" | ...)` (pas de transfert direct).

```1162:1163:backend/engine.py
                    return self._trigger_intent_router(session, "name_fails_3", user_text)
```

#### C. INTENT_ROUTER après 3 échecs
- ✅ Partout où recovery : `should_escalate_recovery()` puis `return self._trigger_intent_router(...)`. Aucun `transfer_to_human()` direct après 3 échecs sur un champ.

**Recommandation :** Aucune.

---

## RÈGLE 3 — SILENCE INTERDIT

**Statut global :** ⚠️ PARTIEL

**Détails :**

#### A. Guard message vide
- ✅ Guard existe (l.707-718) : `if not user_text or not user_text.strip()` → incrément `empty_message_count`, puis selon `silence_limit` (RECOVERY_LIMITS["silence"] = 2) → INTENT_ROUTER ou message.  
- ⚠️ **Écart** : un seul message utilisé pour le vide : `MSG_EMPTY_MESSAGE` = "Je n'ai pas reçu votre message. Pouvez-vous réessayer ?".  
  - Spec : 1re fois "Je n'ai rien entendu. Répétez ?", 2e "Êtes-vous toujours là ?", 3e INTENT_ROUTER.  
- ⚠️ **Seuil** : actuellement 2 silences → INTENT_ROUTER (config `silence: 2`). La spec prévoit 3 niveaux de messages puis 3e → INTENT_ROUTER.

```708:718:backend/engine.py
        if not user_text or not user_text.strip():
            session.empty_message_count = getattr(session, "empty_message_count", 0) + 1
            _persist_ivr_event(session, "empty_message")
            silence_limit = _recovery_limit_for("silence")
            if session.empty_message_count >= silence_limit:
                return safe_reply(
                    self._trigger_intent_router(session, "empty_repeated", user_text or ""),
                    session,
                )
            msg = prompts.MSG_EMPTY_MESSAGE
            session.add_message("agent", msg)
```

#### B. safe_reply() en dernière barrière
- ✅ `safe_reply()` existe : si pas d’events ou aucun event avec texte non vide → fallback `SAFE_REPLY_FALLBACK` ("D'accord. Je vous écoute.") et `session.add_message("agent", msg)`.  
- ✅ Tous les retours de `handle_message` passent par `safe_reply(..., session)`.

```371:391:backend/engine.py
def safe_reply(events: List[Event], session: Session) -> List[Event]:
    ...
    if not events:
        log_ivr_event(logger, session, "safe_reply")
        msg = SAFE_REPLY_FALLBACK
        session.add_message("agent", msg)
        return [Event("final", msg, conv_state=session.state)]
    for ev in events:
        if ev.text and ev.text.strip():
            return events
    ...
    session.add_message("agent", msg)
    return [Event("final", msg, conv_state=session.state)]
```

**Recommandation :**  
- Ajouter deux messages dédiés (1re et 2e fois) pour le silence vocal (ex. "Je n'ai rien entendu. Répétez ?" puis "Êtes-vous toujours là ?") et faire 3 niveaux avant INTENT_ROUTER si la spec doit être stricte.

---

## RÈGLE 4 — ANTI-LOOP

**Statut global :** ✅ CONFORME (avec seuils différents de la spec)

**Détails :**

#### A. Anti-loop guard
- ✅ En début de pipeline : `session.turn_count += 1`, puis `if session.turn_count > max_turns` (25) → `_trigger_intent_router(session, "anti_loop_25", ...)`.  
- ✅ Seuil 25 (MAX_TURNS_ANTI_LOOP). Pas de transfert direct : on envoie vers INTENT_ROUTER.

```649:656:backend/engine.py
        session.turn_count = getattr(session, "turn_count", 0) + 1
        max_turns = getattr(Session, "MAX_TURNS_ANTI_LOOP", 25)
        if session.turn_count > max_turns:
            _persist_ivr_event(session, "anti_loop_trigger")
            return safe_reply(
                self._trigger_intent_router(session, "anti_loop_25", user_text or ""),
                session,
            )
```

#### B. Compteur questions consécutives
- ✅ `consecutive_questions` dans Session, `MAX_CONSECUTIVE_QUESTIONS = 3` (spec indiquait 5).  
- ✅ Utilisation dans `should_trigger_intent_router` : `consecutive_questions >= 7` → trigger (et ailleurs reset quand l’utilisateur répond).  
- ⚠️ Seuils différents de la spec (3 vs 5 pour questions, 7 pour trigger).

**Recommandation :** Documenter ou aligner les seuils (3/7) avec la spec (5) si souhaité.

---

## RÈGLE 5 — TOUJOURS CONFIRMER INFÉRENCES

**Statut global :** ✅ CONFORME

**Détails :**

#### A. Inférence + confirmation
- ✅ Préférence inférée → `session.pending_preference = inferred`, `session.state = "PREFERENCE_CONFIRM"`, message de confirmation (ex. `format_inference_confirmation`, templates "C'est bien ça ?").  
- Fichier : `backend/engine.py` (QUALIF_PREF, inférence matin/après-midi/neutral puis passage en PREFERENCE_CONFIRM).

#### B. Répétition = confirmation implicite
- ✅ En PREFERENCE_CONFIRM : si ré-inférence égale à `pending_preference` → acceptation directe.  
- ✅ `last_preference_user_text` : si l’utilisateur répète exactement la même phrase → confirmation implicite.

```2271:2278:backend/engine.py
        # Répétition de la même phrase (ex: "je finis à 17h" redit) → confirmation implicite
        last_txt = (getattr(session, "last_preference_user_text", None) or "").strip().lower()
        current_txt = user_text.strip().lower()
        if pending and last_txt and current_txt and last_txt == current_txt:
            session.qualif_data.pref = pending
            session.pending_preference = None
            ...
            return self._next_qualif_step(session)
```

**Recommandation :** Aucune.

---

## RÈGLE 6 — RÉPÉTITION ≠ CORRECTION

**Statut global :** ✅ CONFORME

**Détails :**

#### A. Fonction de détection
- ✅ `detect_user_intent_repeat(message)` dans `backend/engine.py` : retourne `'correction'` (attendez, erreur, trompé, …) ou `'repeat'` (répét, redis, pas compris, …) ou `None`.

#### B. Gestion dans le pipeline
- ✅ Bloc **avant** guards (l.686-701) :  
  - `correction` → rejouer `last_question_asked` (ou fallback).  
  - `repeat` → renvoyer `last_agent_message` (sans ré-ajout au historique pour éviter doublon).  
- ✅ Session : `last_agent_message`, `last_question_asked` mis à jour dans `add_message()` (role == "agent").

**Recommandation :** Aucune.

---

## RÈGLE 7 — CONTRAINTE HORAIRE vs CABINET

**Statut global :** ❌ NON CONFORME

**Détails :**

#### A. Extraction contrainte horaire
- ❌ Aucune fonction `extract_time_constraint(message)` retournant `{'type': 'after', 'hour': 17}`.  
- Les commentaires / inférence évoquent "je finis à 17h" pour la préférence (matin/après-midi), mais pas d’extraction d’heure explicite ni de comparaison à une heure de fermeture.

#### B. Comparaison avec horaires cabinet
- ❌ Pas de variable `CABINET_CLOSING_HOUR` dans `config`.  
- ❌ Pas de branche "impossible / possible" selon l’heure utilisateur vs fermeture.

#### C. Filtrage créneaux
- ⚠️ Filtrage par préférence (matin/après-midi) dans `tools_booking.get_slots_for_display(pref=...)` et cohérence avec "je finis à 17h" (éviter 10h si après-midi). Pas de filtre explicite sur une heure maximale utilisateur (ex. créneaux > user_hour).

**Recommandation :**  
- Ajouter `extract_time_constraint(message)` et `CABINET_CLOSING_HOUR`.  
- Si `user_hour >= CABINET_CLOSING_HOUR` → message d’impossibilité + alternatives ou transfert.  
- Sinon, filtrer les créneaux proposés (ex. exclure les créneaux avant user_hour si type "after").

---

## RÈGLE 8 — NO HALLUCINATION

**Statut global :** ✅ CONFORME

**Détails :**

#### A. Pas de créneaux hardcodés
- ✅ Aucune liste de créneaux en dur. Les slots viennent de `tools_booking.get_slots_for_display()` (Google Calendar ou SQLite via `list_free_slots`).

#### B. Vérification slots non vides
- ✅ Dans `_propose_slots()` : `if not slots:` → `session.state = "TRANSFERRED"`, `msg = prompts.get_message("no_slots", channel=channel)` (ex. "Désolé, nous n'avons plus de créneaux disponibles. Je vous mets en relation avec un humain.").

```1571:1576:backend/engine.py
        if not slots:
            print(f"⚠️ _propose_slots: NO SLOTS AVAILABLE")
            session.state = "TRANSFERRED"
            msg = prompts.get_message("no_slots", channel=channel)
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
```

**Recommandation :** Aucune.

---

## RÈGLE 9 — UNE QUESTION À LA FOIS

**Statut global :** ✅ CONFORME

**Détails :**

#### A. Audit des messages
- ✅ Aucun message avec deux questions distinctes (pas de "C'est à quel nom ? Et vous préférez le matin ?").  
- Les formulations du type "Et votre numéro de téléphone pour vous rappeler ?" constituent une seule question (contact).  
- Qualif : une question par étape (nom, motif, préférence, contact). Clarification : un objectif par message (slot_choice, name, phone, etc.).

**Recommandation :** Aucune.

---

## RÈGLE 10 — CALLER ID RESPECT

**Statut global :** ✅ CONFORME

**Détails :**

#### A. Confirmation Caller ID
- ✅ Si `session.customer_phone` (vocal) : passage en `CONTACT_CONFIRM` avec message du type "Votre numéro est bien le {format_phone_for_voice(phone)} ?" (ou équivalent). Pas d’utilisation directe sans confirmation.

```1092:1106:backend/engine.py
        if next_field == "contact" and channel == "vocal" and session.customer_phone:
            ...
                    session.state = "CONTACT_CONFIRM"
                    phone_formatted = prompts.format_phone_for_voice(phone[:10])
```

#### B. Gestion confirmation
- ✅ État `CONTACT_CONFIRM` : intent YES → utilisation du numéro (booking/confirmation). Intent NO → retour à `QUALIF_CONTACT` et demande manuelle du numéro.  
- Fichier : `_handle_contact_confirm()` (l.2144-2206).

**Recommandation :** Aucune.

---

# RÉSUMÉ AUDIT

| Règle | Statut | Priorité correction |
|-------|--------|---------------------|
| RÈGLE 1 — Intent Override | ✅ CONFORME | - |
| RÈGLE 2 — Max Recovery | ✅ CONFORME | - |
| RÈGLE 3 — Silence | ⚠️ PARTIEL | P2 |
| RÈGLE 4 — Anti-loop | ✅ CONFORME | - |
| RÈGLE 5 — Confirmer inférences | ✅ CONFORME | - |
| RÈGLE 6 — Répétition ≠ Correction | ✅ CONFORME | - |
| RÈGLE 7 — Contrainte horaire / Cabinet | ❌ NON CONFORME | P1 |
| RÈGLE 8 — No hallucination | ✅ CONFORME | - |
| RÈGLE 9 — Une question à la fois | ✅ CONFORME | - |
| RÈGLE 10 — Caller ID respect | ✅ CONFORME | - |

**Conformité globale :** 8/10 règles conformes (1 partielle, 1 non conforme).

**Actions prioritaires :**  
1. **[P1]** RÈGLE 7 — Implémenter contrainte horaire : `extract_time_constraint()`, `CABINET_CLOSING_HOUR`, comparaison et filtrage des créneaux (ou documenter hors scope V3).  
2. **[P2]** RÈGLE 3 — Aligner silence vocal : 2 messages distincts (1re / 2e fois) puis 3e → INTENT_ROUTER, et seuil à 3 si la spec doit être stricte.

**Prêt pour production :** OUI pour les flows actuels (vocal + web), sous réserve de décision explicite sur la RÈGLE 7 (contrainte horaire cabinet). Si la contrainte "je finis à Xh" vs heure de fermeture est requise pour les premiers déploiements, traiter P1 avant.

---

# POST-CORRECTIFS (2025-02-03)

Les correctifs P1 (RÈGLE 7) et P2 (RÈGLE 3) ont été implémentés et validés par les tests.

| Règle | Statut initial | Statut post-patch |
|-------|----------------|-------------------|
| RÈGLE 3 — Silence | ⚠️ PARTIEL | ✅ CONFORME |
| RÈGLE 7 — Contrainte horaire | ❌ NON CONFORME | ✅ CONFORME |

**Conformité globale post-correctifs : 10 / 10 règles.**

Détail des changements, implémentations et ajustements connexes (FAQ no match, booking CONTACT_CONFIRM) : voir **[CHANGELOG_AUDIT_10_REGLES_2025-02-03.md](./CHANGELOG_AUDIT_10_REGLES_2025-02-03.md)**.
