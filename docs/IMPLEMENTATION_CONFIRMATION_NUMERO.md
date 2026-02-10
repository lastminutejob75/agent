# Implémentation — Confirmation numéro « robuste mais fluide » (UX vocal v2)

## Objectif

- Accepter les réponses naturelles (« c'est bien ça », « ok », « d'accord »)
- Éviter les boucles et la relecture du numéro
- 1 seul filet puis transfert (fiabilité > intelligence)
- Réduire la lourdeur et la fragilité

## Règle en CONTACT_CONFIRM

- **YES** → booking  
- **YES_IMPLICIT** → booking  
- **NO** → reprise contact (ou re-dictée)  
- **UNCLEAR** → 1 filet (« Juste pour confirmer : oui ou non ? »)  
- Si encore UNCLEAR → **transfert**  
➡️ Max 2 tours dans CONTACT_CONFIRM.

## Modifications appliquées

### 1. Phrase de confirmation (courte, guidée)

- **Avant** : « Le 06 52 39 84 14, c'est bien ça ? »  
- **Après** : « Je confirme votre numéro : 06 52 39 84 14. Dites oui ou non. »

Constantes mises à jour : `VOCAL_PHONE_CONFIRM`, `VOCAL_CONTACT_CONFIRM`, `VOCAL_CONTACT_CONFIRM_SHORT`.

### 2. Filet (sans relecture du numéro)

- **Avant** : « D'accord. Juste pour confirmer : oui ou non ? »  
- **Après** : « Juste pour confirmer : oui ou non ? »  
- Pas de relecture du numéro, pas d’ack supplémentaire.

Constante : `MSG_CONTACT_CONFIRM_INTENT_1`.

### 3. YES implicite (déjà en place + exclusions)

- Accepté : « c'est bien ça », « ok », « d'accord », « exact », « c'est bon » (lexique + filet engine).  
- Exclu du YES implicite : phrases avec « non », « pas », « attends », « euh » (dont « euh oui »).

### 4. Comportement

- 1er tour UNCLEAR → filet « Juste pour confirmer : oui ou non ? »  
- 2e tour encore UNCLEAR → `_trigger_intent_router` (transfert).  
- Pas de 3e relance, pas de relecture du numéro après filet.

## Critères d’acceptation

- « c'est bien ça » → booking  
- « ok » → booking  
- Max 1 relance « oui ou non »  
- Pas de relecture du numéro après échec  
- Ambiguïté persistante → transfert (pas de boucle)

## Tests vocaux (scénarios)

| Scénario | Attendu |
|----------|---------|
| User « c'est bien ça » | → booking |
| User « ok » | → booking |
| User « euh… » → filet → « oui » | → booking |
| User « je sais pas » → filet → « je sais pas » | → transfert |

---

*Référence : PRD UX Vocal v2, étape 4.*
