# Script de Mise à Jour Incrémentale — Agent Vocal UWI
**Améliorer sans casser ce qui fonctionne**

---

## 🎯 Objectif

Appliquer les améliorations **Niveau 1 (Production-Grade)** SANS toucher aux fonctionnalités qui marchent déjà bien.

**Principe** : Patch minimal, pas de refactoring global.

---

## ✅ Ce qui FONCTIONNE déjà (NE PAS TOUCHER)

### 1. Caller ID automatique ☎️

```python
# ✅ À CONSERVER TEL QUEL
# Logique actuelle :
# - session.caller_id peuplé automatiquement
# - Confirmation : "Votre numéro est bien le 06 12 34 56 78 ?"
# - Si "oui" → valider
# - Si "non" → demander manuellement

# NE PAS MODIFIER :
- session.caller_id (source de données)
- État PHONE_CONFIRM (si existe)
- handle_phone_confirm() (si existe)
- format_phone_for_tts() (si existe)
```

### 2. Google Calendar intégration 📅

```python
# ✅ À CONSERVER TEL QUEL
# backend/google_calendar.py
# - Recherche créneaux
# - Création RDV
# - Logging
# 
# NE PAS MODIFIER ce fichier
```

### 3. Entity extraction existante 🧠

```python
# ✅ À CONSERVER et ENRICHIR
# backend/entity_extraction.py
# - extract_name()
# - extract_phone()
# - extract_time_preference()
# 
# GARDER les fonctions actuelles
# AJOUTER : infer_preference_from_context() (si pas déjà présent)
```

### 4. Prompts actuels qui fonctionnent 💬

```python
# ✅ À CONSERVER
# backend/prompts.py
# - First message
# - Messages de qualification (nom, préférence, contact)
# - Messages de confirmation RDV
# 
# GARDER tous les messages actuels
# AJOUTER : Messages INTENT_ROUTER + Recovery (si pas présents)
```

---

## 🔧 Ce qu'il FAUT AJOUTER/MODIFIER (améliorations Niveau 1)

### 1. Session enrichie (ajouts uniquement)

```python
# Fichier : backend/session.py (ou équivalent)

# ✅ AJOUTER ces champs à la Session existante (pas de suppression)
@dataclass
class Session:
    # ... champs existants (GARDER) ...
    id: str
    state: str
    channel: str
    caller_id: Optional[str] = None  # ← Déjà présent, GARDER
    
    # ========================================
    # NOUVEAUX CHAMPS (à ajouter)
    # ========================================
    last_intent: Optional[str] = None
    last_question_asked: Optional[str] = None
    consecutive_questions: int = 0
    turn_count: int = 0
    correction_count: int = 0
    empty_message_count: int = 0
    
    # Recovery counters (à ajouter)
    slot_choice_fails: int = 0
    name_fails: int = 0
    phone_fails: int = 0
    preference_fails: int = 0
    global_recovery_fails: int = 0
    
    MAX_TURNS_BEFORE_ESCALATION: int = 25
    MAX_CONSECUTIVE_QUESTIONS: int = 3
    
    # Méthodes à ajouter
    def increment_turn(self):
        self.turn_count += 1
    
    def is_looping(self) -> bool:
        return self.turn_count >= self.MAX_TURNS_BEFORE_ESCALATION
    
    def is_terminal_state(self) -> bool:
        return self.state in ['CONFIRMED', 'CANCEL_DONE', 'DONE', 'TRANSFERRED']
```

---

### 2. Intent Override (nouveau fichier)

