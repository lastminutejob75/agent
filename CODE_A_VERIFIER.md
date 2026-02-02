# Code à vérifier — Engine + Prompts + Session

Document regroupant le code modifié (pipeline, intent override, INTENT_ROUTER, seuils, messages) pour revue externe.

---

## 1. backend/engine.py — Fonctions globales (l.200–326)

```python
# ========================
# PRODUCTION-GRADE V3 (safe_reply, intent override, INTENT_ROUTER)
# ========================

SAFE_REPLY_FALLBACK = "D'accord. Je vous écoute."


def safe_reply(events: List[Event], session: Session) -> List[Event]:
    """
    Dernière barrière anti-silence (spec V3).
    Aucun message utilisateur ne doit mener à zéro output.
    """
    if not events:
        msg = SAFE_REPLY_FALLBACK
        session.add_message("agent", msg)
        return [Event("final", msg, conv_state=session.state)]
    for ev in events:
        if ev.text and ev.text.strip():
            return events
    msg = SAFE_REPLY_FALLBACK
    session.add_message("agent", msg)
    return [Event("final", msg, conv_state=session.state)]


def detect_strong_intent(text: str) -> Optional[str]:
    """
    Détecte les intents qui préemptent le flow en cours (CANCEL, MODIFY, TRANSFER).
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
    return None


def should_override_current_flow_v3(session: Session, message: str) -> bool:
    """
    Intent override avec garde-fou anti-boucle (spec V3).
    Ne pas rerouter si déjà dans le bon flow ou si même intent consécutif.
    TRANSFER : exiger une phrase explicite (éviter "humain" / "quelqu'un" seuls = interruption).
    """
    strong = detect_strong_intent(message)
    if not strong:
        return False
    # Ne pas transférer sur un mot court (interruption fréquente : "humain", "quelqu'un")
    if strong == "TRANSFER" and len(message.strip()) < 14:
        return False
    if strong == "CANCEL" and session.state in ("CANCEL_NAME", "CANCEL_CONFIRM"):
        return False
    if strong == "MODIFY" and session.state in ("MODIFY_NAME", "MODIFY_CONFIRM"):
        return False
    last = getattr(session, "last_intent", None)
    if strong == last:
        return False
    return True


def detect_correction_intent(text: str) -> bool:
    """Détecte si l'utilisateur demande à recommencer / corriger."""
    t = text.strip().lower()
    if not t:
        return False
    correction_words = [
        "attendez", "recommencez", "recommence", "repetez", "répétez",
        "non c'est pas", "pas ça", "refaites", "recommencer",
    ]
    return any(w in t for w in correction_words)


def should_trigger_intent_router(session: Session, user_message: str) -> tuple[bool, str]:
    """
    IVR Principe 3 — Un seul mécanisme de sortie universel.
    Détermine si on doit activer INTENT_ROUTER (menu 1/2/3/4).
    Seuils volontairement hauts : privilégier comprendre plutôt que transférer.
    """
    if session.state in ("INTENT_ROUTER", "TRANSFERRED", "CONFIRMED"):
        return False, ""
    if getattr(session, "global_recovery_fails", 0) >= 3:
        return True, "global_fails_3"
    if detect_correction_intent(user_message) and getattr(session, "correction_count", 0) >= 3:
        return True, "correction_repeated"
    if getattr(session, "consecutive_questions", 0) >= 7:
        return True, "blocked_state"
    return False, ""


def increment_recovery_counter(session: Session, context: str) -> int:
    """Incrémente le compteur de recovery pour un contexte. Retourne la valeur après incrément."""
    if context == "slot_choice":
        session.slot_choice_fails = getattr(session, "slot_choice_fails", 0) + 1
        return session.slot_choice_fails
    if context == "name":
        session.name_fails = getattr(session, "name_fails", 0) + 1
        return session.name_fails
    if context == "phone":
        session.phone_fails = getattr(session, "phone_fails", 0) + 1
        return session.phone_fails
    if context == "preference":
        session.preference_fails = getattr(session, "preference_fails", 0) + 1
        return session.preference_fails
    if context == "contact_confirm":
        session.contact_confirm_fails = getattr(session, "contact_confirm_fails", 0) + 1
        return session.contact_confirm_fails
    session.global_recovery_fails = getattr(session, "global_recovery_fails", 0) + 1
    return session.global_recovery_fails


def should_escalate_recovery(session: Session, context: str) -> bool:
    """True si ≥ MAX_CONTEXT_FAILS échecs sur ce contexte."""
    max_fails = getattr(Session, "MAX_CONTEXT_FAILS", 3)
    counters = {
        "slot_choice": getattr(session, "slot_choice_fails", 0),
        "name": getattr(session, "name_fails", 0),
        "phone": getattr(session, "phone_fails", 0),
        "preference": getattr(session, "preference_fails", 0),
        "contact_confirm": getattr(session, "contact_confirm_fails", 0),
    }
    return counters.get(context, getattr(session, "global_recovery_fails", 0)) >= max_fails
```

