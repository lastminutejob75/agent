"""Diagnostic ponctuel : liste les fiches patients + emails pour vérifier l'isolation."""
import os
import psycopg

url = os.environ.get("PG_EVENTS_URL") or os.environ.get("DATABASE_URL")
with psycopg.connect(url, row_factory=psycopg.rows.dict_row) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT tenant_id, phone, display_name, validated_name, raw_name,
                   email, created_at, updated_at
            FROM cabinet_clients
            ORDER BY updated_at DESC NULLS LAST, created_at DESC
            LIMIT 15
        """)
        rows = cur.fetchall()
        if not rows:
            print("(aucun patient)")
        for r in rows:
            name = (r.get("display_name") or r.get("validated_name") or r.get("raw_name") or "-")[:30]
            email = (r.get("email") or "<vide>")[:40]
            print(
                f"tenant={r['tenant_id']:<3} phone={r['phone']:<14} "
                f"nom={name:<32} email={email:<40} updated={r['updated_at']}"
            )
        print()
        cur.execute("""
            SELECT COUNT(*) AS n,
                   COUNT(NULLIF(email,'')) AS with_email,
                   COUNT(DISTINCT tenant_id) AS n_tenants,
                   COUNT(DISTINCT (tenant_id, phone)) AS n_unique
            FROM cabinet_clients
        """)
        r = cur.fetchone()
        print(
            f"TOTAL: {r['n']} fiches, {r['with_email']} avec email, "
            f"{r['n_tenants']} tenants distincts, {r['n_unique']} couples (tenant, phone) uniques"
        )