```python
# Fichier : backend/intent_override.py (CRÉER)

"""
Détection d'intents forts qui préemptent le flow actuel.
À appeler AVANT tout traitement dans process_message().
"""

from typing import Optional

# Intents forts (priorité absolue)
CANCEL_PATTERNS = [
    "annuler", "annulation", "supprimer",
    "annuler mon rdv", "supprimer mon rendez-vous",
    "je veux annuler"
]

MODIFY_PATTERNS = [
    "modifier", "modification", "changer", "déplacer",
    "reporter", "reprogrammer", "bouger",
    "je veux modifier", "changer mon rendez-vous"
]

TRANSFER_PATTERNS = [
    "humain", "personne", "quelqu'un", "conseiller",
    "parler à", "joindre", "opérateur", "secrétaire"
]

ABANDON_PATTERNS = [
    "je rappelle", "rappellerai", "plus tard",
    "laissez tomber", "tant pis", "c'est bon"
]

CORRECTION_PATTERNS = [
    "attendez", "attends", "erreur",
    "je me suis trompé", "c'est pas ça",
    "rectification", "correction"
]


def detect_strong_intent(message: str) -> Optional[str]:
    """
    Détection déterministe des intents forts.
    
    Returns:
        'CANCEL' | 'MODIFY' | 'TRANSFER' | 'ABANDON' | None
    """
    msg_lower = message.lower().strip()
    
    if any(pattern in msg_lower for pattern in CANCEL_PATTERNS):
        return 'CANCEL'
    if any(pattern in msg_lower for pattern in MODIFY_PATTERNS):
        return 'MODIFY'
    if any(pattern in msg_lower for pattern in TRANSFER_PATTERNS):
        return 'TRANSFER'
    if any(pattern in msg_lower for pattern in ABANDON_PATTERNS):
        return 'ABANDON'
    
    return None


def detect_correction_intent(message: str) -> bool:
    """Détecte si l'utilisateur veut corriger sa dernière réponse"""
    msg_lower = message.lower().strip()
    return any(pattern in msg_lower for pattern in CORRECTION_PATTERNS)


def should_override_current_flow(session, message: str) -> bool:
    """
    Détermine si un intent fort doit interrompre le flow actuel.
    """
    strong = detect_strong_intent(message)
    
    if not strong:
        return False
    
    # Ne pas override si déjà dans le bon flow
    if strong == 'CANCEL' and session.state == 'CANCEL_FLOW':
        return False
    if strong == 'MODIFY' and session.state == 'MODIFY_FLOW':
        return False
    if strong == 'TRANSFER' and session.state == 'TRANSFERRED':
        return False
    
    # Éviter boucles
    if strong == session.last_intent:
        return False
    
    return True
```

---

### 3. Recovery Policy (nouveau fichier)

```python
# Fichier : backend/recovery.py (CRÉER)

"""
Recovery policy graduée (3 niveaux avant transfert).
"""

from typing import Optional

class RecoveryMessages:
    """Messages par contexte et niveau d'échec"""
    
    SLOT_CHOICE = {
        1: "Je n'ai pas compris. Dites : un, deux ou trois.",
        2: "Dites le numéro. Par exemple : 'le deux'. Alors ?",
        3: "Dites : le premier, le deuxième, ou le troisième.",
        4: None  # Transfert
    }
    
    NAME = {
        1: "Je n'ai pas noté votre nom. Répétez ?",
        2: "Votre nom et prénom. Par exemple : 'Martin Dupont'.",
        3: None  # Transfert
    }
    
    PHONE = {
        1: "Je n'ai pas compris. Redites chiffre par chiffre.",
        2: "Par exemple : zéro six, douze. Allez-y.",
        3: "Vous préférez donner un email à la place ?",
        4: None
    }
    
    PREFERENCE = {
        1: "Préférez-vous le matin ou l'après-midi ?",
        2: "Dites juste : matin ou après-midi.",
        3: "Je propose le matin. Ça vous va ?",
        4: None
    }


def get_recovery_message(context: str, fail_count: int) -> Optional[str]:
    """Retourne le message de recovery approprié"""
    messages_map = {
        'slot_choice': RecoveryMessages.SLOT_CHOICE,
        'name': RecoveryMessages.NAME,
        'phone': RecoveryMessages.PHONE,
        'preference': RecoveryMessages.PREFERENCE
    }
    messages = messages_map.get(context, {})
    return messages.get(fail_count)


def handle_recovery(session, context: str) -> dict:
    """
    Gestion complète de la recovery.
    
    Returns:
        {
            'message': str,
            'action': 'retry' | 'transfer',
            'state': str
        }
    """
    # Incrémenter compteur selon contexte
    if context == 'slot_choice':
        session.slot_choice_fails += 1
        fail_count = session.slot_choice_fails
    elif context == 'name':
        session.name_fails += 1
        fail_count = session.name_fails
    elif context == 'phone':
        session.phone_fails += 1
        fail_count = session.phone_fails
    elif context == 'preference':
        session.preference_fails += 1
        fail_count = session.preference_fails
    else:
        session.global_recovery_fails += 1
        fail_count = session.global_recovery_fails
    
    recovery_msg = get_recovery_message(context, fail_count)
    
    if recovery_msg is None:
        # Transfert nécessaire
        return {
            'message': "Je vais vous mettre en relation. Un instant.",
            'action': 'transfer',
            'state': 'TRANSFERRED'
        }
    
    # Retry
    return {
        'message': recovery_msg,
        'action': 'retry',
        'state': session.state
    }
```

