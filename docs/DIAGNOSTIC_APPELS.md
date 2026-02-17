# Diagnostic — Les appels ne marchent plus

Checklist pour retrouver pourquoi les appels vocaux (Vapi) ne fonctionnent plus.

---

## 1. Quelle URL Vapi appelle ?

Le **backend des appels** est le **serveur FastAPI** (Railway ou autre), **pas** le front Next.js.

| Rôle | URL à configurer dans Vapi |
|------|----------------------------|
| **Server URL** (base) | `https://<ton-backend>.railway.app` (ou ton domaine backend) |
| **Webhook** | `POST https://<backend>/api/vapi/webhook` |
| **Tool** (function calling) | `POST https://<backend>/api/vapi/tool` |
| **Custom LLM** (chat) | `POST https://<backend>/api/vapi/chat/completions` |

Si Vapi pointe vers une URL **Next.js** (ex. Vercel) au lieu du backend FastAPI, les appels utiliseront l’ancien flux limité (voir `app/api/vapi/webhook/route.ts`) et pas l’engine complet (tenant, créneaux, FAQ, etc.).

**À faire** : Dans le dashboard Vapi, vérifier que Server URL / Webhook URL / Custom LLM URL pointent bien vers le **backend FastAPI** (ex. Railway).

---

## 2. Variables d’environnement (production)

En **production** (`ENV=production` ou `RAILWAY_ENVIRONMENT=production`), si `TEST_TENANT_ID` n’est **pas** défini, l’init en arrière-plan **échoue** (RuntimeError) et tout le reste ne s’exécute pas :

- Pas de chargement des credentials Google Calendar  
- Pas de pose de la route numéro test → tenant (`ensure_test_number_route`)  
- Résultat : pas de créneaux, ou tenant mal résolu  

**À faire** : Sur Railway (ou ton host), définir au minimum :

- `TEST_TENANT_ID` = ID du tenant pour le numéro de démo (ex. `1`)
- `TEST_VOCAL_NUMBER` ou `ONBOARDING_DEMO_VOCAL_NUMBER` = numéro E.164 (ex. `+33939240575`)
- `DATABASE_URL` (ou `PG_TENANTS_URL`) si tu utilises PG pour le routing (`USE_PG_TENANTS=true`)

Après déploiement, regarder les logs : tu dois voir « Heavy init done » et « ensure_test_number_route OK ». Si tu vois « TEST_TENANT_ID must be set in production », l’init a planté et les appels peuvent être cassés (pas de calendrier, pas de route).

---

## 3. Health checks

Depuis ta machine ou un curl :

```bash
# Santé globale
curl -s https://<backend>/health

# Santé Vapi
curl -s https://<backend>/api/vapi/health
```

Réponse attendue : `200` avec un body du type `{"status":"ok"}`. Si 404 ou 500, le backend ne répond pas ou une dépendance manque.

---

## 4. Test minimal webhook

Pour vérifier que le webhook accepte bien les requêtes Vapi :

```bash
curl -s -X POST https://<backend>/api/vapi/webhook \
  -H "Content-Type: application/json" \
  -d '{"message":{"type":"status-update","call":{"id":"test-call-1","customer":{"number":"+33600000000"},"phoneNumber":{"number":"+33939240575"}}}}'
```

Réponse attendue : `200` (body vide ou minimal). Si 500, regarder les logs backend (exception dans `vapi_webhook`).

---

## 5. Résolution tenant (numéro test)

Le numéro de démo (ex. `09 39 24 05 75` / `+33939240575`) doit être routé vers `TEST_TENANT_ID`. Si la route n’existe pas (PG et SQLite vides), `resolve_tenant_id_from_vocal_call` retourne `DEFAULT_TENANT_ID` (souvent 1). Ça peut suffire si le tenant 1 existe ; sinon, créneaux ou config tenant incorrects.

**À faire** : S’assurer que `ensure_test_number_route()` s’exécute au démarrage (voir logs « ensure_test_number_route OK »). Si PG est down au boot, la route est quand même écrite en SQLite par `add_route` avant l’appel à `pg_add_routing`.

---

## 6. Causes fréquentes « plus rien ne marche »

| Cause | Symptôme typique | Action |
|-------|------------------|--------|
| Mauvaise URL dans Vapi | Appel vers Next au lieu de FastAPI, ou 404 | Corriger Server URL / Webhook / Custom LLM dans Vapi |
| `TEST_TENANT_ID` absent en prod | Pas de « Heavy init done », pas de Google, pas de route test | Définir `TEST_TENANT_ID` (et redéployer) |
| PG inaccessible | Logs « PG_HEALTH down » / « ensure_test_number_route failed » | Vérifier `DATABASE_URL`, ou accepter le fallback SQLite |
| Calendrier désactivé | « Aucun créneau » à chaque fois | Vérifier `GOOGLE_SERVICE_ACCOUNT_BASE64` / `GOOGLE_CALENDAR_ID` |
| Timeout premier token | Silence ou coupure côté Vapi | Vérifier latence < 3s (logs `LATENCY_FIRST_TOKEN_MS`) |

---

## 7. Logs utiles côté backend

En production, filtrer les logs sur :

- `[TENANT_ROUTE]` : numéro appelé → tenant_id et source (route vs default)
- `CALLER_ID_PERSISTED` / `CALLER_ID` : persistance du numéro appelant
- `TOOL_CALL` : appels get_slots / book / faq
- `LATENCY_FIRST_TOKEN_MS` : temps jusqu’au premier token (objectif < 3000 ms)
- `ensure_test_number_route` / `Heavy init` : succès ou échec de l’init

Si tu veux, on peut ensuite cibler un scénario précis (ex. « pas de créneaux », « silence », « 500 ») et tracer le code path correspondant.
