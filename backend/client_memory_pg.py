"""
Couche PostgreSQL pour ClientMemory (multi-tenant).
Tables: tenant_clients, tenant_booking_history, scopées par tenant_id.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from backend.client_memory import Client, BookingHistory

logger = logging.getLogger(__name__)


def _pg_url() -> Optional[str]:
    import os
    return os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")


def _ensure_tables(conn) -> None:
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tenant_clients (
            id BIGSERIAL PRIMARY KEY,
            tenant_id BIGINT NOT NULL,
            phone TEXT,
            name TEXT NOT NULL DEFAULT '',
            email TEXT,
            created_at TIMESTAMPTZ DEFAULT now(),
            last_contact TIMESTAMPTZ DEFAULT now(),
            total_bookings INTEGER DEFAULT 0,
            last_motif TEXT,
            preferred_time TEXT,
            notes TEXT
        )
    """)
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_tenant_clients_tenant_phone
        ON tenant_clients (tenant_id, phone) WHERE phone IS NOT NULL AND phone != ''
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tenant_clients_tenant_id ON tenant_clients(tenant_id)")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tenant_booking_history (
            id BIGSERIAL PRIMARY KEY,
            tenant_id BIGINT NOT NULL,
            client_id BIGINT NOT NULL,
            slot_label TEXT NOT NULL,
            motif TEXT,
            status TEXT DEFAULT 'confirmed',
            created_at TIMESTAMPTZ DEFAULT now(),
            completed_at TIMESTAMPTZ
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tenant_booking_tenant_client ON tenant_booking_history(tenant_id, client_id)")
    conn.commit()


def _row_to_client(row: Tuple) -> Client:
    return Client(
        id=int(row[0]),
        phone=row[2],
        name=row[3] or "",
        email=row[4],
        created_at=row[5] if row[5] else datetime.utcnow(),
        last_contact=row[6] if row[6] else datetime.utcnow(),
        total_bookings=int(row[7] or 0),
        last_motif=row[8],
        preferred_time=row[9],
        notes=row[10],
    )


def _row_to_booking(row: Tuple) -> BookingHistory:
    return BookingHistory(
        id=int(row[0]),
        client_id=int(row[2]),
        slot_label=row[3],
        motif=row[4] or "",
        status=row[5] or "confirmed",
        created_at=row[6] if row[6] else datetime.utcnow(),
        completed_at=row[7],
    )


def _normalize_phone(phone: Optional[str]) -> str:
    if not phone:
        return ""
    s = phone.replace(" ", "").replace("-", "").replace(".", "")
    if s.startswith("+33"):
        s = "0" + s[3:]
    elif s.startswith("33"):
        s = "0" + s[2:]
    return s


def pg_get_client_by_phone(tenant_id: int, phone: str) -> Optional[Client]:
    url = _pg_url()
    if not url:
        return None
    try:
        import psycopg
        p = _normalize_phone(phone)
        if not p:
            return None
        with psycopg.connect(url) as conn:
            _ensure_tables(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, tenant_id, phone, name, email, created_at, last_contact, total_bookings, last_motif, preferred_time, notes FROM tenant_clients WHERE tenant_id = %s AND phone = %s",
                    (tenant_id, p),
                )
                row = cur.fetchone()
                return _row_to_client(row) if row else None
    except Exception as e:
        logger.debug("client_memory_pg get_by_phone: %s", e)
        return None


def pg_get_client_by_name(tenant_id: int, name: str) -> Optional[Client]:
    url = _pg_url()
    if not url:
        return None
    try:
        import psycopg
        name_lower = (name or "").lower().strip()
        if not name_lower:
            return None
        with psycopg.connect(url) as conn:
            _ensure_tables(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, tenant_id, phone, name, email, created_at, last_contact, total_bookings, last_motif, preferred_time, notes FROM tenant_clients WHERE tenant_id = %s AND LOWER(name) = %s",
                    (tenant_id, name_lower),
                )
                row = cur.fetchone()
                if not row:
                    cur.execute(
                        "SELECT id, tenant_id, phone, name, email, created_at, last_contact, total_bookings, last_motif, preferred_time, notes FROM tenant_clients WHERE tenant_id = %s AND LOWER(name) LIKE %s LIMIT 1",
                        (tenant_id, f"%{name_lower}%"),
                    )
                    row = cur.fetchone()
                return _row_to_client(row) if row else None
    except Exception as e:
        logger.debug("client_memory_pg get_by_name: %s", e)
        return None


def pg_get_or_create_client(
    tenant_id: int,
    phone: Optional[str] = None,
    name: str = "",
    email: Optional[str] = None,
) -> Client:
    p = _normalize_phone(phone) if phone else None
    if p:
        c = pg_get_client_by_phone(tenant_id, p)
        if c:
            if name and name != c.name:
                pg_update_client(tenant_id, c.id, name=name)
                c.name = name
            return c
    if name:
        c = pg_get_client_by_name(tenant_id, name)
        if c:
            if phone and _normalize_phone(phone) != (c.phone or ""):
                pg_update_client(tenant_id, c.id, phone=_normalize_phone(phone))
                c.phone = _normalize_phone(phone)
            return c
    return pg_create_client(tenant_id, phone=p or None, name=name or "", email=email)


