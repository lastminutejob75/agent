# Changelog — Mise à jour post-patch (2025-02-03)

## Contexte

Suite à l’audit initial, deux règles nécessitaient une correction :

- **RÈGLE 3** — Silence interdit (partielle)
- **RÈGLE 7** — Contrainte horaire vs cabinet (non conforme)

Les correctifs ont été implémentés et validés par les tests automatisés.

---

## RÈGLE 3 — SILENCE INTERDIT

**Statut :** CONFORME

### Évolution

Le comportement silence a été aligné strictement sur la spécification :

| Tentative | Comportement |
|-----------|--------------|
| 1er silence | Message dédié : « Je n'ai rien entendu. Pouvez-vous répéter ? » |
| 2e silence | Message dédié : « Êtes-vous toujours là ? » |
| 3e silence | Escalade vers INTENT_ROUTER |

### Implémentation

- `RECOVERY_LIMITS["silence"]` porté à 3
- Messages distincts `MSG_SILENCE_1` / `MSG_SILENCE_2`
- Aucune situation où l’agent reste muet
- Couvert par tests automatisés

**Conclusion :** Règle pleinement conforme et robuste en production.

---

## RÈGLE 7 — CONTRAINTE HORAIRE UTILISATEUR VS HORAIRES CABINET

**Statut :** CONFORME

### Évolution

Ajout d’un traitement explicite des contraintes horaires formulées par l’utilisateur (ex. « je finis à 17h », « après 18h30 »).

### Fonctionnalités ajoutées

- Extraction des contraintes horaires (`extract_time_constraint`)
- Normalisation en minute-of-day
- Comparaison avec l’heure de fermeture du cabinet
- Deux comportements possibles :
  - **Impossible** (ex. after ≥ closing) → message explicite + INTENT_ROUTER
  - **Possible** → filtrage automatique des créneaux proposés

### Implémentation

- Configuration explicite des horaires cabinet (`CABINET_CLOSING_HOUR`, etc.)
- Stockage de la contrainte dans la session
- Filtrage des créneaux côté `tools_booking`
- Logs dédiés : `time_constraint_detected`, `time_constraint_impossible`

**Conclusion :** Règle désormais conforme, sans hallucination ni promesse irréaliste.

---

## Ajustements connexes validés

### FAQ — gestion des “no match”

- Comportement unifié sur 2 niveaux : clarification explicite → escalade vers INTENT_ROUTER
- Suppression des messages “exemples” bavards
- Plus de transfert humain direct sur FAQ incomprise

### Booking — correction d’un anti-pattern

- Si un créneau est déjà sélectionné et que le contact est fourni : passage direct à CONTACT_CONFIRM
- Suppression d’un rebouclage involontaire sur la proposition de créneaux

---

## État global de conformité (post-correctifs)

| Règle | Statut |
|-------|--------|
| RÈGLE 1 — Intent override | Conforme |
| RÈGLE 2 — Max recovery | Conforme |
| RÈGLE 3 — Silence interdit | Conforme |
| RÈGLE 4 — Anti-loop | Conforme |
| RÈGLE 5 — Confirmer inférences | Conforme |
| RÈGLE 6 — Répétition ≠ correction | Conforme |
| RÈGLE 7 — Contrainte horaire | Conforme |
| RÈGLE 8 — No hallucination | Conforme |
| RÈGLE 9 — Une question à la fois | Conforme |
| RÈGLE 10 — Caller ID respect | Conforme |

**Conformité globale : 10 / 10 règles**

Le moteur est désormais aligné avec les spécifications terrain, robuste face aux cas limites, et prêt pour une exploitation production (voix & web).
