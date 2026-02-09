# PRD — Stabilisation confirmation téléphone & booking RDV (Vocal)

**Version 1 page — Notion / GitHub Issue**

---

## Objectif

Éliminer les faux bugs lors de la confirmation du numéro et supprimer le message erroné "ce créneau vient d'être pris" quand la cause est technique.

---

## Portée

- **Agent vocal** — flux prise de RDV
- **États concernés** : CONTACT_CONFIRM → `book_slot_from_session`
- **Hors scope** : refonte STT/TTS provider, nouveaux intents

---

## Problèmes observés

**Confirmation numéro "bug vocal"**

- Lecture TTS peu naturelle (virgules)
- "oui" parfois non reconnu (intent None/UNCLEAR)
- Chevauchement TTS ↔ réponse user (barge-in)

**"Ce créneau vient d'être pris" quasi systématique**

- Booking échoue pour cause technique (403 Google writer), mais message fonctionnel affiché

---

## Causes racines (confirmées)

- **TTS** : format numéro avec virgules → mauvaise prosodie
- **STT/Intent** : réponses très courtes ("oui/ouais") + barge-in
- **Google Calendar** : Service Account sans droits writer

---

## Décisions produit (validées)

### A) TTS — Numéro de téléphone

- Format unique vocal : **espaces uniquement** — ex. `"06 52 39 84 14"`
- Centralisé via `format_phone_for_voice` (impact global contrôlé)

### B) CONTACT_CONFIRM — Filet UX

- Si intent ≠ YES/NO :
  - **1er échec** : "D'accord. Juste pour confirmer : oui ou non ?"
  - **2e échec** : `_trigger_intent_router` (menu guidé)
- Ne pas relire le numéro après le 1er échec

### C) Booking — Google Calendar

- Partager le calendrier cible avec l'email du Service Account
- Droit requis : **Modifier les événements** (writer)

---

## Logs minimaux (diagnostic 1 run)

**Avant booking**

- `pending_slots_display_len`
- `pending_slot_choice`
- `chosen_slot_source`
- Champs slot présents (Google: start_iso/end_iso, SQLite: slot_id)
- state_before, session_id

**Résultat booking**

- Google : HTTP code + message (ou exception_type)
- SQLite : slot_id + rows_affected / total_changes

---

## Critères d'acceptation

- Le numéro est lu naturellement (sans virgules)
- Un "oui" ambigu déclenche une seule relance courte
- ❌ **Aucune boucle vocale** (max 1 relance en CONTACT_CONFIRM)
- Avec droits writer OK :
  - Le RDV est créé
  - Le message "ce créneau vient d'être pris" n'apparaît plus pour une 403

---

## Plan de test (1 appel)

1. Arriver à CONTACT_CONFIRM
2. Vérifier TTS avec espaces
3. Répondre "oui" (ou tester 1 ambiguïté → filet)
4. Booking réussi → confirmation RDV

---

## Risques connus

- **Barge-in résiduel** sur certains TTS (acceptable avec filet UX)
- **Dépendance aux permissions Google Calendar** (mitigée par checklist QA)

---

## Backlog (non bloquant)

- Ne pas afficher un message fonctionnel (« créneau pris ») quand la cause est technique — principe *ne jamais mentir à l'utilisateur* (agent vocal).
- Message d'erreur différencié (403 vs conflit réel vs API down)
- Option TTS "zéro six / cinquante-deux …" pour voix capricieuses

---

*Si besoin : version "GitHub Issue" (checklist + labels + reproduction) ou version "post-mortem" pour l'historique produit.*