---

### 4. INTENT_ROUTER (ajouts dans engine.py et prompts.py)

```python
# Fichier : backend/prompts.py (AJOUTER)

# ========================================
# INTENT_ROUTER (menu reset universel)
# ========================================

INTENT_ROUTER_MENU = """Je vais simplifier. Dites :
Un : pour prendre un rendez-vous.
Deux : pour annuler ou modifier.
Trois : pour poser une question.
Quatre : pour parler à quelqu'un.
Dites simplement : un, deux, trois ou quatre."""


# Fichier : backend/engine.py (AJOUTER ces fonctions)

def trigger_intent_router(session, reason: str, user_message: str) -> dict:
    """
    Menu reset universel (sortie de secours).
    """
    from .prompts import INTENT_ROUTER_MENU
    
    # Logger
    import logging
    logger = logging.getLogger('uwi.intent_router')
    logger.info('intent_router_triggered', extra={
        'session_id': session.id,
        'reason': reason,
        'previous_state': session.state,
        'user_message': user_message
    })
    
    # Réinitialiser
    session.state = 'INTENT_ROUTER'
    session.last_question_asked = None
    session.consecutive_questions = 0
    
    return {
        'message': INTENT_ROUTER_MENU,
        'state': 'INTENT_ROUTER'
    }


def handle_intent_router_response(session, user_message: str) -> dict:
    """Gestion menu INTENT_ROUTER (4 choix)"""
    msg_lower = user_message.lower().strip()
    
    # Choix 1 : Booking
    if any(p in msg_lower for p in ["un", "1", "premier", "rendez-vous", "rdv"]):
        session.state = 'BOOKING_COLLECT'
        return {'message': "Très bien. C'est à quel nom ?", 'state': 'BOOKING_COLLECT'}
    
    # Choix 2 : Cancel/Modify
    if any(p in msg_lower for p in ["deux", "2", "deuxième", "annuler", "modifier"]):
        session.state = 'CANCEL_OR_MODIFY'
        return {'message': "Annuler ou modifier ? Dites : annuler ou modifier.", 'state': 'CANCEL_OR_MODIFY'}
    
    # Choix 3 : FAQ
    if any(p in msg_lower for p in ["trois", "3", "troisième", "question"]):
        session.state = 'FAQ_FLOW'
        return {'message': "Quelle est votre question ?", 'state': 'FAQ_FLOW'}
    
    # Choix 4 : Transfer
    if any(p in msg_lower for p in ["quatre", "4", "quatrième", "quelqu'un", "humain"]):
        session.state = 'TRANSFERRED'
        return {'message': "Je vous mets en relation. Un instant.", 'state': 'TRANSFERRED'}
    
    # Incompréhension → retry 1 fois puis transfert
    session.global_recovery_fails += 1
    if session.global_recovery_fails >= 2:
        session.state = 'TRANSFERRED'
        return {'message': "Je vais vous passer quelqu'un. Un instant.", 'state': 'TRANSFERRED'}
    
    return {'message': "Dites juste le numéro. Par exemple : 'un' pour rendez-vous.", 'state': 'INTENT_ROUTER'}


def should_trigger_intent_router(session, user_message: str) -> bool:
    """Détermine si on doit activer INTENT_ROUTER"""
    # ≥2 échecs globaux
    if session.global_recovery_fails >= 2:
        return True
    
    # Correction répétée
    if session.correction_count >= 2:
        return True
    
    # Message vide répété
    if session.empty_message_count >= 2:
        return True
    
    # >5 tours sans progression
    if session.consecutive_questions >= 5:
        return True
    
    return False
```

---

### 5. Safe Reply (dernière barrière)

