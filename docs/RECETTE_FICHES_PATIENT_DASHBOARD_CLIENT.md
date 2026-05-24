# Recette — Fiches patient (dashboard client)

Objectif : une **« fiche patient »** existe sur le dashboard praticien lorsque l’**identité est validée** (`validated_name` ≥ 2 caractères après normalisation serveur). Aligné avec l’agenda (`patient_has_file`).

## 1. Agenda

| Cas | Étapes attendues |
|-----|------------------|
| Téléphone connu + fiche avec identité validée | Ouvrir un RDV avec téléphone → bouton **Fiche patient** → dashboard patient charge (notes/documents selon données). |
| Téléphone connu sans identité validée | **Créer fiche patient** → modale préremplie → enregistrer → rechargement → **Fiche patient** puis navigation fiche. |
| Sans téléphone | Pastille ou détail : **Patients** vers la liste, pas de création directe depuis le RDV. |
| Sources | Vérifier au moins un créneau **UWI** (local) et, si configuré, un créneau **Google** après synchronisation des numéros. |

## 2. Journal d’appels (`CallJournalPage` / flux `useCalls`)

| Cas | Étapes attendues |
|-----|------------------|
| Appel avec numéro, pas d’identité validée | Ligne/badge **sans fiche** (ou équivalent visuel selon vue) ; action principale permet **Créer fiche**. |
| Après validation depuis la modale | Statut passe à patient **avec fiche** ; lien **Voir la fiche patient** si applicable. |
| Filtres onglets | Onglet **Sans fiche** ne liste que les appels encore sans identité validée (`validated_name` &lt; 2 car.). |

## 3. Page Appels legacy (`AppCalls`)

| Cas | Vérifier |
|-----|----------|
| Liste | Pastille ou libellé cohérent **Fiche OK** vs **À compléter** / **sans fiche** selon `validated_name`. |
| Détail / modale | Section **Fiche patient** : mentions **Nom issu de l’appel** ou **À valider sur la fiche**, bouton validation crée bien la ligne + note/doc si renseignés. |

## 4. Liste Patients (`AppPatients`)

| Cas | Étapes attendues |
|-----|------------------|
| Ligne avec appel source (`source_call_id` ou `last_call_id`) | **Confirmer** le nom passe par PATCH appel puis met à jour la liste. |
| Ligne sans appel associé mais numéro connu | Même champ **Confirmer** : doit enregistrer via **création fiche** (sans `call_id`) sans message bloquant « Aucun appel lié ». |
| Filtre **À valider** | Liste les fiches sans identité validée (`validated_name` &lt; 2 car.). |

## 5. Règle métier (rappel)

- **Pas** le nom commercial du cabinet.
- Une ligne patient en base **sans** `validated_name` (ou trop court) = **pas encore** une fiche exploitable comme « connue » ; même logique agenda / journal / appels.

## 6. Non-régression API (tests auto)

Voir `tests/test_dashboard_patient_file_flags.py` et `landing/src/lib/callsService.patientFile.test.js`.
