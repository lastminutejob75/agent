# Batterie STT finale — validation post-patch

Validation manuelle à rejouer **après le patch REPEAT / YES-NO contextualisé**, pour vérifier que REPEAT, YES/NO contextualisé, router et slots séquentiels n’ont pas régressé.

**À faire dans l’ordre ci-dessous, en vocal si possible.**

---

## 1️⃣ START — « oui » ambigu (garde-fou critique)

**User :** « oui »

**✅ Attendu :**
- Pas de booking
- Clarification courte

**Agent :** *« Pas de souci. C’est pour un rendez-vous, ou pour une question ? »*

**❌ Échec si :** demande du nom directement.

---

## 2️⃣ START — filler pur

**User :** « euh… »

**✅ Attendu :**
- 1ʳᵉ fois : clarification
- Pas de FAQ
- Pas de silence

---

## 3️⃣ INTENT_ROUTER — « cat » (quatre mal reconnu)

*(Provoquer le router via 2–3 réponses floues avant.)*

**User :** « cat »

**✅ Attendu :**
- Reconnu comme 4
- Transfert immédiat

**Agent :** *« Je vous passe un conseiller. Un instant. »*

---

## 4️⃣ TRANSFER → REPEAT (le plus important)

*Après un transfert :*

**User :** « répétez »

**✅ Attendu :**
- Relecture du message de transfert
- État toujours TRANSFERRED

**❌ Échec si :** message générique sans lien / retour menu.

---

## 5️⃣ BOOKING — slot séquentiel + REPEAT

*Arriver à la proposition de créneau :*

**Agent :** *« Le prochain créneau est mardi à 9h30. Ça vous convient ? »*

**User :** « répétez »

**✅ Attendu :**
- Exactement le même créneau relu
- `slot_offer_index` inchangé

---

## 6️⃣ BOOKING — slot séquentiel + NO

*Toujours au même moment :*

**User :** « non »

**✅ Attendu :**
- Proposition du créneau suivant
- Pas de menu
- Pas de clarification inutile

---

## 7️⃣ QUALIF_NAME — « oui » hors état confirm

**Agent :** *« À quel nom est le rendez-vous ? »*

**User :** « oui »

**✅ Attendu :**
- Clarification du nom
- Rester en QUALIF_NAME

**❌ Échec si :** passage à l’étape suivante.

---

## 8️⃣ POST_FAQ — « d’accord »

*Après une réponse FAQ :*

**User :** « d’accord »

**✅ Attendu :**
- Disambiguation POST_FAQ_CHOICE
- Pas de booking direct

**Agent :** *« Vous voulez prendre rendez-vous, ou poser une question ? »*

---

## Verdict attendu

Si ces 8 phrases passent :

- REPEAT est fiable  
- YES/NO ne déclenche plus d’actions fantômes  
- Router robuste aux erreurs STT  
- Slots séquentiels solides  
- Aucune boucle frustrante  

À ce stade, l’agent vocal est prêt pour une validation pré-prod sérieuse.

---

## En cas d’échec sur un des 3 appels manuels

Si l’un des scénarios ne se comporte pas comme attendu, envoyer :

- **state** au moment du souci  
- **la phrase STT transcrite** (ce que l’agent a compris)  
- **la réponse agent** (texte renvoyé)

→ Ajustement ciblé possible sans casser les tests.
