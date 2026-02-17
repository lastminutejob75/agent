# backend/tenant_routing.py
"""
DID → tenant_id routing.
Permet de router un appel vocal ou WhatsApp vers le bon tenant selon le numéro (E.164).
"""
from __future__ import annotations

import logging
import re
from contextvars import ContextVar
from typing import Optional

from backend import config, db

logger = logging.getLogger(__name__)

# Contexte tenant pour la requête en cours (str pour cohérence avec set_config PG)
current_tenant_id: ContextVar[Optional[str]] = ContextVar("current_tenant_id", default=None)

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


def normalize_did_canonical(raw: str) -> str:
    """
    Forme canonique pour comparaison (guard) : 09... → +33..., espaces/00 normalisés.
    Garantit que "09 39 24 05 75" et "+33939240575" matchent.
    """
    if not raw or not isinstance(raw, str):
        return ""
    s = re.sub(r"[\s\-\.]", "", raw.strip())
    if not s or not s.isdigit() and not s.startswith("+"):
        return normalize_did(raw)  # fallback
    if s.startswith("00"):
        s = "+" + s[2:]
    elif s.startswith("0") and len(s) == 10 and s.isdigit():
        s = "+33" + s[1:]
    elif s.isdigit() and len(s) >= 10:
        s = "+" + s
    elif not s.startswith("+"):
        return normalize_did(raw)
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


def resolve_tenant_from_whatsapp(to_number: str) -> int:
    """
    Résout le tenant_id à partir du numéro WhatsApp Business destinataire (To).
    Utilise tenant_routing(channel='whatsapp', key=E.164).
    Lève HTTPException(404) si aucun route trouvée pour ce numéro.
    """
    from fastapi import HTTPException
    from backend.utils.phone import normalize_e164
    try:
        key = normalize_e164(to_number or "")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid phone number format")
    if not key:
        raise HTTPException(status_code=400, detail="Missing or invalid To number")

    if config.USE_PG_TENANTS:
        try:
            from backend.tenants_pg import pg_resolve_tenant_id
            result = pg_resolve_tenant_id("whatsapp", key)
            if result:
                tenant_id, _ = result
                logger.debug("TENANT_READ whatsapp source=pg to=%s -> tenant_id=%s", key, tenant_id)
                return tenant_id
        except Exception as e:
            logger.debug("TENANT_READ whatsapp pg failed: %s (fallback sqlite)", e)

    db.ensure_tenant_config()
    conn = db.get_conn()
    try:
        row = conn.execute(
            "SELECT tenant_id FROM tenant_routing WHERE channel = ? AND did_key = ?",
            ("whatsapp", key),
        ).fetchone()
        if row:
            logger.debug("TENANT_READ whatsapp source=sqlite to=%s -> tenant_id=%s", key, row[0])
            return int(row[0])
    except Exception as e:
        logger.debug("tenant_routing whatsapp resolve: %s", e)
    finally:
        conn.close()

    raise HTTPException(status_code=404, detail=f"No tenant configured for WhatsApp number {key}")


def resolve_tenant_from_api_key(api_key: Optional[str]) -> int:
    """
    Résout le tenant_id à partir de la clé API Web (header X-Tenant-Key).
    Utilise tenant_routing(channel='web', key=api_key).
    - Si api_key vide/absent : retourne DEFAULT_TENANT_ID (rétrocompat).
    - Si api_key fourni mais inconnu : lève HTTPException 401.
    """
    from fastapi import HTTPException

    key = (api_key or "").strip()
    if not key:
        return config.DEFAULT_TENANT_ID

    if config.USE_PG_TENANTS:
        try:
            from backend.tenants_pg import pg_resolve_tenant_id
            result = pg_resolve_tenant_id("web", key)
            if result:
                tenant_id, _ = result
                logger.debug("TENANT_READ web source=pg key=*** -> tenant_id=%s", tenant_id)
                return tenant_id
        except Exception as e:
            logger.debug("TENANT_READ web pg failed: %s (fallback sqlite)", e)

    db.ensure_tenant_config()
    conn = db.get_conn()
    try:
        row = conn.execute(
            "SELECT tenant_id FROM tenant_routing WHERE channel = ? AND did_key = ?",
            ("web", key),
        ).fetchone()
        if row:
            logger.debug("TENANT_READ web source=sqlite key=*** -> tenant_id=%s", row[0])
            return int(row[0])
    except Exception as e:
        logger.debug("tenant_routing web resolve: %s", e)
    finally:
        conn.close()

    raise HTTPException(status_code=401, detail="Invalid or unknown X-Tenant-Key")


