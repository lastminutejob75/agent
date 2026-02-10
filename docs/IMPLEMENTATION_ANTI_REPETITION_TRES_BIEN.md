# Implémentation — Anti-répétition « Très bien » (Over-acknowledgement)

## Objectif

- 1 seul acquiescement max par étape
- Éviter « Très bien » en double (ou triple)
- Garder un ton pro et fluide

## Règle produit

Dans un même tour, **une seule phrase d’acquiescement** maximum.  
Acquiescements concernés : « Très bien. », « D’accord. », « Parfait. », « OK. », « Je vois. »  
➡️ Si une réponse contient déjà un acquiescement, on n’en remet pas un second.

## Option choisie : A (source de vérité dans les templates)

- Correction **directe** des messages dans **prompts.py** (et engine si besoin).
- Pas de post-processing global (risque de casser du contenu).

## Modifications appliquées

### Pivot unique : « Parfait. »

- **ACK_VARIANTS_LIST** = `["Parfait."]` → `pick_ack()` retourne toujours « Parfait. »
- **TransitionSignals** : PROGRESSION et RESULT = « Parfait. » (au lieu de « Très bien. »)
- **wrap_with_signal** : n’ajoute pas de signal si le message commence déjà par « parfait », « très bien » ou « d’accord »

### Templates (prompts.py)

- **Double ack / ack avant action** → phrase directe :
  - « Très bien. Voici trois créneaux » → « Voici trois créneaux »
  - « Très bien. Je vous propose un autre créneau » → « Je vous propose un autre créneau »
  - « Très bien, j’ai annulé l’ancien » → « J’ai annulé l’ancien. Plutôt matin ou après-midi ? »
  - « Très bien. Je propose le matin » → « Je propose le matin. Ça vous va ? »
  - « Très bien. Voici les créneaux disponibles » → « Voici les créneaux disponibles »
- **Un seul ack conservé** → remplacé par « Parfait. » :
  - Contact, qualif nom, slot early confirm, FAQ goodbye, etc. : « Très bien. » → « Parfait. »

### Engine

- **1 acknowledgement max** : pas d’ACK préfixé si la question commence par « parfait », « très bien », « d’accord » (déjà en place).
- Messages annulation / modification maintenus : « Très bien, je n’annule pas » → « Parfait, je n’annule pas ».

## Checklist de nettoyage (zones couvertes)

- Proposition de slots : pas de double ack
- Choix de slot : pas de double ack
- Saisie contact : pas de double ack
- Contact confirm : pas de double ack
- Confirmation RDV : pas de double ack

## Tests vocaux

- Enchaîner 3 tours (proposition → choix → contact) : doit rester fluide, pas de « Très bien » répété 2 fois de suite.
- Résultat attendu : flow plus rapide, moins robot, même fiabilité.

---

*Référence : PRD UX Vocal v2, étape 3.*
