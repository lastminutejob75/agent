# Plan de refacto : Fix #9, #4, #6

## État actuel (structure Session + sérialisation)

### Champs “compteurs / contact” concernés (Fix #9)

| Champ Session | Utilisation | Sérialisé où |
|---------------|-------------|--------------|
| `contact_retry_count` | QUALIF_CONTACT retries | SQLite row, codec |
| `partial_phone_digits` | Accumulation chiffres vocal | SQLite row |
| `contact_mode` | "phone" \| "email" | reset() only, pas dans codec |
| `contact_fails` | Échecs contact (2 → transfert) | codec |
| `phone_fails` | Échecs saisie téléphone | codec |
| `contact_confirm_fails` | Échecs confirmation contact | codec |
| `contact_confirm_intent_repeat_count` | "je veux un rdv" en CONTACT_CONFIRM | — |
| `slot_choice_fails` | Échecs choix 1/2/3 | codec |
| `name_fails` | Échecs nom | codec |
| `preference_fails` | Échecs préférence | codec |
| `confirm_retry_count` | Confirmation créneau | SQLite, codec |
| `no_match_turns` | Hors FAQ | SQLite, codec |

**Sérialisation :**
- **SQLite** (`session_store_sqlite`) : colonnes explicites pour `contact_retry_count`, `partial_phone_digits` ; le reste dans le **pickle** (tout l’objet Session).
- **Postgres / checkpoints** (`session_codec`) : `session_to_dict` / `session_from_dict` pour `load_session_pg_first` ; liste explicite de compteurs (no_match_turns, confirm_retry_count, contact_retry_count, contact_fails, slot_choice_fails, name_fails, phone_fails, preference_fails, contact_confirm_fails, turn_count, intent_router_visits). **Pas** de `partial_phone_digits` ni `contact_mode` dans le codec actuel.

---

## Fix #9 — Compteurs contact unifiés (Postgres-friendly)

### Objectif
Un seul namespace sérialisable JSON, rétrocompatible.

### 1) Structure cible

```python
# session.py
session.recovery: Dict[str, Any] = field(default_factory=lambda: {
    "contact": {"fails": 0, "retry": 0, "mode": None},
    "phone": {"partial": "", "turns": 0},
    "confirm_contact": {"fails": 0, "intent_repeat": 0},
    "slot_choice": {"fails": 0},
    "name": {"fails": 0},
    "preference": {"fails": 0},
    "confirm_slot": {"retry": 0},
})
```

### 2) Helpers (dans session.py ou backend/recovery.py)

```python
def rec_get(session, path: str, default=None):
    """Ex: rec_get(session, "phone.partial", "")"""
    d = getattr(session, "recovery", None) or {}
    for k in path.split("."):
        d = (d or {}).get(k, default if k == path.split(".")[-1] else {})
    return d if d is not None else default

def rec_inc(session, path: str, delta: int = 1):
    """Ex: rec_inc(session, "contact.fails")"""
    ...

def rec_set(session, path: str, value):
    """Ex: rec_set(session, "phone.partial", "0612")"""
    ...

def rec_reset(session, top_key: str):
    """Réinitialise tout un sous-objet. Ex: rec_reset(session, "contact")."""
    ...
```

### 3) Migration rétrocompatible
- Au chargement (SQLite `_deserialize_session` ou au premier `get_or_create` / `session_from_dict`) : si `session.recovery` absent ou vide, initialiser `recovery` et **remplir depuis les anciens champs** :
  - `contact.fails` ← `contact_fails`
  - `contact.retry` ← `contact_retry_count`
  - `contact.mode` ← `contact_mode`
  - `phone.partial` ← `partial_phone_digits`
  - `confirm_contact.fails` ← `contact_confirm_fails`
  - `confirm_contact.intent_repeat` ← `contact_confirm_intent_repeat_count`
  - `slot_choice.fails` ← `slot_choice_fails`
  - `name.fails` ← `name_fails`
  - `preference.fails` ← `preference_fails`
  - `phone_fails` → peut être mappé sur `phone.turns` ou gardé en `contact.fails` selon la sémantique actuelle
  - `confirm_slot.retry` ← `confirm_retry_count`
- Écrire dans **un seul sens** : le code lit/écrit via `rec_*` ; les anciens champs restent en lecture pour la migration, puis on pourra les supprimer une fois tout migré.