def guard_demo_number_routing(*, channel: str = "", did_key: str, tenant_id: int) -> None:
    """
    Lève ValueError si le DID test est routé vers un tenant_id ≠ TEST_TENANT_ID.
    Comparaison en forme canonique E.164 (09... et +33... matchent).
    """
    did_norm = normalize_did_canonical(did_key or "")
    if not did_norm or channel != "vocal":
        return
    test_did_key = normalize_did_canonical((getattr(config, "TEST_VOCAL_NUMBER", None) or "") or "")
    if not test_did_key or did_norm != test_did_key:
        return
    test_tid = getattr(config, "TEST_TENANT_ID", config.DEFAULT_TENANT_ID)
    if int(tenant_id) != int(test_tid):
        msg = (
            f"Forbidden: test number {did_norm} must stay routed to TEST_TENANT_ID={test_tid}, "
            f"got tenant_id={tenant_id}"
        )
        logger.error("[guard_demo_number_routing] %s", msg)
        raise ValueError(msg)


def add_route(channel: str, did_key: str, tenant_id: int) -> None:
    """Ajoute ou met à jour une route (UPSERT). Rejette la réassignation du numéro démo (guard_demo_number_routing)."""
    guard_demo_number_routing(channel=channel, did_key=did_key, tenant_id=tenant_id)
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


def ensure_test_number_route() -> bool:
    """
    Pose la route DID test → TEST_TENANT_ID (idempotent UPSERT).
    À appeler au boot ou en migration pour garantir un environnement test propre.
    """
    test_number = getattr(config, "TEST_VOCAL_NUMBER", None) or getattr(config, "ONBOARDING_DEMO_VOCAL_NUMBER", None)
    if not test_number:
        return False
    test_tid = getattr(config, "TEST_TENANT_ID", config.DEFAULT_TENANT_ID)
    add_route("vocal", test_number, test_tid)
    if config.USE_PG_TENANTS:
        try:
            from backend.tenants_pg import pg_add_routing
            key = normalize_did(test_number)
            if key and pg_add_routing("vocal", key, test_tid):
                logger.info("ensure_test_number_route: vocal %s → tenant_id=%s (pg)", key, test_tid)
        except Exception as e:
            logger.warning(
                "[ROUTING] ensure_test_number_route skipped (PG down); relying on SQLite fallback: %s", e
            )
    return True


def extract_to_number_from_vapi_payload(payload: dict) -> Optional[str]:
    """
    Extrait le numéro appelé (DID) du payload Vapi.
    Ordre de priorité: message.call (webhook), phoneNumber, call.phoneNumber, call.to
    """
    # Webhook Vapi : message.call.phoneNumber.number / message.call.to
    message = payload.get("message") or {}
    call = message.get("call") or {}
    pn = call.get("phoneNumber")
    if isinstance(pn, dict) and pn.get("number"):
        return str(pn["number"])
    if call.get("to"):
        return str(call["to"])

    # Chat Completions / racine
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

    # 0) Webhook Vapi : message.call.customer.number (assistant.started, status-update, etc.)
    message = payload.get("message") or {}
    call = message.get("call") or {}
    customer = call.get("customer") or message.get("customer") or {}
    for key in ("number", "phone"):
        val = customer.get(key)
        if val:
            n = _norm(str(val))
            if n and len(n) >= 10:
                return str(val).strip()
    from_val = call.get("from")
    if from_val:
        n = _norm(str(from_val))
        if n and len(n) >= 10:
            return str(from_val).strip()

    # 1) Racine : call.customer.number (Chat Completions / ancien format)
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
