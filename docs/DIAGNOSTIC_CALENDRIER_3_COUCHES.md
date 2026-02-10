# Diagnostic calendrier — 3 couches (prod Railway)

Pour trancher rapidement A/B/C/D/E sans redemander 50 infos.

---

## Étape 1 — Google actif en prod ?

**Endpoint (sans secrets) :**
```bash
curl -s https://agent-production-c246.up.railway.app/debug/config
```
**Réponse attendue si OK :** `{"google_calendar_enabled": true, "reason": null}`  
**Si false :** `reason` indique la cause (credentials manquants, decode_error, etc.).

**Logs au démarrage Railway :** chercher
- `Google Calendar enabled: true` → Google actif
- `Google Calendar enabled: false (reason: …)` → fallback SQLite, corriger variables / partage calendrier

---

## Étape 2 — Proposition de créneaux

**Log à chercher :** `get_free_slots: date=… start_hour=… end_hour=… events_busy=… free_slots=…`

- **events_busy** = nombre d’events occupés sur le calendrier pour ce jour
- **free_slots** = nombre de créneaux libres retournés (avant filtre limit 3)

Si **free_slots=0** alors que le calendrier est vide → timezone / fenêtre horaire (start_hour, end_hour) ou mauvais **GOOGLE_CALENDAR_ID**.  
Si **events_busy** est cohérent mais **free_slots=0** → contraintes métier (horaires cabinet, week-end).

---

## Étape 3 — Booking (créneaux proposés mais résa échoue)

**Log à chercher :** `[BOOKING_CHOSEN_SLOT] choice=… start_iso=… end_iso=… source=google pending_slots_display_len=…`

Vérifier que **start_iso** / **end_iso** correspondent bien au créneau affiché (pas de perte de session / mauvais index).

**En cas d’échec API Google**, le log indique le type :
- `Error booking appointment: HTTP 403 (permission)` → partager le calendrier avec le service account (écriture)
- `Error booking appointment: HTTP 409 (conflict)` → conflit réel (créneau pris entre-temps)
- `Error booking appointment: HTTP 400 (format)` → format date/heure (timezone, ISO)

---

## Arbre de décision (symptôme → cause probable)

| Symptôme | Vérification | Correctif typique |
|----------|--------------|-------------------|
| **A)** Aucun créneau proposé | `/debug/config` → enabled ? Log `get_free_slots` → events_busy, free_slots | Calendar ID explicite @group.calendar.google.com ; partager calendrier (lecture) ; Europe/Paris |
| **B)** Créneaux proposés, résa échoue | Log `[BOOKING_CHOSEN_SLOT]` + `Error booking: HTTP 403/409/400` | 403 → droits écriture ; 409 → retry déjà en place ; 400 → format ISO |
| **C)** Mauvais horaires / fuseau | Log get_free_slots (start_hour, end_hour) + format start/end en booking | Europe/Paris partout ; contraintes cabinet |
| **D)** Google pas utilisé (SQLite) | `/debug/config` → google_calendar_enabled: false | Variables Railway ; load_google_credentials au startup |
| **E)** Autre | Logs [BOOKING_ATTEMPT], [BOOKING_RESULT], [BOOKING_CHOSEN_SLOT] | Croiser avec conv_id et état session |

---

## Résumé des logs ajoutés

- **Startup :** `Google Calendar enabled: true|false (reason: …)`
- **get_free_slots :** `get_free_slots: date=… start_hour=… end_hour=… events_busy=… free_slots=…`
- **Booking :** `[BOOKING_CHOSEN_SLOT] choice=… start_iso=… end_iso=… source=google pending_slots_display_len=…`
- **Erreur booking :** `Error booking appointment: HTTP 403 (permission)` (ou 409/400/other)
