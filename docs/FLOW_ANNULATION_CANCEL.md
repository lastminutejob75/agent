# Flow ANNULATION (CANCEL) — Documentation technique

Documentation du comportement **réel** du système (code lu), pas de la spec.  
Références : `backend/engine.py`, `backend/session.py`, `backend/prompts.py`, `backend/tools_booking.py`, `tests/`.

---

## A) Déclenchement du flow CANCEL

### Quelles phrases déclenchent CANCEL ?

**Fichier :** `backend/prompts.py` (l. 636-641)

```python
CANCEL_PATTERNS = [
    "annuler", "annulation", "supprimer",
    "je veux annuler", "annuler mon rendez-vous",
    "annuler mon rdv", "annule mon rdv",
]
```

Détection : **substring** (ex. "annuler" dans "je voudrais annuler s'il vous plaît" → CANCEL). Pas de normalisation ni de score.

### Où se fait l’override ?

- **`detect_strong_intent(text)`** — `engine.py` l. 395-412 : appelle `prompts.CANCEL_PATTERNS` (même logique que `detect_intent` pour CANCEL).
- **`should_override_current_flow_v3(session, message)`** — `engine.py` l. 442-624 : retourne `True` si `detect_strong_intent(message)` vaut `"CANCEL"` **et** que les garde-fous ne bloquent pas.

Override effectif : **`engine.py` l. 659-668** (bloc « 2. INTENT OVERRIDE CRITIQUES ») : si `should_override_current_flow_v3` alors `strong = detect_strong_intent(user_text)`, `session.last_intent = strong`, et si `strong == "CANCEL"` → `return safe_reply(self._start_cancel(session), session)`.

### Quels états peuvent être préemptés ?

Tous les états sont préemptables par CANCEL **sauf** si l’un des garde-fous s’applique :

- **`engine.py` l. 454-455** : si `strong == "CANCEL"` **et** `session.state in ("CANCEL_NAME", "CANCEL_NO_RDV", "CANCEL_CONFIRM")` → `return False` (pas d’override, on reste en flow CANCEL).
- **`engine.py` l. 619-621** : si `strong == last_intent` (même intent consécutif) → `return False`.

Donc : **booking (QUALIF_*, WAIT_CONFIRM, CONTACT_CONFIRM), FAQ (START, FAQ_ANSWERED), MODIFY, CLARIFY, INTENT_ROUTER, etc.** peuvent tous être préemptés par une phrase CANCEL. Seuls les états déjà dans le flow CANCEL ne sont pas re-déclenchés.

### Cas « déjà en CANCEL » : anti re-trigger

- **`should_override_current_flow_v3`** (l. 454-455) : si `session.state in ("CANCEL_NAME", "CANCEL_NO_RDV", "CANCEL_CONFIRM")`, l’intent CANCEL ne déclenche **pas** un nouveau `_start_cancel` (évite reset en boucle).
- **`last_intent`** (l. 619-621) : si l’utilisateur renvoie une phrase CANCEL alors que `last_intent == "CANCEL"`, pas d’override (évite boucle sur « annuler » répété).

---

## B) State machine CANCEL (diagramme texte)

### États impliqués

| State           | Rôle |
|-----------------|------|
| `CANCEL_NAME`   | Demande du nom pour chercher le RDV |
| `CANCEL_NO_RDV` | RDV pas trouvé → proposer vérifier ou humain |
| `CANCEL_CONFIRM`| RDV trouvé → confirmation oui/non annuler |
| `CONFIRMED`     | Fin (annulé ou maintenu) |
| `TRANSFERRED`   | Fin (user a choisi « humain » en CANCEL_NO_RDV) |
| `INTENT_ROUTER` | Escalade après N échecs (nom ou RDV pas trouvé) |

**Absent :** pas d’état explicite type `CANCEL_START` ou `CANCEL_DONE` ; `_start_cancel` met directement `CANCEL_NAME`. La fin « annulé » est `CONFIRMED` + message CANCEL_DONE.

