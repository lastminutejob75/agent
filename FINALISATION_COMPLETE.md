# FINALISATION COMPLÈTE — Architecture béton

**Les 3 derniers micro-ajustements intégrés.**  
Patch minimal, comportement maximal. Aucun nouveau fichier ni nouvelle architecture.

---

## Étape 1 — Copie et taille

Pour archiver la finalisation et calculer la taille totale de la collection :

```bash
cp FINALISATION_COMPLETE.md /chemin/vers/outputs/ && du -sh /chemin/vers/outputs/
```

*(Exemple : `cp FINALISATION_COMPLETE.md ./outputs/ && du -sh ./outputs/` → affiche la taille, ex. 190K.)*

---

## 1. Ordre pipeline NON NÉGOCIABLE

À chaque message, l’ordre doit être **strictement** :

1. **Anti-loop guard** (ex. `turn_count` > 25 → INTENT_ROUTER)
2. **Intent override CRITIQUES** (CANCEL / TRANSFER / ABANDON) — priorité absolue
3. **Guards basiques** (vide, langue, spam)
4. **Correction / Recovery**
5. **State handler**
6. **Safe reply**

**Règle d’or :** Les intents "danger" ont priorité **absolue** sur tout le reste.

---

## 2. INTENT_ROUTER = stabilisation (non fonctionnel)

INTENT_ROUTER est un état de **stabilisation**, pas un flow fonctionnel.

**Ne jamais :**
- Collecter des données métier (nom, téléphone)
- Poser une question ouverte
- Rester plus de 2 tours dans INTENT_ROUTER
- Enchaîner un flow en douce depuis le menu

**Seulement :** Router vers un flow clair (1 tour max après le choix 1/2/3/4).

---

## 3. Privilégier comprendre (seuils effectifs)

Pour éviter de transférer dès la première difficulté (ex. interruption, "attendez") :

- **TRANSFER** : ne pas considérer comme demande de transfert un message **trop court** (< 14 caractères), ex. "humain", "quelqu'un" seuls → souvent une interruption.
- **INTENT_ROUTER** : déclencher le menu seulement après **3** échecs (global_recovery_fails, correction_count, empty_message_count) ; **3** retries dans le menu avant transfert. Seuil `consecutive_questions` : 7.
- En résumé : dégradation progressive (reformuler → exemple → choix fermé) avec **3** essais avant menu, puis **3** essais dans le menu avant transfert.

---

## 4. Logs = design signals (pas erreurs user)

INTENT_ROUTER, anti-loop, transfert auto = **signaux de design** à analyser.

**Questions à se poser :**
- Pourquoi l’utilisateur n’a pas compris ?
- Le prompt était-il clair ?
- Manque-t-il une variante de formulation ?

**But :** Amélioration continue du design, pas blâme utilisateur.  
Logger en **INFO** (pas WARNING/ERROR), avec : raison, état précédent, slots manquants, `turn_count`.

---

## 5. Prompt Cursor FINAL (tout-en-un)

À copier-coller pour Cursor avec tous les ajustements :

```
Lis d'abord PRINCIPES_STRUCTURANTS_IVR.md (philosophie et règles non négociables).

Puis implémente UNIQUEMENT le Niveau 1 décrit dans PRODUCTION_GRADE_SPEC_V3.md (objectif: agent qui ne casse pas), sans refactor global.

Livrables attendus :
1) process_message_v3() avec pipeline strict (ordre NON NÉGOCIABLE) :
   anti_loop_guard -> intent_override -> guards -> correction -> state_handler -> safe_reply
2) INTENT_ROUTER universel (menu 4 choix) + triggers unifiés (seuils hauts = privilégier comprendre) :
   - >=3 incompréhensions / échecs (global_recovery_fails, correction_count, empty_message_count) -> INTENT_ROUTER
   - 3 retries dans le menu avant transfert ; TRANSFER override seulement si phrase explicite (>=14 car.)
3) Dégradation progressive (reformule -> exemple -> choix fermé -> transfert) avec compteur par contexte
4) Override global à chaque message : CANCEL/MODIFY/TRANSFER/ABANDON
5) No Hangup Policy + safe_reply() : aucun tour ne doit produire silence

Ajoute aussi 10 tests (ou scénarios) couvrant :
- "oui" ambigu
- choix slot par jour/heure ("celui de mardi", "14h")
- interruption en plein booking ("je veux annuler")
- 2 incompréhensions -> intent_router
- handler qui retourne None -> safe_reply

Contraintes :
- Pas de LLM "freestyle" : parsing déterministe d'abord, clarification ensuite, transfert si échec.
- Minimal changes : modifier uniquement backend/engine.py, backend/prompts.py, backend/guards.py si nécessaire.
- Logs structurés (design signals) : intent_override, intent_router_trigger, recovery_step, safe_reply_trigger. Niveau INFO.

Règles IVR additionnelles (niveau enterprise) :

1. INTENT_ROUTER strict :
   - Menu fermé uniquement (1/2/3/4)
   - Jamais de question ouverte type "comment puis-je vous aider ?"

2. 1 message = 1 objectif :
   - Chaque message poursuit UN seul but (question OU confirmation OU menu)
   - Max 2 phrases par message
   - Interdit de combiner question + explication + menu

3. Garde-fou anti-boucle :
   - session.turn_count (ou équivalent)
   - Si >25 tours sans DONE/TRANSFERRED -> forcer INTENT_ROUTER
   - Si INTENT_ROUTER échoue aussi -> transfert immédiat

Règles critiques additionnelles :

1. Ordre pipeline NON NÉGOCIABLE :
   anti_loop_guard -> intent_override CRITIQUES -> guards -> correction -> state_handler -> safe_reply
   NE PAS réorganiser cet ordre.

2. INTENT_ROUTER = état de stabilisation :
   - Ne collecte AUCUNE donnée métier
   - Ne pose AUCUNE question libre
   - Switch immédiat vers autre état après choix 1/2/3/4
   - Max 3 tours dans le menu (3 échecs -> transfert). Privilégier comprendre.

3. Logging = design signals (pas erreurs user) :
   - INTENT_ROUTER / anti-loop / transfert auto en INFO
   - Inclure : raison, état précédent, slots manquants, turn_count

Ne crée pas de nouveaux fichiers ni de nouvelle architecture. Patch minimal, comportement maximal.
```

---

## 6. Collection FINALE (ordre pour Cursor)

**12 documents (~190 KB total)** — Production-ready.

| Priorité | Document | Rôle |
|----------|----------|------|
| ⭐⭐⭐ | PRINCIPES_STRUCTURANTS_IVR.md | Philosophie |
| ⭐⭐ | PRODUCTION_GRADE_SPEC_V3.md | Implémentation |
| ⭐ | PROMPT_CURSOR_OPTIMISE.md | Prompt + Checklist |
| 🔥 | **FINALISATION_COMPLETE.md** | 3 ajustements critiques + prompt final |
| ✨ | ADDENDUM_FINAL_IVR_PRO.md (si dispo) | Garde-fous enterprise |
| Optionnel | ADDENDUM_V3.1_POLISH.md | Polish UX |

**Référence :** Documents 7–12 (V2 : summary, scripts, tests, etc.).

---

*Document de finalisation — patch minimal, comportement maximal.*
