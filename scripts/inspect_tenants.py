"""Diagnostic ponctuel : identité des tenants concernés par les fiches patient."""
import os
import psycopg

url = os.environ.get("DATABASE_URL")
with psycopg.connect(url, row_factory=psycopg.rows.dict_row) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT t.tenant_id, t.name, t.created_at, t.status
            FROM tenants t
            WHERE t.tenant_id IN (1, 2)
            ORDER BY t.tenant_id
        """)
        for r in cur.fetchall():
            name = (r['name'] or '?')[:40]
            print(
                f"tenant={r['tenant_id']} name={name:<42} status={r['status']:<10} "
                f"created={r['created_at']}"
            )
        print()
        # Liste les emails des comptes attachés à ces tenants
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'tenant_users'
            ORDER BY ordinal_position
        """)
        cols = [r['column_name'] for r in cur.fetchall()]
        print(f"colonnes tenant_users: {cols}")
        if 'email' in cols:
            cur.execute(
                "SELECT tenant_id, email FROM tenant_users WHERE tenant_id IN (1,2) ORDER BY tenant_id"
            )
            for r in cur.fetchall():
                print(f"  tenant={r['tenant_id']} user_email={r['email']}")

        print()
        cur.execute("""
            SELECT tenant_id, COUNT(*) AS n_patients,
                   COUNT(DISTINCT phone) AS phones,
                   COUNT(NULLIF(email,'')) AS with_email
            FROM cabinet_clients
            GROUP BY tenant_id
            ORDER BY tenant_id
        """)
        for r in cur.fetchall():
            print(
                f"tenant={r['tenant_id']}: {r['n_patients']} fiches, "
                f"{r['phones']} numéros uniques, {r['with_email']} avec email"
            )
