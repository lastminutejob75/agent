"""Tokens JWT temporaires pour les actions publiques sur un rendez-vous."""
from __future__ import annotations

import os
import time
import uuid
from typing import Any, Dict, Optional

import jwt

_PUBLIC_ACTION_TYP = "public_appt_action"
_PUBLIC_ACTION_TTL_SECONDS = int(os.environ.get("PUBLIC_ACTION_TOKEN_TTL_SECONDS", "900"))


def _secret() -> str:
    return (os.environ.get("JWT_SECRET") or os.environ.get("LEAD_ACCESS_SECRET") or "").strip()


def issue_public_action_token(
    *,
    tenant_id: int,
    source_type: str,
    source_id: str,
    booking_code: str,
) -> str:
    secret = _secret()
    if not secret:
        raise RuntimeError("JWT_SECRET required for public action tokens")
    now = int(time.time())
    payload = {
        "typ": _PUBLIC_ACTION_TYP,
        "jti": str(uuid.uuid4()),
        "tenant_id": int(tenant_id),
        "source_type": (source_type or "").strip(),
        "source_id": str(source_id or ""),
        "booking_code": (booking_code or "").strip().upper(),
        "iat": now,
        "exp": now + _PUBLIC_ACTION_TTL_SECONDS,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_public_action_token(token: Optional[str]) -> Optional[Dict[str, Any]]:
    secret = _secret()
    if not secret or not token:
        return None
    try:
        payload = jwt.decode(str(token).strip(), secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None
    if payload.get("typ") != _PUBLIC_ACTION_TYP:
        return None
    tenant_id = payload.get("tenant_id")
    source_type = (payload.get("source_type") or "").strip()
    source_id = str(payload.get("source_id") or "").strip()
    booking_code = (payload.get("booking_code") or "").strip().upper()
    if tenant_id is None or not source_type or not source_id:
        return None
    return {
        "tenant_id": int(tenant_id),
        "source_type": source_type,
        "source_id": source_id,
        "booking_code": booking_code,
    }