```python
# Fichier : backend/engine.py (AJOUTER)

def safe_reply(response: dict, session) -> dict:
    """
    Dernière barrière anti-silence.
    AUCUN message ne doit être vide.
    """
    if not response or not response.get("message") or not response["message"].strip():
        # Logger
        import logging
        logger = logging.getLogger('uwi.safe_reply')
        logger.warning('safe_reply_triggered', extra={
            'session_id': session.id,
            'state': session.state,
            'response': response
        })
        
        # Fallback absolu
        return {
            "message": "D'accord. Je vous écoute.",
            "state": session.state
        }
    
    return response
```

---

### 6. Pipeline strict dans process_message (MODIFIER)

```python
# Fichier : backend/engine.py (MODIFIER process_message existant)

async def process_message(session, user_message: str):
    """
    Pipeline avec ordre NON NÉGOCIABLE.
    
    ✅ GARDE CE QUI FONCTIONNE (Caller ID, Google Calendar, etc.)
    ✅ AJOUTE les garde-fous (intent override, recovery, safe_reply)
    """
    
    # Importer les nouveaux modules
    from .intent_override import (
        should_override_current_flow,
        detect_strong_intent,
        detect_correction_intent
    )
    from .recovery import handle_recovery
    
    # Incrémenter tour
    session.increment_turn()
    
    # ========================================
    # 1. ANTI-LOOP GUARD
    # ========================================
    if session.is_looping() and not session.is_terminal_state():
        if session.state == 'INTENT_ROUTER':
            session.state = 'TRANSFERRED'
            return safe_reply({
                'message': "Je vais vous passer quelqu'un. Un instant.",
                'state': 'TRANSFERRED'
            }, session)
        else:
            return safe_reply(
                trigger_intent_router(session, 'antiloop_25_turns', user_message),
                session
            )
    
    # ========================================
    # 2. INTENT OVERRIDE CRITIQUES
    # ========================================
    if should_override_current_flow(session, user_message):
        strong = detect_strong_intent(user_message)
        session.last_intent = strong
        
        if strong == 'CANCEL':
            session.state = 'CANCEL_FLOW'
            return safe_reply({'message': "Pas de problème. C'est à quel nom ?"}, session)
        elif strong == 'TRANSFER':
            session.state = 'TRANSFERRED'
            return safe_reply({'message': "Je vais vous mettre en relation. Un instant."}, session)
        elif strong == 'ABANDON':
            session.state = 'DONE'
            return safe_reply({'message': "Pas de souci. Au revoir !"}, session)
        elif strong == 'MODIFY':
            session.state = 'MODIFY_FLOW'
            return safe_reply({'message': "D'accord. C'est à quel nom ?"}, session)
    
    # ========================================
    # 3. GUARDS BASIQUES
    # ========================================
    if not user_message.strip():
        session.empty_message_count += 1
        if session.empty_message_count >= 2:
            return safe_reply(trigger_intent_router(session, 'empty_repeated', user_message), session)
        return safe_reply({'message': "Je n'ai rien entendu. Répétez ?"}, session)
    
    if len(user_message) > 500:
        return safe_reply({'message': "C'est un peu long. Résumez ?"}, session)
    
    # ========================================
    # 4. CORRECTION
    # ========================================
    if detect_correction_intent(user_message) and session.last_question_asked:
        session.correction_count += 1
        if session.correction_count >= 2:
            return safe_reply(trigger_intent_router(session, 'correction_repeated', user_message), session)
        return safe_reply({'message': session.last_question_asked, 'state': session.state}, session)
    
    # ========================================
    # 5. TRIGGERS RECOVERY GLOBAUX
    # ========================================
    if should_trigger_intent_router(session, user_message):
        return safe_reply(trigger_intent_router(session, 'unified_fallback', user_message), session)
    
    # ========================================
    # 6. STATE HANDLER (TON CODE ACTUEL)
    # ========================================
    # ✅ GARDER ton code existant ici (handle_start, handle_booking_collect, etc.)
    # ✅ NE PAS TOUT RÉÉCRIRE
    
    if session.state == 'INTENT_ROUTER':
        response = handle_intent_router_response(session, user_message)
    
    elif session.state == 'START':
        response = handle_start(session, user_message)  # ← TON CODE ACTUEL
    
    elif session.state == 'BOOKING_COLLECT':
        response = handle_booking_collect(session, user_message)  # ← TON CODE ACTUEL
    
    elif session.state == 'PHONE_CONFIRM':
        response = handle_phone_confirm(session, user_message)  # ← TON CODE ACTUEL (Caller ID)
    
    elif session.state == 'SLOTS_CONFIRM':
        response = handle_slots_confirm(session, user_message)  # ← TON CODE ACTUEL
    
    # ... autres états (garder ton code existant)
    
    else:
        response = {'message': "État non géré.", 'state': 'TRANSFERRED'}
    
    # ========================================
    # 7. SAFE REPLY (dernière barrière)
    # ========================================
    return safe_reply(response, session)
```