### Diagramme texte

```
                    [phrase CANCEL]
                           │
                           ▼
                    _start_cancel
                           │
                           ▼
                  ┌─────────────────┐
                  │   CANCEL_NAME   │
                  │ Q: "C'est à     │
                  │  quel nom ?"    │
                  └────────┬────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    nom vide/<2 car   nom valide         (autre: fallback
    cancel_name_fails   │                 _fallback_transfer)
         │              │
         ▼              ▼
    retry 1/2 ou    find_booking_by_name(name)
    INTENT_ROUTER         │
    (si >=3)         ┌────┴────┐
                     │         │
                pas trouvé   trouvé
                     │         │
                     ▼         ▼
             ┌──────────────┐  ┌─────────────────┐
             │ CANCEL_NO_RDV│  │  CANCEL_CONFIRM │
             │ "Vérifier ou │  │ "RDV {label}.   │
             │  humain ?"   │  │  Annuler ?"     │
             └──────┬───────┘  └────────┬────────┘
                    │                   │
     ┌──────────────┼──────────────┐   │
     │              │              │   ├── YES → cancel_booking() → CONFIRMED (CANCEL_DONE)
     │              │              │   ├── NO  → CONFIRMED (CANCEL_KEPT)
     │              │              │   └── unclear → clarification 1/2 (boucle, pas d’escalade)
     │              │              │
  "vérifier"     "humain"    nouveau nom
  / YES          / NO            │
     │              │             │
     ▼              ▼             ▼
  CANCEL_NAME   TRANSFERRED   find_booking_by_name
  (redemander                  → trouvé → CANCEL_CONFIRM
   le nom)                     → pas trouvé → CANCEL_NO_RDV + compteurs
```

### Par state : question, donnée attendue, validation, compteurs, next state

| State           | Question agent (ex.) | Donnée attendue | Validation | Compteur fails | Next state |
|-----------------|----------------------|-----------------|------------|----------------|------------|
| **CANCEL_NAME** | « C'est à quel nom ? » | Nom (texte) | `len(raw) >= 2` ; sinon « nom pas compris » | `cancel_name_fails` (1→ retry_1, 2→ retry_2, ≥3→ INTENT_ROUTER) | CANCEL_NO_RDV si RDV pas trouvé ; CANCEL_CONFIRM si trouvé ; INTENT_ROUTER si nom invalide ≥3 |
| **CANCEL_NO_RDV** | « Je ne trouve pas au nom de {name}. Vérifier ou humain ? » | Oui/vérifier / Non/humain / Nouveau nom | Intent YES/NO ou mots-clés ; sinon nouveau nom → recherche | `cancel_rdv_not_found_count`, `cancel_name_fails` (≥max_fails → INTENT_ROUTER) | CANCEL_NAME (vérifier) ; TRANSFERRED (humain) ; CANCEL_CONFIRM si nouveau nom trouvé ; sinon CANCEL_NO_RDV |
| **CANCEL_CONFIRM** | « Vous avez un RDV {slot_label}. Voulez-vous l'annuler ? » | Oui / Non | `detect_intent` YES/NO | `confirm_retry_count` (clarification 1 ou 2, **pas d’escalade** vers INTENT_ROUTER) | CONFIRMED (annulé ou maintenu) |

### Transitions vers INTENT_ROUTER / TRANSFERRED

- **INTENT_ROUTER** :
  - `CANCEL_NAME` : `cancel_name_fails >= 3` → `_trigger_intent_router(session, "cancel_name_fails_3", user_text)` (engine l. 1849-1852).
  - `CANCEL_NAME` (1er nom, RDV pas trouvé) : `cancel_rdv_not_found_count >= max_fails` → `_trigger_intent_router(session, "cancel_not_found_3", user_text)` (l. 1870-1873).
  - `CANCEL_NO_RDV` : après nouveau nom encore pas trouvé, `cancel_rdv_not_found_count >= max_fails` ou `cancel_name_fails >= max_fails` → `_trigger_intent_router(session, "cancel_not_found_3", user_text)` (l. 1835-1838).
