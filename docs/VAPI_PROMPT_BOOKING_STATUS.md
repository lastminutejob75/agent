# Prompt Vapi — Gestion des statuts de réservation (V3)

## Statut

| Élément | Statut |
|--------|--------|
| Backend `handle_book` → JSON `status` | OK (`vapi_tool_handlers.handle_book`) |
| Backend `get_slots` avec `exclude_start_iso` / `exclude_end_iso` | OK (route `/api/vapi/tool`) |
| System prompt Vapi (Dashboard) | À coller (bloc ci-dessous) |

À intégrer dans le **system prompt** de l’assistant Vapi (Dashboard → Assistant → Model → System instructions, ou via API `partial_update`). Ce bloc garantit que l’assistant réagit correctement au **JSON retourné par le tool de réservation** (champ `status`).

---

## Bloc à coller dans le prompt système

```markdown
### Gestion des statuts de réservation

Le tool de réservation retourne toujours un objet JSON avec un champ **status**. Tu dois adapter ta réponse uniquement à ce statut. Ne jamais inventer un statut.

- **confirmed**  
  → Confirmer clairement la réservation (date + heure).  
  → Remercier et clôturer l’échange.

- **slot_taken**  
  → Expliquer brièvement que le créneau vient d’être pris.  
  → Proposer immédiatement d’autres créneaux en rappelant le tool get_slots **en excluant** le créneau refusé (paramètres exclude_start_iso et exclude_end_iso avec les valeurs retournées dans le résultat).  
  → Ne jamais reproposer le même créneau.

- **technical_error**  
  → S’excuser brièvement.  
  → Indiquer qu’un problème technique empêche la réservation.  
  → Proposer de réessayer dans un instant ou de rappeler plus tard.

- **fallback_transfer**  
  → Informer que la demande nécessite un conseiller humain.  
  → Lancer le transfert immédiatement (sans redemander de créneaux).
```

---

## Comportements attendus (mini-eval)

| Statut              | Action attendue |
|---------------------|------------------|
| `confirmed`         | Confirmation date/heure + remerciement + fin. |
| `slot_taken`       | « Ce créneau n’est plus disponible » + rappel get_slots avec exclude. |
| `technical_error`  | Excuse + « problème technique » + proposer réessayer / rappeler. |
| `fallback_transfer`| « Je vous mets en relation avec un conseiller » + transfert. |

---

## Format du résultat du tool `book`

Le backend renvoie une **chaîne JSON** dans `results[0].result`. Exemple après parsing :

- **confirmed** : `{ "status": "confirmed", "event_id": "...", "start_iso": "...", "end_iso": "..." }`
- **slot_taken** : `{ "status": "slot_taken", "start_iso": "...", "end_iso": "..." }`
- **technical_error** : `{ "status": "technical_error", "code": "calendar_unavailable" }` ou `"code": "permission"`
- **fallback_transfer** : `{ "status": "fallback_transfer" }`

L’assistant doit **toujours baser sa réponse sur le champ `status`** et ne jamais inventer un autre statut.

---

## Tool `get_slots` — paramètres d’exclusion

Après un **slot_taken**, l’assistant doit rappeler `get_slots` en excluant le créneau refusé pour ne pas le reproposer.

Le backend accepte deux paramètres optionnels sur l’appel au tool **get_slots** :

| Paramètre           | Type   | Description |
|---------------------|--------|-------------|
| `exclude_start_iso` | string | Début du créneau à exclure (ISO 8601, ex. valeur `start_iso` du résultat book). |
| `exclude_end_iso`   | string | Fin du créneau à exclure (ISO 8601, ex. valeur `end_iso` du résultat book). |

À configurer dans la définition du tool (Dashboard ou API) : ajouter ces deux champs optionnels. Le prompt ci‑dessus indique d’utiliser les valeurs retournées par le tool `book` (status `slot_taken`) pour les passer au prochain `get_slots`.

---

## Tool get_slots — Exclure un créneau (après slot_taken)

Pour ne pas reproposer le même créneau après un **slot_taken**, le modèle doit rappeler le tool **get_slots** en passant les ISO du créneau refusé :

- **exclude_start_iso** (optionnel) : `start_iso` retourné dans le résultat `slot_taken`
- **exclude_end_iso** (optionnel) : `end_iso` retourné dans le résultat `slot_taken`

Exemple d’arguments du tool get_slots après un slot_taken :
```json
{
  "action": "get_slots",
  "exclude_start_iso": "2025-02-05T14:00:00+01:00",
  "exclude_end_iso": "2025-02-05T14:30:00+01:00",
  "preference": "après-midi"
}
```

Le backend filtre alors ce créneau et renvoie d’autres disponibilités.

---

## Référence

- Backend : `backend/vapi_tool_handlers.handle_book` → payload strict V3.  
- Route : `POST /api/vapi/tool` (action `book`) → `result = json.dumps(payload)`.  
- get_slots : `handle_get_slots(..., exclude_start_iso=..., exclude_end_iso=...)` → `get_slots_for_display(..., exclude_start_iso=..., exclude_end_iso=...)`.  
- Voir aussi : `VAPI_CONFIG.md`, `PRODUCTION_GRADE_SPEC_V3.md`.