---

## 2. backend/engine.py — Pipeline handle_message (ordre strict)

Ordre appliqué à chaque message :

1. **Terminal gate** : si CONFIRMED ou TRANSFERRED → MSG_CONVERSATION_CLOSED, return.
2. **Anti-loop** : `session.turn_count += 1` ; si `turn_count > 25` → `_trigger_intent_router(session, "anti_loop_25", user_text)`.
3. **Intent override** : si `should_override_current_flow_v3(session, user_text)` → CANCEL / MODIFY / TRANSFER (TRANSFER uniquement si message ≥ 14 car. dans should_override).
4. **Guards** : vide (si ≥ 3 vides → INTENT_ROUTER), length, langue, spam.
5. **Session expired** → reset + MSG_SESSION_EXPIRED.
6. **Intent + correction** : incrément correction_count si correction ; `should_trigger_intent_router` → si True, `_trigger_intent_router` ; si correction et last_question_asked → rejouer dernière question.
7. **State handlers** : INTENT_ROUTER, PREFERENCE_CONFIRM, QUALIF_*, AIDE_CONTACT, WAIT_CONFIRM, CANCEL, MODIFY, CLARIFY, CONTACT_CONFIRM, START, FAQ_ANSWERED.
8. **Safe reply** : tous les retours passent par `safe_reply(..., session)`.

Extrait (début du pipeline) :

```python
        if session.state in ["CONFIRMED", "TRANSFERRED"]:
            msg = prompts.MSG_CONVERSATION_CLOSED
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]

        session.turn_count = getattr(session, "turn_count", 0) + 1
        max_turns = getattr(Session, "MAX_TURNS_ANTI_LOOP", 25)
        if session.turn_count > max_turns:
            return safe_reply(
                self._trigger_intent_router(session, "anti_loop_25", user_text or ""),
                session,
            )

        channel = getattr(session, "channel", "web")
        if should_override_current_flow_v3(session, user_text):
            strong = detect_strong_intent(user_text)
            session.last_intent = strong
            if strong == "CANCEL":
                return safe_reply(self._start_cancel(session), session)
            if strong == "MODIFY":
                return safe_reply(self._start_modify(session), session)
            if strong == "TRANSFER":
                session.state = "TRANSFERRED"
                msg = prompts.VOCAL_TRANSFER_COMPLEX if channel == "vocal" else prompts.MSG_TRANSFER
                ...
        if not user_text or not user_text.strip():
            session.empty_message_count = getattr(session, "empty_message_count", 0) + 1
            if session.empty_message_count >= 3:
                return safe_reply(
                    self._trigger_intent_router(session, "empty_repeated", user_text or ""),
                    session,
                )
            ...
```

---

## 3. backend/engine.py — TRANSFER en START (phrase ≥ 14 car.)

```python
            # TRANSFER → Transfert direct (doc: phrase explicite >=14 car., pas interruption courte)
            if intent == "TRANSFER":
                if len(user_text.strip()) >= 14:
                    session.state = "TRANSFERRED"
                    msg = prompts.VOCAL_TRANSFER_COMPLEX if channel == "vocal" else prompts.MSG_TRANSFER
                    session.add_message("agent", msg)
                    return safe_reply([Event("final", msg, conv_state=session.state)], session)
                # Message court type "humain" → traiter comme unclear, pas transfert
                return safe_reply(self._handle_faq(session, user_text, include_low=True), session)
```

---

## 4. backend/engine.py — _trigger_intent_router + _handle_intent_router

