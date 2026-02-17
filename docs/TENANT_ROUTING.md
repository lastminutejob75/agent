# Ajouter les routes en base (tenant_routing)

Les routes associent un **canal + numéro/clé** au **tenant_id**. Utilisées pour le **vocal** (DID), **WhatsApp** (numéro Business) et **Web** (clé API widget = header `X-Tenant-Key`).

---

## 1. Via l’API admin (recommandé)

**Endpoint :** `POST /api/admin/routing`  
**Auth :** nécessaire (cookie JWT ou header admin selon votre config).

**Body JSON :**
```json
{
  "channel": "whatsapp",
  "key": "+33939240575",
  "tenant_id": 1
}
```

- **channel** : `"vocal"`, `"whatsapp"` ou `"web"`
- **key** : numéro E.164 **avec le `+`** (vocal/WhatsApp) ou **clé API widget** (web, ex. `widget-key-tenant-42`)
- **tenant_id** : ID du tenant (1 = défaut)

**Exemple curl (avec token admin) :**
```bash
curl -X POST "https://VOTRE_DOMAINE/api/admin/routing" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer VOTRE_TOKEN" \
  -d '{"channel":"whatsapp","key":"+33939240575","tenant_id":1}'
```

L’API écrit en **PostgreSQL** si `USE_PG_TENANTS=true`, sinon en **SQLite**. La clé est normalisée (espaces enlevés, `00` → `+`).

---

## 2. En SQL

### PostgreSQL

Table : `tenant_routing`  
Colonnes utilisées : `channel`, `key`, `tenant_id`, `is_active`.

```sql
INSERT INTO tenant_routing (channel, key, tenant_id, is_active, updated_at)
VALUES ('whatsapp', '+33939240575', 1, TRUE, now())
ON CONFLICT (channel, key) DO UPDATE SET tenant_id = EXCLUDED.tenant_id, is_active = TRUE, updated_at = now();
```

Pour le **vocal** (numéro appelé) :
```sql
INSERT INTO tenant_routing (channel, key, tenant_id, is_active, updated_at)
VALUES ('vocal', '+33100000000', 1, TRUE, now())
ON CONFLICT (channel, key) DO UPDATE SET tenant_id = EXCLUDED.tenant_id, is_active = TRUE, updated_at = now();
```

### SQLite

Table : `tenant_routing`  
Colonnes : `channel`, `did_key`, `tenant_id`.

```sql
INSERT OR REPLACE INTO tenant_routing (channel, did_key, tenant_id, created_at)
VALUES ('whatsapp', '+33939240575', 1, datetime('now'));
```

Vocal :
```sql
INSERT OR REPLACE INTO tenant_routing (channel, did_key, tenant_id, created_at)
VALUES ('vocal', '+33100000000', 1, datetime('now'));
```

---

## 3. Vérifier les routes

- **Admin API** : détail d’un tenant (ex. `GET /api/admin/tenants/1`) contient la liste des routes (`routing`).
- **PostgreSQL :**  
  `SELECT channel, key, tenant_id, is_active FROM tenant_routing ORDER BY channel, key;`
- **SQLite :**  
  `SELECT channel, did_key, tenant_id FROM tenant_routing;`

---

## 4. Canal Web (X-Tenant-Key)

Pour le **widget chat** (`POST /chat`, `GET /stream/{conv_id}`) :

- Envoyer le header **`X-Tenant-Key`** avec la clé configurée en base (route `channel='web'`).
- **Sans header** (ou clé vide) : le tenant par défaut (`tenant_id=1`) est utilisé (rétrocompatibilité).
- **Avec une clé inconnue** : la requête reçoit **401** (Invalid or unknown X-Tenant-Key).

Exemple d’ajout d’une route web (API admin) :
```json
{"channel": "web", "key": "widget-key-tenant-42", "tenant_id": 2}
```

Le front doit envoyer : `X-Tenant-Key: widget-key-tenant-42` sur chaque `POST /chat` ; le stream réutilise le `tenant_id` déjà fixé sur la session.

---

## 5. Règles

- **key** : pour vocal/WhatsApp = format **E.164** avec `+` (ex. `+33612345678`). Pas d’espace dans la valeur stockée. Pour web = chaîne libre (clé API widget).
- **WhatsApp** : `key` = numéro **destinataire** du webhook Twilio (champ **To**), c’est-à-dire le numéro WhatsApp Business du tenant.
- **Vocal** : `key` = numéro **appelé** (DID) utilisé par Vapi pour cet assistant.
- **Web** : `key` = valeur du header `X-Tenant-Key` envoyée par le widget.

Une fois la route en base, les prochains appels/messages vers ce numéro ou avec cette clé sont attribués au bon `tenant_id`.
