# Sentry — Error tracking

Intégration optionnelle pour capturer les exceptions non gérées et les logs `ERROR` du backend.

## Vue d'ensemble

| Composant | Fichier |
|-----------|---------|
| Module Sentry | `backend/sentry_setup.py` |
| Initialisation | `init_sentry()` dans `backend/main.py` (avant `configure_logging()`) |
| Tests | `tests/test_sentry_setup.py` (skipped si `sentry-sdk` absent) |

## Activation

Définir `SENTRY_DSN` dans l'environnement. Si la variable est absente ou vide, l'intégration est désactivée (no-op, aucun coût runtime).

```bash
SENTRY_DSN=https://xxxxxxxxxxxx@sentry.io/123456
```

C'est tout. Au prochain démarrage du backend, les logs montrent :

```
Sentry: initialise (env=production, release=uwi-backend@a1b2c3d4, traces=0.0)
```

## Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `SENTRY_DSN` | (vide) | DSN du projet Sentry. **Active l'intégration.** |
| `SENTRY_ENVIRONMENT` | `RAILWAY_ENVIRONMENT` ou `ENV` ou `development` | `production` / `staging` / `development` |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.0` | Taux d'échantillonnage des traces (0.0-1.0). `0.0` = pas de tracing (errors uniquement). |
| `SENTRY_RELEASE` | git sha auto-détecté | Version envoyée à Sentry pour grouper les erreurs par release |

## Ce qui est capturé

Via `sentry-sdk[fastapi]` :

1. **Exceptions non gérées** dans les routes FastAPI (sauf `HTTPException` 4xx, filtrées par `_before_send`).
2. **Logs `ERROR`** émis par n'importe quel logger Python (via `LoggingIntegration`).
3. **Breadcrumbs** : tous les logs `INFO+` sont attachés à chaque event capturé (contexte).
4. **Transactions** si `SENTRY_TRACES_SAMPLE_RATE > 0` (perf monitoring).

## Ce qui n'est *pas* capturé (volontairement)

- `HTTPException` avec status code < 500 : `404 Not Found`, `401 Unauthorized`, `422 Validation Error`, etc. Ce ne sont pas des erreurs applicatives, on évite de noyer Sentry.
- Cookies, IPs, headers complets : `send_default_pii=False`. RGPD-friendly.

Si tu veux capturer un événement spécifique, utilise :

```python
from backend.sentry_setup import capture_exception, capture_message

try:
    risky_operation()
except SomeError as e:
    capture_exception(e)  # no-op si Sentry pas initialisé
    raise

capture_message("Audit critique : suspension forcée", level="warning")
```

## Capture des ERROR du log buffer

L'intégration `LoggingIntegration` capture automatiquement toute ligne de log `ERROR` ou plus grave, peu importe d'où elle vient :

```python
logger.error("Echec critique du paiement Stripe pour tenant %s", tenant_id)
# → envoyé à Sentry avec contexte (breadcrumbs des INFO précédents)
```

Combiné avec `backend/log_setup.py` (JSON + `request_id` dans `contextvars`), Sentry voit :

- Le message d'erreur
- Le `request_id` (corrélation avec `LogsPanel`)
- Les ~50 derniers logs `INFO/DEBUG` du même request (breadcrumbs)
- L'environnement (production/staging)
- La release (git sha)

## Sécurité

- `send_default_pii=False` : pas de cookies, headers `Authorization`, ni IP envoyés.
- `_before_send` filtre les `HTTPException 4xx` (pas vraiment des erreurs).
- Le DSN Sentry seul ne permet pas de lire les events, juste d'en envoyer.

## Désactiver temporairement

Supprimer la variable `SENTRY_DSN` (ou la laisser vide). Pas besoin de modifier le code.

## Lien avec les autres outils d'observabilité

| Outil | Rôle |
|-------|------|
| `LogsPanel` (in-app) | Lecture des derniers logs en RAM, debug rapide |
| `MetricsPanel` (in-app) | KPIs HTTP agrégés sur le buffer |
| `AuditLogPanel` (in-app) | Trace des actions admin (RGPD) |
| **Sentry** | Alertes sur les erreurs en prod (notifications email/Slack) |

`LogsPanel` est volatile (in-memory, perdu au restart). Sentry persiste les erreurs ad vitam, alerte, et permet de tracker leur résolution.

## Coût

Sentry a un tier gratuit avec ~5k events/mois. Pour un projet à faible volume d'erreurs, c'est largement suffisant. Si on commence à dépasser, c'est probablement qu'il y a quelque chose à fixer.

## Bonus : Sentry pour le frontend

Pas configuré pour le moment. Pour ajouter le tracking côté React :

```bash
cd landing
npm install @sentry/react
```

Et dans `landing/src/main.jsx` :

```js
import * as Sentry from "@sentry/react";

if (import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    environment: import.meta.env.MODE,
    tracesSampleRate: 0.0,
  });
}
```

À faire si on veut tracker les erreurs JS côté client.
