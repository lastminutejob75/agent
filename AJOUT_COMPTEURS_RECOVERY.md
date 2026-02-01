# Ajout Compteurs Recovery par Contexte
**Amélioration analytics et tuning fin (1-2h)**

---

## 🎯 Objectif

Ajouter des **compteurs de recovery par contexte** pour :
1. **Analytics précis** : Savoir où l'agent bloque (choix créneau vs nom vs préférence)
2. **Tuning fin** : Ajuster les messages selon le contexte problématique
3. **Recovery ciblée** : Différencier 3 échecs sur le nom vs 3 échecs sur le créneau

---

## 📊 Exemple d'utilité

### Sans compteurs par contexte (actuel)

```python
# Tous les échecs incrémentent le même compteur
session.global_recovery_fails += 1

# Problème : on ne sait pas QUOI est difficile
# - 3 échecs = créneau mal compris ? Nom incompris ? Préférence floue ?
```

**Analytics flous** :
```
Session X : global_recovery_fails = 5
→ On sait que c'est difficile, mais QUOI exactement ?
```

### Avec compteurs par contexte (V2)

```python
# Chaque contexte a son compteur
session.slot_choice_fails += 1
session.name_fails += 1
session.preference_fails += 1

# On sait exactement où ça bloque
```

**Analytics précis** :
```
Session X :
- slot_choice_fails: 3  ← Problème détection créneau
- name_fails: 0         ← Nom OK
- preference_fails: 1   ← Préférence OK
→ Action : Améliorer detect_slot_choice_v2()
```

---

## 🚀 Prompt pour Cursor (copier-coller)

```
OBJECTIF : Ajouter compteurs recovery par contexte pour analytics fins.

CONTEXTE : Recovery existe déjà avec ClarificationMessages dans prompts.py.
On veut juste INSTRUMENTER pour savoir QUEL contexte échoue le plus.

ACTIONS :

1. ENRICHIR Session (fichier où Session est définie) :
   Ajouter 5 compteurs :
   - slot_choice_fails: int = 0
   - name_fails: int = 0
   - phone_fails: int = 0
   - preference_fails: int = 0
   - contact_confirm_fails: int = 0
   - MAX_CONTEXT_FAILS: int = 3

2. CRÉER helpers dans engine.py :
   
   def increment_recovery_counter(session, context: str) -> int:
       """Incrémente compteur pour un contexte, retourne la valeur"""
       if context == 'slot_choice':
           session.slot_choice_fails += 1
           return session.slot_choice_fails
       elif context == 'name':
           session.name_fails += 1
           return session.name_fails
       elif context == 'phone':
           session.phone_fails += 1
           return session.phone_fails
       elif context == 'preference':
           session.preference_fails += 1
           return session.preference_fails
       elif context == 'contact_confirm':
           session.contact_confirm_fails += 1
           return session.contact_confirm_fails
       else:
           session.global_recovery_fails += 1
           return session.global_recovery_fails
   
   def should_escalate_recovery(session, context: str) -> bool:
       """Détermine si ≥3 échecs sur ce contexte"""
       counters = {
           'slot_choice': session.slot_choice_fails,
           'name': session.name_fails,
           'phone': session.phone_fails,
           'preference': session.preference_fails,
           'contact_confirm': session.contact_confirm_fails
       }
       return counters.get(context, session.global_recovery_fails) >= session.MAX_CONTEXT_FAILS

3. INSTRUMENTER recovery :
   Partout où tu fais actuellement :
     session.global_recovery_fails += 1
   
   Remplacer par :
     fail_count = increment_recovery_counter(session, '<context>')
   
   Contextes à instrumenter :
   - handle_slots_confirm (ou équivalent) → context='slot_choice'
   - handle qualification nom → context='name'
   - handle qualification phone → context='phone'
   - handle qualification preference → context='preference'
   - handle CONTACT_CONFIRM → context='contact_confirm'
   
   Exemple pour slot_choice :
   
   # AVANT
   if choice is None:
       session.global_recovery_fails += 1
       clarification = get_clarification_message('slot_choice', session.global_recovery_fails)
   
   # APRÈS
   if choice is None:
       fail_count = increment_recovery_counter(session, 'slot_choice')
       clarification = get_clarification_message('slot_choice', fail_count)
       
       if should_escalate_recovery(session, 'slot_choice'):
           return trigger_intent_router(session, 'slot_choice_fails_3', user_message)

4. ENRICHIR logging :
   Dans tes fonctions de logging (si elles existent), ajouter all_counters :
   
   logger.info('recovery_triggered', extra={
       'session_id': session.id,
       'context': context,
       'fail_count': fail_count,
       'all_counters': {
           'slot_choice': session.slot_choice_fails,
           'name': session.name_fails,
           'phone': session.phone_fails,
           'preference': session.preference_fails,
           'contact_confirm': session.contact_confirm_fails,
           'global': session.global_recovery_fails
       }
   })

CONTRAINTES :
- GARDER global_recovery_fails (compatibilité)
- NE PAS casser la logique actuelle
- Juste AJOUTER l'instrumentation
- Temps estimé : 1-2h

TESTS à ajouter (dans tests/test_niveau1.py ou nouveau fichier) :
- Test increment_recovery_counter('slot_choice') incrémente bien slot_choice_fails
- Test should_escalate_recovery après 3 échecs retourne True
- Test compteurs indépendants (3 échecs name ne déclenche pas escalade slot_choice)
```