- **TRANSFERRED** :
  - Uniquement depuis **CANCEL_NO_RDV** : si l’utilisateur dit Non / humain / parler à quelqu'un → `session.state = "TRANSFERRED"` (l. 1817-1820).

`max_fails` = `Session.MAX_CONTEXT_FAILS` = 3 (engine l. 1803).

---

## C) Données collectées

- **Nom** : requis. Stocké dans `session.qualif_data.name`. Validation minimale : `len(raw) >= 2` (engine l. 1846). Pas de split prénom/nom, pas de normalisation orthographe. **Prénom seul non géré explicitement** (traité comme un nom).
- **Contact** : **absent** dans le flow CANCEL. Pas de demande email/téléphone, pas d’utilisation du caller-id pour l’annulation.
- **Date/heure du RDV** : **non demandées**. Le RDV est identifié uniquement par le **nom** via `find_booking_by_name(name)` ; la date/heure viennent du premier RDV trouvé (label affiché en confirmation).
- **Identification du RDV à annuler** : **matching par nom** uniquement (voir section D). Un seul RDV renvoyé (premier match). Plusieurs RDV au même nom : **seul le premier est proposé** à l’annulation.

---

## D) Tools & actions

### Fonctions appelées pour chercher le RDV

- **`tools_booking.find_booking_by_name(name: str) -> Optional[Dict]`** (tools_booking.py l. 508-524).
  - Si Google Calendar configuré : `_find_booking_google_calendar(calendar, name)` (l. 527-567).
  - Sinon : `_find_booking_sqlite(name)` (l. 571-590).
- **Google** : `calendar.list_upcoming_events(days=30)` puis premier event dont `name_lower in summary or name_lower in description`.
- **SQLite** : `from backend.db import find_booking_by_name as db_find` puis `db_find(name)`. **Note :** `backend/db.py` ne contient pas de fonction `find_booking_by_name` dans la liste des `def` ; si absente, `_find_booking_sqlite` lèvera une erreur à l’appel.

### Annulation effective

- **`tools_booking.cancel_booking(slot_or_session)`** (l. 479-505).
  - Attend un `event_id` (dict `pending_cancel_slot` ou attribut `google_event_id`).
  - Si `event_id` absent → `logger.warning("Pas d'event_id Google Calendar à annuler")` et **return False**.
  - **SQLite :** `_find_booking_sqlite` retourne `event_id: None` (l. 579). Donc **`cancel_booking` ne peut pas annuler un RDV SQLite** ; il retourne False. L’engine **ne vérifie pas** le retour de `cancel_booking` (l. 1895-1901) : il affiche quand même « C'est fait, votre rendez-vous est bien annulé » → **risque terrain : annulation SQLite non effective, message faux**.

### Gestion des erreurs (0 RDV, plusieurs RDV, tool fail)

- **0 RDV** : `find_booking_by_name` retourne `None` → passage en `CANCEL_NO_RDV` avec message « vérifier ou humain » (CANCEL_NAME) ou réutilisation du même état (CANCEL_NO_RDV) avec incrément des compteurs.
- **Plusieurs RDV** : **non géré**. Seul le premier event (Google) ou le premier booking (SQLite) est retourné ; pas de liste, pas de choix par l’utilisateur.
- **Tool fail** : Google en exception → `_find_booking_google_calendar` retourne `None` (l. 565-567). Même comportement que « 0 RDV ». Pas de message spécifique « erreur technique ».

### Logging (log_ivr_event + persist)