```python
    def _trigger_intent_router(
        self,
        session: Session,
        reason: str = "unknown",
        user_message: str = "",
    ) -> List[Event]:
        """Menu 1/2/3/4 quand perdu ou après 3 échecs (doc: privilégier comprendre). Logging structuré INFO."""
        import logging
        context = {
            "name": session.qualif_data.name,
            "motif": session.qualif_data.motif,
            "pref": session.qualif_data.pref,
            "contact": session.qualif_data.contact,
        }
        missing = [f for f in ["name", "motif", "pref", "contact"] if not context.get(f)]
        log_data = {
            "session_id": session.conv_id,
            "trigger_reason": reason,
            "previous_state": session.state,
            "missing_slots": missing,
            "turn_count": getattr(session, "turn_count", 0),
            "consecutive_questions": getattr(session, "consecutive_questions", 0),
            "global_recovery_fails": getattr(session, "global_recovery_fails", 0),
            "no_match_turns": session.no_match_turns,
            "user_last_message": (user_message or "")[:200],
            "all_counters": {
                "slot_choice": getattr(session, "slot_choice_fails", 0),
                "name": getattr(session, "name_fails", 0),
                "phone": getattr(session, "phone_fails", 0),
                "preference": getattr(session, "preference_fails", 0),
                "contact_confirm": getattr(session, "contact_confirm_fails", 0),
                "global": getattr(session, "global_recovery_fails", 0),
            },
        }
        logger = logging.getLogger("uwi.intent_router")
        logger.info(
            "intent_router_triggered reason=%s previous_state=%s missing=%s",
            reason,
            session.state,
            missing,
            extra=log_data,
        )
        channel = getattr(session, "channel", "web")
        session.state = "INTENT_ROUTER"
        session.last_question_asked = None
        session.consecutive_questions = 0
        session.global_recovery_fails = 0
        session.correction_count = 0
        session.empty_message_count = 0
        session.turn_count = 0
        session.slot_choice_fails = 0
        session.name_fails = 0
        session.phone_fails = 0
        session.preference_fails = 0
        session.contact_confirm_fails = 0
        msg = prompts.MSG_INTENT_ROUTER
        session.last_question_asked = msg
        session.add_message("agent", msg)
        return [Event("final", msg, conv_state=session.state)]

    def _handle_intent_router(self, session: Session, user_text: str) -> List[Event]:
        """Gestion du menu 1/2/3/4."""
        channel = getattr(session, "channel", "web")
        msg_lower = user_text.lower().strip()

        if any(p in msg_lower for p in ["un", "1", "premier", "rendez-vous", "rdv"]):
            session.state = "QUALIF_NAME"
            session.consecutive_questions = 0
            msg = prompts.get_qualif_question("name", channel=channel)
            ...
        if any(p in msg_lower for p in ["deux", "2", "deuxième", "annuler", "modifier"]):
            return self._start_cancel(session)
        if any(p in msg_lower for p in ["trois", "3", "troisième", "question"]):
            session.state = "START"
            msg = prompts.MSG_INTENT_ROUTER_FAQ
            ...
        if any(p in msg_lower for p in ["quatre", "4", "quatrième", "quelqu'un", "humain"]):
            session.state = "TRANSFERRED"
            msg = prompts.VOCAL_TRANSFER_COMPLEX if channel == "vocal" else prompts.MSG_TRANSFER
            ...

        session.global_recovery_fails = getattr(session, "global_recovery_fails", 0) + 1
        if session.global_recovery_fails >= 3:
            session.state = "TRANSFERRED"
            msg = prompts.VOCAL_STILL_UNCLEAR if channel == "vocal" else prompts.MSG_TRANSFER
            ...
        msg = prompts.MSG_INTENT_ROUTER_RETRY
        ...
```

---

## 5. backend/engine.py — CLARIFY (TRANSFER ≥14 car., 3 relances avant transfert)

```python
        # Intent TRANSFER (doc: phrase explicite >=14 car.)
        if intent == "TRANSFER" and len(user_text.strip()) >= 14:
            session.state = "TRANSFERRED"
            msg = prompts.VOCAL_TRANSFER_COMPLEX if channel == "vocal" else prompts.MSG_TRANSFER
            ...

        # Toujours pas clair → transfert après 3 relances (doc: privilégier comprendre)
        session.confirm_retry_count = getattr(session, "confirm_retry_count", 0) + 1
        if session.confirm_retry_count >= 3:
            session.state = "TRANSFERRED"
            msg = prompts.VOCAL_STILL_UNCLEAR if channel == "vocal" else prompts.MSG_TRANSFER
            ...

        msg = prompts.VOCAL_CLARIFY if channel == "vocal" else prompts.MSG_CLARIFY_WEB
```

---

## 6. backend/prompts.py — Nouvelles constantes (messages web / INTENT_ROUTER)

