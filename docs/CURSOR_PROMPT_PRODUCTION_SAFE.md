# Prompt Cursor — Mode production safe (référence)

Ce fichier contient le prompt complet à coller dans Cursor pour sécuriser les modifications sur le backend UWI. La règle résumée est dans `.cursor/rules/production-critical.mdc` (appliquée automatiquement).

**Version stricte (prod critique) :**
- Toute suppression de code existant est interdite sans justification explicite.
- Toute modification de texte utilisateur est interdite.

---

## Règle absolue

Tu ne dois **JAMAIS** casser les fonctionnalités suivantes :

- Lecture Google Calendar (`get_free_slots`)
- Écriture Google Calendar (`book_appointment`)
- Retry sur conflit 409
- Distinction **403** (permission) vs **409** (slot_taken) vs technical
- Persistance `pending_slots_display`
- Rapport quotidien `/api/reports/daily`
- Envoi email (Postmark/SMTP/API)
- Logs métier existants
- Streaming SSE Vapi
- Anti-hang (premier token < 3s)
- State machine déterministe

---

## Fonctionnalités critiques à ne pas casser

### 1) Google Calendar

- `get_free_slots()` : lire les événements busy, timezone Europe/Paris, slots cohérents, log `get_free_slots: date=... free_slots=...`
- `book_appointment()` : distinguer HTTP 403 → permission, HTTP 409 → slot_taken ; retry si nécessaire ; logger l’erreur exacte ; ne jamais masquer une erreur technique
- `tools_booking.py` : renvoyer `(success, reason)` avec `reason ∈ {"slot_taken", "permission", "technical"}`  
  **Ne jamais transformer un 403 en slot_taken.**

### 2) Session & slots

- `pending_slots_display` doit rester persisté
- `pending_slot_choice` ne doit jamais être perdu
- Aucun refactor ne doit vider ces champs

### 3) Rapport quotidien

- Endpoint `/api/reports/daily` : 202 immédiat, exécution en background, log `report_daily`, ne jamais bloquer la requête
- SMTP / API email ne doit pas être supprimé
- Variables d’environnement existantes restent supportées

### 4) Streaming SSE

- Format : `data: {"choices":[{"delta":{"content":"..."}}]}`
- Fin obligatoire : `data: [DONE]`
- Premier chunk immédiat (« Un instant. »)
- Logs : `LATENCY_FIRST_TOKEN_MS`, `LATENCY_STREAM_END_MS`  
  **Ne pas modifier le contrat SSE.**

### 5) Logs & observabilité

Ne pas supprimer : `DECISION_TRACE`, `BOOKING_RESULT`, `VALIDATION_DEVIATION`, `LATENCY_*`, logs `get_free_slots`.  
Ils servent au diagnostic prod.

---

## Modification autorisée

Uniquement :

- Ajouter la couche validation avant TTS
- Ajouter du logging structuré
- Ajouter des tests unitaires
- Améliorer la robustesse sans changer l’API

---

## Interdictions

- Pas de refactor massif
- Pas de renommage de fonctions critiques
- Pas de modification des textes dans `prompts.py`
- Pas de modification des signatures publiques
- Pas de suppression des retry Google
- Pas de modification des routes existantes
- Pas de modification des codes HTTP

---

## Checklist avant proposition

Avant chaque changement, vérifier :

1. Est-ce que ça peut casser le booking Google ?
2. Est-ce que ça peut casser le retry 409 ?
3. Est-ce que ça peut masquer un 403 ?
4. Est-ce que ça modifie le SSE ?
5. Est-ce que ça supprime un log existant ?
6. Est-ce que ça peut bloquer `/api/reports/daily` ?
7. Est-ce que ça peut impacter `LATENCY_FIRST_TOKEN_MS` ?

Si **OUI** à une seule question → proposer une version plus safe.

---

## Priorités

Stabilité > performance  
Déterminisme > intelligence  
Logs > propreté du code  
Médical > expérimentation

---

## Format attendu

- Diff minimal
- Code prêt à coller
- Tests inclus
- Explication claire
- Aucune suppression silencieuse

**Confirmer que tu respectes ces contraintes avant toute modification.**
