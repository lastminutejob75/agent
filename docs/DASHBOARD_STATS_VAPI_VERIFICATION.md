# Vérification : stats dashboard (appels, RDV) ↔ VAPI

## Chaîne de données

1. **VAPI** envoie les requêtes au backend :
   - `POST /api/vapi/chat/completions` (chaque tour de conversation)
   - `POST /api/vapi/tool` (book, transfer, etc.)
   - Webhook avec `message.call.id` (= `call_id`) et numéro appelé (DID = `to_number`).

2. **Backend (voice.py)** :
   - Extrait `call_id` (ex. `message.call.id`) et `to_number` (numéro appelé).
   - Résout `tenant_id` via `resolve_tenant_id_from_vocal_call(to_number, "vocal")` (DID → tenant dans `tenant_routing` PG ou SQLite).
   - Récupère/crée la session : `session = _get_or_resume_voice_session(tenant_id, call_id)` → `session.conv_id = call_id`.
   - Affecte `session.tenant_id = resolved_tenant_id` et `session.channel = "vocal"`.

3. **Engine** lors des actions :
   - RDV confirmé → `_persist_ivr_event(session, "booking_confirmed")` (engine.py ~l.3878).
   - Transfert → `_persist_ivr_event(session, "transferred_human")` (engine.py).
   - Abandon → `_persist_ivr_event(session, "user_abandon")` (engine.py).

4. **Persistance (`_persist_ivr_event` → `create_ivr_event`)** :
   - `client_id` = `session.tenant_id` (si channel vocal), sinon `session.client_id`.
   - `call_id` = `session.conv_id` (ID d’appel VAPI).
   - Écriture : SQLite (`backend/db.py`) + Postgres si `USE_PG_EVENTS=true` (`backend/ivr_events_pg.py`).

5. **Dashboard client** (`_get_dashboard_snapshot`, admin.py) :
   - Lit `ivr_events` (PG si `DATABASE_URL` ou `PG_EVENTS_URL`, sinon SQLite).
   - Filtre par `client_id = tenant_id` (tenant connecté).
   - Agrège : `calls_total` (COUNT DISTINCT call_id), `bookings_confirmed`, `transfers`, `abandons`, dernier appel, dernier RDV.

## Conclusion

- **Oui, la collecte des stats (appels, RDV pris) est bien connectée à VAPI** : chaque appel VAPI utilise le même `call_id` et le même `tenant_id` (résolu via le DID) de bout en bout ; les événements sont persistés dans `ivr_events` avec ce `tenant_id` et ce `call_id`, et le dashboard lit ces mêmes données.

## Points à vérifier en prod

1. **Routing DID → tenant** : le numéro VAPI (DID) doit être enregistré dans `tenant_routing` (PG ou SQLite) avec `channel = 'vocal'` et le bon `tenant_id`. Sinon `resolve_tenant_id_from_vocal_call` renvoie le tenant par défaut (1).
2. **Même base pour écriture et lecture** :
   - Si vous utilisez Postgres : `USE_PG_EVENTS=true` et `DATABASE_URL` (ou `PG_EVENTS_URL`) définis ; le dashboard utilise cette même URL pour lire.
   - Si vous utilisez uniquement SQLite : le dashboard utilise `backend.db` (même base que `create_ivr_event`).
3. **`call_id` présent** : les payloads VAPI doivent contenir `message.call.id` (ou équivalent) pour que `call_id` soit renseigné ; sinon les événements peuvent être ignorés (ex. `booking_confirmed` si `call_id` vide).

## Fichiers clés

| Rôle | Fichier |
|------|--------|
| Résolution tenant (DID → tenant_id) | `backend/tenant_routing.py`, `backend/tenants_pg.py` |
| Session + tenant_id/call_id sur la voix | `backend/routes/voice.py` (_get_or_resume_voice_session, chat completions, tool) |
| Persistance événements | `backend/engine.py` (_persist_ivr_event), `backend/db.py` (create_ivr_event), `backend/ivr_events_pg.py` |
| Lecture dashboard | `backend/routes/admin.py` (_get_dashboard_snapshot) |
