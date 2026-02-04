# Vérification : dispo agenda + booking réel à chaque demande de RDV

Vérification effectuée sur le code (comportement réel).

---

## 1. Vérification de dispo sur l’agenda

**Réponse : OUI.** À chaque proposition de créneaux, le moteur interroge l’agenda (Google Calendar ou SQLite).

### Où c’est fait

- **Point d’entrée** : `Engine._propose_slots(session)` — `backend/engine.py` (l. 1599-1647).
- **Appel** : `tools_booking.get_slots_for_display(limit=..., pref=..., session=session)` (l. 1612-1614).

### Détail

- **Google Calendar** : `tools_booking._get_slots_from_google_calendar()` appelle `calendar.get_free_slots(date=..., duration_minutes=15, start_hour=..., end_hour=..., limit=...)` pour les 7 prochains jours (hors week-end).  
  → `backend/google_calendar.py` : `get_free_slots()` récupère les events du calendrier et calcule les créneaux libres (pas de liste statique).
- **SQLite** : `tools_booking._get_slots_from_sqlite()` appelle `db.list_free_slots(limit=..., pref=...)`.  
  → `backend/db.py` (l. 198-231) : `SELECT id, date, time FROM slots WHERE is_booked=0 AND date >= ?` (+ filtre horaire si `pref`).  
  → Seuls les créneaux **libres** sont renvoyés.

### Quand c’est appelé

- Quand le flow de qualification a rempli **nom + préférence** (et éventuellement motif selon config), `_next_qualif_step()` appelle `_propose_slots(session)`.
- Aucun créneau proposé sans passer par `get_slots_for_display` (donc sans lecture dispo).

### Si pas de dispo

- Si `get_slots_for_display` renvoie une liste vide (ou erreur non gérée → liste vide) :  
  `_propose_slots` met `session.state = "TRANSFERRED"` et envoie le message `no_slots` (ex. "Désolé, nous n'avons plus de créneaux disponibles. Je vous mets en relation avec un humain.") — `engine.py` l. 1626-1630.

---

## 2. Booking réel à la fin de l’appel

**Réponse : OUI.** La confirmation « RDV pris » n’est envoyée qu’après un **booking réel** réussi (Google ou SQLite).

### Où c’est fait

- **Point d’entrée** : `Engine._handle_contact_confirm(session, user_text)` — `backend/engine.py` (l. 2244-2277).
- Quand l’utilisateur **confirme** le contact (intent `"YES"`) et qu’un créneau a déjà été choisi (`session.pending_slot_choice is not None`), le code appelle :
  - `tools_booking.book_slot_from_session(session, slot_idx)` (l. 2257).

### Détail

- **Google Calendar** : `tools_booking._book_via_google_calendar(session, idx)` → `calendar.book_appointment(start_time=..., end_time=..., patient_name=..., patient_contact=..., motif=...)` — `google_calendar.py` crée un event via l’API Calendar.
- **SQLite** : `tools_booking._book_via_sqlite(session, idx)` → `db.book_slot_atomic(slot_id=..., name=..., contact=..., contact_type=..., motif=...)` — `db.py` (l. 234-268) : `UPDATE slots SET is_booked=1 WHERE id=? AND is_booked=0` + `INSERT INTO appointments (...)`.
  - Si le créneau a déjà été pris entre-temps (`is_booked=1`), `book_slot_atomic` ne met à jour aucune ligne et renvoie `False`.

### Gestion de l’échec

- Si `book_slot_from_session` renvoie **False** (créneau déjà pris ou erreur) :  
  `session.state = "TRANSFERRED"`, message `MSG_SLOT_ALREADY_BOOKED` ("Désolé, ce créneau vient d'être pris. Je vous mets en relation avec un humain.") — `engine.py` l. 2258-2263.
- Le message type « RDV confirmé » (`format_booking_confirmed`) et le passage en `CONFIRMED` + `_persist_ivr_event(session, "booking_confirmed")` ne sont exécutés **que** si `success` est True (l. 2265-2274).

### Résumé du flux

1. Proposition de créneaux → **lecture dispo** (`get_slots_for_display` → Google `get_free_slots` ou SQLite `list_free_slots`).
2. Utilisateur choisit un créneau (ex. « oui 2 ») → on stocke `pending_slot_choice`, on demande le contact.
3. Utilisateur donne contact puis confirme (ex. « oui ») → **booking réel** `book_slot_from_session` (Google ou SQLite).
4. Si succès → message de confirmation + `CONFIRMED` + event `booking_confirmed`.  
   Si échec → message « créneau pris » + `TRANSFERRED`.

---

## 3. Points d’attention (sans remettre en cause la vérif dispo / booking)

- **Google : ordre des slots** : `store_pending_slots` appelle `_store_google_calendar_slots`, qui **re-refetch** des créneaux avec une plage 9h–18h fixe. Si la proposition affichée avait été filtrée par préférence (ex. matin 9–12h), l’ordre dans `pending_google_slots` peut en théorie différer de l’ordre affiché. En pratique, les premiers créneaux renvoyés par `get_free_slots` avec la bonne plage (dans `_get_slots_from_google_calendar`) sont cohérents avec ce qui est proposé ; à surveiller si on constate un décalage créneau affiché / créneau réservé.
- **Cache slots** : `get_slots_for_display` utilise un cache (60 s) **uniquement quand `pref is None`** (`tools_booking.py`). Dès qu’une préférence est fournie, les slots sont rechargés depuis l’agenda.

---

## 4. Conclusion

| Critère | Statut | Référence code |
|--------|--------|-----------------|
| Vérif dispo à chaque demande de RDV | Oui | `_propose_slots` → `get_slots_for_display` → Google `get_free_slots` / SQLite `list_free_slots` |
| Booking réel à la fin (après confirmation contact) | Oui | `_handle_contact_confirm` (intent YES + `pending_slot_choice`) → `book_slot_from_session` → Google `book_appointment` / SQLite `book_slot_atomic` |
| Pas de message « RDV confirmé » sans booking réussi | Oui | Message + `CONFIRMED` + `booking_confirmed` uniquement si `success` True ; sinon `TRANSFERRED` + `MSG_SLOT_ALREADY_BOOKED` |

Donc : à chaque demande de RDV, il y a bien une **vérification de dispo** sur l’agenda au moment de proposer les créneaux, et un **booking réel** (Google ou SQLite) à la fin de l’appel, avec message de succès seulement si le booking a réussi.

---

## 5. Vérification automatisée (tests)

| Test | Vérifie |
|------|--------|
| `tests/test_google_calendar_booking.py::test_book_appointment_calls_api_with_correct_body` | `GoogleCalendarService.book_appointment()` construit le bon body (summary, start/end Europe/Paris) et appelle `events().insert().execute()` |
| `tests/test_google_slot_consistency.py::test_pending_slots_display_matches_booking` | Choix créneau 2 → `book_slot_from_session` appelle `_book_google_by_iso` avec les bons `start_iso` / `end_iso` du slot affiché |
| `tests/test_engine.py::test_booking_flow_happy_path` | Parcours complet : intent RDV → qualif → proposition slots → choix → contact → confirmation → booking |
| `tests/test_db.py::test_find_booking_by_name_and_cancel_sqlite` | Booking SQLite + annulation (fallback si Google non configuré) |

Commande : `pytest tests/test_google_calendar_booking.py tests/test_google_slot_consistency.py tests/test_engine.py tests/test_db.py -v`
