# backend/pg_tenant_context.py
"""
Contexte tenant pour RLS PostgreSQL.
Pose app.current_tenant_id sur la connexion pour que les policies RLS
ne retournent que les lignes du tenant courant.
À appeler juste après ouverture de la connexion, avant toute requête.
"""
from __future__ import annotations

from typing import Optional


def set_tenant_id_on_connection(conn, tenant_id: Optional[int]) -> None:
    """
    Exécute SET LOCAL app.current_tenant_id sur la connexion.
    À appeler après psycopg.connect() pour les requêtes scopées par tenant.
    Si tenant_id est None ou < 1, n'appelle pas SET (opération globale ou non scopée).
    """
    if tenant_id is None or tenant_id < 1:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL app.current_tenant_id = %s", (str(tenant_id),))
    except Exception:
        # RLS peut être désactivé ou la variable non utilisée ; ne pas faire échouer le flow
        pass
