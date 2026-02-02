# Diff recovery progressive CANCEL / MODIFY

## Statut actuel

**La recovery progressive est déjà implémentée** dans le repo :

- **CANCEL** : recovery nom (3 niveaux), état `CANCEL_NO_RDV` avec "vérifier ou humain", oui/non, `cancel_rdv_not_found_count` / `name_fails`, INTENT_ROUTER après 3 échecs (jamais transfert direct sans retries).
- **MODIFY** : même logique (`MODIFY_NO_RDV`, `modify_rdv_not_found_count`, etc.).
- **Session** : `name_fails`, `cancel_rdv_not_found_count`, `cancel_name_fails`, `modify_rdv_not_found_count`, `modify_name_fails` présents et réinitialisés dans `reset()` et `_trigger_intent_router()`.
- **Prompts** : `VOCAL_CANCEL_NAME_RETRY_1/2`, `MSG_CANCEL_NAME_RETRY_1_WEB/2_WEB`, `VOCAL_CANCEL_NOT_FOUND_VERIFIER_HUMAN`, `MSG_CANCEL_NOT_FOUND_VERIFIER_HUMAN_WEB` (idem pour MODIFY).
- **Tests** : `tests/test_cancel_modify_faq.py` avec `test_cancel_name_incompris_recovery`, `test_cancel_rdv_pas_trouve_offre_alternatives`, `test_modify_name_incompris_recovery`.

---

## Diff optionnel (wording spec)

Ta spec demande pour l’échec 2 :  
**"Votre nom et prénom, s'il vous plaît. Par exemple : Martin Dupont."**  
Actuellement le texte est : **"Votre nom et prénom. Par exemple : Martin Dupont."** (sans "s'il vous plaît").

### 1. backend/prompts.py

```diff
--- a/backend/prompts.py
+++ b/backend/prompts.py
@@ -157,7 +157,7 @@ VOCAL_CANCEL_ASK_NAME = "Bien sûr, pas de problème ! C'est à quel nom ?"
 # Recovery progressive : nom pas compris (CANCEL_NAME)
 VOCAL_CANCEL_NAME_RETRY_1 = "Je n'ai pas noté votre nom. Vous pouvez répéter ?"
-VOCAL_CANCEL_NAME_RETRY_2 = "Votre nom et prénom. Par exemple : Martin Dupont."
+VOCAL_CANCEL_NAME_RETRY_2 = "Votre nom et prénom, s'il vous plaît. Par exemple : Martin Dupont."
 
 VOCAL_CANCEL_NOT_FOUND = (
@@ -195,7 +195,7 @@ VOCAL_MODIFY_ASK_NAME = "Pas de souci. C'est à quel nom ?"
 # Recovery progressive : nom pas compris (MODIFY_NAME)
 VOCAL_MODIFY_NAME_RETRY_1 = "Je n'ai pas noté votre nom. Vous pouvez répéter ?"
-VOCAL_MODIFY_NAME_RETRY_2 = "Votre nom et prénom. Par exemple : Martin Dupont."
+VOCAL_MODIFY_NAME_RETRY_2 = "Votre nom et prénom, s'il vous plaît. Par exemple : Martin Dupont."
 
 VOCAL_MODIFY_NOT_FOUND = (
@@ -694,7 +694,7 @@ MSG_CANCEL_ASK_NAME_WEB = "Pas de problème. C'est à quel nom ?"
 MSG_CANCEL_NAME_RETRY_1_WEB = "Je n'ai pas noté votre nom. Répétez ?"
-MSG_CANCEL_NAME_RETRY_2_WEB = "Votre nom et prénom. Par exemple : Martin Dupont."
+MSG_CANCEL_NAME_RETRY_2_WEB = "Votre nom et prénom, s'il vous plaît. Par exemple : Martin Dupont."
 MSG_MODIFY_ASK_NAME_WEB = "Pas de souci. C'est à quel nom ?"
 MSG_MODIFY_NAME_RETRY_1_WEB = "Je n'ai pas noté votre nom. Répétez ?"
-MSG_MODIFY_NAME_RETRY_2_WEB = "Votre nom et prénom. Par exemple : Martin Dupont."
+MSG_MODIFY_NAME_RETRY_2_WEB = "Votre nom et prénom, s'il vous plaît. Par exemple : Martin Dupont."
```

---

## Tests déjà couverts

- **test_cancel_name_recovery** → `test_cancel_name_incompris_recovery` (nom incompris 3× → reformulation puis INTENT_ROUTER).
- **test_cancel_rdv_not_found** → `test_cancel_rdv_pas_trouve_offre_alternatives` (RDV pas trouvé → clarification "vérifier/orthographe/humain", pas transfert).
- **test_modify_name_recovery** → `test_modify_name_incompris_recovery` (même logique que CANCEL).

Aucun nouveau test à ajouter pour la mission ; les noms peuvent être renommés si tu veux coller exactement à `test_cancel_name_recovery` / `test_cancel_rdv_not_found` / `test_modify_name_recovery`.

---

## ClarificationMessages

La spec dit « Utiliser les ClarificationMessages existants si possible ».  
`ClarificationMessages.NAME_UNCLEAR` contient :
- 1 : "Pouvez-vous répéter votre nom en détachant les syllabes ?"
- 2 : "Pouvez-vous épeler votre nom ? Par exemple : D, U, P, O, N, T."

Tu demandes explicitement :
- 1 : "Je n'ai pas noté votre nom. Répétez ?"
- 2 : "Votre nom et prénom, s'il vous plaît. Par exemple : Martin Dupont."

Donc les messages dédiés CANCEL/MODIFY sont conservés ; le seul diff proposé est l’ajout de **"s'il vous plaît"** dans le retry 2 ci-dessus.

---

## Résumé

| Élément | Déjà en place | Diff proposé |
|--------|----------------|--------------|
| Recovery nom 3 niveaux (CANCEL) | Oui | — |
| RDV pas trouvé → clarification (CANCEL) | Oui | — |
| Compteurs name_fails, cancel_rdv_not_found_count | Oui | — |
| Même logique MODIFY | Oui | — |
| INTENT_ROUTER avant transfert (3 retries) | Oui | — |
| Wording retry 2 "s'il vous plaît" | Non | Oui (diff ci-dessus) |

Souhaites-tu que j’applique le diff wording (s'il vous plaît) dans `backend/prompts.py` ?
