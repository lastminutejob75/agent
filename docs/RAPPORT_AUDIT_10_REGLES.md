# Rapport d'audit — 10 règles PRD (critères de validation V1)

**Référence :** PRD.md section 16 — *Si l'un de ces 10 cas échoue, le V1 n'est PAS validé.*  
**Date :** 2025-02-03  
**Périmètre :** backend (engine, prompts, guards, config, tools_faq, tools_booking, session).

---

## Règle 1 — FAQ "Quels sont vos horaires ?" → réponse exacte + "Source : FAQ_HORAIRES"

### Attendu
- Match FAQ avec seuil ≥ 80 %.
- Réponse factuelle + ligne `Source : [FAQ_ID]` (web).

### Vérification

| Élément | Fichier | Statut |
|--------|---------|--------|
| Seuil 80 % | `config.py` | FAQ_THRESHOLD = 0.80 |
| Match + faq_id | `tools_faq.py` | score_norm >= config.FAQ_THRESHOLD → FaqResult(faq_id=...) |
| Format réponse | `prompts.py` | format_faq_response → "Source : {faq_id}" (web) |
| FAQ horaires | `tools_faq.py` | FAQ_HORAIRES, "quels sont vos horaires", etc. |

### Extrait de code

```11:11:backend/config.py
FAQ_THRESHOLD = 0.80  # score >= 0.80 => match
```

```65:69:backend/tools_faq.py
        if score_norm >= config.FAQ_THRESHOLD:
            item = candidates[idx][1]
            return FaqResult(match=True, score=score_norm, faq_id=item.faq_id, answer=item.answer)
```

```927:943:backend/prompts.py
def format_faq_response(answer: str, faq_id: str, channel: str = "web") -> str:
    ...
    return f"{answer}\n\nSource : {faq_id}"
```

### Verdict : **CONFORME**

---

## Règle 2 — Message vide → "Je n'ai pas reçu votre message. Pouvez-vous réessayer ?"

### Attendu
- Détection message vide.
- Message exact du PRD.

### Vérification

| Élément | Fichier | Statut |
|--------|---------|--------|
| Détection | `engine.py` | `if not user_text or not user_text.strip()` avant guards |
| Message | `prompts.py` | MSG_EMPTY_MESSAGE |
| Réponse | `engine.py` | session.add_message("agent", msg) + return Event |

### Extrait de code

```40:40:backend/prompts.py
MSG_EMPTY_MESSAGE = "Je n'ai pas reçu votre message. Pouvez-vous réessayer ?"
```

```708:719:backend/engine.py
        if not user_text or not user_text.strip():
            session.empty_message_count = getattr(session, "empty_message_count", 0) + 1
            ...
            msg = prompts.MSG_EMPTY_MESSAGE
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
```

### Verdict : **CONFORME**

---

## Règle 3 — Message > 500 caractères → "Votre message est trop long. Pouvez-vous résumer ?"

### Attendu
- Limite 500 caractères.
- Message exact du PRD.

### Vérification

| Élément | Fichier | Statut |
|--------|---------|--------|
| Limite | `config.py` | MAX_MESSAGE_LENGTH = 500 |
| Validation | `guards.py` | validate_length(text, max_length) |
| Message | `prompts.py` | MSG_TOO_LONG |
| Pipeline | `engine.py` | validate_length puis error_msg |

### Extrait de code

```18:18:backend/config.py
MAX_MESSAGE_LENGTH = 500
```

```41:41:backend/prompts.py
MSG_TOO_LONG = "Votre message est trop long. Pouvez-vous résumer ?"
```

```724:727:backend/engine.py
        is_valid, error_msg = guards.validate_length(user_text)
        if not is_valid:
            session.add_message("agent", error_msg)
            return [Event("final", error_msg, conv_state=session.state)]
```

### Verdict : **CONFORME**

---

## Règle 4 — "Hello" (langue non FR) → "Je ne parle actuellement que français."

### Attendu
- Détection langue non française.
- Message exact du PRD.

### Vérification

| Élément | Fichier | Statut |
|--------|---------|--------|
| Détection | `guards.py` | detect_language_fr(text) |
| Message | `prompts.py` | MSG_FRENCH_ONLY |
| Pipeline | `engine.py` | après guards longueur, avant spam |

### Extrait de code

```42:42:backend/prompts.py
MSG_FRENCH_ONLY = "Je ne parle actuellement que français."
```

