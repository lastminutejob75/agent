# P0 Option B — Persistance sessions vocales (journal + checkpoints)

## Objectif

Ne plus perdre l'état d'un appel si redémarrage / multi-instance / webhook sur autre instance. Réduire `unknown_state` et transferts techniques. Garder performance via checkpoints.

## Pourquoi journal + checkpoint

- **Journal** (`call_messages`) : trace complète user/agent, rejouable pour recalculer l'état.
- **Checkpoints** (`call_state_checkpoints`) : snapshots périodiques de la session, évitent de rejouer tout l'historique.
- **Phase 1** : dual-write uniquement (on écrit en PG, on lit toujours in-memory). Zéro changement fonctionnel.
- **Phase 2** : read PG-first pour reprise après restart. Si session absente en mémoire → charge depuis PG (checkpoint snapshot), fallback in-memory si PG down.

## Schéma des tables

### call_sessions
| Colonne     | Type        | Description                    |
|-------------|-------------|--------------------------------|
| tenant_id   | INT         | Tenant (multi-tenant)          |
| call_id     | TEXT        | ID appel (conv_id)             |
| status      | TEXT        | active \| closed              |
| started_at  | TIMESTAMPTZ | Début appel                    |
| updated_at  | TIMESTAMPTZ | Dernière mise à jour           |
| last_state  | TEXT        | Dernier état FSM               |
| last_seq    | INT         | Dernier seq (messages)         |

**PRIMARY KEY** : (tenant_id, call_id)

### call_messages
| Colonne   | Type        | Description      |
|-----------|-------------|------------------|
| tenant_id | INT         | Tenant           |
| call_id   | TEXT        | ID appel         |
| seq       | INT         | Numéro séquence   |
| role      | TEXT        | user \| agent    |
| text      | TEXT        | Contenu          |
| ts        | TIMESTAMPTZ | Timestamp        |

**PRIMARY KEY** : (tenant_id, call_id, seq)
**INDEX** : (tenant_id, call_id, ts)

### call_state_checkpoints
| Colonne   | Type        | Description                    |
|-----------|-------------|--------------------------------|
| tenant_id | INT         | Tenant                         |
| call_id   | TEXT        | ID appel                       |
| seq       | INT         | Couvre tous les messages <= seq |
| state_json| JSONB       | Snapshot Session (sans secrets)|
| ts        | TIMESTAMPTZ | Timestamp                      |

**PRIMARY KEY** : (tenant_id, call_id, seq)
**INDEX** : (tenant_id, call_id, ts DESC)

## Quand checkpoint écrit

- **Changement d'état** : `state_before != state_after`
- **pending_slots_display mis à jour** : étape critique (proposition créneaux)
- **Toutes les N écritures** : N=3 (évite trop de checkpoints)

## Feature flag

- `USE_PG_CALL_JOURNAL=true` (défaut en prod)
- Si PG down : log `[CALL_JOURNAL_WARN]`, pas de crash.

## Logs structurés

```
[CALL_JOURNAL] tenant_id=1 call_id=xxx seq=1 role=user
[CALL_JOURNAL] tenant_id=1 call_id=xxx seq=2 role=agent
[CHECKPOINT] tenant_id=1 call_id=xxx seq=2 state=WAIT_CONFIRM
[CALL_JOURNAL_WARN] pg_down reason=ensure ...
[CALL_RESUME] source=pg tenant_id=1 call_id=xxx state=WAIT_CONFIRM ck_seq=2 last_seq=2
[CALL_RESUME_WARN] pg_down/err=connection refused
[CALL_LOCK] acquired tenant_id=1 call_id=xxx
[CALL_LOCK_TIMEOUT] tenant_id=1 call_id=xxx
[CALL_LOCK_WARN] err=...
```

## Phase 2 : PG-first read

- **Condition** : si `session_store.get(call_id)` renvoie `None` (restart, nouvelle instance) → tenter `load_session_pg_first(tenant_id, call_id)`.
- **Option A (P0)** : snapshot uniquement (checkpoint state_json), pas de replay messages.
- **Fallback** : si PG down ou pas de checkpoint → `get_or_create` (comportement actuel).
- **Garde-fou** : si state = `TRANSFERRED` ou `CONFIRMED` → ne pas rouvrir, répondre `VOCAL_RESUME_ALREADY_TERMINATED`.

## Phase 2.1 : Lock anti-concurrence

- **Objectif** : éviter 2 webhooks simultanés qui rechargent/écrivent la même session (double réponse, état incohérent).
- **Principe** : lock Postgres court (2s timeout) sur `call_sessions` pendant resume + handle_message.
- **Endpoints** : transcript, tool, chat/completions. Lock court sur get_or_resume uniquement (journal après release).
- **Timeout** : `lock_timeout = 2s` → si non acquis, lever `LockTimeout`.
- **Sur LockTimeout** : return 204 (no content), log `[CALL_LOCK_TIMEOUT]`, ivr_event `call_lock_timeout`. Pas de transfert, pas de double TTS.
- **Logs** : `[CALL_LOCK] acquired tenant_id call_id`, `[CALL_LOCK_TIMEOUT]`, `[CALL_LOCK_WARN] err=...`

## Mesurer l'impact (Phase 2)

- **rate session_reconstruct_used** doit chuter : moins de reconstructions depuis l'historique.
- **unknown_state** : moins de transferts techniques.

## KPI call_lock_timeout (Phase 2.1)

- **call_lock_timeout_rate_pct** : `lock_timeouts / calls` sur 7j (GET `/api/admin/tenants/{id}/technical-status`).
- **call_lock_timeout_alert** : `true` si rate > 0.5% (Vapi doublons ou latence DB).
- **Spike** : si ça grimpe d'un coup → incident possible.

### KPI reprise (export hebdo / dashboard admin)

- `resume_from_pg_count` : `COUNT(*) WHERE event='resume_from_pg'` dans ivr_events
- `resume_from_pg_rate` = resumes / calls_total
- Corréler avec `transfer_rate` pour prouver l'impact

### Validation prod

1. Lancer un appel, arriver à WAIT_CONFIRM (créneaux affichés)
2. Redéployer/restart Railway pendant l'appel
3. Dire "oui" ou "le 2"
4. ✅ Attendu : confirmation correcte (pas retour START, pas transfert)

### Test lock (2 hits simultanés)

1. Faire un appel, déclencher 2 hits simultanés (ou replay webhook)
2. ✅ Attendu : 1 seul `[CALL_LOCK] acquired`, l'autre `[CALL_LOCK_TIMEOUT]` + event
3. ✅ Une seule réponse vocale (pas de double TTS)

## Migration

```bash
DATABASE_URL=postgres://... python -m backend.run_migration 008
```

Fichier : `migrations/008_call_sessions_messages_checkpoints.sql`
