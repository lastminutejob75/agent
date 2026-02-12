# Events IVR P0 — Noms canoniques

Payload minimal : `tenant_id` (implicite via client_id), `call_id`, `state`, `event`, `context`, `reason`.

## Fin de call (3)

| Event | Quand |
|-------|-------|
| `booking_confirmed` | RDV confirmé ( créneau + contact validé ) |
| `transferred_human` | Transfert vers un humain (1x par call, idempotent) |
| `user_abandon` | Raccrochage / abandon utilisateur |

## Erreurs UX (2)

| Event | Quand |
|-------|-------|
| `repeat_used` | L'utilisateur a dit "répétez" (ou équivalent) |
| `yes_ambiguous_router` | Escalade vers INTENT_ROUTER via "oui" ambigu (reason: yes_ambiguous_2 ou yes_ambiguous_3) |

## Persistence

Tous ces events sont insérés dans `ivr_events` (client_id, call_id, event, context, reason).

Le rapport quotidien agrège : `booked`, `transfers`, `abandons`. Les events `repeat_used` et `yes_ambiguous_router` servent à mesurer les irritants par client.