- **log_ivr_event** (engine l. 102-127) : appelé avec `event="recovery_step"`, `context="cancel_name"` ou `"cancel_rdv_not_found"`, `reason="retry_1"` / `"retry_2"` / `"escalate_intent_router"` / `"offer_verify_or_human"` (l. 1811, 1834, 1837, 1839, 1849, 1852, 1854, 1857, 1871, 1872, 1874).
- **Persist** : si `event in ("recovery_step", "intent_router_trigger")`, `_persist_ivr_event` est appelée (l. 126-127). **Absent :** pas d’event dédié type `cancel_done` ou `cancel_kept` persisté en base (contrairement à `booking_confirmed`).

---

## E) Recovery & robustesse

- **Max retries par champ** :
  - **CANCEL_NAME** : `cancel_name_fails` ; seuil 3 → INTENT_ROUTER (l. 1849-1852). Messages retry 1 et 2 (prompts VOCAL_CANCEL_NAME_RETRY_1 / _2, idem web).
  - **CANCEL_NO_RDV** : `cancel_rdv_not_found_count` et `cancel_name_fails` ; seuil `max_fails` (3) → INTENT_ROUTER (l. 1836-1838, 1870-1873).
  - **CANCEL_CONFIRM** : `confirm_retry_count` ; seulement 2 niveaux de clarification (CANCEL_CONFIRM_UNCLEAR 1 et 2) ; **pas d’escalade** vers INTENT_ROUTER ni TRANSFERRED (l. 1910-1918). Boucle possible si l’utilisateur ne dit jamais oui/non clair.
- **Silence / vague / repeat / correction / intent override pendant CANCEL** :
  - **Silence** : géré en amont dans le pipeline (RÈGLE 3 : 1er/2e silence → messages dédiés, 3e → INTENT_ROUTER). En CANCEL_NAME/CANCEL_NO_RDV/CANCEL_CONFIRM, un message vide est traité avant d’atteindre `_handle_cancel` (bloc « 3. GUARDS BASIQUES ») → même comportement global.
  - **Vague / repeat / correction** : pas de branche spécifique dans `_handle_cancel`. En CANCEL_NAME, tout texte de longueur ≥ 2 est considéré comme nom (pas de détection « je n’ai pas compris » sémantique). En CANCEL_CONFIRM, seul `detect_intent` YES/NO compte ; sinon clarification 1 ou 2.
  - **Intent override** : si l’utilisateur dit TRANSFER / BOOKING / etc. alors qu’il est en CANCEL, le bloc override (l. 659-682) peut préempter et quitter le flow CANCEL (sauf si `last_intent == "CANCEL"` pour éviter re-trigger CANCEL).
- **Anti-loop et escalade** : INTENT_ROUTER après 3 échecs (nom ou RDV pas trouvé). TRANSFERRED uniquement par choix explicite « humain » en CANCEL_NO_RDV. Pas de limite de tours spécifique au flow CANCEL (la limite globale turn_count / anti_loop s’applique avant d’entrer dans les flows).

---

## F) Tests actuels

### Liste des tests liés à CANCEL

| Fichier | Test | Ce qu’il couvre |
|---------|------|------------------|
| `tests/test_cancel_modify_faq.py` | `test_cancel_name_incompris_recovery` | Déclenchement par « annuler un rdv », demande du nom, puis 3 réponses invalides (« e ») → vérifie retry 1 (répéter/noté), retry 2 (exemple Martin Dupont), puis INTENT_ROUTER (un, deux, rendez, etc.). |
| `tests/test_cancel_modify_faq.py` | `test_cancel_rdv_pas_trouve_offre_alternatives` | « annuler » puis nom inexistant → message contenant vérifier/orthographe/humain et `conv_state != TRANSFERRED`. |
| `tests/test_niveau1.py` | `test_annuler_pendant_booking` | Override : en plein booking (après « Je veux un rdv », « Paul Dupont »), « je veux annuler » → bascule en flow annulation (texte contient « annul » ou « nom » / « quel nom »). |

### Scénarios non couverts (à ajouter)