```python
# Clarification (web) — doc SCRIPT_CONVERSATION_AGENT
MSG_CLARIFY_WEB = "D'accord. Vous avez une question ou vous souhaitez prendre rendez-vous ?"
MSG_CLARIFY_WEB_START = "D'accord. Vous avez une question ou un autre besoin ?"

# Abandon / FAQ goodbye (web)
MSG_ABANDON_WEB = "Pas de problème. Bonne journée !"
MSG_FAQ_GOODBYE_WEB = "Parfait, bonne journée !"

# FAQ no match premier échec
MSG_FAQ_NO_MATCH_FIRST = "Je n'ai pas cette information. Souhaitez-vous prendre un rendez-vous ?"

# Cancel / Modify (web fallbacks)
MSG_CANCEL_ASK_NAME_WEB = "Pas de problème. C'est à quel nom ?"
MSG_MODIFY_ASK_NAME_WEB = "Pas de souci. C'est à quel nom ?"
MSG_CANCEL_NOT_FOUND_WEB = "Je n'ai pas trouvé de rendez-vous à ce nom. Pouvez-vous me redonner votre nom complet ?"
MSG_CANCEL_DONE_WEB = "C'est fait, votre rendez-vous est annulé. Bonne journée !"
MSG_CANCEL_KEPT_WEB = "Pas de souci, votre rendez-vous est maintenu. Bonne journée !"
MSG_MODIFY_NOT_FOUND_WEB = "Je n'ai pas trouvé de rendez-vous à ce nom. Pouvez-vous me redonner votre nom complet ?"
MSG_MODIFY_CONFIRM_WEB = "Vous avez un rendez-vous {slot_label}. Voulez-vous le déplacer ?"
MSG_CANCEL_CONFIRM_WEB = "Vous avez un rendez-vous {slot_label}. Voulez-vous l'annuler ?"
MSG_FAQ_TO_BOOKING_WEB = "Pas de souci. C'est à quel nom ?"
MSG_MODIFY_CANCELLED_WEB = "J'ai annulé l'ancien. Plutôt le matin ou l'après-midi pour le nouveau ?"

# INTENT_ROUTER option 3 (question)
MSG_INTENT_ROUTER_FAQ = "Quelle est votre question ?"
```

---

## 7. backend/session.py — Compteurs et constantes

```python
    # Production-grade V3
    last_intent: Optional[str] = None
    consecutive_questions: int = 0
    last_question_asked: Optional[str] = None
    global_recovery_fails: int = 0
    correction_count: int = 0
    pending_preference: Optional[str] = None
    empty_message_count: int = 0
    turn_count: int = 0

    # Recovery par contexte (AJOUT_COMPTEURS_RECOVERY)
    slot_choice_fails: int = 0
    name_fails: int = 0
    phone_fails: int = 0
    preference_fails: int = 0
    contact_confirm_fails: int = 0

    MAX_CONSECUTIVE_QUESTIONS = 3
    MAX_TURNS_ANTI_LOOP = 25
    MAX_CONTEXT_FAILS = 3
```

Dans `reset()` : tous ces champs sont remis à 0 (y compris slot_choice_fails, name_fails, etc.).

---

## Résumé des règles codées

| Règle (doc) | Implémentation |
|-------------|----------------|
| Pipeline : anti_loop → intent_override → guards → correction → state → safe_reply | Oui, dans cet ordre dans handle_message |
| TRANSFER uniquement si phrase ≥ 14 car. | should_override_current_flow_v3 + en START (intent TRANSFER) + en CLARIFY |
| 3 échecs avant INTENT_ROUTER | global_recovery_fails ≥ 3, correction_count ≥ 3, empty_message_count ≥ 3 |
| 3 retries dans le menu avant transfert | global_recovery_fails ≥ 3 dans _handle_intent_router |
| consecutive_questions ≥ 7 → INTENT_ROUTER | should_trigger_intent_router |
| turn_count > 25 → INTENT_ROUTER | En tête de handle_message après terminal gate |
| CLARIFY : 3 relances avant transfert | confirm_retry_count >= 3 dans _handle_clarify |
| Messages depuis prompts.py uniquement | Nouvelles constantes MSG_*_WEB, usage dans engine |
| Logs design signals (INFO, raison, état, slots, turn_count) | log_data dans _trigger_intent_router avec turn_count |

---

*Fichier généré pour revue — code réel dans backend/engine.py, backend/prompts.py, backend/session.py.*