def pg_create_client(
    tenant_id: int,
    phone: Optional[str] = None,
    name: str = "",
    email: Optional[str] = None,
) -> Client:
    url = _pg_url()
    if not url:
        raise RuntimeError("client_memory_pg: no DATABASE_URL")
    import psycopg
    with psycopg.connect(url) as conn:
        _ensure_tables(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tenant_clients (tenant_id, phone, name, email, created_at, last_contact)
                VALUES (%s, %s, %s, %s, now(), now())
                RETURNING id, tenant_id, phone, name, email, created_at, last_contact, total_bookings, last_motif, preferred_time, notes
                """,
                (tenant_id, phone, name, email),
            )
            row = cur.fetchone()
            conn.commit()
            return _row_to_client(row)


def pg_update_client(tenant_id: int, client_id: int, **kwargs: Any) -> None:
    if not kwargs:
        return
    url = _pg_url()
    if not url:
        return
    import psycopg
    allowed = {"phone", "name", "email", "last_contact", "last_motif", "preferred_time", "notes"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    set_parts = [f"{k} = %s" for k in updates]
    values = list(updates.values()) + [tenant_id, client_id]
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE tenant_clients SET {', '.join(set_parts)} WHERE tenant_id = %s AND id = %s",
                values,
            )
            conn.commit()


def pg_record_booking(
    tenant_id: int,
    client_id: int,
    slot_label: str,
    motif: str,
    status: str = "confirmed",
) -> int:
    url = _pg_url()
    if not url:
        return 0
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            _ensure_tables(conn)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tenant_booking_history (tenant_id, client_id, slot_label, motif, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, now())
                    RETURNING id
                    """,
                    (tenant_id, client_id, slot_label, motif, status),
                )
                bid = cur.fetchone()[0]
                cur.execute(
                    """
                    UPDATE tenant_clients
                    SET total_bookings = total_bookings + 1, last_contact = now(), last_motif = %s
                    WHERE tenant_id = %s AND id = %s
                    """,
                    (motif, tenant_id, client_id),
                )
                conn.commit()
                return bid
    except Exception as e:
        logger.warning("client_memory_pg record_booking: %s", e)
        return 0


def pg_get_history(tenant_id: int, client_id: int, limit: int = 10) -> List[BookingHistory]:
    url = _pg_url()
    if not url:
        return []
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, tenant_id, client_id, slot_label, motif, status, created_at, completed_at
                    FROM tenant_booking_history
                    WHERE tenant_id = %s AND client_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (tenant_id, client_id, limit),
                )
                rows = cur.fetchall()
                return [_row_to_booking(r) for r in rows]
    except Exception as e:
        logger.debug("client_memory_pg get_history: %s", e)
        return []


def pg_get_clients_with_email(tenant_id: int) -> List[Tuple[int, str, str]]:
    url = _pg_url()
    if not url:
        return []
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, name, email FROM tenant_clients WHERE tenant_id = %s AND email IS NOT NULL AND email != ''",
                    (tenant_id,),
                )
                return [(int(r[0]), r[1] or "", r[2] or "") for r in cur.fetchall()]
    except Exception as e:
        logger.debug("client_memory_pg get_clients_with_email: %s", e)
        return []


def pg_get_stats(tenant_id: int, days: int = 30) -> Dict[str, Any]:
    url = _pg_url()
    if not url:
        return {"total_clients": 0, "new_clients": 0, "active_clients": 0, "total_bookings": 0, "top_clients": [], "period_days": days}
    try:
        import psycopg
        since = datetime.utcnow() - timedelta(days=days)
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM tenant_clients WHERE tenant_id = %s", (tenant_id,))
                total_clients = cur.fetchone()[0]
                cur.execute(
                    "SELECT COUNT(*) FROM tenant_clients WHERE tenant_id = %s AND created_at >= %s",
                    (tenant_id, since),
                )
                new_clients = cur.fetchone()[0]
                cur.execute(
                    "SELECT COUNT(DISTINCT client_id) FROM tenant_booking_history WHERE tenant_id = %s AND created_at >= %s",
                    (tenant_id, since),
                )
                active_clients = cur.fetchone()[0]
                cur.execute(
                    "SELECT COUNT(*) FROM tenant_booking_history WHERE tenant_id = %s AND created_at >= %s",
                    (tenant_id, since),
                )
                total_bookings = cur.fetchone()[0]
                cur.execute(
                    """
                    SELECT c.name, COUNT(b.id) FROM tenant_clients c
                    JOIN tenant_booking_history b ON b.tenant_id = c.tenant_id AND b.client_id = c.id
                    WHERE c.tenant_id = %s AND b.created_at >= %s
                    GROUP BY c.id, c.name ORDER BY count DESC LIMIT 5
                    """,
                    (tenant_id, since),
                )
                top_clients = cur.fetchall()
                return {
                    "total_clients": total_clients,
                    "new_clients": new_clients,
                    "active_clients": active_clients,
                    "total_bookings": total_bookings,
                    "top_clients": [{"name": r[0], "bookings": r[1]} for r in top_clients],
                    "period_days": days,
                }
    except Exception as e:
        logger.debug("client_memory_pg get_stats: %s", e)
        return {"total_clients": 0, "new_clients": 0, "active_clients": 0, "total_bookings": 0, "top_clients": [], "period_days": days}
