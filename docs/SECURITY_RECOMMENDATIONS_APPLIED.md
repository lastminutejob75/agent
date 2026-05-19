# Durcissements sécurité (reco audit)

Résumé des changements backend alignés avec l’audit authentification / multi-tenant / données sensibles.

## Impersonation admin → session client

- **JTI obligatoire** dans le JWT `scope=impersonate`. Les anciens jetons sans `jti` sont **rejetés**.
- **`register_impersonate_jti`** : consommation obligatoire (une session client par lien d’échange dans la fenêtre de révocation TTL).
- **Rate limit** : `check_impersonate_exchange` (`AUTH_RATE_LIMIT_IMPERSONATE_PER_MIN`, défaut 20/min/IP). Sous pytest, limite très haute automatique pour éviter les flaky tests.

Frontend : **`POST /api/auth/impersonate`** avec body JSON (voir `landing/src/lib/api.js`) — évite les fuites dans les logs serveur ou proxy versus query string GET.

## Login admin

- **Rate limit** : `check_admin_login` sur `POST /api/admin/auth/login` (`AUTH_RATE_LIMIT_ADMIN_LOGIN_PER_MIN`, défaut 10/min/IP).

## Limites configurables (auth)

Via variables d’environnement :

| Variable | Défaut | Usage |
|----------|--------|--------|
| `AUTH_RATE_LIMIT_LOGIN_PER_MIN` | 10 | `POST /api/auth/login` |
| `AUTH_RATE_LIMIT_ADMIN_LOGIN_PER_MIN` | 10 | Admin login mot de passe |
| `AUTH_RATE_LIMIT_IMPERSONATE_PER_MIN` | 20 | Échange impersonation |
| `AUTH_RATE_LIMIT_FORGOT_IP_PER_MIN` | 5 | Mot de passe oublié (IP) |
| `AUTH_RATE_LIMIT_FORGOT_EMAIL_PER_MIN` | 3 | Mot de passe oublié (email) |
| `AUTH_RATE_LIMIT_RESET_PASSWORD_PER_MIN` | 10 | Réinit. mot de passe |

Implémentation : `backend/rate_limit.py` (mémoire ou **Redis** si `REDIS_URL`).

## Routage Vapi / vocal → tenant

- **`resolve_tenant_id_from_vapi_payload`** utilisé également sur le chemin **Custom LLM** (`voice.py`), pour bénéficier du même fallback **assistantId → tenant** qu’ailleurs (évite DEFAUT quand DID manque mais assistant connu).

- **Production** : si après DID + caches + lookup assistant le résultat reste **`DEFAULT_TENANT_ID`** avec **`source=default`**, FastAPI **`422`** (refus silencieux de la mélange de tenants).

  - **Opt-out temporaire** (legacy uniquement) : `VAPI_ALLOW_DEFAULT_TENANT_FALLBACK=true`

## Secrets (rappels opérationnels)

- **`ADMIN_SESSION_SECRET`** : fortement recommandé en production (**≠ `JWT_SECRET`**). Un warning existe déjà si absent.
- **`ADMIN_API_TOKEN`** : périmètre total admin — rotation courte, audit d’usage.