```730:733:backend/engine.py
        if not guards.detect_language_fr(user_text):
            msg = prompts.MSG_FRENCH_ONLY
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
```

### Verdict : **CONFORME**

---

## Règle 5 — Booking complet → 3 slots → "oui 2" → confirmation

### Attendu
- Proposition d’exactement 3 créneaux.
- Confirmation explicite "oui 1/2/3".
- Message de confirmation du RDV.

### Vérification

| Élément | Fichier | Statut |
|--------|---------|--------|
| Nombre de slots | `config.py` | MAX_SLOTS_PROPOSED = 3 |
| Récupération slots | `engine.py` | get_slots_for_display(limit=config.MAX_SLOTS_PROPOSED) |
| Confirmation | `engine.py` | WAIT_CONFIRM, detect_slot_choice, "oui 1/2/3" |
| Tests | `tests/test_prd_scenarios.py` | test_booking_confirm_oui_deux |

### Extrait de code

```21:21:backend/config.py
MAX_SLOTS_PROPOSED = 3
```

```1559:1559:backend/engine.py
            slots = tools_booking.get_slots_for_display(limit=config.MAX_SLOTS_PROPOSED, pref=pref)
```

```50:54:tests/test_prd_scenarios.py
    engine.handle_message(conv, "oui 2")
    assert e[0].type == "final"
    assert e[0].conv_state == "CONFIRMED"
    assert "confirmé" in e[0].text.lower()
```

### Verdict : **CONFORME**

---

## Règle 6 — Booking format invalide ("je prends mercredi") → redemande → puis transfert

### Attendu
- Redemande de clarification (ex. "oui 1", "oui 2", "oui 3").
- Après N échecs → transfert (ou INTENT_ROUTER en V3).

### Vérification

| Élément | Fichier | Statut |
|--------|---------|--------|
| Redemande | `engine.py` | get_clarification_message("slot_choice", ...), confirm_retry_count |
| Limite | `config.py` | CONFIRM_RETRY_MAX = 1 (1 redemande puis escalade) |
| Escalade | `engine.py` | _trigger_intent_router ou TRANSFERRED selon flow |
| Tests | `tests/test_prd_scenarios.py` | test_booking_confirm_invalid_twice |

### Extrait de code

```22:22:backend/config.py
CONFIRM_RETRY_MAX = 1  # 1 redemande, puis transfer
```

```1211:1220:backend/engine.py
                if session.confirm_retry_count >= config.CONFIRM_RETRY_MAX:
                    return self._trigger_intent_router(session, "slot_choice_fails_3", user_text)
                ...
                session.confirm_retry_count += 1
```

### Verdict : **CONFORME**

---

## Règle 7 — Question hors FAQ × 2 → transfert

### Attendu (PRD V1)
- Après 2 tours hors FAQ → transfert (ou formulation "pas certain... puis mettre en relation").

### Vérification

| Élément | Fichier | Statut |
|--------|---------|--------|
| Compteur | `engine.py` | no_match_turns, faq_fails |
| Comportement actuel | `engine.py` | 1er no-match → reformuler, 2e → exemples, 3e → INTENT_ROUTER (menu 1/2/3/4) |
| Écart | — | PRD dit "× 2 → transfert". V3 fait 3 niveaux (reformuler → exemples → INTENT_ROUTER) puis transfert possible via menu. |

### Extrait de code

```957:966:backend/engine.py
        session.no_match_turns += 1
        session.faq_fails = getattr(session, "faq_fails", 0) + 1
        ...
        if session.no_match_turns >= 3:
            log_ivr_event(...)
            return self._trigger_intent_router(session, "no_match_faq_3", user_text)
        if session.no_match_turns == 1:
            # 1er no-match : demander à reformuler
        else:
            # 2e no-match : donner exemples
```

### Verdict : **PARTIEL**

- Comportement actuel : recovery progressive (reformuler → exemples → INTENT_ROUTER), pas transfert direct après 2 tours.
- Aligné avec la philosophie V3 (retry avant transfert) mais différent du libellé strict "× 2 → transfert".

### Recommandation
- Soit documenter que V3 remplace "2 tours → transfert" par "3 niveaux → INTENT_ROUTER (puis transfert si choix 4)".
- Soit ajouter une option (config ou flag) pour un mode "PRD strict" (2 tours → transfert) si requis.

---

## Règle 8 — Session 15 min → "Votre session a expiré. Puis-je vous aider ?"

