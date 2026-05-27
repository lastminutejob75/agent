# Observabilité backend

Logs structurés, request_id, buffer en mémoire et endpoint d'inspection pour l'admin.
Implémenté lors de l'audit observabilité 2026-05.

## TL;DR

- Tous les logs Python du backend passent par un handler racine configuré dans `backend/log_setup.py`.
- Chaque requête HTTP reçoit un `request_id` (UUID4 ou repris du header `X-Request-ID`) propagé via un `contextvars.ContextVar`. Tous les logs émis pendant la requête l'incluent automatiquement.
- À la fin de chaque requête, un log `request_end` est émis avec `method`, `path`, `status_code`, `duration_ms`.
- Les ~1000 derniers logs sont gardés en RAM (ring buffer) et exposés via `GET /api/admin/logs/recent` pour inspection rapide depuis l'admin.
- Format JSON disponible (`LOG_JSON=true`), idéal pour ingestion type Datadog / Loki / CloudWatch.

## Variables d'environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Niveau racine (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `LOG_JSON` | `false` | Si `true` : `JsonFormatter`. Sinon format texte avec `[rid=...]` |
| `LOG_BUFFER_ENABLED` | `true` | Active le buffer en mémoire |
| `LOG_BUFFER_SIZE` | `1000` | Nombre de logs gardés en mémoire |

## Architecture

### `backend/log_setup.py`

| Composant | Rôle |
|---|---|
| `configure_logging()` | Configure le root logger : niveau, handler stdout (JSON ou texte), handler buffer. Idempotent (peut être appelé plusieurs fois). |
| `JsonFormatter` | Sérialise chaque record en JSON. Champs : `ts`, `level`, `logger`, `msg`, `request_id` + tous les `extra={...}` passés au logger. |
| `LogBuffer` | `deque(maxlen=N)` thread-safe. API : `append(entry)`, `recent(limit, level)`, `clear()`, `size()`. |
| `BufferHandler` | `logging.Handler` qui pousse chaque record (sous forme dict) dans le `LogBuffer` global. |
| `set_request_id(rid)` / `get_request_id()` | Helpers `contextvars` pour propager le request_id. |
| `install_request_logging_middleware(app)` | Middleware FastAPI qui génère/réutilise un request_id, le pousse dans le contextvar, log `request_end` avec durée, ajoute le header `X-Request-ID` à la réponse. |

### `backend/main.py`

```python
from backend.log_setup import configure_logging, install_request_logging_middleware
configure_logging()
install_request_logging_middleware(app)
```

### `GET /api/admin/logs/metrics`

Endpoint admin qui retourne des métriques agrégées calculées à partir du buffer (sans dépendances externes type Prometheus / Datadog) :

```json
{
  "ok": true,
  "metrics": {
    "total_requests": 47,
    "by_status": {"200": 40, "404": 5, "500": 2},
    "by_method": {"GET": 30, "POST": 17},
    "errors_4xx": 5,
    "errors_5xx": 2,
    "latency": {
      "p50_ms": 12, "p95_ms": 156, "p99_ms": 487, "max_ms": 1024, "avg_ms": 47
    },
    "top_paths": [
      {"path": "/api/admin/calls", "count": 12, "avg_ms": 87, "errors": 0}
    ],
    "logs_by_level": {"INFO": 80, "WARNING": 5, "ERROR": 1},
    "buffer_size": 86
  }
}
```

Affiché dans `AdminMonitoring` via `<MetricsPanel />` (poll toutes les 15s).

### `GET /api/admin/logs/recent`

Endpoint admin (auth requise) qui retourne les derniers logs du buffer.

**Query params :**

- `limit` (int, 1-1000, défaut 100) : nombre max d'entrées
- `level` (str, optionnel) : filtre par niveau (`DEBUG`, `INFO`, `WARNING`, `ERROR`)

**Réponse :**

```json
{
  "ok": true,
  "items": [
    {
      "ts": "2026-05-09T11:30:00.123+00:00",
      "level": "INFO",
      "logger": "uwi.request",
      "msg": "request_end",
      "request_id": "abc-123",
      "method": "GET",
      "path": "/api/admin/tenants",
      "status_code": 200,
      "duration_ms": 47
    }
  ],
  "count": 1,
  "buffer_size": 47
}
```

Plus récent en premier.

## Patterns de logging

### Log structuré classique

```python
import logging
logger = logging.getLogger(__name__)

logger.info(
    "user_action",
    extra={
        "user_id": user.id,
        "action": "login",
        "tenant_id": tenant_id,
    },
)
```

En `LOG_JSON=true` :

```json
{
  "ts": "2026-05-09T11:30:00.123+00:00",
  "level": "INFO",
  "logger": "backend.routes.admin",
  "msg": "user_action",
  "request_id": "abc-123",
  "user_id": 42,
  "action": "login",
  "tenant_id": 17
}
```

### Tracer une requête bout-en-bout

Le `request_id` est ajouté automatiquement à tous les logs émis pendant le traitement d'une requête HTTP. Pour le retrouver côté client :

