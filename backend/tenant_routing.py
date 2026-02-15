# backend/tenant_routing.py
"""
DID → tenant_id routing.
Permet de router un appel vocal vers le bon tenant selon le numéro appelé (E.164).
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from backend import config, db

logger = logging.getLogger(__name__)

# Nettoyage E.164 : espaces, 00→+, garder +digits
def normalize_did(raw: str) -> str:
    if not raw or not isinstance(raw, str):
        return ""
    s = re.sub(r"\s+", "", raw.strip())
    if s.startswith("00"):
        s = "+" + s[2:]
    if not s.startswith("+"):
        return s  # digits seuls
    return s


def resolve_tenant_id_from_vocal_call(to_number: Optional[str], channel: str = "vocal") -> tuple[int, str]:
    """
    Résout tenant_id à partir du numéro appelé (DID).
    PG-first read, SQLite fallback.
    Returns: (tenant_id, source) avec source="route"|"default", logs [TENANT_READ] source=pg|sqlite
    """
    key = normalize_did(to_number or "")
    if not key:
        return (config.DEFAULT_TENANT_ID, "default")

    # PG-first (si USE_PG_TENANTS)
    if config.USE_PG_TENANTS:
        try:
            from backend.tenants_pg import pg_resolve_tenant_id
            result = pg_resolve_tenant_id(channel, key)
            if result:
                tenant_id, _ = result
                logger.debug("TENANT_READ source=pg route=%s -> tenant_id=%s", key, tenant_id)
                return (tenant_id, "route")
        except Exception as e:
            logger.debug("TENANT_READ pg failed: %s (fallback sqlite)", e)

    # Fallback SQLite
    db.ensure_tenant_config()
    conn = db.get_conn()
    try:
        row = conn.execute(
            "SELECT tenant_id FROM tenant_routing WHERE channel = ? AND did_key = ?",
            (channel, key),
        ).fetchone()
        if row:
            logger.debug("TENANT_READ source=sqlite route=%s -> tenant_id=%s", key, row[0])
            return (int(row[0]), "route")
    except Exception as e:
        logger.debug("tenant_routing resolve: %s (using default)", e)
    finally:
        conn.close()

    return (config.DEFAULT_TENANT_ID, "default")


def add_route(channel: str, did_key: str, tenant_id: int) -> None:
    """Ajoute ou met à jour une route."""
    key = normalize_did(did_key)
    if not key:
        return
    db.ensure_tenant_config()
    conn = db.get_conn()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO tenant_routing (channel, did_key, tenant_id, created_at)
            VALUES (?, ?, ?, datetime('now'))
            """,
            (channel, key, tenant_id),
        )
        conn.commit()
    finally:
        conn.close()


def extract_to_number_from_vapi_payload(payload: dict) -> Optional[str]:
    """
    Extrait le numéro appelé (DID) du payload Vapi.
    Ordre de priorité: phoneNumber.number, call.phoneNumber.number, call.to
    """
    # Vapi common metadata: phoneNumber
    pn = payload.get("phoneNumber")
    if isinstance(pn, dict) and pn.get("number"):
        return str(pn["number"])
    if isinstance(pn, str):
        return pn

    call = payload.get("call") or {}
    pn = call.get("phoneNumber")
    if isinstance(pn, dict) and pn.get("number"):
        return str(pn["number"])
    if isinstance(pn, str):
        return pn

    if call.get("to"):
        return str(call["to"])

    return None


def extract_customer_phone_from_vapi_payload(payload: dict) -> Optional[str]:
    """
    Extrait le numéro de l'appelant (caller ID) du payload Vapi.
    Utilisé pour : proposition "Votre numéro est bien le X ?" en QUALIF_CONTACT,
    client_memory, rapports. Plusieurs chemins possibles selon version Vapi / provider.
    """
    if not payload:
        return None

    def _norm(s: Optional[str]) -> Optional[str]:
        if not s or not isinstance(s, str):
            return None
        s = re.sub(r"[\s\-\.]", "", s.strip())
        return s if s else None

    # 1) call.customer.number (documentation courante)
    call = payload.get("call") or {}
    customer = call.get("customer") or payload.get("customer") or {}
    for key in ("number", "phone"):
        val = customer.get(key)
        if val:
            n = _norm(str(val))
            if n and len(n) >= 10:
                return str(val).strip()

    # 2) call.from (convention téléphonie)
    from_val = call.get("from")
    if from_val:
        n = _norm(str(from_val))
        if n and len(n) >= 10:
            return str(from_val).strip()

    # 3) Racine payload (fallback)
    for key in ("customerNumber", "callerNumber", "from"):
        val = payload.get(key)
        if val:
            n = _norm(str(val))
            if n and len(n) >= 10:
                return str(val).strip()

    # 4) Premier message avec customer (webhook message.customer selon provider)
    for msg in payload.get("messages") or []:
        if not isinstance(msg, dict):
            continue
        c = msg.get("customer") or {}
        for key in ("number", "phone"):
            v = c.get(key)
            if v:
                n = _norm(str(v))
                if n and len(n) >= 10:
                    return str(v).strip()

    return None
