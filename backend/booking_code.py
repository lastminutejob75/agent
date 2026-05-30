"""Génération et normalisation des codes rendez-vous publics (ex. RDV-A7K3M2)."""
from __future__ import annotations

import logging
import secrets
from typing import Optional

logger = logging.getLogger(__name__)

BOOKING_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
BOOKING_CODE_LENGTH = 6
BOOKING_CODE_PREFIX = "RDV-"


def generate_booking_code(length: int = BOOKING_CODE_LENGTH) -> str:
    """Génère un code alphanumérique sans caractères ambigus (O/0, I/1)."""
    size = max(4, min(int(length), 12))
    return "".join(secrets.choice(BOOKING_CODE_ALPHABET) for _ in range(size))


def normalize_booking_code(raw: Optional[str]) -> str:
    """Retire le préfixe RDV- et normalise en majuscules (format stocké en base)."""
    value = (raw or "").strip().upper()
    if value.startswith("RDV-"):
        value = value[4:]
    return value


def format_booking_code(code: Optional[str]) -> str:
    """Format affiché patient : RDV-A7K3M2."""
    normalized = normalize_booking_code(code)
    if not normalized:
        return ""
    return f"{BOOKING_CODE_PREFIX}{normalized}"


def _booking_code_exists_pg(cur, tenant_id: Optional[int], code: str) -> bool:
    if tenant_id is not None:
        cur.execute(
            """
            SELECT 1
            FROM appointments
            WHERE tenant_id = %s AND booking_code = %s
            UNION ALL
            SELECT 1
            FROM public_bookings
            WHERE tenant_id = %s AND booking_code = %s
            LIMIT 1
            """,
            (tenant_id, code, tenant_id, code),
        )
    else:
        cur.execute(
            """
            SELECT 1 FROM public_bookings
            WHERE booking_code = %s
            LIMIT 1
            """,
            (code,),
        )
    return cur.fetchone() is not None


def create_unique_booking_code_pg(cur, tenant_id: Optional[int]) -> str:
    """Génère un code unique pour un tenant (appointments + public_bookings)."""
    for _ in range(12):
        code = generate_booking_code()
        if not _booking_code_exists_pg(cur, tenant_id, code):
            return code
    raise RuntimeError("Unable to generate unique booking code")


def create_unique_booking_code_for_tenant(tenant_id: Optional[int]) -> str:
    """Génère un code unique via connexion PG (hors transaction appelante)."""
    from backend.pg_pool import pg_connection

    with pg_connection() as conn:
        with conn.cursor() as cur:
            return create_unique_booking_code_pg(cur, tenant_id)


def booking_code_exists_sqlite(conn, tenant_id: int, code: str) -> bool:
    cur = conn.execute(
        """
        SELECT 1 FROM appointments
        WHERE tenant_id = ? AND booking_code = ?
        LIMIT 1
        """,
        (tenant_id, code),
    )
    return cur.fetchone() is not None


def create_unique_booking_code_sqlite(conn, tenant_id: int) -> str:
    for _ in range(12):
        code = generate_booking_code()
        if not booking_code_exists_sqlite(conn, tenant_id, code):
            return code
    raise RuntimeError("Unable to generate unique booking code")