1. Soit fourni par le client : `curl -H "X-Request-ID: my-trace-id" ...` → repris.
2. Soit généré par le serveur : présent dans le header de réponse `X-Request-ID`.

Dans les logs JSON :

```bash
# Tous les logs d'une requête particulière
curl -H "Authorization: Bearer $ADMIN_API_TOKEN" \
  "https://backend/api/admin/logs/recent?limit=1000" \
  | jq '.items[] | select(.request_id == "abc-123")'
```

### Niveaux conseillés

| Niveau | Usage |
|---|---|
| `DEBUG` | Détails techniques (variables intermédiaires). Désactivé en prod. |
| `INFO` | Événements métier normaux (login, booking, webhook reçu). |
| `WARNING` | Anomalie non bloquante (signature webhook invalide en mode souple, fallback config). |
| `ERROR` | Échec d'une opération (DB indisponible, exception non gérée). |

## Observabilité opérationnelle

### Local / dev

```bash
# Tous les logs d'une requête depuis un terminal
LOG_LEVEL=DEBUG LOG_JSON=true uvicorn backend.main:app | jq '.'

# Filtre les warnings
LOG_LEVEL=DEBUG LOG_JSON=true uvicorn backend.main:app \
  | jq 'select(.level == "WARNING")'
```

### Prod (Railway / autre)

- Activer `LOG_JSON=true` pour ingestion structurée.
- `LOG_LEVEL=INFO` (défaut) : pas de bruit, mais tous les events métier.
- Le buffer reste actif (`LOG_BUFFER_ENABLED=true` par défaut). Permet à l'admin d'inspecter les ~1000 derniers logs sans se connecter aux logs Railway.

### Inspection rapide depuis l'admin

```bash
# Derniers warnings et erreurs
curl -H "Authorization: Bearer $ADMIN_API_TOKEN" \
  "https://backend/api/admin/logs/recent?level=WARNING&limit=50" \
  | jq '.items[]'

# Derniers logs d'une route Vapi
curl -H "Authorization: Bearer $ADMIN_API_TOKEN" \
  "https://backend/api/admin/logs/recent?limit=200" \
  | jq '.items[] | select(.path | startswith("/api/vapi"))'
```

## Frontend AdminMonitoring

`AdminMonitoring.jsx` affiche un dashboard live avec deux panneaux :

- **`<MetricsPanel />`** (poll 15s) — KPIs (total requêtes, taux d'erreur, 4xx/5xx), latence p50/p95/p99/max/avg, top 10 routes par volume + erreurs, répartition par niveau (INFO/WARNING/ERROR).
- **`<LogsPanel />`** (poll 10s, pause/play) — derniers logs avec :
  - Filtre par niveau (`ERROR`, `WARNING`, `INFO`, `DEBUG`) + limit (50/100/200/500).
  - **Recherche full-text** (`msg`, `path`, `logger`, `request_id`, `method`, `level`).
  - **Groupement par `request_id`** (icône `Layers`) : regroupe tous les logs d'une même requête, affiche un résumé (méthode, path, status, durée, nb de logs).
  - **Pin sur `request_id`** : clic sur `rid=xxxxxxxx` (vue plate) ou bouton "Pin" (vue groupée) pour filtrer uniquement ce request_id. Pratique pour suivre une requête sur plusieurs lignes de log.
  - **Export JSON** (icône `Download`) : télécharge les logs filtrés (respecte la recherche + le pin) au format JSON pour analyse externe / partage / archivage.
  - Expand au clic sur une ligne pour voir le JSON brut complet.

Helpers correspondants dans `landing/src/lib/adminApi.js` :

```js
export const fetchLogMetrics = () => adminFetch("/api/admin/logs/metrics");
export const fetchRecentLogs = (limit = 100, level = null) => { ... };
```

## Tests

`tests/test_log_setup.py` (30 tests) couvre :

- `LogBuffer` : append, maxlen, filtre niveau, clear, limit cap.
- `JsonFormatter` : JSON valide, champs extra, request_id, valeurs non-sérialisables.
- `BufferHandler` : intégration avec `logging.getLogger`.
- `configure_logging()` : idempotence, activation JSON via env.
- Middleware : `X-Request-ID` dans la réponse, réutilise le header client, log `request_end` en buffer.
- Endpoint `GET /api/admin/logs/recent` : auth requise, `limit`, `level`, validation des bornes.
- `compute_metrics()` : buffer vide, count par status/method, percentiles latence (p50/p95/p99), top paths triés avec erreurs, logs_by_level, ignore non-`request_end`.
- Endpoint `GET /api/admin/logs/metrics` : auth requise, structure de la réponse.

```bash
python3 -m pytest tests/test_log_setup.py -v
# 30 passed in ~1s
```

## Voir aussi

- [`AUDIT_SECURITE_2026-05.md`](./AUDIT_SECURITE_2026-05.md) — Audit sécurité (signature Vapi, etc.)
- [`TESTS_BACKEND.md`](./TESTS_BACKEND.md) — Suite de tests backend
- [`INTEGRATION_VAPI.md`](./INTEGRATION_VAPI.md) — Vapi (logs `[VAPI_WEBHOOK_SIGNATURE_INVALID]`, etc.)