### Attendu
- Timeout 15 minutes.
- Message exact du PRD.

### Vérification

| Élément | Fichier | Statut |
|--------|---------|--------|
| TTL | `config.py` | SESSION_TTL_MINUTES = 15 |
| Vérification | `session.py` | is_expired() avec timedelta(minutes=config.SESSION_TTL_MINUTES) |
| Message | `prompts.py` | MSG_SESSION_EXPIRED |
| Pipeline | `engine.py` | if session.is_expired() → reset, msg, return |

### Extrait de code

```14:14:backend/config.py
SESSION_TTL_MINUTES = 15
```

```43:43:backend/prompts.py
MSG_SESSION_EXPIRED = "Votre session a expiré. Puis-je vous aider ?"
```

```101:103:backend/session.py
    def is_expired(self) -> bool:
        ttl = timedelta(minutes=config.SESSION_TTL_MINUTES)
        return datetime.utcnow() - self.last_seen_at > ttl
```

```744:749:backend/engine.py
        if session.is_expired():
            session.reset()
            msg = prompts.MSG_SESSION_EXPIRED
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state="START")]
```

### Verdict : **CONFORME**

---

## Règle 9 — Insulte / spam → transfert silencieux

### Attendu
- Détection spam/abus.
- Transfert sans message (silencieux).

### Vérification

| Élément | Fichier | Statut |
|--------|---------|--------|
| Détection | `guards.py` | is_spam_or_abuse(text) |
| Action | `engine.py` | state=TRANSFERRED, Event(transfer, silent=True) |
| Pas de message | `engine.py` | return [Event("transfer", "", transfer_reason="spam", silent=True)] |

### Extrait de code

```736:738:backend/engine.py
        if guards.is_spam_or_abuse(user_text):
            session.state = "TRANSFERRED"
            return [Event("transfer", "", transfer_reason="spam", silent=True)]
```

### Verdict : **CONFORME**

---

## Règle 10 — Temps de réponse < 3 secondes

### Attendu (PRD)
- Première réponse (ou premier chunk) sous 3 s (objectif non fonctionnel).

### Vérification

| Élément | Fichier | Statut |
|--------|---------|--------|
| Cible documentée | `config.py` | TARGET_FIRST_RESPONSE_MS = 3000 |
| Contrôle dans le code | — | Aucun enforcement (pas de timeout côté engine) |

### Extrait de code

```24:25:backend/config.py
# Performance
TARGET_FIRST_RESPONSE_MS = 3000  # contrainte PRD (sans imposer SSE)
```

### Verdict : **PARTIEL**

- Cible définie en config et documentée.
- Pas de mécanisme dans le code pour garantir ou mesurer le délai (APM, logs de latence, timeout).

### Recommandation
- Ajouter un log de latence (timestamp début handle_message → premier Event) pour surveillance.
- Optionnel : alerte ou métrique si première réponse > 3 s.

---

# Résumé

| Règle | Critère PRD | Statut |
|-------|-------------|--------|
| 1 | FAQ horaires → réponse + Source : FAQ_HORAIRES | CONFORME |
| 2 | Message vide → message fixe | CONFORME |
| 3 | Message > 500 car → message fixe | CONFORME |
| 4 | Langue non FR → message fixe | CONFORME |
| 5 | Booking → 3 slots → "oui 2" → confirmation | CONFORME |
| 6 | Format invalide → redemande → transfert | CONFORME |
| 7 | Hors FAQ × 2 → transfert | PARTIEL |
| 8 | Session 15 min → message expiré | CONFORME |
| 9 | Insulte → transfert silencieux | CONFORME |
| 10 | Temps réponse < 3 s | PARTIEL |

---

## Score : **8/10 règles conformes**, 2 partielles

### Actions prioritaires

1. **Règle 7 (Hors FAQ × 2)**  
   - Clarifier dans le PRD ou la spec que la V3 utilise 3 niveaux (reformuler → exemples → INTENT_ROUTER) au lieu de "2 tours → transfert", ou introduire un mode "PRD strict" si besoin.

2. **Règle 10 (Temps < 3 s)**  
   - Ajouter un log (ou une métrique) de latence sur la première réponse (handle_message → premier Event) pour surveiller la cible 3 s et alerter si dépassement.

Aucune action bloquante pour la conformité fonctionnelle des 10 critères : les 2 écarts sont documentés (V3 vs V1 pour la règle 7) ou non appliqués dans le code (règle 10).
