# Schéma global UWi — Vocal & tenants

Doc court, une seule source de vérité : numéro test = vitrine, dashboard = interne, clients = numéros dédiés.

**Règle (immuable)** : le numéro TEST est immuable et doit toujours router vers TEST_TENANT_ID. Aucune réassignation possible (guard + 409 en API).

---

## A. Schéma global

**Prospect**
- uwiapp.com → clique « Appeler le numéro test »
- appelle **09 39 24 05 75**
- routage → **TENANT_TEST**
- aucun compte / aucun dashboard

**Interne (toi)**
- `/login` (magic link) → `/app`
- `/app` = appels / events / rdv filtrés `tenant_id = TENANT_TEST`

**Client réel**
- création tenant dédié + DID dédié
- routage DID → tenant client

---

## B. Mapping central (source de vérité)

- **Table** : `tenant_routing`
- **Règle** : 1 DID → 1 tenant
- **Contrainte** : clé unique sur `(channel, did_key)` (SQLite) / `(channel, key)` (Postgres) — une seule ligne par DID par canal, l’UPSERT est donc bien défini.
- **Formats** : stocker `did_key` normalisé (E.164 recommandé, ex. `+33939240575`).
- **Canal démo** : la route du numéro test est toujours `channel = "vocal"` (toutes les écritures démo utilisent ce canal pour éviter des doublons par canal).

**Colonnes**
- SQLite : `channel`, `did_key`, `tenant_id`, `created_at` — `PRIMARY KEY (channel, did_key)`.
- Postgres : `channel`, `key`, `tenant_id`, `is_active`, `updated_at` — contrainte unique `(channel, key)`.

**UPSERT SQL (exemple)**

SQLite :
```sql
INSERT OR REPLACE INTO tenant_routing (channel, did_key, tenant_id, created_at)
VALUES ('vocal', '+33939240575', 1, datetime('now'));
```

Postgres :
```sql
INSERT INTO tenant_routing (channel, key, tenant_id, is_active, updated_at)
VALUES ('vocal', '+33939240575', 1, TRUE, now())
ON CONFLICT (channel, key) DO UPDATE SET tenant_id = EXCLUDED.tenant_id, is_active = TRUE, updated_at = now();
```

---

## C. Pourquoi l’onboarding ne touche pas au numéro test

- L’onboarding sert à créer un tenant client (optionnel aujourd’hui).
- Le DID test est fixe sur **TENANT_TEST**.
- Donc pas de liaison automatique « onboarding → numéro test ».

---

## D. Où c’est dans le code

| Élément | Fichier |
|--------|--------|
| **TEST_VOCAL_NUMBER** / **TEST_TENANT_ID** | `backend/config.py` |
| **add_route** (écriture routage) | `backend/tenant_routing.py` |
| **guard_demo_number_routing** | `backend/tenant_routing.py` — appelée dans `add_route` et avant `pg_add_routing` |
| **Résolution DID → tenant_id** | `backend/tenant_routing.py` : `resolve_tenant_id_from_vocal_call(to_number)` ; utilisée dans le webhook Vapi (ex. `backend/routes/voice.py`) |

---

## E. Poser la route démo une fois (idempotent)

Au boot ou en migration :

1. `ensure_test_tenant_exists()` (si besoin : créer le tenant 1 / TEST_TENANT_ID).
2. **ensure_test_number_route()** — UPSERT DID test → tenant test.

**Script Python** (déjà dans le projet) :

```python
# backend/tenant_routing.py
def ensure_test_number_route() -> bool:
    """Pose la route vocal TEST_VOCAL_NUMBER → TEST_TENANT_ID (idempotent)."""
```

À appeler au démarrage ou dans un script de seed pour garantir un environnement test propre après reset DB.

---

## F. Wording homepage

- **CTA** : « 📞 Écouter la démo vocale : 09 39 24 05 75 »
- **Petit texte** : « Numéro de démonstration (public). »

---

## G. Bonus prod

Sur **TENANT_TEST** : sandbox booking / horaires restreints / pas de création client réelle, pour éviter qu’un appel sur le numéro public pollue la prod.
