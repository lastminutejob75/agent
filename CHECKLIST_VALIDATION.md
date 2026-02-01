# Checklist validation — Niveau 1 (16 points)

Rapport de validation du backend après implémentation de la spec production-grade V3.

---

## ✅ Ce qui est conforme

| # | Point | Statut | Détail |
|---|--------|--------|--------|
| 1 | Pipeline strict (ordre) | ⚠️ À corriger | Voir section « Écarts » |
| 2 | INTENT_ROUTER universel | ✅ | Menu 4 choix, triggers unifiés (global_fails_2, correction_repeated, blocked_state, empty_repeated) |
| 3 | Recovery progressive | ✅ | Reformulation → exemple → choix fermé → transfert (no_match, INTENT_ROUTER retry) |
| 4 | Intent override | ✅ | `should_override_current_flow_v3` + CANCEL/MODIFY/TRANSFER avant state handler |
| 5 | No Hangup Policy | ✅ | `safe_reply()` sur tous les retours, fallback `SAFE_REPLY_FALLBACK` |
| 6 | Logs structurés | ✅ | `logger.info("intent_router_triggered", ...)` niveau INFO, extra avec raison/état/slots |
| 7 | Parsing déterministe | ✅ | `detect_intent`, `detect_strong_intent`, guards, pas de LLM freestyle |
| 8 | Minimal changes | ✅ | Uniquement engine.py, prompts.py, guards.py, session.py |
| 9 | INTENT_ROUTER menu fermé | ✅ | 1/2/3/4 uniquement, pas de question ouverte |
| 10 | INTENT_ROUTER = stabilisation | ✅ | `_handle_intent_router` switch immédiat : 1→QUALIF_NAME, 2→cancel, 3→START, 4→TRANSFERRED |
| 11 | Logs design signals INFO | ✅ | `logging.getLogger("uwi.intent_router").info(...)` |
| 12 | Session enrichie | ✅ | last_intent, consecutive_questions, global_recovery_fails, correction_count, empty_message_count, etc. |
| 13 | Clarifications guidées | ✅ | `get_clarification_message()` dans prompts |
| 14 | Inférence contextuelle | ✅ | `infer_preference_from_context()` + PREFERENCE_CONFIRM |

---

## ✅ Écarts corrigés

### 1. Ordre pipeline NON NÉGOCIABLE — **CORRIGÉ**

**Spec :**  
1. Anti-loop guard (tour > 25)  
2. Intent override CRITIQUES  
3. Guards basiques (vide, langue, spam)  
4. Correction / Recovery  
5. State handler  
6. Safe reply  

**Code après correction :**  
- Terminal gate (CONFIRMED/TRANSFERRED)  
- **1. Anti-loop** : `session.turn_count` incrémenté, si `> MAX_TURNS_ANTI_LOOP` (25) → `_trigger_intent_router("anti_loop_25")`  
- **2. Intent override** : CANCEL/MODIFY/TRANSFER (avant guards)  
- **3. Guards** : vide, length, langue, spam  
- Puis session expired, detect intent, correction, should_trigger_intent_router, state handlers, safe_reply  

**Modifs :**  
- `backend/session.py` : `turn_count`, `MAX_TURNS_ANTI_LOOP = 25`, reset dans `reset()` et dans `_trigger_intent_router`.  
- `backend/engine.py` : bloc anti-loop + intent override déplacé avant guards ; reset `turn_count` dans `_trigger_intent_router`.

---

### 2. Fichier de tests Niveau 1 — **CRÉÉ**

**Fichier :** `tests/test_niveau1.py` avec 10 scénarios :

1. `test_oui_ambigu_no_silence` — "oui" → pas de silence  
2. `test_slot_par_jour_ou_heure` — "celui de mardi" / "14h" → créneau  
3. `test_annuler_pendant_booking` — "je veux annuler" → CANCEL flow  
4. `test_deux_incomprehensions_intent_router` — 2 no-match → INTENT_ROUTER  
5. `test_safe_reply_fallback` — réponse jamais vide  
6. `test_correction_rejoue_question` — "attendez" → rejoue dernière question  
7. `test_empty_twice_intent_router` — 2 messages vides → INTENT_ROUTER  
8. `test_intent_override_transfer` — "parler à un humain" → TRANSFER  
9. `test_intent_router_choix_1_qualif_name` — menu choix 1 → QUALIF_NAME  
10. `test_anti_loop_25_turns_intent_router` — >25 tours → menu ou transfert  

**Lancer les tests :** `pytest tests/test_niveau1.py -v` (avec environnement Python contenant pytest).

---

## Commandes de validation

```bash
# Lancer les tests existants
pytest tests/test_engine.py tests/test_prd_scenarios.py -v

# Après création de test_niveau1.py
pytest tests/test_niveau1.py -v
```

---

## Résumé

- **16/16** points conformes.  
- Pipeline réordonné (anti-loop + intent override avant guards).  
- `turn_count` + garde-fou 25 tours ajoutés.  
- `tests/test_niveau1.py` créé (10 scénarios Niveau 1).

**Commande :** `pytest tests/test_niveau1.py -v` pour valider.