---

## 🎯 Instructions pour Cursor (prompt)

```
OBJECTIF : Améliorer l'agent vocal SANS casser ce qui fonctionne.

RÈGLE ABSOLUE : NE PAS TOUCHER :
- Caller ID automatique (session.caller_id, PHONE_CONFIRM, format_phone_for_tts)
- Google Calendar intégration (backend/google_calendar.py)
- Prompts actuels qui fonctionnent (messages de qualification)
- Entity extraction existante (extract_name, extract_phone, extract_time_preference)

ACTIONS À FAIRE :

1. ENRICHIR Session (ajouter nouveaux champs, ne rien supprimer) :
   - last_intent, last_question_asked, consecutive_questions, turn_count
   - Compteurs recovery : slot_choice_fails, name_fails, phone_fails, preference_fails, global_recovery_fails
   - Méthodes : increment_turn(), is_looping(), is_terminal_state()

2. CRÉER backend/intent_override.py :
   - detect_strong_intent() : CANCEL/MODIFY/TRANSFER/ABANDON
   - detect_correction_intent()
   - should_override_current_flow()

3. CRÉER backend/recovery.py :
   - RecoveryMessages (3 niveaux par contexte)
   - get_recovery_message()
   - handle_recovery()

4. AJOUTER dans backend/prompts.py :
   - INTENT_ROUTER_MENU (menu 4 choix)
   - (garder tous les messages actuels)

5. AJOUTER dans backend/engine.py :
   - safe_reply() (dernière barrière)
   - trigger_intent_router()
   - handle_intent_router_response()
   - should_trigger_intent_router()

6. MODIFIER process_message() dans backend/engine.py :
   - Ajouter pipeline strict AVANT ton code actuel :
     1. Anti-loop guard
     2. Intent override
     3. Guards basiques
     4. Correction
     5. Triggers recovery
   - GARDER ton code de state handling existant
   - AJOUTER safe_reply() en dernier

7. LOGGING structuré :
   - Logger intent_override, intent_router_trigger, safe_reply_trigger
   - Niveau INFO (pas WARNING/ERROR)

CONTRAINTES :
- Minimal changes : ajouter, ne pas supprimer
- Garder Caller ID tel quel (session.caller_id → PHONE_CONFIRM → validation)
- Pas de refactoring global
- Pas de nouveaux fichiers sauf intent_override.py et recovery.py
- Ordre pipeline NON NÉGOCIABLE (voir point 6)

TESTS à ajouter (créer tests/test_niveau1.py) :
- "oui" ambigu → pas de silence
- "annuler" pendant booking → switch CANCEL_FLOW
- 2 incompréhensions → INTENT_ROUTER
- handler None → safe_reply actif
- Caller ID confirmé → passe aux créneaux (garder logique actuelle)

Ne crée pas de nouvelle architecture. Patch minimal, comportement maximal.
```

---

## ✅ Checklist de validation (après Cursor)

### Vérifier que ça marche toujours

- [ ] **Caller ID** : Numéro détecté automatiquement
- [ ] **Confirmation phone** : "Votre numéro est bien le 06... ?" fonctionne
- [ ] **Google Calendar** : Créneaux récupérés correctement
- [ ] **Booking flow** : Nom → Préférence → Phone → Créneaux → Confirmation

### Vérifier les nouveautés

- [ ] **Intent override** : "annuler" pendant booking → switch
- [ ] **Recovery** : 2 incompréhensions → reformulation/exemple/transfert
- [ ] **INTENT_ROUTER** : Menu 4 choix après blocage
- [ ] **Safe reply** : Jamais de message vide
- [ ] **Anti-loop** : >25 tours → INTENT_ROUTER puis transfert

