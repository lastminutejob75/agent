# Audit-log admin

Trace de toutes les actions d'écriture (POST/PUT/PATCH/DELETE) effectuées sur les routes `/api/admin/*`. But : RGPD, forensic, debug ("qui a fait quoi quand").

## Vue d'ensemble

| Composant | Fichier | Rôle |
|-----------|---------|------|
| Migration SQL | `migrations/034_admin_audit_log.sql` | Crée la table `admin_audit_log` + index |
| Helpers Python | `backend/audit_log.py` | Sanitisation, write/fetch, middleware |
| Middleware FastAPI | `install_audit_middleware(app)` dans `backend/main.py` | Capture + insert auto sur chaque write admin |
| Endpoint admin | `GET /api/admin/audit-log` dans `backend/routes/admin.py` | Lecture filtrable |
| UI | `landing/src/admin/components/dashboard/AuditLogPanel.jsx` | Affiche les writes récents dans `AdminMonitoring` |
| Tests | `tests/test_audit_log.py` (~30 tests) | Unit + intégration |

## Schéma de la table

```sql
admin_audit_log (
    id BIGSERIAL PRIMARY KEY,
    actor_email   TEXT,        -- email admin (NULL si action systeme)
    actor_role    TEXT,        -- "admin" / "system" / "bearer-token"
    tenant_id     BIGINT,      -- best-effort, extrait de l'URL
    method        TEXT,        -- POST/PUT/PATCH/DELETE
    path          TEXT,        -- ex: /api/admin/tenants/42/suspend
    status_code   INTEGER,     -- code HTTP retourne
    request_id    TEXT,        -- correle avec les logs structures
    ip            TEXT,        -- X-Forwarded-For prioritaire
    user_agent    TEXT,
    payload       JSONB,       -- body sanitise (passwords masques, tronque > 4KB)
    description   TEXT,        -- libelle humain pour les actions critiques
    created_at    TIMESTAMPTZ DEFAULT now()
)
```

Index :
- `idx_admin_audit_log_created` (tri par défaut DESC)
- `idx_admin_audit_log_actor` (filtre par admin)
- `idx_admin_audit_log_tenant` (partial WHERE NOT NULL — filtre par cible)
- `idx_admin_audit_log_path` (filtre par route)

## Middleware

Installé une fois dans `backend/main.py` :

```python
from backend.audit_log import install_audit_middleware
install_audit_middleware(app)
```

Comportement :
1. Filtre `method in {POST, PUT, PATCH, DELETE}` ET `path.startswith("/api/admin/")`.
2. Exclut les routes contenant des secrets en clair :
   - `/api/admin/auth/login`
   - `/api/admin/auth/logout`
   - `/api/admin/auth/me`
   - `/api/admin/logs/recent`
   - `/api/admin/logs/metrics`
3. Capture le body, le ré-injecte (Starlette), exécute la route, puis insère la ligne d'audit après la réponse.
4. Best-effort : si Postgres est indisponible, on log seulement (`logger.info("[ADMIN_AUDIT] ...")`) — la requête utilisateur n'est jamais bloquée.

### Désactiver le middleware

```bash
ADMIN_AUDIT_LOG_ENABLED=false
```

(par défaut activé). Utile en dev local sans Postgres pour réduire le bruit.

## Sanitisation

`_redact()` masque récursivement les clés contenant l'un de ces substrings (case-insensitive) :

```
password, passwd, secret, token, api_key, apikey,
authorization, auth, client_secret, stripe_key,
twilio_auth_token, vapi_api_key
```

Exemple :

```json
// body original
{"email": "alice@example.fr", "password": "hunter2", "stripe_key": "sk_live_..."}

// payload stocke
{"email": "alice@example.fr", "password": "***REDACTED***", "stripe_key": "***REDACTED***"}
```

Limites :
- Strings > 1024 chars tronquées (évite de stocker des uploads base64).
- Profondeur max d'imbrication : 6 niveaux.
- Taille totale max du JSON : 4 KB → au-delà, payload remplacé par `{"_truncated": true, "_size_bytes": ..., "_preview": "..."}`.

## Endpoint de lecture

```
GET /api/admin/audit-log?limit=100&offset=0
```

Auth : admin (cookie ou Bearer).

Query params (tous optionnels) :

| Param | Type | Description |
|-------|------|-------------|
| `limit` | int 1-500 | Nb max d'entrées (défaut 100) |
| `offset` | int >= 0 | Pagination |
| `actor_email` | string | Filtrer par admin |
| `tenant_id` | int | Filtrer par tenant cible |
| `method` | string | POST/PUT/PATCH/DELETE |
| `path_prefix` | string | Préfixe URL (ex: `/api/admin/tenants`) |

Réponse :

```json
{
  "ok": true,
  "items": [
    {
      "id": 1234,
      "actor_email": "admin@uwiapp.com",
      "actor_role": "admin",
      "tenant_id": 42,
      "method": "POST",
      "path": "/api/admin/tenants/42/suspend",
      "status_code": 200,
      "request_id": "abc12345-...",
      "ip": "1.2.3.4",
      "user_agent": "Mozilla/5.0 ...",
      "payload": {"mode": "hard"},
      "description": null,
      "created_at": "2026-05-09T21:12:00.123456+00:00"
    }
  ],
  "count": 1
}
```

## Helper `write_audit_entry()`

Pour logger explicitement une action critique (au-delà du middleware HTTP automatique) :

```python
from backend.audit_log import write_audit_entry

write_audit_entry(
    actor_email=admin_email,
    actor_role="admin",
    method="POST",
    path="/api/admin/tenants/42/suspend",
    status_code=200,
    tenant_id=42,
    description="Suspended tenant 42 (reason: unpaid)",
)
```

Best-effort : retourne `False` si l'insert échoue (PG indispo, table absente). Le log applicatif `[ADMIN_AUDIT]` est toujours émis dans `stdout` pour traçabilité minimale.

## UI

Panel `AuditLogPanel.jsx` intégré dans `AdminMonitoring` (route `/admin/monitoring`). Features :
- Filtres : method, email admin, tenant_id, préfixe URL, limit.
- Auto-refresh toutes les 30 s.
- Click sur une ligne = expand le payload JSON.
- Pills colorés par méthode (POST=vert, PATCH/PUT=orange, DELETE=rouge) et par status code.

## Migration / déploiement

1. Lancer la migration `034_admin_audit_log.sql` (postgres prod).
2. Déployer le backend → middleware actif automatiquement.
3. Vérifier dans `AdminMonitoring` qu'une ligne apparaît après une action admin (ex: PATCH params d'un tenant).

Pas de migration de données nécessaire — l'audit-log démarre vide et se remplit progressivement.

## Conformité RGPD

- `actor_email`, `ip` : données personnelles → rétention recommandée 12 mois (à configurer via cron `DELETE FROM admin_audit_log WHERE created_at < now() - interval '12 months'`).
- Pas de mot de passe stocké (sanitisation systématique).
- Endpoint accessible aux admins uniquement.

## Lien avec les autres systèmes d'observabilité

- `request_id` est le **même** que celui propagé par `backend/log_setup.py` (cf. `docs/OBSERVABILITE.md`). Permet de corréler une ligne d'audit avec la trace complète du request dans `LogsPanel`.
- Pour la lecture des actions admin, `AuditLogPanel` complète `LogsPanel` (logs bruts) et `MetricsPanel` (KPIs HTTP).
