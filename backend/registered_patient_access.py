"""Accès réservé aux patients déjà enregistrés (fiche ``cabinet_clients``)."""
from __future__ import annotations

from typing import Any, Optional

import backend.db as db
from backend.handoffs import _normalized_phone_from_session

REGISTERED_PATIENT_ONLY_DETAIL = (
    "Cette demande est réservée aux patients déjà enregistrés au cabinet. "
    "Pour un premier contact, prenez rendez-vous en ligne ou appelez le cabinet."
)


def find_registered_patient(
    tenant_id: int,
    *,
    phone: Optional[str] = None,
    email: Optional[str] = None,
) -> Optional[dict]:
    """Retourne la fiche patient si le numéro ou l'email est connu du cabinet."""
    return db.find_cabinet_client(int(tenant_id), phone=phone or "", email=email or "")


def find_registered_patient_for_session(tenant_id: int, session: Any) -> Optional[dict]:
    qualif = getattr(session, "qualif_data", None)
    email = getattr(qualif, "email", None) if qualif else None
    phone = _normalized_phone_from_session(session)
    return find_registered_patient(tenant_id, phone=phone, email=email)


def is_registered_patient(
    tenant_id: int,
    *,
    phone: Optional[str] = None,
    email: Optional[str] = None,
) -> bool:
    return find_registered_patient(tenant_id, phone=phone, email=email) is not None


def registered_patient_only_message(channel: str) -> str:
    from backend import prompts

    if (channel or "").strip().lower() == "vocal":
        return prompts.VOCAL_REGISTERED_PATIENT_ONLY
    return prompts.MSG_REGISTERED_PATIENT_ONLY_WEB
