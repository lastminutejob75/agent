"""Liste tous les comptes utilisateurs (toutes tables candidates)."""
import os
import psycopg

url = os.environ.get("DATABASE_URL")
with psycopg.connect(url, row_factory=psycopg.rows.dict_row) as conn:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name ~ 'user|tenant' "
            "ORDER BY table_name"
        )
        tables = [r['table_name'] for r in cur.fetchall()]
        print("tables candidates:", tables)
        print()
        for t in tables:
            try:
                cur.execute(f"SELECT COUNT(*) AS n FROM {t}")
                n = cur.fetchone()['n']
                print(f"  {t}: {n} lignes")
            except Exception as e:
                print(f"  {t}: ERREUR {e}")
        print()
        # Si users existe, le détailler
        if 'users' in tables:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='users' ORDER BY ordinal_position"
            )
            cols = [r['column_name'] for r in cur.fetchall()]
            print(f"colonnes users: {cols}")
            cur.execute(
                f"SELECT {','.join(c for c in cols if c in ('id','user_id','tenant_id','email','role','auth_provider','created_at'))} "
                f"FROM users ORDER BY tenant_id NULLS LAST, created_at LIMIT 20"
            )
            for r in cur.fetchall():
                print(" ", dict(r))