- **CANCEL_CONFIRM** : oui → annulation effective ; non → RDV maintenu (et message CANCEL_KEPT).
- **CANCEL_NO_RDV** : « vérifier » → redemande du nom ; « humain » → TRANSFERRED.
- **CANCEL_NO_RDV** : nouveau nom donné → RDV trouvé → passage en CANCEL_CONFIRM.
- **Escalade** : 3 fois « RDV pas trouvé » (ou 3 noms invalides) → INTENT_ROUTER.
- **Comportement SQLite** : RDV trouvé en SQLite puis « oui » → `cancel_booking` retourne False ; aujourd’hui le message dit quand même « annulé » (scénario à corriger ou à documenter comme limite).
- **Plusieurs RDV au même nom** : seul le premier est proposé (comportement à valider ou à faire évoluer).
- **Intent override** : depuis CANCEL_NAME, phrase TRANSFER ou BOOKING → sortie du flow CANCEL.

---

## G) Conclusion

### Résumé du comportement réel

- **Déclenchement** : phrases contenant un des `CANCEL_PATTERNS` ; override depuis presque tous les états, sauf déjà en flow CANCEL ou même intent consécutif.
- **Parcours** : CANCEL_NAME → (optionnel) CANCEL_NO_RDV → CANCEL_CONFIRM → CONFIRMED ou TRANSFERRED / INTENT_ROUTER. Donnée clé : **nom** ; pas de contact, pas de date/heure demandée.
- **Lookup** : `find_booking_by_name(name)` (Google 30 jours ou SQLite) ; premier match uniquement.
- **Annulation** : `cancel_booking(pending_cancel_slot)` ; **efficace seulement si `event_id` présent** (Google). SQLite : `event_id` toujours None → annulation non faite alors que le message dit « annulé ».

### Points faibles / risques terrain

1. **Annulation SQLite non effective** : `cancel_booking` ne fait rien sans `event_id` ; l’engine affiche quand même « C'est fait, votre rendez-vous est bien annulé » → **faux positif grave**.
2. **Plusieurs RDV au même nom** : un seul proposé, pas de choix explicite pour l’utilisateur.
3. **CANCEL_CONFIRM** : pas d’escalade après N réponses floues → boucle possible.
4. **Pas de persistance** d’un event « cancel_done » / « cancel_kept » pour analytics/rapports.
5. **Recherche SQLite** : dépendance à `backend.db.find_booking_by_name` qui n’apparaît pas dans les fonctions exportées de `db.py` → risque d’erreur à l’exécution si non implémentée.

### Recommandations

| Priorité | Action |
|----------|--------|
| **P0** | Vérifier/corriger annulation SQLite : soit implémenter annulation par `slot_id`/appointments dans `db` + l’utiliser dans `cancel_booking`, soit ne pas afficher « annulé » si `cancel_booking` retourne False. |
| **P1** | Ajouter persistance d’un event type `cancel_done` / `cancel_kept` (et optionnellement `cancel_abandon`) pour rapports et analytics. |
| **P1** | Escalade en CANCEL_CONFIRM après 2–3 réponses non oui/non (ex. INTENT_ROUTER ou message clair « je n’ai pas compris, voulez-vous annuler oui ou non ? » puis transfert). |
| **P2** | Tests : scénarios complets (CANCEL_CONFIRM oui/non, CANCEL_NO_RDV vérifier/humain, escalade 3×, override depuis CANCEL). |
| **P2** | Cas « plusieurs RDV » au même nom : documenter ou faire choisir (ex. liste 1/2/3 ou premier seulement). |

---

*Références de code : engine.py (l. 281, 306-308, 395-412, 442-455, 578-596, 659-668, 780-782, 815-817, 874-876, 1789-1921, 2334-2335, 2469-2471), session.py (l. 64, 85-86, 138-139), prompts.py (l. 164-199, 333-336, 636-641, 762-804), tools_booking.py (l. 479-505, 508-590).*
