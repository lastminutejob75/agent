# Analyse (sans code) — Bug confirmation numéro vocal + "ce créneau vient d'être pris"

**Objectif** : diagnostiquer en 1 run + appliquer le correctif ciblé.

---

## 0) Statut actuel (preuves déjà établies)

**✅ "Ce créneau vient d'être pris" — cause confirmée**

- Logs Google : **403 Forbidden** — *"You need to have writer access to this calendar."*
- ➡️ Le Service Account lit mais ne peut pas créer d'événements.

**✅ Bug vocal confirmation numéro — causes confirmées**

- TTS prononce : "Le 06, 52, 39…" (virgules) → prosodie bancale probable
- Parfois **intent_detected=None** alors que le user dit "oui" → YES non détecté

---

## 1) Bug vocal au moment "Je confirme le numéro…"

**Symptôme** : à la confirmation du numéro, impression que "ça bug vocalement".

### Contexte

- **État** : `CONTACT_CONFIRM`
- **Message** : VOCAL_PHONE_CONFIRM → "Je confirme : {phone_spaced}. C'est bien ça ?"
- **Attendu** : user dit "oui" → intent YES → booking → confirmation RDV

### Causes probables (dans l'ordre)

1. **TTS + ponctuation (virgules)** — Pauses longues, intonation "liste", parfois rendu "zéro six virgule…".
2. **Barge-in / chevauchement** — Le user dit "oui" pendant la fin de phrase → STT pollué → intent None/UNCLEAR/NO.
3. **YES trop court** — "oui/ouais" seul sur ligne téléphonique = faible confiance → intent None.

### Test en 1 run (30 secondes)

Sur le tour exact de CONTACT_CONFIRM :

- **assistant_text_sent** : vérifier la phrase envoyée au TTS
- **transcript brut user** + **intent_detected**
- **indicateur de timing** : user parle avant la fin du TTS ? → barge-in

### Correctifs décidés (déjà posés / à poser)

- **✅ TTS** : format numéro en espaces (sans virgules) — ex. `"06 52 39 84 14"` → résout la prosodie "liste".
- **✅ Filet UX en CONTACT_CONFIRM** :
  - Si intent ≠ YES/NO (None/UNCLEAR) :
    - **1er échec** : "D'accord. Juste pour confirmer : oui ou non ?"
    - **2e échec** : `_trigger_intent_router` (menu 1/2/3/4)
  - → on évite de relire le numéro complet (réduit barge-in + boucles).

---

## 2) "Ce créneau vient d'être pris" quasi à chaque RDV

**Principe** : si c'est systématique, ce n'est presque jamais un "slot conflict", c'est un échec technique masqué.

### Cause confirmée (ici)

**✅ Google Calendar : permissions insuffisantes**

- Erreur : **403 writer access required**
- L'agent transforme l'échec en message générique "créneau pris".

### Correctif (sans code)

1. Ouvrir **Google Calendar** (compte propriétaire du calendrier)
2. **Paramètres** du calendrier cible → **Partage et droits d'accès**
3. **Ajouter** l'email du Service Account (`…@…iam.gserviceaccount.com`)
4. **Droit** : "Modifier les événements" (writer)
5. Retester un RDV

### Points d'attention (sinon ça "semble" toujours cassé)

- Vérifier que tu partages **le bon calendrier** (celui dont le `calendar_id` est réellement utilisé).
- Si tu utilises un calendrier de type `…@group.calendar.google.com`, c'est celui-là à partager.

---

## 3) Logs minimaux pour conclure en 1 scénario (référence)

Même si on a déjà trouvé les causes, cette section reste utile comme "template diagnostic".

### A) Au début de `book_slot_from_session`

Logger :

- **pending_slots_display_len**
- **pending_slot_choice**
- **chosen_slot_source** (google / sqlite / legacy)
- **présence champs slot** : Google → `start_iso`, `end_iso` ; SQLite → `slot_id`
- **state_before**, **session_id**

### B) Résultat booking

- **Google** : HTTP code + message (ou exception_type)
- **SQLite** : slot_id + rows_affected / total_changes

**Lecture :**

- **403** → permission writer
- **409 / conflit** → vrai créneau pris
- **SQLite rows=0** → mauvais slot_id / mismatch

---

## 4) Plan de validation (après tes fixes)

**Objectif** : 1 appel vocal = verdict.

1. Arriver à **CONTACT_CONFIRM**
2. Vérifier que le TTS lit le numéro **avec espaces** (plus naturel)
3. Répondre **"oui"** :
   - si intent OK → booking direct
   - si intent None → 1 filet "oui ou non ?" puis OK
4. **Booking** : si writer OK → event créé → plus de "créneau pris"

---

## 5) Backlog produit (améliorations non bloquantes)

- **TTS** : option "zéro six / cinquante-deux …" si une voix reste capricieuse.
- **Booking** : différencier les messages :
  - **403** → "Autorisation manquante sur le calendrier (support)"
  - **conflit réel** → "Ce créneau vient d'être pris"
  - **API down** → "Problème technique temporaire, je vous transfère / je propose un autre créneau"
