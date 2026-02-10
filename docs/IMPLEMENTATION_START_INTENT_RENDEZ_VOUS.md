# Implémentation — Start intent « rendez-vous » (UX vocal v2)

## Objectif

Si l’utilisateur dit au démarrage : « rendez-vous », « rdv », « prendre rendez-vous », « un rendez-vous », etc.  
➡️ l’agent entre directement dans le flow booking, sans questions génériques ni UNCLEAR.

## Où c’est branché

- **Début du tour**, dans le handler de l’état d’entrée (**START**).
- Ordre : récupérer le transcript → normalisation (déjà dans `intent_parser.normalize_stt_text`) → détection mot-clé start (`_is_booking` + `_is_booking_blacklist`) → si match intent BOOKING → sinon pipeline normal.
- **Uniquement** tant que l’utilisateur n’est pas engagé dans un flow (état START). Pas dans CONTACT_CONFIRM, etc.

## Normalisation (déjà en place)

- `intent_parser.normalize_stt_text` : lower, trim, `-` → espace, accents → ascii, doubles espaces.
- Ex. « Rendez-vous » → « rendez yous », « prendre RDV » → « prendre rdv ».

## Liste blanche (contains)

- rdv, rendez yous, prendre rdv, prendre rendez yous, prise de rendez yous, rendez yous svp, un rendez yous, un rdv, etc.  
➡️ intent = BOOKING (traité comme BOOKING_START_KEYWORD en START).

## Liste noire (exclusions)

- **Annulation / déplacement** : annuler, deplacer, reporter, changer mon rendez → pas BOOKING (CANCEL/MODIFY déjà prioritaires en strong intent).
- **Négation** : pas, plus, aucun, non (mot ou en contexte) → pas BOOKING.
- **RDV existant ambigu** : « j’ai déjà un rendez-vous », « mon rendez-vous » → pas BOOKING (router normal).

## Priorité (ordre strict)

En état START : **CANCEL / MODIFY** (strong intent) → puis **BOOKING** (mot-clé start) → sinon pipeline normal.  
« Annuler mon rendez-vous » part donc en CANCEL, pas en prise de RDV.

## Réponse agent après détection

- Pas « je n’ai pas compris ». Enchaînement direct sur la première question du flow booking (ex. « Parfait. À quel nom, s’il vous plaît ? »).

## Logs (implémentés)

- À chaque déclenchement :  
  **`[INTENT_START_KEYWORD] conv_id=... state=... intent=BOOKING_START_KEYWORD text=... normalized=...`**

## Tests vocaux (checklist)

| User dit | Attendu |
|----------|---------|
| « rendez-vous » | → booking |
| « rdv » | → booking |
| « prendre rendez-vous » | → booking |
| « je veux un rdv » | → booking |
| « rendez vous s'il vous plaît » | → booking |
| « annuler mon rendez-vous » | → CANCEL (pas booking) |
| « déplacer mon rendez-vous » | → MODIFY (pas booking) |
| « pas de rendez-vous » | → pas booking |
| « j’ai déjà un rendez-vous » | → pas booking |

---

*Référence : PRD UX Vocal v2. Code : `intent_parser._is_booking`, `_is_booking_blacklist` ; log dans `engine.handle_message` (START + intent BOOKING).*