---

## 📊 Analytics post-déploiement

Une fois les compteurs en place, créer `analytics/analyze_recovery.py` :

```python
"""Analyse recovery logs pour identifier zones faibles."""
import json
import pandas as pd

def analyze_recovery_logs(log_file='logs/recovery.jsonl'):
    logs = [json.loads(line) for line in open(log_file)]
    df = pd.DataFrame(logs)
    
    print("=== TOP CONTEXTES PROBLÉMATIQUES ===")
    print(df['context'].value_counts())
    print()
    
    print("=== MOYENNE ÉCHECS PAR CONTEXTE ===")
    print(df.groupby('context')['fail_count'].mean())
    
    # Recommandations
    top = df['context'].value_counts().index[0]
    print(f"\nAction : Améliorer contexte '{top}'")

if __name__ == '__main__':
    analyze_recovery_logs()
```

**Utilisation** :
```bash
python analytics/analyze_recovery.py
```

**Sortie exemple** :
```
=== TOP CONTEXTES PROBLÉMATIQUES ===
slot_choice          45
preference           23
name                 12

=== MOYENNE ÉCHECS PAR CONTEXTE ===
slot_choice          2.3
preference           1.8
name                 1.5

Action : Améliorer contexte 'slot_choice'
→ Ajouter plus de variantes dans detect_slot_choice_v2()
```

---

## ✅ Bénéfices

| Avant | Après |
|-------|-------|
| "15% INTENT_ROUTER, mais pourquoi ?" | "45 échecs sur slot_choice → améliorer detect_slot_choice_v2()" |
| Itération à l'aveugle | **Amélioration data-driven** |
| Temps gaspillé sur non-problèmes | **Focus sur vrais points faibles** |

---

**Temps total : 1-2h**  
**Impact : Analytics + Tuning fin**  
**Recommandation : OUI** (très bon ROI)

---

## ✅ Implémenté dans ce dépôt

- **Session** : `slot_choice_fails`, `name_fails`, `phone_fails`, `preference_fails`, `contact_confirm_fails`, `MAX_CONTEXT_FAILS = 3` ; reset dans `reset()` et dans `_trigger_intent_router`.
- **engine.py** : `increment_recovery_counter(session, context)`, `should_escalate_recovery(session, context)` ; instrumentation dans :
  - QUALIF_NAME (nom trop court) → `name`
  - WAIT_CONFIRM (choix créneau invalide) → `slot_choice`
  - QUALIF_CONTACT (contact invalide, web) → `phone`
  - CONTACT_CONFIRM (pas oui/non) → `contact_confirm`
  - PREFERENCE_CONFIRM (pas oui/non) → `preference`
- **Logging** : `all_counters` ajouté dans `_trigger_intent_router` (extra du logger INFO).
- **Tests** : `tests/test_recovery_counters.py` — `increment_recovery_counter`, `should_escalate_recovery` après 3 échecs, compteurs indépendants.

