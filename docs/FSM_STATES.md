# Inventaire des états FSM (engine.py)

Document généré pour la migration P2.1 — FSM explicite.  
Source : `backend/engine.py` + `backend/fsm.py` + `backend/routes/voice.py`.

## Liste triée des états

| État | Assigné dans engine | Dispatché (if/elif) | Notes |
|------|---------------------|----------------------|--------|
| **START** | Oui (931, 2562, 2656, 2664) | Oui (843) | Point d'entrée, premier message |
| **FAQ_ANSWERED** | Oui (965) | Oui (916) | Après réponse FAQ, choix continuer/abandon |
| **QUALIF_NAME** | Oui (864, 2227, 2553, 2649) | Oui (805) | Qualification booking : nom |
| **QUALIF_MOTIF** | Via state_map (1036, 1128) | Oui (805) | Qualification : motif |
| **QUALIF_PREF** | Oui (1338, 1351, 1361, 1371, 1384, 1394, 1404, 2187, 2601) | Oui (805) | Qualification : préférence créneau |
| **QUALIF_CONTACT** | Oui (1596, 1860, 2426) | Oui (805) | Qualification : contact (tél/email) |
| **PREFERENCE_CONFIRM** | Oui (plusieurs) | Oui (801) | Confirmation préférence inférée (matin/après-midi) |
| **AIDE_CONTACT** | — | Oui (809) | Aide guidance contact (rare) |
| **WAIT_CONFIRM** | Oui (1659) | Oui (813) | Attente choix créneau 1/2/3 |
| **CONTACT_CONFIRM** | Oui (1111, 1463, 1500, 1560, 1846) | Oui (837) | Confirmation numéro/email avant book |
| **CONFIRMED** | Oui (plusieurs) | — (terminal) | RDV confirmé, fin de flow |
| **TRANSFERRED** | Oui (nombreux) | — (terminal) | Transfert humain |
| **INTENT_ROUTER** | Oui (2493) | Oui (797) | Menu 1/2/3/4 (reset universel) |
| **CLARIFY** | Oui (874) | Oui (833) | Clarification intent (non/oui) |
| **CANCEL_NAME** | Oui (1902, 1923) | Oui (817) | Flow annulation : demander nom |
| **CANCEL_NO_RDV** | Oui (1987) | Oui (1918) | Annulation : RDV non trouvé |
| **CANCEL_CONFIRM** | Oui (1995, 1939) | Oui (2002) | Annulation : confirmer oui/non |
| **MODIFY_NAME** | Oui (2087, 2105) | Oui (821) | Flow modification : nom |
| **MODIFY_NO_RDV** | Oui (2165) | Oui (2101) | Modification : RDV non trouvé |
| **MODIFY_CONFIRM** | Oui (2172, 2119) | Oui (2179) | Modification : confirmer |
| **ORDONNANCE_CHOICE** | Oui (2223) | Oui (825) | Choix RDV vs message (ordonnance) |
| **ORDONNANCE_MESSAGE** | Oui (2237, 2346) | Oui (827) | Envoi message ordonnance |
| **ORDONNANCE_PHONE_CONFIRM** | Oui (2284, 2298) | Oui (829) | Confirmation tél ordonnance |

## États réellement traités (dispatch)

Chaque branche `if session.state == ...` ou `if session.state in [...]` dans `handle_message` :

- **START** — premier message, intent YES/NO/BOOKING/…
- **INTENT_ROUTER** — `_handle_intent_router`
- **PREFERENCE_CONFIRM** — `_handle_preference_confirm`
- **QUALIF_NAME**, **QUALIF_MOTIF**, **QUALIF_PREF**, **QUALIF_CONTACT** — `_handle_qualification`
- **AIDE_CONTACT** — `_handle_aide_contact`
- **WAIT_CONFIRM** — `_handle_booking_confirm`
- **CANCEL_NAME**, **CANCEL_NO_RDV**, **CANCEL_CONFIRM** — `_handle_cancel`
- **MODIFY_NAME**, **MODIFY_NO_RDV**, **MODIFY_CONFIRM** — `_handle_modify`
- **ORDONNANCE_CHOICE** — `_handle_ordonnance_flow`
- **ORDONNANCE_MESSAGE** — `_handle_ordonnance_message`
- **ORDONNANCE_PHONE_CONFIRM** — `_handle_ordonnance_phone_confirm`
- **CLARIFY** — `_handle_clarify`
- **CONTACT_CONFIRM** — `_handle_contact_confirm`
- **FAQ_ANSWERED** — bloc dédié (intent YES/NO/BOOKING après FAQ)

## États « fantômes » (jamais assignés comme state principal)

- **AIDE_MOTIF** — présent dans `backend/fsm.py` (ConvState) mais **non utilisé** dans le dispatch engine ; le flow motif utilise QUALIF_MOTIF + transfert / aide motif inline. À considérer comme legacy FSM1.

## Terminaux

- **CONFIRMED** — fin réussie (RDV pris, abandon poli, etc.)
- **TRANSFERRED** — transfert humain

## P2.1 — États couverts par FSM2 (phase 1)

- **QUALIF_NAME** — handler booking (qualif name)
- **WAIT_CONFIRM** — handler booking (confirm slot)

Les autres états restent en logique legacy jusqu’à migration progressive.
