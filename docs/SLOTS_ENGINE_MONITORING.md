# Moteur de créneaux — Points de surveillance et évolution

## Resets des refus (rejected_slot_starts, rejected_day_periods)

**À la confirmation** : reset déjà fait ✅

**À surveiller** — s'assurer que les refus sont aussi reset dans :

- **Changement de motif** : si motif influence durée/agenda, reset avant re-fetch
- **Re-fetch nouveau pool** : nouvelle journée, nouvelle préférence → reset déjà fait ✅ (qualif "non x2" → QUALIF_PREF)
- **Changement séquentiel ↔ liste** : si on bascule de mode, reset pour éviter accumulation

**Risque** : "il ne me propose plus rien" après plusieurs tours si les refus s'accumulent.

---

## Préférence ouverte : gérer "autre jour"

Quand user répond "un autre jour" à la question préférence :

- **Minimum viable** (`session.blocked_days` temporaire) :
  - Si `demain` → contrainte jour = demain
  - Si `autre jour` → interdire le jour du dernier proposé

- Pas de nouveau state nécessaire, juste une variable session `blocked_days`.

---

## KPI à suivre (logs existants)

| KPI | Source | Interprétation |
|-----|--------|----------------|
| `avg_seq_skip` | `[SLOT_SEQUENTIAL] seq_skip=N` | Si trop haut = pool mal filtré / contraintes mal comprises |
| `%slot_refuse_pref_asked` | ivr_event `slot_refuse_pref_asked` | % appels où refus x2 → question préférence |
| `%convert_after_refuse_pref` | parmi `slot_refuse_pref_asked` ⇒ `booking_confirmed` | Si bas = question préférence au mauvais moment |
| `%transfer_after_no_slots` | `VOCAL_NO_SLOTS` / transfer | Si monte = pool trop faible / mauvaise intégration calendar |

---

## Règle ack_idx

- **pick_slot_refusal_message** = OK pour `ack_idx` (round-robin naturel)
- **Messages critiques** (consentement, RGPD, urgence) = formulation **fixe**, ne pas appeler `next_ack_index()`

---

## Checklist prod (vérifiée)

| Point | Statut |
|-------|--------|
| **1. Pas de double question** | `pick_slot_refusal_message` retourne le message complet avec "Ça vous convient ?". Aucun prompt supplémentaire après. |
| **2. Cooldown refus (anti-barge-in)** | "non" ∈ CRITICAL_TOKENS (voice.py) → passe toujours pendant TTS. speaking_until_ts : seul le silence vide est ignoré, pas "non". |
| **3. Métrique refus→préférence** | Voir KPI ci-dessous |

---

## Améliorations UX déjà en place

- **Micro-texte après refus** : variantes round-robin + "Ça vous convient ?" (question fermée vocal)
- **Skip voisins** : ±90 min après un "non"
- **Anti-spam période** : `rejected_day_periods` évite matin → 11h30
- **Escalade** : "non x2" → question préférence ouverte
- **Métrique** : ivr_event `slot_refuse_pref_asked` pour % refus→préférence et conversion

---

## Dashboard minimal (ops)

Même un CSV/SQL hebdo suffit au début.

| Métrique | Source SQL / log |
|----------|------------------|
| `slot_refuse_pref_asked` (taux) | `SELECT COUNT(*) FROM ivr_events WHERE event='slot_refuse_pref_asked'` / nb appels |
| `convert_after_refuse_pref` | Parmi appels avec `slot_refuse_pref_asked` ⇒ `booking_confirmed` même call_id |
| `transfer_after_no_slots` | Appels avec transfer après `VOCAL_NO_SLOTS` |
| `avg_seq_skip` | `[SLOT_SEQUENTIAL] seq_skip=N` → moyenne par jour |

---

## Seuils d'alerte (simples)

| Seuil | Alerte | Action |
|-------|--------|--------|
| `transfer_after_no_slots` ↑ sur 7 jours | Problème pool/calendrier | Vérifier intégration Google Calendar, sync, disponibilités |
| `avg_seq_skip > 3` | Pool mal étalé ou filtrage refusés trop agressif | Revoir `_spread_slots`, `REJECTED_SLOT_WINDOW_MINUTES` |
| `convert_after_refuse_pref` < conversion globale − X pts | Question préférence au mauvais moment | Tester seuil à 3 refus au lieu de 2 |

---

## Playbook debug : "il propose n'importe quoi"

1. **Récupérer 1 call_id** du client (ex. rapport quotidien, IVR events).
2. **Lire les logs** :
   - `[TURN][START_ROUTE]` → decision_path, intent, why
   - `[SLOT_SEQUENTIAL]` → seq_skip, next_idx
   - `filtered_by_time_constraint` dans get_slots_for_display
3. **Vérifier session** (si stockée) :
   - `rejected_slot_starts` / `rejected_day_periods`
   - `slot_sequential_refuse_count`
   - `time_constraint_type` / `time_constraint_minute`

→ Tu sais quoi regarder tout de suite.
