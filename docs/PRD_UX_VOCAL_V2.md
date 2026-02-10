# PRD — UX Vocal v2 (Fluidité sans perte de fiabilité)

## Objectif

Améliorer la fluidité perçue de l’agent vocal sans dégrader la fiabilité :

- moins de rigidité,
- moins de répétitions,
- meilleure compréhension des réponses naturelles,
- meilleure accroche dès le premier mot.

## Problèmes ciblés (confirmés terrain)

- ❌ Réponse « c’est bien ça » non comprise comme confirmation
- ❌ Trop de « Très bien » / sur-acknowledgement
- ❌ « rendez-vous » non reconnu en début d’appel
- ❌ Parcours ressenti comme mécanique malgré logique correcte

## Principes UX

- **Une intention claire vaut plus qu’un mot exact**
- **Un acquiescement ≠ une phrase parfaite**
- **Un seul feedback vocal par étape**
- **Mieux vaut accepter large et vérifier, que refuser sec**

---

## 1️⃣ Confirmation : YES implicite

📄 **Spec d’implémentation détaillée** : [IMPLEMENTATION_YES_IMPLICIT.md](./IMPLEMENTATION_YES_IMPLICIT.md) (règle produit, liste blanche/noire, priorité intents, audit, où coder, checklist tests).

### Contexte

États concernés :

- **CONTACT_CONFIRM**
- (plus tard) SLOT_CONFIRM, FINAL_CONFIRM

### Règle

Si l’utilisateur répond par une **affirmation claire sans négation**, alors :  
→ traiter comme **YES_IMPLICIT**.

### Exemples acceptés (liste blanche)

- « c’est bien ça »
- « oui c’est ça »
- « exact »
- « tout à fait »
- « d’accord »
- « ok »
- « c’est bon »

### Exemples refusés (NO ou UNCLEAR)

- « non »
- « pas vraiment »
- « je ne sais pas »
- « euh… »

### Sécurité

- Loguer `intent=YES_IMPLICIT` (audit)
- Pas de booking sans confirmation explicite ou implicite
- En cas de doute → filet existant (« oui ou non ? »)

---

## 2️⃣ Nettoyage verbal (anti-robot)

📄 **Spec d’implémentation** : [IMPLEMENTATION_ANTI_REPETITION_TRES_BIEN.md](./IMPLEMENTATION_ANTI_REPETITION_TRES_BIEN.md) (pivot « Parfait », templates, 1 ack max).

### Problème

Accumulation de :

- « Très bien. »
- « Très bien, je vous propose… »
- « Très bien. »

### Règle

➡️ **1 acknowledgement maximum par étape**

### Remplacements recommandés

- « Très bien. » → (rien) ou « Parfait. »
- « Très bien, je vous propose… » → « Je vous propose… »

### Objectif

- réduire la durée perçue
- réduire l’effet robot
- garder un ton professionnel

---

## 3️⃣ Reconnaissance immédiate de « rendez-vous » (start intent)

📄 **Spec d’implémentation** : [IMPLEMENTATION_START_INTENT_RENDEZ_VOUS.md](./IMPLEMENTATION_START_INTENT_RENDEZ_VOUS.md) (liste blanche/noire, log BOOKING_START_KEYWORD, tests).

### Problème

- User : « rendez-vous »
- Agent : ❌ ne comprend pas

### Règle

Dès le **premier tour** :  
Si l’input contient un des tokens :

- **rendez-vous**
- **rendez vous**
- **rdv**
- **prendre rendez-vous**

➡️ Router directement vers **INTENT_BOOKING**.

### Justification

« rendez-vous » est un mot-clé métier central. Ne pas le capter détruit la confiance.

---

## 4️⃣ Confirmation numéro (robuste mais fluide)

📄 **Spec d’implémentation** : [IMPLEMENTATION_CONFIRMATION_NUMERO.md](./IMPLEMENTATION_CONFIRMATION_NUMERO.md) (phrase guidée oui/non, filet sans relecture, 1 relance puis transfert).

- Règle : YES / YES_IMPLICIT → booking ; NO → reprise contact ; UNCLEAR → 1 filet puis transfert (max 2 tours).
- Phrase : « Je confirme votre numéro : XX. Dites oui ou non. » — filet : « Juste pour confirmer : oui ou non ? » (pas de relecture du numéro).

---

## Hors scope (volontairement)
- ❌ Reformulation intelligente / LLM libre
- ❌ Changement de STT/TTS

---

## Critères d’acceptation (UX)

| Critère | Statut |
|--------|--------|
| « c’est bien ça » déclenche la suite du flow | À valider |
| Un seul « acknowledgement » audible par étape | À valider |
| Dire « rendez-vous » au démarrage lance le bon parcours | À valider |
| Aucun booking sans confirmation valide | À valider |
| Aucun nouveau cas de faux positifs | À valider |

---

## Priorité d’implémentation

1. **1️⃣ YES implicite**
2. **2️⃣ Intent « rendez-vous » au start**
3. **3️⃣ Nettoyage du langage**
4. **4️⃣ Confirmation numéro** (implémenté)

---

## Checklist de tests vocaux (validation manuelle / scénarios)

À exécuter après chaque modification pour ne pas régresser.

### T1 — YES implicite (CONTACT_CONFIRM)

- [ ] **T1.1** Agent demande « Le 06 XX XX XX XX, c’est bien ça ? » → User dit **« c’est bien ça »** → Agent enchaîne (booking ou suite), pas « Dites oui ou non ».
- [ ] **T1.2** Même contexte → User dit **« oui c’est ça »** → idem.
- [ ] **T1.3** Même contexte → User dit **« exact »** ou **« tout à fait »** → idem.
- [ ] **T1.4** Même contexte → User dit **« non »** → Agent redemande le numéro (pas de booking).
- [ ] **T1.5** Logs : au moins une ligne `[YES_IMPLICIT]` quand user dit « c’est bien ça » (audit).

### T2 — Nettoyage verbal (1 ack par étape)

- [ ] **T2.1** User dit **« rendez-vous »** au start → Réponse agent : **pas** « Très bien. Très bien, à quel nom… » (au plus un « Parfait » ou « À quel nom »).
- [ ] **T2.2** Après avoir donné son nom → Pas deux « Très bien » d’affilée.
- [ ] **T2.3** Proposition de créneaux : pas « Très bien. Très bien, je vous propose… ».

### T3 — Intent « rendez-vous » au start

- [ ] **T3.1** User dit **« rendez-vous »** seul → Agent demande le nom (qualif booking), pas clarification / transfert.
- [ ] **T3.2** User dit **« rdv »** seul → idem.
- [ ] **T3.3** User dit **« prendre rendez-vous »** → idem.

### T4 — Non-régression

- [ ] **T4.1** User dit **« non »** en CONTACT_CONFIRM → pas de booking, redemande numéro ou correction.
- [ ] **T4.2** Booking uniquement après une confirmation (oui / c’est bien ça / etc.), jamais sur « euh » ou silence.

---

*Document de référence pour les évolutions UX vocal.*

**Checklist d’audit (script par script) :** [CHECKLIST_AUDIT_UX_VOCAL.md](./CHECKLIST_AUDIT_UX_VOCAL.md) — sur-acknowledgement, sur-confirmation, densité, numéro, YES implicite, début de flow, règle des 30 %.