### Tests manuels

```bash
# 1. Tests automatiques
pytest tests/test_niveau1.py -v

# 2. Test Caller ID (ne doit pas casser)
# - Lancer agent
# - Caller ID dispo → agent confirme (pas demande)
# - User dit "oui" → passe aux créneaux
# - User dit "non" → demande numéro manuellement

# 3. Test intent override
# - Démarrer booking
# - Dire "annuler" → doit switcher vers CANCEL_FLOW
```

---

## 📊 Résultat attendu

| Fonctionnalité | Avant | Après |
|----------------|-------|-------|
| **Caller ID** | ✅ Fonctionne | ✅ Fonctionne (conservé) |
| **Google Calendar** | ✅ Fonctionne | ✅ Fonctionne (conservé) |
| **Intent override** | ❌ Absent | ✅ Ajouté |
| **Recovery** | ❌ Absent | ✅ Ajouté |
| **INTENT_ROUTER** | ❌ Absent | ✅ Ajouté |
| **Safe reply** | ❌ Absent | ✅ Ajouté |
| **Anti-loop** | ❌ Absent | ✅ Ajouté |

**Temps estimé Cursor** : 2-3h  
**Risque de casse** : Faible (ajouts uniquement, pas de suppression)

---

**Script prêt pour Cursor — Amélioration sans régression** ✅

---

## 📍 État dans ce dépôt (alignement avec la codebase actuelle)

Ce script a été copié dans le projet. Voici le **mapping** avec l’implémentation actuelle (sans créer de nouveaux fichiers `intent_override.py` ni `recovery.py`) :

| Élément du script | Dans ce dépôt |
|-------------------|---------------|
| **Session enrichie** | `backend/session.py` : `last_intent`, `last_question_asked`, `consecutive_questions`, `turn_count`, `correction_count`, `empty_message_count`, `global_recovery_fails`, `MAX_CONSECUTIVE_QUESTIONS`, `MAX_TURNS_ANTI_LOOP`. Pas de `slot_choice_fails` / `name_fails` / `phone_fails` / `preference_fails` ni de méthodes `increment_turn()`, `is_looping()`, `is_terminal_state()` (équivalent : test `turn_count > MAX_TURNS_ANTI_LOOP` dans engine). |
| **Intent override** | `backend/engine.py` : `detect_strong_intent()`, `detect_correction_intent()`, `should_override_current_flow_v3()`. Patterns dans `backend/prompts.py` (CANCEL_PATTERNS, MODIFY_PATTERNS, TRANSFER_PATTERNS). Pas de fichier séparé `intent_override.py`. |
| **Recovery** | `backend/prompts.py` : `ClarificationMessages`, `get_clarification_message()`. Dégradation progressive dans `engine.py` (retry par contexte). Pas de fichier `recovery.py` ni de compteurs par contexte (slot_choice_fails, etc.). |
| **INTENT_ROUTER** | `backend/prompts.py` : `MSG_INTENT_ROUTER`, `MSG_INTENT_ROUTER_RETRY`. `backend/engine.py` : `_trigger_intent_router()`, `_handle_intent_router()`, `should_trigger_intent_router()`. |
| **Safe reply** | `backend/engine.py` : `safe_reply(events, session)` (signature List[Event], pas dict). |
| **Pipeline strict** | `backend/engine.py` : ordre 1. Anti-loop → 2. Intent override → 3. Guards → 4. Correction / recovery → 5. State handler → 6. Safe reply. Méthode : `handle_message()` (synchrone, pas `async process_message`). |
| **Caller ID** | `session.customer_phone` (pas `caller_id`). États : QUALIF_CONTACT, CONTACT_CONFIRM, etc. (pas PHONE_CONFIRM). |
| **Tests Niveau 1** | `tests/test_niveau1.py` (10 scénarios). |

Pour aller plus loin selon le script (optionnel) : ajouter dans `Session` les champs `slot_choice_fails`, `name_fails`, `phone_fails`, `preference_fails` et les méthodes `increment_turn()`, `is_looping()`, `is_terminal_state()` si tu veux un alignement 100 % avec la recovery policy par contexte.
