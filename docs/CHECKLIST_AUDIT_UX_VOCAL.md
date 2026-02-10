# Checklist d’audit UX vocal — Agent RDV

**Mode d’emploi :** Pour chaque réplique agent, coche mentalement (ou dans un tableau) les points ci-dessous. Dès qu’un ❌ apparaît → il y a optimisation à faire.

---

## 1️⃣ Audit « Parfait / Très bien / D’accord » (sur-acknowledgement)

**❓ Question à se poser**  
Est-ce que l’agent vient déjà de montrer qu’il a compris en avançant ?

**❌ À corriger si :**
- Deux répliques agent consécutives commencent par « Parfait », « Très bien », « D’accord »
- « Parfait » est utilisé sans apporter d’information
- « Parfait » précède immédiatement une question simple

**✅ Bon pattern**
- 0 ou 1 acquiescement par phase
- Aucun acquiescement si la phrase suivante suffit

**📌 Règle**  
Si tu peux supprimer « Parfait. » sans changer le sens → supprime-le.

---

## 2️⃣ Audit « C’est bien ça ? » (sur-confirmation)

**❓ Question à se poser**  
L’étape suivante prouve-t-elle déjà que l’agent a compris ?

**❌ À corriger si :**
- « C’est bien ça ? » est utilisé :
  - juste avant une action logique (ex. demande du numéro)
  - deux fois en moins de 3 tours
  - pour une info simple (matin / après-midi)

**✅ Bon pattern**
- 1 confirmation explicite max par bloc logique
- Zéro confirmation explicite si l’enchaînement suffit

**📌 Règle**  
Si l’agent agit comme si c’était confirmé, ne pas demander confirmation.

---

## 3️⃣ Audit densité de confirmation (rythme)

**❓ Question à se poser**  
Combien de confirmations explicites dans les 3 derniers tours ?

**❌ À corriger si :**
- ≥ 2 confirmations explicites dans 3 tours
- confirmation créneau puis confirmation numéro sans respiration
- confirmation verbale + confirmation guidée trop proches

**✅ Bon pattern**
- Une confirmation → puis action → puis autre bloc

**📌 Règle**  
Une conversation ≠ une checklist orale.

---

## 4️⃣ Audit confirmation numéro (spécifique)

**❓ Question à se poser**  
Est-ce que l’agent re-lit le numéro inutilement ?

**❌ À corriger si :**
- Le numéro est relu après un premier doute
- Plus d’un filet est utilisé
- Un acquiescement précède le filet

**✅ Bon pattern**
- Phrase guidée : « Dites oui ou non »
- 1 seul filet
- Puis transfert

**📌 Règle**  
Sur le numéro : 2 tours max, jamais plus.

---

## 5️⃣ Audit YES implicite (naturalité)

**❓ Question à se poser**  
Est-ce que l’utilisateur a confirmé naturellement ?

**❌ À corriger si :**
- « c’est bien ça », « ok », « d’accord » → non reconnus
- l’agent redemande alors que le sens est clair

**✅ Bon pattern**
- YES implicite accepté
- Loggé
- Flow continue sans friction

**📌 Règle**  
Si un humain comprendrait → l’agent doit comprendre.

---

## 6️⃣ Audit début de flow (accroche)

**❓ Question à se poser**  
Un humain dirait-il ça à un accueil téléphonique ?

**❌ À corriger si :**
- « Je n’ai pas compris » après « rendez-vous »
- question générique inutile
- trop de politesse dès la première phrase

**✅ Bon pattern**
- mot-clé = action
- question utile immédiate

**📌 Règle**  
Le premier mot de l’utilisateur doit suffire à lancer le bon flow.

---

## 7️⃣ Audit global — règle des 30 %

**Test rapide**  
Relis le script et supprime 30 % des mots :
- « Parfait »
- « Très bien »
- « D’accord »
- confirmations verbales

Si le sens reste clair → le script est meilleur.

**📌 Règle finale**  
Moins de mots = plus de confiance.

---

## Grille rapide (exemple à remplir)

| Tour | Texte agent | Parfait ? | Confirmation ? | Utile ? | Action |
|------|-------------|-----------|----------------|---------|--------|
| 2 | Parfait. À quel nom… | ❌ | ❌ | ⚠️ | Supprimer « Parfait » |
| 4 | Parfait. Vous préférez… | ❌ | ❌ | ⚠️ | Supprimer |
| 7 | C’est bien ça ? | ⚠️ | ❌ | ❌ | Supprimer |

*(Dupliquer la ligne pour chaque tour agent du script.)*

---

## Règles d’or (synthèse)

| Règle | Résumé |
|-------|--------|
| **1 — Progression > validation** | Si l’agent enchaîne vers l’étape suivante, il n’a pas besoin de confirmer verbalement. |
| **2 — 1 confirmation max par bloc** | Bloc créneau → 1 confirmation. Bloc contact → 1. Bloc préférence → souvent 0. |
| **3 — Laisser l’utilisateur confirmer** | Laisser l’utilisateur dire « c’est bien ça », « ok », « oui » plutôt que de le dire soi-même. |
| **4 — Pas d’ack sur deux tours consécutifs** | Sauf changement de phase majeure. |
| **5 — Pas de « c’est bien ça ? » si l’étape suivante prouve la compréhension** | Agir = suffisant. |

---

*Document de référence pour l’audit des scripts vocaux. À utiliser tour par tour pour repérer sur-acknowledgements et sur-confirmations.*
