# Référence type tenant_id (Jour 0)

**À vérifier en base** (exécuter une fois) :
```sql
SELECT data_type, udt_name
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'tenants' AND column_name = 'tenant_id';
```

- Si `bigint` / `integer` → **TENANT_ID_TYPE = int** (Python `int`, DDL `BIGINT`)
- Si `uuid` → **TENANT_ID_TYPE = uuid** (Python `UUID`, DDL `UUID`)

**État actuel du code :** tout le projet utilise `int` (tenants_pg, db.py, slots_pg, etc.).  
En l’absence de résultat SQL, on considère **TENANT_ID_TYPE = int (BIGINT)**.

Ne pas mélanger : toutes les FK, paramètres Python et DDL doivent utiliser le même type.
