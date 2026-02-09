# 🐛 Bug — Confirmation téléphone vocale & faux "créneau pris"

**Type**  
🐞 Bug | 🎧 Voice / Booking | 🔥 Priority: High

---

## 🎯 Objectif

Stabiliser :

- La confirmation vocale du numéro de téléphone
- Le booking RDV (éviter le message erroné "ce créneau vient d'être pris" quand la cause est technique)

---

## 🧩 Contexte

- **Agent vocal** — flux de prise de rendez-vous
- **États concernés** : `CONTACT_CONFIRM` → `book_slot_from_session`

---

## ❌ Problèmes observés

### 1️⃣ Confirmation numéro — bug vocal

- Lecture TTS peu naturelle du numéro
- "oui" parfois non reconnu (`intent_detected=None`)
- Chevauchement TTS ↔ réponse utilisateur (barge-in)

### 2️⃣ Booking — "ce créneau vient d'être pris"

- Message affiché même quand l'échec est technique
- Logs Google : **403 Forbidden** — writer access required

---

## 🔎 Causes racines (confirmées)

**Confirmation numéro**

- Format TTS avec virgules → mauvaise prosodie
- Réponse "oui" trop courte / bruitée → intent UNCLEAR
- Barge-in sur phrase de confirmation

**Booking**

- Service Account Google Calendar avec droits lecture seule
- L'erreur 403 est transformée en "créneau pris"

---

## ✅ Correctifs appliqués / validés

### A) TTS — Numéro de téléphone

- Format vocal **sans virgules**, espaces uniquement — ex. `06 52 39 84 14`
- Centralisé via `format_phone_for_voice`

### B) CONTACT_CONFIRM — Filet UX

- Si intent ≠ YES / NO :
  - **1er échec** : "D'accord. Juste pour confirmer : oui ou non ?"
  - **2e échec** : `_trigger_intent_router` (menu guidé)
- Ne pas relire le numéro après le 1er échec

### C) Google Calendar — Permissions

- Partage du calendrier cible avec l'email du Service Account
- Droit requis : **Modifier les événements** (writer)

---

## 🧪 Plan de test (1 appel suffit)

- [ ] Lancer un appel vocal
- [ ] Aller jusqu'à CONTACT_CONFIRM
- [ ] Vérifier lecture du numéro (espaces, prosodie OK)
- [ ] Répondre "oui"
- [ ] Si intent ambigu → 1 relance "oui / non"
- [ ] Booking RDV
- [ ] Aucun message "ce créneau vient d'être pris"
- [ ] RDV créé dans Google Calendar

---

## 📊 Logs à vérifier (si régression)

**Avant booking**

- `pending_slots_display_len`
- `pending_slot_choice`
- `chosen_slot_source`
- Champs slot présents (start_iso/end_iso ou slot_id)
- state_before, session_id

**Résultat booking**

- Google : HTTP code + message
- SQLite : rows_affected / total_changes

---

## 🧠 Résultat attendu

- Confirmation téléphone fluide, sans boucle
- Un seul filet UX en cas d'ambiguïté
- Booking fiable dès que les droits Google sont corrects
- Plus de faux positifs "créneau pris"

---

## 🗂 Backlog (optionnel)

- Différencier messages utilisateur : **403** → autorisation calendrier | **conflit réel** → créneau pris | **API down** → problème technique
- Option TTS "zéro six / cinquante-deux …" pour voix capricieuses

---

*Suites possibles : version Post-Mortem (timeline + impact) | checklist QA pré-prod | spec "erreurs booking" orientée UX vocal*