### 4) Sérialisation
- **SQLite** : une colonne JSON `recovery_json` (ou inclure `recovery` dans le pickle). Si tu gardes le pickle, `recovery` est automatiquement persisté.
- **Codec (Postgres)** : dans `session_to_dict`, ajouter `"recovery": getattr(session, "recovery", None) or {}` ; dans `session_from_dict`, restaurer `session.recovery = d.get("recovery") or {}` puis appliquer la même migration (anciens champs → recovery) si besoin pour vieux checkpoints.

### 5) Champs à supprimer progressivement (après migration)
- `contact_fails`, `contact_retry_count`, `contact_mode`
- `partial_phone_digits`
- `phone_fails`, `contact_confirm_fails`, `contact_confirm_intent_repeat_count`
- `slot_choice_fails`, `name_fails`, `preference_fails`
- `confirm_retry_count` (remplacé par `recovery["confirm_slot"]["retry"]`)

Ne pas toucher pour l’instant : `no_match_turns`, `turn_count`, `intent_router_visits` (hors “contact”), sauf si tu veux les mettre dans `recovery` plus tard.

### 6) Tests à ajouter (Fix #9)
- `rec_get` / `rec_inc` / `rec_set` / `rec_reset` sur une session avec `recovery` vide puis rempli.
- Session sans `recovery` (legacy) : après migration, `rec_get(session, "contact.fails")` renvoie la valeur de l’ancien `contact_fails`.
- Checkpoint : `session_to_dict` → `session_from_dict` → les compteurs recovery sont restaurés.
- Un scénario engine (ex. QUALIF_CONTACT) qui incrémente un compteur via `rec_inc` et déclenche transfert après N échecs.

---

## Fix #4 — Reset centralisé `is_reading_slots`

### Objectif
Un seul endroit pour “on lit les créneaux” / “on ne lit plus”, et invariant : hors WAIT_CONFIRM ⇒ `is_reading_slots` False.

### 1) Helpers (session.py ou engine)

```python
def set_reading_slots(session, on: bool, reason: str = ""):
    session.is_reading_slots = on
    # optionnel: logger.debug("[SLOTS_READING] conv_id=%s on=%s reason=%s", ...)

def reset_slots_reading(session):
    if getattr(session, "is_reading_slots", False):
        set_reading_slots(session, False, "reset")
```

### 2) Où appeler
- **Mettre à True** : uniquement dans `_propose_slots` (web : liste complète) et dans le bloc WAIT_CONFIRM quand on envoie la liste (preface+list).
- **Mettre à False** : dans `reset_slots_reading(session)` appelé :
  - au début de `handle_message` si `session.state != "WAIT_CONFIRM"` (invariant),
  - dans chaque transition qui quitte WAIT_CONFIRM (ex. après confirmation créneau, après transfert, etc.).

### 3) Invariant
- Au début du handler WAIT_CONFIRM (ou dans un guard) : si `state != "WAIT_CONFIRM"` et `is_reading_slots` True → log warning + `reset_slots_reading(session)`.

### 4) Tests
- Après un tour en WAIT_CONFIRM avec liste envoyée, `is_reading_slots` True (ou selon ton flow).
- Après transition vers CONFIRMED ou TRANSFERRED, `is_reading_slots` False.
- Session chargée depuis checkpoint avec state=QUALIF_NAME et is_reading_slots=True → au premier handle_message, correction automatique à False.

---

## Fix #6 — Politique TRANSFER (“humain” seul → clarify)

### Règle proposée
- **Court** (“humain”, “transfert”, “conseiller”, < ~14 caractères) ⇒ **clarify** : “Vous souhaitez prendre rendez-vous, annuler, modifier, ou poser une question ?”
- **Phrase explicite** (“je veux parler à quelqu’un”, “mettez-moi en relation”) ⇒ **transfert direct**.

### Implémentation
- Dans le chemin qui gère l’intent TRANSFER (ou équivalent “demande humain”) : selon `len(user_text.strip())` et/ou liste de tokens courts, soit appeler le flow clarify (menu 1/2/3/4), soit déclencher le transfert.
- Ajouter 2 tests : “humain” seul → message clarify (pas transfert) ; “je veux parler à un conseiller” → transfert.

---

## Ordre recommandé
1. **Fix #9** : recovery namespace + migration + rec_* + tests (sans supprimer les anciens champs tout de suite).
2. **Fix #4** : set_reading_slots / reset_slots_reading + invariant + tests.
3. **Fix #6** : règle humain court → clarify + tests.

---

## Note safe_reply (Fix #7)
Tu as déjà le collapse “un seul final en vocal”. Pour durcir : en env test/staging, si `len(finals) > 1` → logger.warning + (optionnel) métrique ; en test, un `assert len(events) == 1` dans les tests vocal pour forcer la correction à la source.
